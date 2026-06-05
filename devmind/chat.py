import anthropic

from devmind import config
from devmind import prompts
from devmind.store import search

MODEL_ALIASES: dict[str, str] = {
    "sonnet": config.SONNET_MODEL,
    "haiku": config.HAIKU_MODEL,
}


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

    answer_parts: list[str] = []
    with client.messages.stream(
        model=resolved_model,
        max_tokens=config.CHAT_MAX_TOKENS,
        system=prompts.CHAT_SYSTEM,
        messages=[{"role": "user", "content": f"{context}\n\n--- QUESTION ---\n{question}"}],
    ) as stream:
        for text in stream.text_stream:
            answer_parts.append(text)

    return {
        "answer": "".join(answer_parts),
        "files_used": [h["relative_path"] for h in hits],
        "model": resolved_model,
    }


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
    ) as stream:
        for text in stream.text_stream:
            parts.append(text)

    return "".join(parts)
