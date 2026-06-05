import json
import os

from mcp.server.fastmcp import FastMCP

from devmind import config
from devmind.store import search as _chroma_search

_DEVMIND_PATH = os.environ.get("DEVMIND_PATH", ".devmind")
_STORE_PATH = os.path.join(_DEVMIND_PATH, config.CHROMA_DIR)

_summaries_by_path: dict[str, dict] = {}
_graph: dict = {}


def _load_state() -> None:
    global _summaries_by_path, _graph

    index_path = os.path.join(_DEVMIND_PATH, "index.json")
    graph_path = os.path.join(_DEVMIND_PATH, "graph.json")

    if os.path.exists(index_path):
        with open(index_path, encoding="utf-8") as f:
            summaries: list[dict] = json.load(f)
        _summaries_by_path = {
            s["relative_path"]: s
            for s in summaries
            if "relative_path" in s
        }

    if os.path.exists(graph_path):
        with open(graph_path, encoding="utf-8") as f:
            _graph = json.load(f)


_load_state()

mcp = FastMCP("devmind")


def _resolve_path(target: str, candidates: dict) -> str | None:
    if target in candidates:
        return target
    matches = [k for k in candidates if target in k]
    return matches[0] if len(matches) == 1 else None


@mcp.tool(description=(
    "Search the indexed codebase by natural-language query. "
    "Returns the most relevant files with their purpose, domain, and similarity score."
))
def search_codebase(query: str, n_results: int = 5) -> list[dict]:
    try:
        hits = _chroma_search(query, _STORE_PATH, n_results=n_results)
    except Exception as exc:
        return [{"error": f"Search failed: {exc}"}]

    return [
        {
            "relative_path": h["relative_path"],
            "purpose": h["purpose"],
            "domain": h["domain"],
            "score": h["similarity_score"],
        }
        for h in hits
    ]


@mcp.tool(description=(
    "Return the full summary for a single file from the index. "
    "Includes purpose, key functions, imports, exports, domain, and complexity. "
    "Accepts partial paths (e.g. 'store' matches 'devmind/store.py')."
))
def get_file_summary(relative_path: str) -> dict:
    if not _summaries_by_path:
        return {"error": "Index not loaded. Run 'devmind setup' first."}

    resolved = _resolve_path(relative_path, _summaries_by_path)
    if resolved is None:
        matches = [k for k in _summaries_by_path if relative_path in k]
        if len(matches) > 1:
            return {"error": f"Ambiguous path — matched {len(matches)} files.", "matches": matches}
        return {"error": f"File not found: {relative_path}"}

    summary = dict(_summaries_by_path[resolved])
    summary.pop("path", None)
    return summary


@mcp.tool(description=(
    "Return the dependency relationships for a file: what it imports and what imports it. "
    "Accepts partial paths (e.g. 'chat' matches 'devmind/chat.py')."
))
def get_dependency_graph(relative_path: str) -> dict:
    if not _graph:
        return {"error": "Graph not loaded. Run 'devmind setup' first."}

    forward: dict = _graph.get("forward", {})
    reverse: dict = _graph.get("reverse", {})

    resolved = _resolve_path(relative_path, forward)
    if resolved is None:
        matches = [k for k in forward if relative_path in k]
        if len(matches) > 1:
            return {"error": f"Ambiguous path — matched {len(matches)} files.", "matches": matches}
        return {"error": f"File not found in graph: {relative_path}"}

    return {
        "file": resolved,
        "imports": forward.get(resolved, []),
        "imported_by": reverse.get(resolved, []),
    }


@mcp.tool(description=(
    "Return the pre-generated Day 1/2/3 onboarding tour for this codebase. "
    "Generate it first with: devmind tour > .devmind/tour.md"
))
def get_onboarding_tour() -> str:
    tour_path = os.path.join(_DEVMIND_PATH, "tour.md")
    if not os.path.exists(tour_path):
        return (
            "No tour file found at .devmind/tour.md. "
            "Generate one with: devmind tour > .devmind/tour.md"
        )
    with open(tour_path, encoding="utf-8") as f:
        return f.read()


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
