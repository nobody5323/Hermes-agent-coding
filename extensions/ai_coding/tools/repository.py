"""Repository scanning, safe file reads, and keyword search."""

from __future__ import annotations

import re
from pathlib import Path

from ..config import get_config
from ..schemas import RepositoryFile, RepositorySummary


LANGUAGE_BY_EXTENSION = {
    ".py": "python",
    ".md": "markdown",
    ".json": "json",
    ".toml": "toml",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".js": "javascript",
    ".ts": "typescript",
    ".txt": "text",
}

DEPENDENCY_FILES = {
    "pyproject.toml",
    "requirements.txt",
    "poetry.lock",
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "Makefile",
}


def _safe_resolve(repo_path: str | Path, relative_path: str | Path = ".") -> Path:
    root = Path(repo_path).resolve()
    target = (root / relative_path).resolve()
    if target != root and root not in target.parents:
        raise ValueError(f"path escapes repository root: {relative_path}")
    return target


def _is_ignored(path: Path, root: Path) -> bool:
    ignored = get_config().ignored_dirs
    rel_parts = path.relative_to(root).parts
    return any(part in ignored for part in rel_parts)


def _is_probably_binary(path: Path) -> bool:
    try:
        chunk = path.read_bytes()[:2048]
    except OSError:
        return True
    return b"\x00" in chunk


def _classify_file(path: Path) -> str:
    name = path.name.lower()
    suffix = path.suffix.lower()
    parts = {part.lower() for part in path.parts}
    if "test" in name or "tests" in parts:
        return "test"
    if suffix in {".md", ".txt"}:
        return "doc"
    if name in {item.lower() for item in DEPENDENCY_FILES} or suffix in {".toml", ".json", ".yaml", ".yml"}:
        return "config"
    if suffix in {".py", ".js", ".ts"}:
        return "source"
    return "other"


def _line_count(path: Path) -> int:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            return sum(1 for _ in handle)
    except OSError:
        return 0


def detect_project_commands(repo_path: str | Path) -> list[str]:
    root = Path(repo_path).resolve()
    commands: list[str] = []
    if (root / "pytest.ini").exists() or (root / "pyproject.toml").exists() or (root / "tests").exists():
        commands.append("python -m pytest")
    if (root / "package.json").exists():
        commands.append("npm test")
    if (root / "Makefile").exists():
        commands.append("make test")
    return commands


def scan_repository(repo_path: str | Path) -> RepositorySummary:
    root = Path(repo_path).resolve()
    if not root.exists() or not root.is_dir():
        raise ValueError(f"repository path does not exist or is not a directory: {repo_path}")

    config = get_config()
    files: list[RepositoryFile] = []
    languages: dict[str, int] = {}
    entrypoints: list[str] = []
    dependency_files: list[str] = []
    has_readme = False
    has_tests = False

    for path in sorted(root.rglob("*")):
        if not path.is_file() or _is_ignored(path, root):
            continue
        rel = path.relative_to(root).as_posix()
        if path.stat().st_size > config.max_file_bytes or _is_probably_binary(path):
            continue
        suffix = path.suffix.lower()
        if suffix not in config.supported_extensions and path.name not in DEPENDENCY_FILES:
            continue

        language = LANGUAGE_BY_EXTENSION.get(suffix, "text")
        file_type = _classify_file(path.relative_to(root))
        line_count = _line_count(path)
        files.append(
            RepositoryFile(
                path=rel,
                file_type=file_type,
                language=language,
                size_bytes=path.stat().st_size,
                line_count=line_count,
            )
        )
        languages[language] = languages.get(language, 0) + 1
        if path.name in DEPENDENCY_FILES:
            dependency_files.append(rel)
        if path.name.lower().startswith("readme"):
            has_readme = True
        if "tests" in path.relative_to(root).parts or path.name.startswith("test_"):
            has_tests = True
        if path.name in {"main.py", "app.py", "__main__.py"}:
            entrypoints.append(rel)

    return RepositorySummary(
        repo_path=str(root),
        total_files=len(files),
        files=files,
        languages=languages,
        entrypoints=entrypoints,
        dependency_files=dependency_files,
        has_readme=has_readme,
        has_tests=has_tests,
        test_commands=detect_project_commands(root),
    )


def read_file_slice(
    repo_path: str | Path,
    relative_path: str | Path,
    start_line: int = 1,
    end_line: int | None = None,
    max_lines: int | None = None,
) -> str:
    config = get_config()
    max_lines = max_lines or config.max_read_lines
    target = _safe_resolve(repo_path, relative_path)
    if not target.is_file():
        raise ValueError(f"file does not exist: {relative_path}")
    if start_line < 1:
        raise ValueError("start_line must be >= 1")
    if end_line is None:
        end_line = start_line + max_lines - 1
    if end_line < start_line:
        raise ValueError("end_line must be >= start_line")
    end_line = min(end_line, start_line + max_lines - 1)

    selected: list[str] = []
    with target.open("r", encoding="utf-8", errors="replace") as handle:
        for number, line in enumerate(handle, start=1):
            if number < start_line:
                continue
            if number > end_line:
                break
            selected.append(line.rstrip("\n"))
    return "\n".join(selected)


def search_code(
    repo_path: str | Path,
    query: str,
    *,
    regex: bool = False,
    context_lines: int = 1,
    max_results: int = 50,
) -> list[dict[str, object]]:
    root = Path(repo_path).resolve()
    summary = scan_repository(root)
    pattern = re.compile(query, re.IGNORECASE) if regex else None
    results: list[dict[str, object]] = []

    for item in summary.files:
        path = root / item.path
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for index, line in enumerate(lines):
            matched = bool(pattern.search(line)) if pattern else query.lower() in line.lower()
            if not matched:
                continue
            start = max(0, index - context_lines)
            end = min(len(lines), index + context_lines + 1)
            results.append(
                {
                    "path": item.path,
                    "line": index + 1,
                    "match": line,
                    "context": "\n".join(lines[start:end]),
                }
            )
            if len(results) >= max_results:
                return results
    return results
