<<<<<<< HEAD
"""
RAG query and Claude answer module.

Responsibilities:
  - Accept a natural-language question from the CLI.
  - Query store.py to retrieve the top-N relevant code chunks and summaries.
  - Optionally enrich context with graph.py data (e.g. dependency info for
    files mentioned in the retrieved chunks).
  - Build a structured prompt that includes: the retrieved context, the
    dependency graph snippet, and the user's question.
  - Call the Anthropic API (model configured in config.py) with the assembled
    prompt and stream the response back to the caller.
  - Return the final answer text and the list of source files cited, so the
    CLI can render a Rich-formatted response with citations.
"""

import json

import anthropic

from devmind.store import search

MODEL_ALIASES: dict[str, str] = {
    "sonnet": "claude-sonnet-4-6",
    "haiku": "claude-haiku-4-5-20251001",
}

_TOUR_MODEL = "claude-sonnet-4-6"

_TOUR_PROMPT_TEMPLATE = """\
Given these file summaries, generate a structured onboarding guide for a new developer.

Format:
## Day 1 — Understand the foundation
- Read file X because: ...

## Day 2 — Core business logic
...

## Day 3 — Advanced/peripheral systems
...

Be specific about WHY to read each file and what to look for.

Summaries:
{summaries}"""

_MODEL = "claude-sonnet-4-6"

_SYSTEM_PROMPT = """\
You are a senior engineer who has deeply studied this codebase.
You help new developers understand how things work.

Rules:
- Always reference specific file paths when explaining
- For flow questions, trace execution step by step: file → function → file
- For 'why' questions, infer intent from naming and structure
- If you lack context, say which files would answer the question
- Use bullet points for multi-step flows
- Be direct. No filler phrases."""

=======
import anthropic

from devmind import config
from devmind import prompts
from devmind.store import search

MODEL_ALIASES: dict[str, str] = {
    "sonnet": config.SONNET_MODEL,
    "haiku": config.HAIKU_MODEL,
}

>>>>>>> ks-str

def _build_context(
    hits: list[dict],
    summaries_by_path: dict[str, dict],
    reverse: dict[str, list[str]],
    forward: dict[str, list[str]],
) -> str:
<<<<<<< HEAD
    """Assemble the context block that is injected before the question."""
=======
>>>>>>> ks-str
    lines: list[str] = ["--- RELEVANT FILES ---"]

    for hit in hits:
        rel = hit["relative_path"]
        summary = summaries_by_path.get(rel, {})

        key_fns = summary.get("key_functions") or []
        if isinstance(key_fns, list):
            key_fns = ", ".join(key_fns)

        imports = summary.get("imports") or []
        if isinstance(imports, list):
            imports = ", ".join(imports) if imports else "none"

<<<<<<< HEAD
        rev_deps = reverse.get(rel, [])
        imported_by = ", ".join(rev_deps) if rev_deps else "nothing"
=======
        imported_by = ", ".join(reverse.get(rel, [])) or "nothing"
>>>>>>> ks-str

        lines += [
            f"\nFile: {rel} (domain: {summary.get('domain', 'unknown')})",
            f"Purpose: {summary.get('purpose', '')}",
            f"Key functions: {key_fns}",
            f"Imports from: {imports}",
            f"Imported by: {imported_by}",
        ]

    lines += ["\n--- DEPENDENCY RELATIONSHIPS ---"]

    for hit in hits:
        rel = hit["relative_path"]
        deps = forward.get(rel, [])
        rev_deps = reverse.get(rel, [])
        if deps:
            lines.append(f"{rel} → imports → {', '.join(deps)}")
        if rev_deps:
            lines.append(f"{rel} ← used by ← {', '.join(rev_deps)}")

    return "\n".join(lines)


