import json
import os
import re
import sys
from datetime import datetime

from dotenv import load_dotenv

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))
load_dotenv()

import anthropic
import click
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from devmind import config
from devmind.chat import MODEL_ALIASES, answer_question
from devmind.chat import tour as generate_tour
from devmind.graph import extract_dependencies
from devmind.indexer import run_indexer
from devmind.store import build_store

console = Console()

_DEVMIND_DIR = config.DEVMIND_DIR
_INDEX_PATH = os.path.join(_DEVMIND_DIR, "index.json")
_GRAPH_PATH = os.path.join(_DEVMIND_DIR, "graph.json")
_MANIFEST_PATH = os.path.join(_DEVMIND_DIR, "manifest.json")
_STORE_PATH = os.path.join(_DEVMIND_DIR, config.CHROMA_DIR)

_MODEL_CHOICES = click.Choice(list(MODEL_ALIASES.keys()))

_PATH_RE = re.compile(r"\b\w[\w./\\-]*\.(?:py|js|ts|go|java|rb|rs)\b")
_FUNC_RE = re.compile(r"\b[a-z_][a-z0-9_]*(?=\()")

_BAR_WIDTH = 28


def _load_json(path: str) -> list | dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _colorize_answer(text: str) -> Text:
    result = Text()
    in_code_block = False

    for line in text.splitlines(keepends=True):
        bare = line.rstrip("\n\r")
        newline = line[len(bare):]

        if bare.startswith("```"):
            in_code_block = not in_code_block
            result.append(line, style="dim")
            continue

        if in_code_block:
            result.append(line, style="dim")
            continue

        if bare.startswith("### "):
            result.append(bare[4:], style="bold dim")
            result.append(newline)
            continue
        if bare.startswith("## "):
            result.append(bare[3:], style="bold")
            result.append(newline)
            continue
        if bare.startswith("# "):
            result.append(bare[2:], style="bold underline")
            result.append(newline)
            continue

        matches = []
        for m in _PATH_RE.finditer(line):
            matches.append((m.start(), m.end(), "cyan bold"))
        for m in _FUNC_RE.finditer(line):
            matches.append((m.start(), m.end(), "yellow"))
        matches.sort(key=lambda x: x[0])

        pos = 0
        for start, end, style in matches:
            if start < pos:
                continue
            if start > pos:
                result.append(line[pos:start])
            result.append(line[start:end], style=style)
            pos = end
        if pos < len(line):
            result.append(line[pos:])

    return result


def _show_graph_for(target: str, graph_data: dict) -> None:
    forward: dict = graph_data.get("forward", {})
    reverse: dict = graph_data.get("reverse", {})

    matches = [p for p in forward if target in p]
    if not matches:
        console.print(f"[yellow]No file matching '{target}' in graph.[/yellow]")
        return

    for path in matches:
        imports = forward.get(path, [])
        imported_by = reverse.get(path, [])

        items = []
        if imports:
            items.append(("imports", imports))
        if imported_by:
            items.append(("imported by", imported_by))

        console.print(Text(path, style="cyan bold"))

        for i, (label, deps) in enumerate(items):
            connector = "└──" if i == len(items) - 1 else "├──"
            line = Text()
            line.append(f"  {connector} {label}: ", style="dim")
            for j, dep in enumerate(deps):
                line.append(dep, style="cyan")
                if j < len(deps) - 1:
                    line.append(", ")
            console.print(line)

        if not items:
            console.print("  [dim]└── (no relationships)[/dim]")

        console.print()


@click.group()
def cli():
    pass


@cli.command()
@click.option("--repo", required=True, type=click.Path(exists=True, file_okay=False, resolve_path=True), help="Path to the repository to index.")
@click.option("--output", default=_DEVMIND_DIR, show_default=True, type=click.Path(file_okay=False, resolve_path=True), help="Directory where index.json and manifest.json are written.")
def index(repo: str, output: str) -> None:
    run_indexer(repo_path=repo, output_path=output)


@cli.command("build-store")
@click.option("--index", "index_path", default=_INDEX_PATH, show_default=True, type=click.Path(exists=True, dir_okay=False, resolve_path=True), help="Path to index.json.")
@click.option("--store", "store_path", default=_STORE_PATH, show_default=True, type=click.Path(file_okay=False, resolve_path=True), help="Directory where ChromaDB persists its data.")
def build_store_cmd(index_path: str, store_path: str) -> None:
    count = build_store(index_json_path=index_path, store_path=store_path)
    console.print(f"[green]Stored {count} files in vector DB[/green]")


