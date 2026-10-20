"""Summaries, the longitudinal view, and the plain-text table."""

from __future__ import annotations

from decimal import Decimal

from uccskill.crawl import FileRecord
from uccskill.diff import diff_files
from uccskill.reuse import classify, esloc_total, format_esloc

LANGUAGE_ORDER = ("python", "javascript", "typescript", "sql", "html", "css")


def logical_total(files: list[FileRecord]) -> int:
    return sum(part.logical for record in files for part in record.parts)


def physical_total(files: list[FileRecord]) -> int:
    return sum(part.physical for record in files for part in record.parts)


def by_language(files: list[FileRecord]) -> dict[str, dict[str, int]]:
    totals: dict[str, dict[str, int]] = {}
    for record in files:
        languages_here = set()
        for part in record.parts:
            bucket = totals.setdefault(
                part.language,
                {"sources": 0, "lines": 0, "blank": 0, "comment": 0, "physical": 0, "logical": 0},
            )
            bucket["lines"] += part.lines
            bucket["blank"] += part.blank
            bucket["comment"] += part.comment
            bucket["physical"] += part.physical
            bucket["logical"] += part.logical
            languages_here.add(part.language)
        for language in languages_here:
            totals[language]["sources"] += 1
    return totals


def language_names(present: set[str]) -> list[str]:
    ordered = [name for name in LANGUAGE_ORDER if name in present]
    ordered.extend(sorted(present - set(ordered)))
    return ordered


def build_columns(snapshots: list[dict]) -> list[dict]:
    columns = []
    previous = None
    for snapshot in snapshots:
        files = snapshot["files"]
        languages = by_language(files)
        column = {
            "id": snapshot["id"],
            "created": snapshot.get("created") or "",
            "label": snapshot.get("label") or "",
            "git_ref": snapshot.get("git_ref"),
            "root": snapshot.get("root") or "",
            "files": len(files),
            "physical": physical_total(files),
            "logical": logical_total(files),
            "esloc": esloc_total(files),
            "by_language": languages,
            "delta_physical": None,
            "delta_logical": None,
            "delta_esloc": None,
            "diff": None,
        }
        if previous is not None:
            column["delta_physical"] = column["physical"] - previous["physical"]
            column["delta_logical"] = column["logical"] - previous["logical"]
            column["delta_esloc"] = column["esloc"] - previous["esloc"]
            column["diff"] = diff_files(previous_files, files)
            for name, bucket in languages.items():
                earlier = previous["by_language"].get(name, {}).get("logical", 0)
                bucket["delta_logical"] = bucket["logical"] - earlier
        else:
            for bucket in languages.values():
                bucket["delta_logical"] = None
        columns.append(column)
        previous = column
        previous_files = files
    return columns


def build_tree(files: list[FileRecord]) -> dict:
    reuse = classify(files)
    root = {
        "name": "",
        "physical": 0,
        "logical": 0,
        "esloc": Decimal(0),
        "dirs": {},
        "files": [],
    }
    for record in files:
        physical = sum(part.physical for part in record.parts)
        logical = sum(part.logical for part in record.parts)
        item = reuse[record.path]
        node = root
        pieces = [piece for piece in record.path.split("/") if piece]
        for piece in pieces[:-1]:
            node = node["dirs"].setdefault(
                piece,
                {
                    "name": piece,
                    "physical": 0,
                    "logical": 0,
                    "esloc": Decimal(0),
                    "dirs": {},
                    "files": [],
                },
            )
        node["files"].append(
            {
                "name": pieces[-1] if pieces else record.path,
                "path": record.path,
                "physical": physical,
                "logical": logical,
                "esloc": item.esloc,
                "role": item.role,
                "set_name": item.set_name,
                "exemplar": item.exemplar,
                "header": record.header,
                "parts": [
                    {
                        "language": part.language,
                        "physical": part.physical,
                        "logical": part.logical,
                        "blank": part.blank,
                        "comment": part.comment,
                        "lines": part.lines,
                        "notes": list(part.notes),
                    }
                    for part in record.parts
                ],
            }
        )
    _sum_tree(root)
    return root


def notes_for(files: list[FileRecord]) -> list[str]:
    found = []
    for record in files:
        for part in record.parts:
            for note in part.notes:
                found.append(f"{record.path} ({part.language}): {note}")
    return found


def format_table(files: list[FileRecord]) -> str:
    languages = by_language(files)
    rows = []
    header = f"{'Language':<14} {'Sources':>7} {'Physical':>10} {'Logical':>10} {'Blank':>8} {'Comment':>8}"
    rows.append(header)
    rows.append("-" * len(header))
    physical = logical = blank = comment = 0
    for name in language_names(set(languages)):
        bucket = languages[name]
        rows.append(
            f"{name:<14} {bucket['sources']:>7} {bucket['physical']:>10} "
            f"{bucket['logical']:>10} {bucket['blank']:>8} {bucket['comment']:>8}"
        )
        physical += bucket["physical"]
        logical += bucket["logical"]
        blank += bucket["blank"]
        comment += bucket["comment"]
    rows.append("-" * len(header))
    rows.append(
        f"{'TOTAL':<14} {len(files):>7} {physical:>10} {logical:>10} {blank:>8} {comment:>8}"
    )
    rows.append(f"{'ESLOC':<14} {format_esloc(esloc_total(files))}")
    return "\n".join(rows)


def csv_rows(files: list[FileRecord]) -> list[list[str]]:
    reuse = classify(files)
    rows = [["path", "language", "lines", "blank", "comment", "physical", "logical", "esloc", "reuse"]]
    for record in files:
        item = reuse[record.path]
        for part in record.parts:
            rows.append(
                [
                    record.path,
                    part.language,
                    str(part.lines),
                    str(part.blank),
                    str(part.comment),
                    str(part.physical),
                    str(part.logical),
                    format_esloc(item.esloc),
                    item.role if item.role != "unique" else "",
                ]
            )
    return rows


def _sum_tree(node: dict) -> tuple[int, int, Decimal]:
    physical = sum(item["physical"] for item in node["files"])
    logical = sum(item["logical"] for item in node["files"])
    esloc = sum((item["esloc"] for item in node["files"]), Decimal(0))
    for child in node["dirs"].values():
        child_physical, child_logical, child_esloc = _sum_tree(child)
        physical += child_physical
        logical += child_logical
        esloc += child_esloc
    node["physical"] = physical
    node["logical"] = logical
    node["esloc"] = esloc
    return physical, logical, esloc