def answer_question(
    question: str,
    store_path: str,
<<<<<<< HEAD
    index_json_path: str,
    graph_json_path: str,
    client: anthropic.Anthropic,
    model: str = "sonnet",
) -> dict:
    """Run RAG over the codebase index and return a Claude-powered answer.

    model accepts an alias ("sonnet" or "haiku") or a full model ID.

    Returns:
      answer      — full text of the model's response
      files_used  — list of relative_paths surfaced as context
      model       — resolved model ID used
    """
    resolved_model = MODEL_ALIASES.get(model, model)

    hits = search(question, store_path, n_results=5)
    hit_paths = [h["relative_path"] for h in hits]

    with open(index_json_path, "r", encoding="utf-8") as f:
        all_summaries: list[dict] = json.load(f)
    summaries_by_path = {s["relative_path"]: s for s in all_summaries if "relative_path" in s}

    with open(graph_json_path, "r", encoding="utf-8") as f:
        graph = json.load(f)
    forward: dict[str, list[str]] = graph.get("forward", {})
    reverse: dict[str, list[str]] = graph.get("reverse", {})

    context = _build_context(hits, summaries_by_path, reverse, forward)

    user_message = f"{context}\n\n--- QUESTION ---\n{question}"
=======
    summaries: list[dict],
    graph: dict,
    client: anthropic.Anthropic,
    model: str = "sonnet",
) -> dict:
    resolved_model = MODEL_ALIASES.get(model, model)

    hits = search(question, store_path, n_results=config.CHAT_CONTEXT_CHUNKS)

    summaries_by_path = {s["relative_path"]: s for s in summaries if "relative_path" in s}

    context = _build_context(
        hits,
        summaries_by_path,
        graph.get("reverse", {}),
        graph.get("forward", {}),
    )
>>>>>>> ks-str

    answer_parts: list[str] = []
    with client.messages.stream(
        model=resolved_model,
<<<<<<< HEAD
        max_tokens=1024,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
=======
        max_tokens=config.CHAT_MAX_TOKENS,
        system=prompts.CHAT_SYSTEM,
        messages=[{"role": "user", "content": f"{context}\n\n--- QUESTION ---\n{question}"}],
>>>>>>> ks-str
    ) as stream:
        for text in stream.text_stream:
            answer_parts.append(text)

    return {
        "answer": "".join(answer_parts),
<<<<<<< HEAD
        "files_used": hit_paths,
=======
        "files_used": [h["relative_path"] for h in hits],
>>>>>>> ks-str
        "model": resolved_model,
    }


<<<<<<< HEAD
def tour(index_json_path: str, client: anthropic.Anthropic) -> str:
    """Generate a Day 1/2/3 onboarding guide from the full index.

    Condenses each summary to a single line (path, domain, purpose) to stay
    within the context budget while giving the model enough signal to order
    files by conceptual importance.

    Returns the guide as a markdown string.
    """
    with open(index_json_path, "r", encoding="utf-8") as f:
        all_summaries: list[dict] = json.load(f)

    condensed_lines: list[str] = []
    for s in all_summaries:
        rel = s.get("relative_path", "?")
        domain = s.get("domain", "unknown")
        purpose = s.get("purpose", "")
        complexity = s.get("complexity", "")
        condensed_lines.append(f"- {rel} [{domain}, {complexity}]: {purpose}")

    condensed = "\n".join(condensed_lines)
    prompt = _TOUR_PROMPT_TEMPLATE.format(summaries=condensed)

    parts: list[str] = []
    with client.messages.stream(
        model=_TOUR_MODEL,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
=======
def tour(summaries: list[dict], client: anthropic.Anthropic) -> str:
    condensed = "\n".join(
        f"- {s.get('relative_path', '?')} [{s.get('domain', 'unknown')}, {s.get('complexity', '')}]: {s.get('purpose', '')}"
        for s in summaries
    )

    parts: list[str] = []
    with client.messages.stream(
        model=config.SONNET_MODEL,
        max_tokens=config.TOUR_MAX_TOKENS,
        messages=[{"role": "user", "content": prompts.TOUR_USER.format(summaries=condensed)}],
>>>>>>> ks-str
    ) as stream:
        for text in stream.text_stream:
            parts.append(text)

    return "".join(parts)
