import os
import ast
from collections import defaultdict
from dataclasses import dataclass, field

@dataclass
class ImpactResult:
    changed_files: list[str]
    directly_impacted: list[str]    # files that import the changed files
    suggested_test_files: list[str] # test files covering changed modules
    import_graph: dict              # full graph for debugging/display


def build_import_graph(repo_path: str) -> dict[str, list[str]]:
    """
    Walks a repo and builds a map of:
    { "app/auth.py": ["app/middleware.py", "app/routes/user.py"] }
    meaning: auth.py is imported by middleware.py and routes/user.py
    
    We use Python's built-in `ast` module here instead of tree-sitter
    for simplicity on Python repos. tree-sitter is better for multi-language
    repos — we'll note where to swap it in.
    """
    # graph[file] = list of files that import it
    imported_by = defaultdict(list)

    for root, dirs, files in os.walk(repo_path):
        # Skip hidden folders and common non-source dirs
        dirs[:] = [d for d in dirs if not d.startswith(".") 
                   and d not in ("__pycache__", "node_modules", ".git", "venv")]
        
        for fname in files:
            if not fname.endswith(".py"):
                continue
            
            filepath = os.path.join(root, fname)
            rel_path = os.path.relpath(filepath, repo_path)
            
            try:
                source = open(filepath).read()
                tree = ast.parse(source)
            except Exception:
                continue  # skip files that fail to parse

            for node in ast.walk(tree):
                # Handle: import app.auth
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imported_module = _module_to_path(alias.name, repo_path)
                        if imported_module:
                            imported_by[imported_module].append(rel_path)

                # Handle: from app.auth import get_user
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported_module = _module_to_path(node.module, repo_path)
                    if imported_module:
                        imported_by[imported_module].append(rel_path)

    return dict(imported_by)


def _module_to_path(module_name: str, repo_path: str) -> str | None:
    """
    Converts a module name like 'app.auth' to a file path like 'app/auth.py'.
    Returns None if the file doesn't exist in the repo (e.g. stdlib imports).
    """
    relative = module_name.replace(".", "/") + ".py"
    full_path = os.path.join(repo_path, relative)
    return relative if os.path.exists(full_path) else None


def find_test_files(changed_files: list[str], repo_path: str) -> list[str]:
    """
    For each changed file, look for test files that likely cover it.
    Matches by convention: auth.py → test_auth.py or auth_test.py
    """
    test_files = []
    
    for changed in changed_files:
        module_name = os.path.basename(changed).replace(".py", "")
        
        for root, dirs, files in os.walk(repo_path):
            dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git", "venv")]
            for fname in files:
                if (fname == f"test_{module_name}.py" or 
                    fname == f"{module_name}_test.py"):
                    rel = os.path.relpath(os.path.join(root, fname), repo_path)
                    test_files.append(rel)
    
    return test_files


def analyze_impact(changed_files: list[str], repo_path: str) -> ImpactResult:
    """
    Main entry point. Given a list of changed files and the repo path,
    returns what's impacted.
    """
    graph = build_import_graph(repo_path)
    
    impacted = []
    for changed in changed_files:
        # Normalize path separators
        normalized = changed.replace("\\", "/")
        if normalized in graph:
            impacted.extend(graph[normalized])
    
    # Deduplicate, exclude the changed files themselves
    impacted = list(set(impacted) - set(changed_files))
    
    test_files = find_test_files(changed_files, repo_path)

    return ImpactResult(
        changed_files=changed_files,
        directly_impacted=impacted,
        suggested_test_files=test_files,
        import_graph=graph,
    )