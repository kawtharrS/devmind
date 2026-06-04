<<<<<<< HEAD
"""
Repository walker and file summarization module.

Responsibilities:
  - Recursively walk a git repository using GitPython, respecting .gitignore.
  - Filter files to indexable types (source code, markdown, config) via utils.py.
  - Read and chunk each file's content so it fits within the token budget
    defined in config.py (uses tiktoken via utils.py for counting).
  - Call the Anthropic API to produce a short natural-language summary of each
    chunk, which is stored alongside the raw text in ChromaDB via store.py.
  - Return a structured list of IndexedFile objects (path, chunks, summaries).
"""

=======
>>>>>>> ks-str
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

<<<<<<< HEAD
=======
from devmind import config
from devmind import prompts
>>>>>>> ks-str
from devmind.utils import chunk_file, get_repo_files

console = Console()

<<<<<<< HEAD
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

=======
>>>>>>> ks-str
_FALLBACK = {
    "purpose": "parse error",
    "key_functions": [],
    "imports": [],
    "exports": [],
    "domain": "unknown",
    "complexity": "unknown",
}

<<<<<<< HEAD
# Haiku pricing as of 2025 (per million tokens)
_INPUT_COST_PER_M = 0.80
_OUTPUT_COST_PER_M = 4.00
_AVG_OUTPUT_TOKENS = 150  # conservative estimate per summary

_ENCODING = tiktoken.get_encoding("cl100k_base")


=======
_ENCODING = tiktoken.get_encoding("cl100k_base")


def _estimate_cost(total_input_tokens: int, file_count: int) -> float:
    est_input = (total_input_tokens / 1_000_000) * config.INPUT_COST_PER_M
    est_output = (file_count * config.AVG_SUMMARY_OUTPUT_TOKENS / 1_000_000) * config.OUTPUT_COST_PER_M
    return est_input + est_output


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


>>>>>>> ks-str
def summarize_file(
    file_path: str,
    relative_path: str,
    client: anthropic.Anthropic,
<<<<<<< HEAD
) -> dict:
    """Read a file, ask Claude to summarize it, and return a structured dict.

    Returns a dict with all JSON fields from the model response plus:
      path          — absolute file path
      relative_path — repo-relative file path

    On any failure (file unreadable, API error, invalid JSON), returns a
    minimal dict with purpose set to a descriptive error string.
    """
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except OSError as exc:
        return {**_FALLBACK, "purpose": f"read error: {exc}", "path": file_path, "relative_path": relative_path}

    user_prompt = USER_PROMPT_TEMPLATE.format(
        relative_path=relative_path,
        content=content,
    )

    try:
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        raw = message.content[0].text.strip()
    except anthropic.APIError as exc:
        return {**_FALLBACK, "purpose": f"api error: {exc}", "path": file_path, "relative_path": relative_path}

    try:
        summary = json.loads(raw)
    except json.JSONDecodeError:
        # Claude occasionally wraps the JSON in a code fence despite the prompt.
        # Try stripping a ```json ... ``` wrapper before giving up.
        if raw.startswith("```"):
            inner = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            try:
                summary = json.loads(inner)
            except json.JSONDecodeError:
                return {**_FALLBACK, "path": file_path, "relative_path": relative_path}
        else:
            return {**_FALLBACK, "path": file_path, "relative_path": relative_path}
=======
    content: str | None = None,
) -> dict:
    if content is None:
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except OSError as exc:
            return {**_FALLBACK, "purpose": f"read error: {exc}", "path": file_path, "relative_path": relative_path}

    user_prompt = prompts.INDEXER_USER.format(relative_path=relative_path, content=content)

    try:
        message = client.messages.create(
            model=config.HAIKU_MODEL,
            max_tokens=config.SUMMARIZE_MAX_TOKENS,
            system=prompts.INDEXER_SYSTEM,
            messages=[{"role": "user", "content": user_prompt}],
        )
    except anthropic.APIError as exc:
        return {**_FALLBACK, "purpose": f"api error: {exc}", "path": file_path, "relative_path": relative_path}

    summary = _parse_summary(message.content[0].text.strip())
    if summary is None:
        return {**_FALLBACK, "path": file_path, "relative_path": relative_path}
>>>>>>> ks-str

    summary["path"] = file_path
    summary["relative_path"] = relative_path
    return summary


def run_indexer(repo_path: str, output_path: str) -> None:
<<<<<<< HEAD
    """Index a repository: summarize every file and write results to output_path.

    Writes two files:
      <output_path>/index.json    — list of summary dicts, one per file
      <output_path>/manifest.json — run metadata (totals, domains, timestamp)
    """
