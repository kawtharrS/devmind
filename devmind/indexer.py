import json
import os
import time
from collections import Counter
from datetime import datetime, timezone

import anthropic
import tiktoken
from rich.console import Console
from rich.progress import BarColumn, MofNCompleteColumn, Progress, TextColumn, TimeElapsedColumn
from rich.table import Table

from devmind import config
from devmind.utils import chunk_file, get_repo_files

console = Console()

SYSTEM_PROMPT = (
    "You are a senior software engineer analyzing a codebase. "
    "Be concise and precise. Never repeat the filename."
)

USER_PROMPT_TEMPLATE = """\
Analyze this file and return ONLY a JSON object with these fields:
- purpose: one sentence describing what this file does
- key_functions: list of the 3-5 most important functions/classes/exports
- imports: list of internal imports (other project files it depends on)
- exports: list of what this file exposes to the rest of the codebase
- domain: one word category (auth, payments, routing, database, ui, config, utils, etc)
- complexity: low/medium/high

File path: {relative_path}
Content:
{content}

Return ONLY the JSON, no markdown, no explanation."""

_FALLBACK = {
    "purpose": "parse error",
    "key_functions": [],
    "imports": [],
    "exports": [],
    "domain": "unknown",
    "complexity": "unknown",
}

_ENCODING = tiktoken.get_encoding("cl100k_base")


def _parse_summary(raw: str) -> dict | None:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    if raw.startswith("```"):
        inner = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        try:
            return json.loads(inner)
        except json.JSONDecodeError:
            pass

    return None


def summarize_file(
    file_path: str,
    relative_path: str,
    client: anthropic.Anthropic,
    content: str | None = None,
) -> dict:
    if content is None:
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except OSError as exc:
            return {**_FALLBACK, "purpose": f"read error: {exc}", "path": file_path, "relative_path": relative_path}

    user_prompt = USER_PROMPT_TEMPLATE.format(relative_path=relative_path, content=content)

    try:
        message = client.messages.create(
            model=config.HAIKU_MODEL,
            max_tokens=config.SUMMARIZE_MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
    except anthropic.APIError as exc:
        return {**_FALLBACK, "purpose": f"api error: {exc}", "path": file_path, "relative_path": relative_path}

    summary = _parse_summary(message.content[0].text.strip())
    if summary is None:
        return {**_FALLBACK, "path": file_path, "relative_path": relative_path}

    summary["path"] = file_path
    summary["relative_path"] = relative_path
    return summary


def run_indexer(repo_path: str, output_path: str) -> None:
    os.makedirs(output_path, exist_ok=True)

    files = get_repo_files(repo_path)
    if not files:
        console.print("[yellow]No indexable files found.[/yellow]")
        return

    client = anthropic.Anthropic()
    summaries = []
    total_input_tokens = 0

    progress = Progress(
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
    )

    with progress:
        task = progress.add_task(f"Indexing {len(files)} files", total=len(files))

        for file_info in files:
            file_path = file_info["path"]
            relative_path = file_info["relative_path"]

            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
            except OSError:
                progress.advance(task)
                continue

            tokens = _ENCODING.encode(content)
            total_input_tokens += len(tokens)

            if len(tokens) > config.MAX_CHUNK_TOKENS:
                content = chunk_file(content, max_tokens=config.MAX_CHUNK_TOKENS)[0]
                result = summarize_file(file_path, relative_path, client, content=content)
                result["note"] = "large file, partial"
            else:
                result = summarize_file(file_path, relative_path, client, content=content)

            summaries.append(result)
            time.sleep(0.1)
            progress.advance(task)

    index_path = os.path.join(output_path, "index.json")
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(summaries, f, indent=2)

    domains = [s.get("domain", "unknown") for s in summaries]
    domain_counts = Counter(domains)
    manifest = {
        "total_files": len(summaries),
        "domains_found": domain_counts,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "repo_path": os.path.abspath(repo_path),
    }
    with open(os.path.join(output_path, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    est_input_cost = (total_input_tokens / 1_000_000) * config.INPUT_COST_PER_M
    est_output_cost = (len(summaries) * config.AVG_SUMMARY_OUTPUT_TOKENS / 1_000_000) * config.OUTPUT_COST_PER_M

    table = Table(title="Indexing Complete", show_header=True, header_style="bold magenta")
    table.add_column("Domain", style="cyan")
    table.add_column("Files", justify="right")
    for domain, count in sorted(domain_counts.items(), key=lambda x: -x[1]):
        table.add_row(domain, str(count))
    table.add_section()
    table.add_row("[bold]Total[/bold]", f"[bold]{len(summaries)}[/bold]")

    console.print(table)
    console.print(f"[green]Index written to:[/green] {index_path}")
    console.print(
        f"[dim]Estimated cost: ${est_input_cost + est_output_cost:.4f} "
        f"({total_input_tokens:,} input tokens × {len(summaries)} files)[/dim]"
    )
