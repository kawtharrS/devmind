import json
import os
import sys

from dotenv import load_dotenv

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))
load_dotenv()

import anthropic
import click
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table

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
_STORE_PATH = os.path.join(_DEVMIND_DIR, config.CHROMA_DIR)

_MODEL_CHOICES = click.Choice(list(MODEL_ALIASES.keys()))


def _load_json(path: str) -> list | dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


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
    console.print(Markdown(guide))


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
        table = Table(title=path, header_style="bold magenta")
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
            console.print(Markdown(generate_tour(summaries=summaries, client=client)))
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
        console.print(Markdown(result["answer"]))
        if result["files_used"]:
            console.print("[dim]Sources: " + "  ·  ".join(result["files_used"]) + "[/dim]\n")


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
    console.print("Run [bold]devmind chat[/bold] to ask questions, or [bold]devmind tour[/bold] for a guided walkthrough.")


if __name__ == "__main__":
    cli()
