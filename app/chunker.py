import os
import ast
from dataclasses import dataclass

@dataclass
class CodeChunk:
    filepath: str        # e.g. "app/auth.py"
    chunk_type: str      # "function" or "class"
    name: str            # e.g. "generate_jwt"
    source: str          # the actual source code of that function/class
    start_line: int
    end_line: int


def chunk_repo(repo_path: str) -> list[CodeChunk]:
    """
    Walks every .py file in the repo and returns one CodeChunk
    per function or class definition found.
    
    Why ast.get_source_segment? It extracts the exact source text
    of a node from the original file — much cleaner than slicing
    lines manually.
    """
    chunks = []

    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if not d.startswith(".")
                   and d not in ("__pycache__", "node_modules", ".git", "venv")]

        for fname in files:
            if not fname.endswith(".py"):
                continue

            filepath = os.path.join(root, fname)
            rel_path = os.path.relpath(filepath, repo_path)

            try:
                source = open(filepath, encoding="utf-8").read()
                tree = ast.parse(source)
            except Exception:
                continue

            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    chunk_source = ast.get_source_segment(source, node)
                    if not chunk_source:
                        continue

                    chunk_type = "class" if isinstance(node, ast.ClassDef) else "function"

                    chunks.append(CodeChunk(
                        filepath=rel_path,
                        chunk_type=chunk_type,
                        name=node.name,
                        source=chunk_source,
                        start_line=node.lineno,
                        end_line=node.end_lineno or node.lineno,
                    ))

    return chunks