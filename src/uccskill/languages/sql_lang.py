"""SQL physical and logical SLOC.

Logical keywords follow Counting_Standards_SQL (2007/2014). Each listed
keyword counts once per occurrence outside comments and strings. Nested
queries count again. GROUP and ORDER count only as GROUP BY and ORDER BY.
IF does not count in END IF. CREATE OR REPLACE counts as CREATE only.

Column definitions inside CREATE TABLE count once each (DDL1). A column is a
top-level item in the column list whose first tokens are a name and a type.
Table constraints (PRIMARY KEY, FOREIGN KEY, UNIQUE, CHECK, CONSTRAINT) are
not extra columns.

Deliberate gaps, recorded in the counting notes: SET and WITH are not in the
UCC keyword list, so they count only when they contain a listed keyword.
Brace comments of the form { ... } are not treated as comments.
"""

from __future__ import annotations

import re

from uccskill.model import Part, make_part, rollup

# Longer words first so ELSIF is not also ELSE.
_KEYWORDS = (
    "ELSEIF",
    "ELSIF",
    "SELECT",
    "UPDATE",
    "INSERT",
    "DELETE",
    "DECLARE",
    "TRUNCATE",
    "ROLLBACK",
    "EXCEPTION",
    "CONTINUE",
    "COMMIT",
    "CREATE",
    "REVOKE",
    "RENAME",
    "HAVING",
    "UNION",
    "WHERE",
    "LIMIT",
    "ALTER",
    "GRANT",
    "CLOSE",
    "FETCH",
    "GROUP",
    "ORDER",
    "DROP",
    "JOIN",
    "LOOP",
    "WHEN",
    "EXIT",
    "ELSE",
    "FOR",
    "IF",
)

_KEYWORD_RE = re.compile(r"\b(" + "|".join(_KEYWORDS) + r")\b", re.IGNORECASE)
_CREATE_TABLE_RE = re.compile(r"\bCREATE\s+TABLE\b", re.IGNORECASE)
_COLUMN_RE = re.compile(r"^[A-Za-z_][\w$]*\s+[A-Za-z_][\w$]*\b")
_CONSTRAINT_RE = re.compile(
    r"^(PRIMARY|FOREIGN|UNIQUE|CHECK|CONSTRAINT|INDEX)\b",
    re.IGNORECASE,
)


def count_sql(text: str) -> Part:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    notes: list[str] = []
    blanked, code_lines, comment_lines = _blank(text, notes)
    found: list[tuple[int, str]] = []
    for match in _KEYWORD_RE.finditer(blanked):
        word = match.group(1).upper()
        if word == "IF" and re.search(r"\bEND$", blanked[: match.start()].rstrip(), re.IGNORECASE):
            continue
        if word in {"GROUP", "ORDER"} and not re.match(
            r"\s+BY\b", blanked[match.end() :], re.IGNORECASE
        ):
            continue
        if word == "COMMENT":
            continue
        snippet = _line_snippet(blanked, match.start())
        found.append((match.start(), f"{word}:{snippet}"))
    found.extend(_columns(blanked))
    found.sort(key=lambda item: item[0])
    units = [item[1] for item in found]
    lines, blank, comment, physical = rollup(text, code_lines, comment_lines)
    return make_part("sql", lines, blank, comment, physical, units, notes)


def _blank(text: str, notes: list[str]):
    chars = list(text)
    code_lines: set[int] = set()
    comment_lines: set[int] = set()
    line = 1
    i = 0
    n = len(text)

    def mark_code() -> None:
        code_lines.add(line)

    def mark_comment() -> None:
        comment_lines.add(line)

    while i < n:
        ch = text[i]
        if ch == "\n":
            line += 1
            i += 1
            continue
        if ch.isspace():
            i += 1
            continue
        if ch == "-" and i + 1 < n and text[i + 1] == "-":
            while i < n and text[i] != "\n":
                if not text[i].isspace():
                    mark_comment()
                chars[i] = " "
                i += 1
            continue
        if ch == "/" and i + 1 < n and text[i + 1] == "*":
            chars[i] = " "
            chars[i + 1] = " "
            i += 2
            closed = False
            while i < n:
                if text[i] == "\n":
                    line += 1
                    i += 1
                    continue
                if text[i] == "*" and i + 1 < n and text[i + 1] == "/":
                    mark_comment()
                    chars[i] = " "
                    chars[i + 1] = " "
                    i += 2
                    closed = True
                    break
                if not text[i].isspace():
                    mark_comment()
                chars[i] = " "
                i += 1
            if not closed:
                notes.append("unclosed block comment")
            continue
        if ch in "'\"":
            quote = ch
            mark_code()
            chars[i] = " "
            i += 1
            closed = False
            while i < n:
                if text[i] == "\n":
                    line += 1
                    i += 1
                    continue
                mark_code()
                if text[i] == quote and i + 1 < n and text[i + 1] == quote:
                    chars[i] = " "
                    chars[i + 1] = " "
                    i += 2
                    continue
                if text[i] == "\\" and quote == "'":
                    chars[i] = " "
                    i += 1
                    if i < n and text[i] != "\n":
                        chars[i] = " "
                        i += 1
                    continue
                if text[i] == quote:
                    chars[i] = " "
                    i += 1
                    closed = True
                    break
                chars[i] = " "
                i += 1
            if not closed:
                notes.append("unclosed string")
            continue
        if ch == "$" and i + 1 < n and text[i + 1] == "$":
            mark_code()
            chars[i] = " "
            chars[i + 1] = " "
            i += 2
            closed = False
            while i < n:
                if text[i] == "\n":
                    line += 1
                    i += 1
                    continue
                mark_code()
                if text[i] == "$" and i + 1 < n and text[i + 1] == "$":
                    chars[i] = " "
                    chars[i + 1] = " "
                    i += 2
                    closed = True
                    break
                chars[i] = " "
                i += 1
            if not closed:
                notes.append("unclosed dollar quote")
            continue
        mark_code()
        i += 1
    return "".join(chars), code_lines, comment_lines


def _line_snippet(text: str, index: int) -> str:
    start = text.rfind("\n", 0, index) + 1
    end = text.find("\n", index)
    if end < 0:
        end = len(text)
    return " ".join(text[start:end].split())


def _columns(blanked: str) -> list[tuple[int, str]]:
    found: list[tuple[int, str]] = []
    for match in _CREATE_TABLE_RE.finditer(blanked):
        open_at = blanked.find("(", match.end())
        if open_at < 0:
            continue
        close_at = _match_paren(blanked, open_at)
        if close_at < 0:
            continue
        body = blanked[open_at + 1 : close_at]
        cursor = open_at + 1
        for piece in _split_commas(body):
            stripped = piece.strip()
            local = piece.find(stripped) if stripped else 0
            position = cursor + max(local, 0)
            cursor += len(piece) + 1
            if not stripped or _CONSTRAINT_RE.match(stripped):
                continue
            if _COLUMN_RE.match(stripped):
                found.append((position, "COL:" + " ".join(stripped.split())))
    return found


def _match_paren(text: str, open_at: int) -> int:
    depth = 0
    for index in range(open_at, len(text)):
        if text[index] == "(":
            depth += 1
        elif text[index] == ")":
            depth -= 1
            if depth == 0:
                return index
    return -1


def _split_commas(text: str) -> list[str]:
    parts: list[str] = []
    depth = 0
    start = 0
    for index, ch in enumerate(text):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        elif ch == "," and depth == 0:
            parts.append(text[start:index])
            start = index + 1
    parts.append(text[start:])
    return parts
