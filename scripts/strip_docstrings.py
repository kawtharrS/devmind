#!/usr/bin/env python3
import ast
import sys
from pathlib import Path


def strip(source: str) -> str:
    tree = ast.parse(source)
    lines = source.splitlines(keepends=True)
    to_remove: set[int] = set()
    sole_body_lines: set[int] = set()  # first line of docstrings that are the only body stmt

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
            continue
        if not node.body:
            continue
        first = node.body[0]
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
            for i in range(first.lineno - 1, first.end_lineno):
                to_remove.add(i)
            if len(node.body) == 1:
                sole_body_lines.add(first.lineno - 1)

    result = []
    for i, line in enumerate(lines):
        if i in to_remove:
            if i in sole_body_lines:
                indent = " " * (len(line) - len(line.lstrip()))
                result.append(f"{indent}pass\n")
        else:
            result.append(line)
    return "".join(result)


if __name__ == "__main__":
    for path_str in sys.argv[1:]:
        path = Path(path_str)
        if path.suffix != ".py":
            continue
        source = path.read_text(encoding="utf-8")
        cleaned = strip(source)
        if cleaned != source:
            path.write_text(cleaned, encoding="utf-8")
            print(f"stripped: {path}")
