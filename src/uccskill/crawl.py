"""Walk a tree and count the languages this tool knows."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from uccskill.header import extract_header
from uccskill.languages import count_source, language_for
from uccskill.model import Part, make_part
from uccskill.reuse import content_id

# Directory names, matched case-insensitively. The requirements name the
# first entries; the rest are the same kind of generated or cached tree.
DEFAULT_EXCLUDES = frozenset(
    {
        "venv",
        ".venv",
        "env",
        "node_modules",
        "__pycache__",
        ".git",
        "dist",
        "build",
        ".tox",
        ".mypy_cache",
        ".ucc-history",
        ".hg",
        ".svn",
        "site-packages",
        "htmlcov",
        ".pytest_cache",
        ".ruff_cache",
        ".eggs",
    }
)


@dataclass
class FileRecord:
    path: str
    parts: list[Part]
    content_id: str = ""
    header: str = ""

    def to_json(self) -> dict:
        return {
            "path": self.path,
            "content_id": self.content_id,
            "header": self.header,
            "parts": [part.to_json() for part in self.parts],
        }

    @classmethod
    def from_json(cls, data: dict) -> "FileRecord":
        return cls(
            data["path"],
            [Part.from_json(part) for part in data["parts"]],
            data.get("content_id") or "",
            data.get("header") or "",
        )


def load_excludes(root: Path, extra: list[str] | None = None) -> tuple[set[str], list[str]]:
    names = {item.lower() for item in DEFAULT_EXCLUDES}
    prefixes: list[str] = []
    for item in extra or []:
        _add_exclude(item, names, prefixes)
    ignore = root / ".uccignore"
    if ignore.is_file():
        for line in ignore.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            _add_exclude(stripped, names, prefixes)
    return names, prefixes


def _add_exclude(item: str, names: set[str], prefixes: list[str]) -> None:
    item = item.strip().strip("/")
    if not item:
        return
    if "/" in item or "\\" in item:
        prefixes.append(item.replace("\\", "/").strip("/"))
    else:
        names.add(item.lower())


def crawl(root: Path, extra_excludes: list[str] | None = None, progress=None) -> list[FileRecord]:
    root = root.resolve()
    names, prefixes = load_excludes(root if root.is_dir() else root.parent, extra_excludes)
    if root.is_file():
        return _count_one_file(root, names, prefixes, progress)
    pending: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        if progress is not None:
            progress.scanning(str(Path(dirpath)))
        dirnames[:] = [
            name
            for name in dirnames
            if not _excluded(root, Path(dirpath) / name, names, prefixes)
        ]
        for name in filenames:
            path = Path(dirpath) / name
            if language_for(path.suffix) is None:
                continue
            pending.append(path)
    return _count_pending(pending, root, names, prefixes, progress)


def crawl_git(root: Path, ref: str, extra_excludes: list[str] | None = None, progress=None) -> list[FileRecord]:
    root = root.resolve()
    names, prefixes = load_excludes(root, extra_excludes)
    if progress is not None:
        progress.scanning(ref)
    verified = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--verify", ref],
        capture_output=True,
        text=True,
    )
    if verified.returncode != 0:
        detail = (verified.stderr or verified.stdout or "git rev-parse failed").strip()
        raise RuntimeError(detail)
    listed = subprocess.run(
        ["git", "-C", str(root), "ls-tree", "-r", "--name-only", ref],
        capture_output=True,
        text=True,
    )
    if listed.returncode != 0:
        detail = (listed.stderr or "git ls-tree failed").strip()
        raise RuntimeError(detail)
    pending = []
    for rel in listed.stdout.splitlines():
        rel_posix = rel.replace("\\", "/")
        if _rel_excluded(rel_posix, names, prefixes):
            continue
        if language_for(Path(rel_posix).suffix) is None:
            continue
        pending.append(rel_posix)
    if progress is not None:
        progress.found(len(pending))
    records: list[FileRecord] = []
    for index, rel_posix in enumerate(pending):
        if progress is not None:
            progress.tick(index, rel_posix)
        shown = subprocess.run(
            ["git", "-C", str(root), "show", f"{ref}:{rel_posix}"],
            capture_output=True,
        )
        if shown.returncode != 0:
            continue
        record = count_bytes(rel_posix, shown.stdout)
        if record:
            records.append(record)
    if progress is not None:
        progress.tick(len(pending), "")
    records.sort(key=lambda item: item.path)
    return records


def _count_one_file(root: Path, names: set[str], prefixes: list[str], progress) -> list[FileRecord]:
    total = 0 if language_for(root.suffix) is None else 1
    if progress is not None:
        progress.found(total)
        if total:
            progress.tick(0, root.name)
    record = count_path(root, root.parent, names, prefixes)
    if progress is not None and total:
        progress.tick(1, root.name)
    return [record] if record else []


def _count_pending(pending: list[Path], root: Path, names: set[str], prefixes: list[str], progress) -> list[FileRecord]:
    if progress is not None:
        progress.found(len(pending))
    records: list[FileRecord] = []
    for index, path in enumerate(pending):
        rel = _display_rel(path, root)
        if progress is not None:
            progress.tick(index, rel)
        record = count_path(path, root, names, prefixes)
        if record:
            records.append(record)
    if progress is not None:
        progress.tick(len(pending), "")
    records.sort(key=lambda item: item.path)
    return records


def _display_rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.name


def count_path(path: Path, root: Path, names: set[str], prefixes: list[str]) -> FileRecord | None:
    try:
        rel = path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        rel = path.name
    if _rel_excluded(rel, names, prefixes):
        return None
    try:
        data = path.read_bytes()
    except OSError as exc:
        language = language_for(path.suffix) or "unknown"
        return FileRecord(rel, [make_part(language, 0, 0, 0, 0, [], [f"read_error: {exc}"])])
    return count_bytes(rel, data)


def count_bytes(rel: str, data: bytes) -> FileRecord | None:
    language = language_for(Path(rel).suffix)
    if language is None:
        return None
    if b"\0" in data[:8192]:
        return None
    text = data.decode("utf-8-sig", errors="replace")
    try:
        parts = count_source(language, text)
    except Exception as exc:
        parts = [make_part(language, 0, 0, 0, 0, [], [f"count_error: {exc}"])]
    return FileRecord(rel, parts, content_id(text), extract_header(language, text))


def _excluded(root: Path, path: Path, names: set[str], prefixes: list[str]) -> bool:
    if path.name.lower() in names or path.name.lower().endswith(".egg-info"):
        return True
    try:
        rel = path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        rel = path.name
    return _rel_excluded(rel, names, prefixes)


def _rel_excluded(rel: str, names: set[str], prefixes: list[str]) -> bool:
    parts = [part for part in rel.split("/") if part]
    if any(part.lower() in names or part.lower().endswith(".egg-info") for part in parts):
        return True
    return any(rel == prefix or rel.startswith(prefix + "/") for prefix in prefixes)
