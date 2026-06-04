<<<<<<< HEAD
"""
Entry point for the devmind CLI.

Defines the top-level `devmind` Click group and its subcommands:
  - `index`       — summarize all repo files → .devmind/index.json
  - `build-store` — embed summaries into ChromaDB → .devmind/chroma/
  - `graph`       — extract dependency graph → .devmind/graph.json
  - `chat`        — interactive RAG Q&A session
  - `tour`        — print a Day 1/2/3 onboarding guide
  - `setup`       — run index + build-store + graph in one shot

All user-facing output uses Rich for formatted console rendering.
"""

import json
import os
=======
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
>>>>>>> ks-str

import anthropic
import click
from rich.console import Console
<<<<<<< HEAD
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table

=======
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from devmind import config
>>>>>>> ks-str
from devmind.chat import MODEL_ALIASES, answer_question
from devmind.chat import tour as generate_tour
from devmind.graph import extract_dependencies
from devmind.indexer import run_indexer
from devmind.store import build_store

console = Console()

<<<<<<< HEAD
# Default paths — every command uses these so they stay consistent.
_DEVMIND_DIR = ".devmind"
_INDEX_PATH = os.path.join(_DEVMIND_DIR, "index.json")
_GRAPH_PATH = os.path.join(_DEVMIND_DIR, "graph.json")
_STORE_PATH = os.path.join(_DEVMIND_DIR, "chroma")

_MODEL_CHOICES = click.Choice(list(MODEL_ALIASES.keys()))


# ---------------------------------------------------------------------------
# Root group
# ---------------------------------------------------------------------------

@click.group()
def cli():
    """devmind — AI-powered developer onboarding assistant.

    Typical workflow:

    \b
      devmind setup --repo /path/to/repo   # index + store + graph in one step
      devmind chat                          # interactive Q&A
      devmind tour                          # Day 1/2/3 onboarding guide
    """


# ---------------------------------------------------------------------------
# index
# ---------------------------------------------------------------------------

@cli.command()
@click.option(
    "--repo",
    required=True,
    type=click.Path(exists=True, file_okay=False, resolve_path=True),
    help="Path to the repository to index.",
)
@click.option(
    "--output",
    default=_DEVMIND_DIR,
    show_default=True,
    type=click.Path(file_okay=False, resolve_path=True),
    help="Directory where index.json and manifest.json are written.",
)
def index(repo: str, output: str) -> None:
    """Summarize every file in a repo and save the results to index.json.

    Uses claude-haiku-4-5 per file. Cost estimate: ~$0.01–0.05 per 100 files
    depending on file size.
    """
    run_indexer(repo_path=repo, output_path=output)


# ---------------------------------------------------------------------------
# build-store
# ---------------------------------------------------------------------------

@cli.command("build-store")
@click.option(
    "--index",
    "index_path",
    default=_INDEX_PATH,
    show_default=True,
    type=click.Path(exists=True, dir_okay=False, resolve_path=True),
    help="Path to index.json produced by the `index` command.",
)
@click.option(
    "--store",
    "store_path",
    default=_STORE_PATH,
    show_default=True,
    type=click.Path(file_okay=False, resolve_path=True),
    help="Directory where ChromaDB persists its data.",
)
def build_store_cmd(index_path: str, store_path: str) -> None:
    """Embed file summaries from index.json into a local ChromaDB vector store.

    Uses ChromaDB's built-in embedding model — no API cost. Fast (seconds).
    Run this once after `index`, and again whenever the index is refreshed.
    """
    build_store(index_json_path=index_path, store_path=store_path)


# ---------------------------------------------------------------------------
# graph
# ---------------------------------------------------------------------------