@cli.command()
@click.option("--index", "index_path", default=_INDEX_PATH, show_default=True, type=click.Path(exists=True, dir_okay=False, resolve_path=True), help="Path to index.json.")
@click.option("--top", default=10, show_default=True, help="Number of most-imported files to display.")
def graph(index_path: str, top: int) -> None:
    core = extract_dependencies(index_path)
    graph_path = os.path.join(os.path.dirname(index_path), "graph.json")
    console.print(f"[green]Graph written to:[/green] {graph_path}")

    if not core:
        console.print("[yellow]No dependency relationships found.[/yellow]")
        return

    table = Table(title=f"Top {top} Most-Imported Files", header_style="bold magenta")
    table.add_column("Rank", justify="right", style="dim")
    table.add_column("File", style="cyan")
    table.add_column("Dependents", justify="right")
    for rank, entry in enumerate(core[:top], start=1):
        if entry["dependents"] == 0:
            continue
        table.add_row(str(rank), entry["file"], str(entry["dependents"]))
    console.print(table)


@cli.command()
@click.option("--index", "index_path", default=_INDEX_PATH, show_default=True, type=click.Path(exists=True, dir_okay=False, resolve_path=True), help="Path to index.json.")
def tour(index_path: str) -> None:
    client = anthropic.Anthropic()
    summaries: list[dict] = _load_json(index_path)
    console.print("[dim]Generating onboarding guide…[/dim]")
    guide = generate_tour(summaries=summaries, client=client)
    console.print(Rule("Onboarding Guide", style="bold cyan"))
    console.print(_colorize_answer(guide))


@cli.command()
@click.option("--output", "output_dir", default=_DEVMIND_DIR, show_default=True,
              type=click.Path(file_okay=False, resolve_path=True),
              help="DevMind output directory (must contain manifest.json and graph.json).")
def stats(output_dir: str) -> None:
    manifest_path = os.path.join(output_dir, "manifest.json")
    graph_path = os.path.join(output_dir, "graph.json")

    if not os.path.exists(manifest_path):
        console.print("[red]No manifest found. Run `devmind setup` first.[/red]")
        return

    manifest: dict = _load_json(manifest_path)
    graph_data: dict = _load_json(graph_path) if os.path.exists(graph_path) else {}

    ts_raw = manifest.get("timestamp", "")
    try:
        ts = datetime.fromisoformat(ts_raw).strftime("%Y-%m-%d %H:%M UTC")
    except (ValueError, AttributeError):
        ts = ts_raw or "unknown"

    cost = manifest.get("estimated_cost")
    cost_str = f"${cost:.4f}" if cost is not None else "unavailable (re-index to capture)"

    console.print(Panel(
        f"[bold cyan]DevMind Index Stats[/bold cyan]\n"
        f"Repo:    [dim]{manifest.get('repo_path', 'unknown')}[/dim]\n"
        f"Indexed: [dim]{ts}[/dim]\n"
        f"Cost:    [dim]{cost_str}[/dim]",
        expand=False,
    ))

    console.print(f"\n[bold]Total files indexed:[/bold] {manifest.get('total_files', '?')}\n")

    domain_counts: dict = manifest.get("domains_found", {})
    if domain_counts:
        max_count = max(domain_counts.values())
        table = Table(title="Domain Breakdown", header_style="bold magenta")
        table.add_column("Domain", style="cyan", min_width=12)
        table.add_column("Files", justify="right", style="dim", min_width=5)
        table.add_column("Distribution", min_width=_BAR_WIDTH)
        for domain, count in sorted(domain_counts.items(), key=lambda x: -x[1]):
            bar_len = max(1, int(count / max_count * _BAR_WIDTH))
            table.add_row(domain, str(count), f"[green]{'█' * bar_len}[/green]")
        console.print(table)

    hub_files = [e for e in graph_data.get("core", [])[:8] if e["dependents"] > 0]
    if hub_files:
        hub_table = Table(title="Hub Files (most depended-on)", header_style="bold magenta")
        hub_table.add_column("File", style="cyan")
        hub_table.add_column("Dependents", justify="right")
        for entry in hub_files:
            hub_table.add_row(entry["file"], str(entry["dependents"]))
        console.print(hub_table)


