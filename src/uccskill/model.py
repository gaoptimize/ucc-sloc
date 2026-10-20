"""Shared count records.

`logical` is always the number of units. Callers must not invent a second total.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Part:
    language: str
    lines: int
    blank: int
    comment: int
    physical: int
    units: list[str]
    notes: list[str] = field(default_factory=list)

    @property
    def logical(self) -> int:
        return len(self.units)

    def to_json(self) -> dict:
        return {
            "language": self.language,
            "lines": self.lines,
            "blank": self.blank,
            "comment": self.comment,
            "physical": self.physical,
            "logical": self.logical,
            "units": list(self.units),
            "notes": list(self.notes),
        }

    @classmethod
    def from_json(cls, data: dict) -> "Part":
        units = list(data.get("units") or [])
        return cls(
            language=data["language"],
            lines=int(data["lines"]),
            blank=int(data["blank"]),
            comment=int(data["comment"]),
            physical=int(data["physical"]),
            units=units,
            notes=list(data.get("notes") or []),
        )


def make_part(
    language: str,
    lines: int,
    blank: int,
    comment: int,
    physical: int,
    units: list[str],
    notes: list[str] | None = None,
) -> Part:
    notes = list(notes or [])
    if blank + comment + physical != lines:
        notes.append(
            f"line partition {blank}+{comment}+{physical} != {lines}"
        )
    return Part(language, lines, blank, comment, physical, units, notes)


def rollup(text: str, code_lines: set[int], comment_lines: set[int]) -> tuple[int, int, int, int]:
    """Classify 1-based line numbers.

    A whitespace-only source line is blank, even inside a string or comment.
    A line with any code character is physical. Embedded comments stay on
    that physical line. Any other non-blank line is a comment line.
    """
    lines = text.splitlines()
    blank = comment = physical = 0
    for index, line in enumerate(lines, start=1):
        if line.strip() == "":
            blank += 1
        elif index in code_lines:
            physical += 1
        elif index in comment_lines:
            comment += 1
        else:
            physical += 1
    return len(lines), blank, comment, physical
