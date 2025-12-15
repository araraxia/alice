#!/usr/bin/env python
"""
Generate an inferred list of external (pip) dependencies for a repo lacking
declared requirement files.

Outputs:
  raw_import_roots.txt
  unresolved_imports.txt
  inferred_requirements_unpinned.txt
  dependency_report.json

Works via static AST parsing (no code execution).
"""

from __future__ import annotations
import os
import ast
import sys
import json
import re
import subprocess
from pathlib import Path
from typing import Set, Dict

REPO_ROOT = Path(__file__).resolve().parent.parent

IGNORE_DIR_NAMES = {
    ".git",
    ".hg",
    ".svn",
    ".idea",
    ".vscode",
    "__pycache__",
    "build",
    "dist",
    ".mypy_cache",
    ".pytest_cache",
    ".venv",
    "venv",
    ".dep-scan-venv",
}

PYTHON_FILE_PATTERN = re.compile(r".*\.py$", re.IGNORECASE)

# Basic alias mapping for mismatched import root vs PyPI distribution name
ALIAS_MAP = {
    "PIL": "Pillow",
    "cv2": "opencv-python",
    "Crypto": "pycryptodome",
    "yaml": "PyYAML",
    "dateutil": "python-dateutil",
    "sklearn": "scikit-learn",
    "bs4": "beautifulsoup4",
    "OpenSSL": "pyOpenSSL",
    "dotenv": "python-dotenv",
    "grpc": "grpcio",
    "pil": "Pillow",
    "lxml": "lxml",
    "win32api": "pywin32",
    "win32con": "pywin32",
    "psycopg2": "psycopg2-binary",
    "PILLOW": "Pillow",
    "redis": "redis",
    "CryptoDomex": "pycryptodomex",
    "orjson": "orjson",
    "ujson": "ujson",
    "tomli": "tomli",  # needed Py<3.11
    "zoneinfo": "backports.zoneinfo",  # only for <3.9 real use
}


# Heuristics: treat these as internal/local if a matching top-level dir/file exists
def detect_local_roots(repo_root: Path) -> Set[str]:
    local = set()
    for item in repo_root.iterdir():
        if item.is_dir():
            if (item / "__init__.py").exists():
                local.add(item.name)
        elif item.is_file() and item.suffix == ".py":
            local.add(item.stem)
    return local


def iter_python_files(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        # mutate dirnames in-place to prune walk
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIR_NAMES]
        for fname in filenames:
            if PYTHON_FILE_PATTERN.match(fname):
                yield Path(dirpath) / fname


def extract_import_roots(path: Path) -> Set[str]:
    roots = set()
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
        node = ast.parse(text, filename=str(path))
    except SyntaxError:
        return roots
    except Exception:
        return roots

    for n in ast.walk(node):
        if isinstance(n, ast.Import):
            for alias in n.names:
                root = alias.name.split(".")[0]
                roots.add(root)
        elif isinstance(n, ast.ImportFrom):
            if n.module is None:
                continue
            if n.level and n.level > 0:
                # relative import - skip
                continue
            root = n.module.split(".")[0]
            roots.add(root)
    return roots


def get_stdlib_modules() -> Set[str]:
    stdlib = set()
    try:
        # Python 3.10+
        stdlib |= set(sys.stdlib_module_names)  # type: ignore[attr-defined]
    except Exception:
        pass

    # Fallback: use stdlib-list if installed
    try:
        from stdlib_list import stdlib_list  # type: ignore

        ver = f"{sys.version_info.major}.{sys.version_info.minor}"
        stdlib |= set(stdlib_list(ver))
    except Exception:
        pass

    # Add builtins
    stdlib |= set(sys.builtin_module_names)
    # Common implicit
    stdlib |= {
        "typing",
        "dataclasses",
        "pathlib",
        "collections",
        "itertools",
        "functools",
        "logging",
    }
    return stdlib


def normalize_candidate(name: str) -> str:
    # Basic normalization: dashes vs underscores
    return name.replace("_", "-")


def probe_distribution_exists(package: str) -> bool:
    """
    Try a lightweight 'pip index versions' (requires pip >= 20.3 and network).
    If that fails (offline), we just return True optimistically.
    """
    try:
        r = subprocess.run(
            [sys.executable, "-m", "pip", "index", "versions", package],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5,
        )
        if r.returncode == 0 and "Available versions" in r.stdout:
            return True
        # Some private indexes or no index command support
        return False
    except Exception:
        return True  # Don't over-prune when offline


def infer_distributions(import_roots: Set[str], stdlib: Set[str], local: Set[str]):
    inferred = {}
    unresolved = []
    details = {}

    for root in sorted(import_roots):
        if root in stdlib:
            details[root] = {"classification": "stdlib"}
            continue
        if root in local:
            details[root] = {"classification": "local"}
            continue

        original = root
        # Apply alias map
        if root in ALIAS_MAP:
            dist = ALIAS_MAP[root]
            details[root] = {"classification": "alias", "dist": dist}
            inferred[dist] = inferred.get(dist, set()) | {original}
            continue

        # Heuristic naming
        candidate = normalize_candidate(root)

        if probe_distribution_exists(candidate):
            details[root] = {"classification": "direct", "dist": candidate}
            inferred[candidate] = inferred.get(candidate, set()) | {original}
        else:
            unresolved.append(root)
            details[root] = {"classification": "unresolved"}

    return inferred, unresolved, details


def main():
    all_import_roots: Set[str] = set()
    for pyfile in iter_python_files(REPO_ROOT):
        all_import_roots |= extract_import_roots(pyfile)

    stdlib = get_stdlib_modules()
    local = detect_local_roots(REPO_ROOT)

    inferred_map, unresolved, detail_map = infer_distributions(
        all_import_roots, stdlib, local
    )

    # Write raw import roots
    Path("raw_import_roots.txt").write_text(
        "\n".join(sorted(all_import_roots)) + "\n", encoding="utf-8"
    )

    # Write unresolved
    if unresolved:
        Path("unresolved_imports.txt").write_text(
            "# These imports could not be confidently mapped to a PyPI distribution.\n"
            "# They may be: local modules, optional extras, plugins, or need alias additions.\n"
            + "\n".join(unresolved)
            + "\n",
            encoding="utf-8",
        )

    # Write inferred unpinned requirements
    inferred_list = sorted(inferred_map.keys(), key=str.lower)
    Path("inferred_requirements_unpinned.txt").write_text(
        "# Inferred external dependencies (UNPINNED). Review manually before pinning.\n"
        + "\n".join(inferred_list)
        + "\n",
        encoding="utf-8",
    )

    # Detailed JSON report
    report = {
        "summary": {
            "total_import_roots": len(all_import_roots),
            "stdlib_count": sum(
                1 for v in detail_map.values() if v["classification"] == "stdlib"
            ),
            "local_count": sum(
                1 for v in detail_map.values() if v["classification"] == "local"
            ),
            "inferred_count": len(inferred_list),
            "unresolved_count": len(unresolved),
        },
        "inferred_map": {
            dist: sorted(list(mods)) for dist, mods in inferred_map.items()
        },
        "unresolved_imports": unresolved,
        "details": detail_map,
    }
    Path("dependency_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )

    print("Done.")
    print("Files generated:")
    print("  raw_import_roots.txt")
    if unresolved:
        print("  unresolved_imports.txt")
    print("  inferred_requirements_unpinned.txt")
    print("  dependency_report.json")
    print(
        "\nNext: review inferred_requirements_unpinned.txt, merge with other tool outputs (pipreqs/pigar), then compile."
    )


if __name__ == "__main__":
    main()
