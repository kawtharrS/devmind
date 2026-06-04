import json

import anthropic

from devmind import config
from devmind.store import search

MODEL_ALIASES: dict[str, str] = {
    "sonnet": config.SONNET_MODEL,
    "haiku": config.HAIKU_MODEL,
}

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


def _build_context(
    hits: list[dict],
    summaries_by_path: dict[str, dict],
    reverse: dict[str, list[str]],
    forward: dict[str, list[str]],
) -> str:
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

        imported_by = ", ".join(reverse.get(rel, [])) or "nothing"

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
    index_json_path: str,
    graph_json_path: str,
    client: anthropic.Anthropic,
    model: str = "sonnet",
) -> dict:
    resolved_model = MODEL_ALIASES.get(model, model)

    hits = search(question, store_path, n_results=config.CHAT_CONTEXT_CHUNKS)

    with open(index_json_path, "r", encoding="utf-8") as f:
        all_summaries: list[dict] = json.load(f)
    summaries_by_path = {s["relative_path"]: s for s in all_summaries if "relative_path" in s}

    with open(graph_json_path, "r", encoding="utf-8") as f:
        graph = json.load(f)

    context = _build_context(
        hits,
        summaries_by_path,
        graph.get("reverse", {}),
        graph.get("forward", {}),
    )

    answer_parts: list[str] = []
    with client.messages.stream(
        model=resolved_model,
        max_tokens=config.CHAT_MAX_TOKENS,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"{context}\n\n--- QUESTION ---\n{question}"}],
    ) as stream:
        for text in stream.text_stream:
            answer_parts.append(text)

    return {
        "answer": "".join(answer_parts),
        "files_used": [h["relative_path"] for h in hits],
        "model": resolved_model,
    }


def tour(index_json_path: str, client: anthropic.Anthropic) -> str:
    with open(index_json_path, "r", encoding="utf-8") as f:
        all_summaries: list[dict] = json.load(f)

    condensed = "\n".join(
        f"- {s.get('relative_path', '?')} [{s.get('domain', 'unknown')}, {s.get('complexity', '')}]: {s.get('purpose', '')}"
        for s in all_summaries
    )

    parts: list[str] = []
    with client.messages.stream(
        model=config.SONNET_MODEL,
        max_tokens=config.TOUR_MAX_TOKENS,
        messages=[{"role": "user", "content": _TOUR_PROMPT_TEMPLATE.format(summaries=condensed)}],
    ) as stream:
        for text in stream.text_stream:
            parts.append(text)

    return "".join(parts)