@cli.command()
@click.option(
    "--index",
    "index_path",
    default=_INDEX_PATH,
    show_default=True,
    type=click.Path(exists=True, dir_okay=False, resolve_path=True),
    help="Path to index.json produced by the `index` command.",
)
@click.option(
    "--top",
    default=10,
    show_default=True,
    help="Number of most-imported files to display.",
)
def graph(index_path: str, top: int) -> None:
    """Extract import dependencies and show the most-imported (core) files.

    Parses the 'imports' field from each file summary and fuzzy-matches them
    to known paths. Writes graph.json next to index.json. No API cost.
    """
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


# ---------------------------------------------------------------------------
# tour
# ---------------------------------------------------------------------------

@cli.command()
@click.option(
    "--index",
    "index_path",
    default=_INDEX_PATH,
    show_default=True,
    type=click.Path(exists=True, dir_okay=False, resolve_path=True),
    help="Path to index.json produced by the `index` command.",
)
def tour(index_path: str) -> None:
    """Generate a Day 1 / Day 2 / Day 3 onboarding guide for this codebase.

    Condenses all file summaries and asks claude-sonnet-4-6 to produce a
    reading guide ordered by conceptual importance. One API call, ~$0.001–0.01
    depending on codebase size.
    """
    client = anthropic.Anthropic()
    console.print("[dim]Generating onboarding guide…[/dim]")
    guide = generate_tour(index_json_path=index_path, client=client)
    console.print(Rule("Onboarding Guide", style="bold cyan"))
    console.print(Markdown(guide))


# ---------------------------------------------------------------------------
# chat
# ---------------------------------------------------------------------------

def _handle_graph_cmd(arg: str, graph_data: dict) -> None:
    """Print the import relationships for the file named in arg."""
    target = arg.strip()
    if not target:
        console.print("[yellow]Usage: /graph <relative_path>[/yellow]")
        return

=======
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
>>>>>>> ks-str
    forward: dict = graph_data.get("forward", {})
    reverse: dict = graph_data.get("reverse", {})

    matches = [p for p in forward if target in p]
    if not matches:
        console.print(f"[yellow]No file matching '{target}' in graph.[/yellow]")
        return

    for path in matches:
        imports = forward.get(path, [])
        imported_by = reverse.get(path, [])
<<<<<<< HEAD
        table = Table(title=path, header_style="bold magenta", show_header=True)
        table.add_column("Direction")
        table.add_column("File", style="cyan")
        for dep in imports:
            table.add_row("imports →", dep)
        for dep in imported_by:
            table.add_row("← used by", dep)
        if not imports and not imported_by:
            table.add_row("[dim]no relationships[/dim]", "")
        console.print(table)


