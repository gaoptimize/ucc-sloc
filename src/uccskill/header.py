"""Leading header text captured with a counted file.

The header is the opening documentation, not a later comment. Python uses the
module docstring when one exists, and a leading ``#`` block otherwise. The
other languages use a leading line-comment block or a leading block comment.
A shebang is skipped. Surrounding whitespace is removed. The stored text is
capped so a comment that swallows a whole file cannot bloat the snapshot.
"""

from __future__ import annotations

import ast

MAX_HEADER = 20000


def extract_header(language: str, text: str) -> str:
    body = _without_shebang(text)
    if language == "python":
        header = _python_header(body)
    elif language in {"javascript", "typescript"}:
        header = _leading_comment(body, ("//",), (("/*", "*/"),))
    elif language == "sql":
        header = _leading_comment(body, ("--",), (("/*", "*/"),))
    elif language == "css":
        header = _leading_comment(body, (), (("/*", "*/"),))
    elif language == "html":
        header = _leading_comment(body, (), (("<!--", "-->"),))
    else:
        header = ""
    if len(header) > MAX_HEADER:
        header = header[:MAX_HEADER].rstrip() + "\n…"
    return header


def _python_header(text: str) -> str:
    comments = _leading_comment(text, ("#",), ())
    document = ""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        tree = None
    if tree is not None:
        raw = ast.get_docstring(tree, clean=True)
        if raw:
            document = raw.strip()
    if comments and document:
        return f"{comments}\n\n{document}"
    return document or comments


def _without_shebang(text: str) -> str:
    if text.startswith("#!"):
        pieces = text.split("\n", 1)
        return pieces[1] if len(pieces) == 2 else ""
    return text


def _leading_comment(
    text: str,
    prefixes: tuple[str, ...],
    blocks: tuple[tuple[str, str], ...],
) -> str:
    lines = text.splitlines()
    while lines and lines[0].strip() == "":
        lines = lines[1:]
    if not lines:
        return ""
    first = lines[0].lstrip()
    for opener, closer in blocks:
        if first.startswith(opener):
            blob = "\n".join(lines)
            start = blob.find(opener)
            end = blob.find(closer, start + len(opener))
            if end == -1:
                return ""
            return blob[start + len(opener) : end].strip()
    if not prefixes:
        return ""
    collected: list[str] = []
    for line in lines:
        stripped = line.lstrip()
        if stripped.strip() == "":
            if collected:
                collected.append("")
            continue
        matched = next((prefix for prefix in prefixes if stripped.startswith(prefix)), None)
        if matched is None:
            break
        rest = stripped[len(matched) :]
        if rest.startswith(" "):
            rest = rest[1:]
        collected.append(rest)
    while collected and collected[-1] == "":
        collected.pop()
    return "\n".join(collected).strip()