=======
>>>>>>> ks-str
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

<<<<<<< HEAD
            token_count = len(_ENCODING.encode(content))
            total_input_tokens += token_count

            if token_count > 3000:
                # Only summarize the first chunk; note the truncation in the summary.
                first_chunk = chunk_file(content, max_tokens=3000)[0]
                summary = summarize_file.__wrapped__ if hasattr(summarize_file, "__wrapped__") else None
                # Call summarize_file with the truncated content directly.
                truncated_path = file_path  # reuse path; content handled below
                user_prompt = USER_PROMPT_TEMPLATE.format(
                    relative_path=relative_path,
                    content=first_chunk,
                )
                try:
                    message = client.messages.create(
                        model="claude-haiku-4-5-20251001",
                        max_tokens=512,
                        system=SYSTEM_PROMPT,
                        messages=[{"role": "user", "content": user_prompt}],
                    )
                    raw = message.content[0].text.strip()
                    try:
                        result = json.loads(raw)
                    except json.JSONDecodeError:
                        if raw.startswith("```"):
                            inner = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
                            result = json.loads(inner) if inner else dict(_FALLBACK)
                        else:
                            result = dict(_FALLBACK)
                except (anthropic.APIError, json.JSONDecodeError):
                    result = dict(_FALLBACK)

                result["path"] = file_path
                result["relative_path"] = relative_path
                result["note"] = "large file, partial"
            else:
                result = summarize_file(file_path, relative_path, client)
=======
            tokens = _ENCODING.encode(content)
            total_input_tokens += len(tokens)

            if len(tokens) > config.MAX_CHUNK_TOKENS:
                content = chunk_file(content, max_tokens=config.MAX_CHUNK_TOKENS)[0]
                result = summarize_file(file_path, relative_path, client, content=content)
                result["note"] = "large file, partial"
            else:
                result = summarize_file(file_path, relative_path, client, content=content)
>>>>>>> ks-str

            summaries.append(result)
            time.sleep(0.1)
            progress.advance(task)

<<<<<<< HEAD
    # Write index
=======
>>>>>>> ks-str
    index_path = os.path.join(output_path, "index.json")
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(summaries, f, indent=2)

<<<<<<< HEAD
    # Build and write manifest
=======
>>>>>>> ks-str
    domains = [s.get("domain", "unknown") for s in summaries]
    domain_counts = Counter(domains)
    manifest = {
        "total_files": len(summaries),
        "domains_found": domain_counts,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "repo_path": os.path.abspath(repo_path),
<<<<<<< HEAD
    }
    manifest_path = os.path.join(output_path, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    # Estimated cost
    est_input_cost = (total_input_tokens / 1_000_000) * _INPUT_COST_PER_M
    est_output_cost = (len(summaries) * _AVG_OUTPUT_TOKENS / 1_000_000) * _OUTPUT_COST_PER_M
    est_total_cost = est_input_cost + est_output_cost

    # Summary table
    table = Table(title="Indexing Complete", show_header=True, header_style="bold magenta")
    table.add_column("Domain", style="cyan")
    table.add_column("Files", justify="right")

    for domain, count in sorted(domain_counts.items(), key=lambda x: -x[1]):
        table.add_row(domain, str(count))

=======
        "total_input_tokens": total_input_tokens,
        "estimated_cost": _estimate_cost(total_input_tokens, len(summaries)),
    }
    with open(os.path.join(output_path, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    table = Table(title="Indexing Complete", show_header=True, header_style="bold magenta")
    table.add_column("Domain", style="cyan")
    table.add_column("Files", justify="right")
    for domain, count in sorted(domain_counts.items(), key=lambda x: -x[1]):
        table.add_row(domain, str(count))
>>>>>>> ks-str
    table.add_section()
    table.add_row("[bold]Total[/bold]", f"[bold]{len(summaries)}[/bold]")

    console.print(table)
    console.print(f"[green]Index written to:[/green] {index_path}")
<<<<<<< HEAD
    console.print(f"[dim]Estimated cost: ${est_total_cost:.4f} "
                  f"({total_input_tokens:,} input tokens × {len(summaries)} files)[/dim]")
=======
    console.print(
        f"[dim]Estimated cost: ${_estimate_cost(total_input_tokens, len(summaries)):.4f} "
        f"({total_input_tokens:,} input tokens × {len(summaries)} files)[/dim]"
    )
>>>>>>> ks-str
