import json
import os
from collections import deque


def _fuzzy_match(import_string: str, all_relative_paths: list[str]) -> str | None:
    normalised = import_string.replace("\\", "/").strip("/")

    # 1. Exact
    if normalised in all_relative_paths:
        return normalised

    # 2. Suffix match (e.g. "auth/utils" matches "src/auth/utils.py")
    for path in all_relative_paths:
        path_norm = path.replace("\\", "/")
        if path_norm.endswith(normalised) or path_norm.endswith(normalised + ".py"):
            return path

    # 3. Dotted-module → path conversion ("devmind.store" → "devmind/store")
    as_path = normalised.replace(".", "/")
    for path in all_relative_paths:
        path_norm = path.replace("\\", "/")
        if path_norm.endswith(as_path) or path_norm.endswith(as_path + ".py"):
            return path

    # 4. Stem match — last component of dotted-or-slash path vs filename stem
    #    "devmind.store" → "devmind/store" → "store" matches "store.py"
    import_stem = as_path.split("/")[-1]
    for path in all_relative_paths:
        path_stem = os.path.splitext(os.path.basename(path))[0]
        if path_stem == import_stem:
            return path

    return None


def extract_dependencies(index_json_path: str) -> dict:
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
