"""Logical-unit diff between two snapshots.

Equal units are unmodified. A replace block counts min(old, new) as modified
and the leftover side as deleted or new. File renames are a deletion plus an
addition; paths are matched as written.
"""

from __future__ import annotations

import difflib

from uccskill.crawl import FileRecord

_KEYS = ("new", "modified", "deleted", "unmodified")


def empty_diff() -> dict[str, int]:
    return {key: 0 for key in _KEYS}


def diff_units(old: list[str], new: list[str]) -> dict[str, int]:
    result = empty_diff()
    matcher = difflib.SequenceMatcher(a=old, b=new, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            result["unmodified"] += i2 - i1
        elif tag == "insert":
            result["new"] += j2 - j1
        elif tag == "delete":
            result["deleted"] += i2 - i1
        elif tag == "replace":
            removed = i2 - i1
            added = j2 - j1
            shared = min(removed, added)
            result["modified"] += shared
            result["deleted"] += removed - shared
            result["new"] += added - shared
    return result


def diff_files(old: list[FileRecord], new: list[FileRecord]) -> dict:
    old_map = _index(old)
    new_map = _index(new)
    total = empty_diff()
    by_language: dict[str, dict[str, int]] = {}
    for key in sorted(set(old_map) | set(new_map)):
        language = key[1]
        piece = diff_units(old_map.get(key, []), new_map.get(key, []))
        bucket = by_language.setdefault(language, empty_diff())
        for name in _KEYS:
            total[name] += piece[name]
            bucket[name] += piece[name]
    return {"total": total, "by_language": by_language}


def _index(records: list[FileRecord]) -> dict[tuple[str, str], list[str]]:
    indexed: dict[tuple[str, str], list[str]] = {}
    for record in records:
        for part in record.parts:
            indexed[(record.path, part.language)] = list(part.units)
    return indexed
