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
import sys

from dotenv import load_dotenv

# Force UTF-8 on Windows so Rich's Unicode output (─, ×, →, etc.) isn't mangled.
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Load .env from project root or devmind/ subdirectory, whichever exists first.
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))
load_dotenv()  # fallback: project root

import anthropic
import click
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table

from devmind.chat import MODEL_ALIASES, answer_question
from devmind.chat import tour as generate_tour
from devmind.graph import extract_dependencies
from devmind.indexer import run_indexer
from devmind.store import build_store

console = Console()

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

    forward: dict = graph_data.get("forward", {})
    reverse: dict = graph_data.get("reverse", {})

    matches = [p for p in forward if target in p]
    if not matches:
        console.print(f"[yellow]No file matching '{target}' in graph.[/yellow]")
        return

    for path in matches:
        imports = forward.get(path, [])
        imported_by = reverse.get(path, [])
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
            guide = generate_tour(index_json_path=index_path, client=client)
            console.print(Markdown(guide))
            continue

        if user_input.startswith("/graph"):
            _handle_graph_cmd(user_input[len("/graph"):], graph_data)
            continue

        result = answer_question(
            question=user_input,
            store_path=store_path,
            index_json_path=index_path,
            graph_json_path=graph_path,
            client=client,
            model=model,
        )

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

    console.print(Rule("Step 1 / 3 — Indexing files", style="bold blue"))
    run_indexer(repo_path=repo, output_path=output)

    console.print(Rule("Step 2 / 3 — Building vector store", style="bold blue"))
    build_store(index_json_path=index_json, store_path=store_dir)

    console.print(Rule("Step 3 / 3 — Extracting dependency graph", style="bold blue"))
    core = extract_dependencies(index_json)

    graph_path = os.path.join(output, "graph.json")
    console.print(f"[green]Graph written to:[/green] {graph_path}")

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
        "or [bold]devmind tour[/bold] for a guided walkthrough."
    )


if __name__ == "__main__":
    cli()
