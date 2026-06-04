"""
Dependency and import graph extraction module.

Responsibilities:
  - Parse Python source files using the `ast` module to extract all import
    statements (both `import X` and `from X import Y` forms).
  - Resolve imports to local project files where possible, distinguishing
    first-party, third-party, and stdlib dependencies.
  - Build a directed graph (dict-of-sets or networkx DiGraph) mapping each
    file to its dependencies.
  - Expose helpers to query the graph: dependents of a file, transitive
    dependencies, cycles, and an adjacency summary suitable for embedding.
  - Serialize the graph to JSON for storage or display via the CLI.
"""

import json
import os
from collections import deque


def _fuzzy_match(import_string: str, all_relative_paths: list[str]) -> str | None:
    """Return the relative_path that best matches import_string, or None.

    Matching strategy (tried in order, first hit wins):
      1. Exact match after normalising separators.
      2. Any path that ends with the normalised import string.
      3. Any path whose stem (no extension) ends with the import stem.
    """
    normalised = import_string.replace("\\", "/").strip("/")

    # 1. Exact
    if normalised in all_relative_paths:
        return normalised

    # 2. Suffix match (e.g. "auth/utils" matches "src/auth/utils.py")
    for path in all_relative_paths:
        path_norm = path.replace("\\", "/")
        if path_norm.endswith(normalised) or path_norm.endswith(normalised + ".py"):
            return path

    # 3. Stem match — strip extensions from both sides
    import_stem = normalised.rstrip("/").split("/")[-1]
    for path in all_relative_paths:
        path_stem = os.path.splitext(os.path.basename(path))[0]
        if path_stem == import_stem:
            return path

    return None


def extract_dependencies(index_json_path: str) -> dict:
    """Build forward and reverse dependency graphs from an index.json file.

    Loads the summaries produced by indexer.run_indexer, fuzzy-matches each
    entry's "imports" list against known relative_paths, and writes a
    graph.json next to the index.

    graph.json schema:
      {
        "forward":  { relative_path: [relative_paths it imports] },
        "reverse":  { relative_path: [relative_paths that import it] },
        "core":     [ {file, dependents} ] sorted descending by dependent count
      }

    Returns the core list so callers can surface the most-imported files.
    """
    index_dir = os.path.dirname(os.path.abspath(index_json_path))

    with open(index_json_path, "r", encoding="utf-8") as f:
        summaries: list[dict] = json.load(f)

    all_relative_paths = [s["relative_path"] for s in summaries if "relative_path" in s]

    forward: dict[str, list[str]] = {}
    reverse: dict[str, list[str]] = {p: [] for p in all_relative_paths}

    for summary in summaries:
        src = summary.get("relative_path")
        if not src:
            continue

        resolved: list[str] = []
        for imp in summary.get("imports", []):
            match = _fuzzy_match(imp, all_relative_paths)
            if match and match != src:
                resolved.append(match)
                reverse[match].append(src)

        forward[src] = resolved

    core = sorted(
        [{"file": path, "dependents": len(importers)} for path, importers in reverse.items()],
        key=lambda x: x["dependents"],
        reverse=True,
    )

    graph = {"forward": forward, "reverse": reverse, "core": core}

    graph_path = os.path.join(index_dir, "graph.json")
    with open(graph_path, "w", encoding="utf-8") as f:
        json.dump(graph, f, indent=2)

    return core


def find_path(graph: dict, start_file: str, end_file: str) -> list[str] | None:
    """BFS over the forward dependency graph from start_file to end_file.

    graph must be a dict with a "forward" key mapping each file to its imports,
    as produced by extract_dependencies.

    Returns the shortest path as a list of relative_paths (inclusive of both
    endpoints), or None if no path exists.
    """
    forward = graph.get("forward", {})

    if start_file not in forward:
        return None

    queue: deque[list[str]] = deque([[start_file]])
    visited: set[str] = {start_file}

    while queue:
        path = queue.popleft()
        node = path[-1]

        for neighbour in forward.get(node, []):
            if neighbour == end_file:
                return path + [end_file]
            if neighbour not in visited:
                visited.add(neighbour)
                queue.append(path + [neighbour])

    return None