@cli.command()
@click.option("--store", "store_path", default=_STORE_PATH, show_default=True, type=click.Path(file_okay=False, resolve_path=True), help="ChromaDB directory.")
@click.option("--index", "index_path", default=_INDEX_PATH, show_default=True, type=click.Path(exists=True, dir_okay=False, resolve_path=True), help="Path to index.json.")
@click.option("--graph", "graph_path", default=_GRAPH_PATH, show_default=True, type=click.Path(exists=True, dir_okay=False, resolve_path=True), help="Path to graph.json.")
@click.option("--model", default="sonnet", show_default=True, type=_MODEL_CHOICES, help="'sonnet' (~$0.003/question) or 'haiku' (~$0.0003/question) for cheap testing.")
def chat(store_path: str, index_path: str, graph_path: str, model: str) -> None:
    client = anthropic.Anthropic()
    summaries: list[dict] = _load_json(index_path)
    graph_data: dict = _load_json(graph_path)

    console.print(Panel(
        f"[bold cyan]DevMind[/bold cyan] — Ask anything about this codebase\n"
        f"[dim]Model: {model} ({MODEL_ALIASES[model]})   Commands: /exit  /graph <file>  /tour[/dim]",
        expand=False,
    ))

    while True:
        try:
            user_input = console.input("[bold green]>[/bold green] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Goodbye.[/dim]")
            break

        if not user_input:
            continue

        if user_input == "/exit":
            console.print("[dim]Goodbye.[/dim]")
            break

        if user_input == "/tour":
            console.print("[dim]Generating onboarding guide…[/dim]")
            console.print(_colorize_answer(generate_tour(summaries=summaries, client=client)))
            continue

        if user_input.startswith("/graph"):
            target = user_input[len("/graph"):].strip()
            if target:
                _show_graph_for(target, graph_data)
            else:
                console.print("[yellow]Usage: /graph <relative_path>[/yellow]")
            continue

        result = answer_question(
            question=user_input,
            store_path=store_path,
            summaries=summaries,
            graph=graph_data,
            client=client,
            model=model,
        )

        console.print(_colorize_answer(result["answer"]))

        files_used = result["files_used"]
        if files_used:
            confidence = "[green]High confidence[/green]" if len(files_used) >= 3 else "[yellow]Partial context[/yellow]"
            console.print("[dim]Sources: " + "  ·  ".join(files_used) + "[/dim]")
            console.print(confidence + "\n")
        else:
            console.print("[red]No relevant context found[/red]\n")


@cli.command()
@click.option("--repo", required=True, type=click.Path(exists=True, file_okay=False, resolve_path=True), help="Path to the repository to index.")
@click.option("--output", default=_DEVMIND_DIR, show_default=True, type=click.Path(file_okay=False, resolve_path=True), help="Directory where all devmind artefacts are written.")
def setup(repo: str, output: str) -> None:
    index_json = os.path.join(output, "index.json")
    store_dir = os.path.join(output, config.CHROMA_DIR)

    console.print(Rule("Step 1 / 3 — Indexing files", style="bold blue"))
    run_indexer(repo_path=repo, output_path=output)

    console.print(Rule("Step 2 / 3 — Building vector store", style="bold blue"))
    count = build_store(index_json_path=index_json, store_path=store_dir)
    console.print(f"[green]Stored {count} files in vector DB[/green]")

    console.print(Rule("Step 3 / 3 — Extracting dependency graph", style="bold blue"))
    core = extract_dependencies(index_json)
    console.print(f"[green]Graph written to:[/green] {os.path.join(output, 'graph.json')}")

    top_core = [e for e in core[:5] if e["dependents"] > 0]
    if top_core:
        table = Table(title="Top Core Files", header_style="bold magenta")
        table.add_column("File", style="cyan")
        table.add_column("Dependents", justify="right")
        for entry in top_core:
            table.add_row(entry["file"], str(entry["dependents"]))
        console.print(table)

    console.print(Rule("Setup complete", style="bold green"))
    console.print(
        "Run [bold]devmind chat[/bold] to ask questions, "
        "[bold]devmind tour[/bold] for a guided walkthrough, "
        "or [bold]devmind stats[/bold] for an index summary."
    )


if __name__ == "__main__":
    cli()