@cli.command()
@click.option(
    "--store",
    "store_path",
    default=_STORE_PATH,
    show_default=True,
    type=click.Path(file_okay=False, resolve_path=True),
    help="ChromaDB directory produced by the `build-store` command.",
)
@click.option(
    "--index",
    "index_path",
    default=_INDEX_PATH,
    show_default=True,
    type=click.Path(exists=True, dir_okay=False, resolve_path=True),
    help="Path to index.json.",
)
@click.option(
    "--graph",
    "graph_path",
    default=_GRAPH_PATH,
    show_default=True,
    type=click.Path(exists=True, dir_okay=False, resolve_path=True),
    help="Path to graph.json.",
)
@click.option(
    "--model",
    default="sonnet",
    show_default=True,
    type=_MODEL_CHOICES,
    help=(
        "Model for answering questions. "
        "'sonnet' (~$0.003/question) is recommended. "
        "'haiku' (~$0.0003/question) is faster and cheaper for testing."
    ),
)
def chat(store_path: str, index_path: str, graph_path: str, model: str) -> None:
    """Start an interactive Q&A session about the indexed codebase.

    Each question retrieves 5 relevant files from ChromaDB and sends them as
    context to Claude. Cost per question: ~$0.003 (sonnet) or ~$0.0003 (haiku).

    \b
    Session commands:
      /exit          — quit
      /graph <file>  — show what a file imports and what imports it
      /tour          — generate the onboarding guide inline
    """
    client = anthropic.Anthropic()

    with open(graph_path, "r", encoding="utf-8") as f:
        graph_data = json.load(f)

    model_label = f"{model} ({MODEL_ALIASES[model]})"
    console.print(Panel(
        f"[bold cyan]DevMind[/bold cyan] — Ask anything about this codebase\n"
        f"[dim]Model: {model_label}   Commands: /exit  /graph <file>  /tour[/dim]",
=======

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
>>>>>>> ks-str
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
<<<<<<< HEAD
            guide = generate_tour(index_json_path=index_path, client=client)
            console.print(Markdown(guide))
            continue

        if user_input.startswith("/graph"):
            _handle_graph_cmd(user_input[len("/graph"):], graph_data)
=======
            console.print(_colorize_answer(generate_tour(summaries=summaries, client=client)))
            continue

        if user_input.startswith("/graph"):
            target = user_input[len("/graph"):].strip()
            if target:
                _show_graph_for(target, graph_data)
            else:
                console.print("[yellow]Usage: /graph <relative_path>[/yellow]")
>>>>>>> ks-str
            continue

        result = answer_question(
            question=user_input,
            store_path=store_path,
<<<<<<< HEAD
            index_json_path=index_path,
            graph_json_path=graph_path,
=======
            summaries=summaries,
            graph=graph_data,
>>>>>>> ks-str
            client=client,
            model=model,
        )

<<<<<<< HEAD
        console.print(Markdown(result["answer"]))

        if result["files_used"]:
            console.print(
                "[dim]Sources: " + "  ·  ".join(result["files_used"]) + "[/dim]\n"
            )


# ---------------------------------------------------------------------------
# setup
# ---------------------------------------------------------------------------

@cli.command()
@click.option(
    "--repo",
    required=True,
    type=click.Path(exists=True, file_okay=False, resolve_path=True),
    help="Path to the repository to index.",
)
@click.option(
    "--output",
    default=_DEVMIND_DIR,
    show_default=True,
    type=click.Path(file_okay=False, resolve_path=True),
    help="Directory where all devmind artefacts are written.",
)
def setup(repo: str, output: str) -> None:
    """Index a repo, build the vector store, and extract the dependency graph.

    Runs `index` → `build-store` → `graph` in sequence. This is the recommended
    first step for a new repository. After this, run `devmind chat` or
    `devmind tour`.

    Cost estimate: ~$0.01–0.05 per 100 files (Haiku for indexing). The
    vector store and graph steps have no API cost.
    """
    index_json = os.path.join(output, "index.json")
    store_dir = os.path.join(output, "chroma")
=======
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
>>>>>>> ks-str

    console.print(Rule("Step 1 / 3 — Indexing files", style="bold blue"))
    run_indexer(repo_path=repo, output_path=output)

    console.print(Rule("Step 2 / 3 — Building vector store", style="bold blue"))
<<<<<<< HEAD
    build_store(index_json_path=index_json, store_path=store_dir)

    console.print(Rule("Step 3 / 3 — Extracting dependency graph", style="bold blue"))
    core = extract_dependencies(index_json)

    graph_path = os.path.join(output, "graph.json")
    console.print(f"[green]Graph written to:[/green] {graph_path}")
=======
    count = build_store(index_json_path=index_json, store_path=store_dir)
    console.print(f"[green]Stored {count} files in vector DB[/green]")

    console.print(Rule("Step 3 / 3 — Extracting dependency graph", style="bold blue"))
    core = extract_dependencies(index_json)
    console.print(f"[green]Graph written to:[/green] {os.path.join(output, 'graph.json')}")
>>>>>>> ks-str

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
<<<<<<< HEAD
        "or [bold]devmind tour[/bold] for a guided walkthrough."
=======
        "[bold]devmind tour[/bold] for a guided walkthrough, "
        "or [bold]devmind stats[/bold] for an index summary."
>>>>>>> ks-str
    )


if __name__ == "__main__":
    cli()
