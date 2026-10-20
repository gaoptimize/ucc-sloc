"""Straight reuse and effectively new source lines (ESLOC).

Identical normalized text is one reuse set. The exemplar is the first path in
lexicographic order and keeps its full logical size. Each other copy contributes
2% of its own logical size. That 2% is the non-coding cost of the additional
unit test and of the final integration that forced the copy.

A file with no content id, including a file that could not be read, is its own
size. There is no feature field in the counted source, so callers sum ESLOC on
the directory module that contains the file.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from decimal import Decimal

STRAIGHT_REUSE_RATE = Decimal("0.02")


@dataclass(frozen=True)
class Reuse:
    esloc: Decimal
    role: str
    set_name: str
    exemplar: str


def content_id(text: str) -> str:
    normalized = "\n".join(text.splitlines())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def classify(files: list) -> dict[str, Reuse]:
    groups: dict[str, list] = {}
    for record in files:
        if record.content_id:
            groups.setdefault(record.content_id, []).append(record)
    info: dict[str, Reuse] = {}
    for record in files:
        logical = sum(part.logical for part in record.parts)
        members = groups.get(record.content_id, [record]) if record.content_id else [record]
        if len(members) < 2:
            info[record.path] = Reuse(Decimal(logical), "unique", "", record.path)
            continue
        exemplar = min(members, key=lambda item: item.path)
        set_name = f"{exemplar.path}#{record.content_id[:12]}"
        if record.path == exemplar.path:
            info[record.path] = Reuse(Decimal(logical), "exemplar", set_name, exemplar.path)
        else:
            esloc = (Decimal(logical) * STRAIGHT_REUSE_RATE).quantize(Decimal("0.01"))
            info[record.path] = Reuse(esloc, "copy", set_name, exemplar.path)
    return info


def esloc_total(files: list) -> Decimal:
    info = classify(files)
    return sum((item.esloc for item in info.values()), Decimal(0))


def straight_reuse_sets(files: list) -> list[dict]:
    info = classify(files)
    grouped: dict[str, dict] = {}
    for record in files:
        item = info[record.path]
        if item.role == "unique":
            continue
        bucket = grouped.setdefault(
            item.set_name,
            {
                "name": item.set_name,
                "exemplar": item.exemplar,
                "copies": 0,
                "copy_esloc": Decimal(0),
            },
        )
        if item.role == "copy":
            bucket["copies"] += 1
            bucket["copy_esloc"] += item.esloc
    return [grouped[name] for name in sorted(grouped)]


def format_esloc(value: Decimal) -> str:
    quantized = Decimal(value).quantize(Decimal("0.01"))
    if quantized == quantized.to_integral_value():
        return str(int(quantized))
    return f"{quantized:.2f}"
