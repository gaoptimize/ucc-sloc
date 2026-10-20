"""HTML and CSS physical and logical SLOC.

HTML follows Counting_Standards_HTML_XML: a start tag or an empty tag counts
once, an end tag does not, and a declaration or processing instruction counts
once. Text is physical when it is not blank or a comment, and it is not logical.

CSS follows Counting_Standards_Cascading_Style_Sheets: each comma-separated
selector counts once (commas inside parentheses stay in one selector) and each
declaration counts once, including a final declaration with no semicolon.
Grouping at-rules (@media, @supports, @container, @keyframes, @layer) count
once in addition to the rules they contain.

A <script> body is counted as JavaScript and a <style> body as CSS. The tags
themselves stay HTML. A script or style element written on one line with its
body is left entirely in HTML; put the body on its own lines.
"""

from __future__ import annotations

import re

from uccskill.model import Part, make_part, rollup

from .js_lang import count_script

_GROUP_AT = (
    "@media",
    "@supports",
    "@container",
    "@document",
    "@layer",
    "@keyframes",
    "@font-feature-values",
)
_SCRIPT_RE = re.compile(r"(<script\b([^>]*)>)(.*?)(</script\s*>)", re.IGNORECASE | re.DOTALL)
_STYLE_RE = re.compile(r"(<style\b([^>]*)>)(.*?)(</style\s*>)", re.IGNORECASE | re.DOTALL)
_JS_TYPES = {"", "module", "text/javascript", "application/javascript", "text/ecmascript"}


def count_css(text: str) -> Part:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    notes: list[str] = []
    blanked, code_lines, comment_lines = _blank_css(text, notes)
    units = _css_units(blanked)
    lines, blank, comment, physical = rollup(text, code_lines, comment_lines)
    return make_part("css", lines, blank, comment, physical, units, notes)


def count_html(text: str) -> list[Part]:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    notes: list[str] = []
    line_starts = _line_starts(text)
    file_lines = text.splitlines()
    n = len(file_lines)
    owner = ["html"] * n
    masked = list(text)

    def take(pattern, language: str, type_ok) -> None:
        for match in pattern.finditer(text):
            attrs = match.group(2) or ""
            if not type_ok(attrs):
                continue
            body_start, body_end = match.start(3), match.end(3)
            for index in range(n):
                start = line_starts[index]
                end = line_starts[index + 1] if index + 1 < len(line_starts) else len(text)
                if _line_inside(start, end, body_start, body_end, text):
                    owner[index] = language
            for index in range(body_start, body_end):
                if masked[index] != "\n":
                    masked[index] = " "

    take(_SCRIPT_RE, "javascript", _script_is_js)
    take(_STYLE_RE, "css", lambda _attrs: True)
    _note_inline_body(text, notes)

    html_code, html_comment = _html_masks("".join(masked), notes)
    html_code_lines = {index for index in html_code if owner[index - 1] == "html"}
    html_comment_lines = {index for index in html_comment if owner[index - 1] == "html"}
    # Lines owned by another language are outside this part. Rebuild a text
    # whose non-HTML lines are omitted by counting only HTML-owned lines.
    html_units = _html_units("".join(masked))
    html_lines = owner.count("html")
    blank = comment = physical = 0
    for index, who in enumerate(owner, start=1):
        if who != "html":
            continue
        if file_lines[index - 1].strip() == "":
            blank += 1
        elif index in html_code_lines:
            physical += 1
        elif index in html_comment_lines:
            comment += 1
        else:
            physical += 1
    parts = [make_part("html", html_lines, blank, comment, physical, html_units, notes)]

    if any(who == "javascript" for who in owner):
        parts.append(_embedded("javascript", owner, file_lines))
    if any(who == "css" for who in owner):
        parts.append(_embedded("css", owner, file_lines))
    return parts


def _embedded(language: str, owner: list[str], file_lines: list[str]) -> Part:
    """Owned lines are both the physical block and the logical source."""
    owned = "\n".join(line for index, line in enumerate(file_lines) if owner[index] == language)
    if language == "javascript":
        block = count_script(owned, language)
    else:
        block = count_css(owned)
    return block


def _line_inside(start: int, end: int, body_start: int, body_end: int, text: str) -> bool:
    content_end = end - 1 if end > start and end <= len(text) and text[end - 1:end] == "\n" else end
    return start >= body_start and content_end <= body_end


def _script_is_js(attrs: str) -> bool:
    match = re.search(r"type\s*=\s*['\"]([^'\"]*)['\"]", attrs, re.IGNORECASE)
    if not match:
        return True
    return match.group(1).strip().lower() in _JS_TYPES


def _note_inline_body(text: str, notes: list[str]) -> None:
    for match in _SCRIPT_RE.finditer(text):
        body = match.group(3)
        if body.strip() and "\n" not in body:
            notes.append("script body shares a line with its tag and was left in the HTML count")
            return


def _line_starts(text: str) -> list[int]:
    starts = [0]
    for index, ch in enumerate(text):
        if ch == "\n":
            starts.append(index + 1)
    return starts


def _html_masks(text: str, notes: list[str]):
    code_lines: set[int] = set()
    comment_lines: set[int] = set()
    line = 1
    i = 0
    n = len(text)
    while i < n:
        if text[i] == "\n":
            line += 1
            i += 1
            continue
        if text.startswith("<!--", i):
            while i < n and not text.startswith("-->", i):
                if text[i] == "\n":
                    line += 1
                elif not text[i].isspace():
                    comment_lines.add(line)
                i += 1
            if text.startswith("-->", i):
                comment_lines.add(line)
                i += 3
            else:
                notes.append("unclosed html comment")
            continue
        if not text[i].isspace():
            code_lines.add(line)
        i += 1
    return code_lines, comment_lines


def _html_units(masked: str) -> list[str]:
    units: list[str] = []
    i = 0
    n = len(masked)
    while i < n:
        if masked.startswith("<!--", i):
            end = masked.find("-->", i + 4)
            i = n if end < 0 else end + 3
            continue
        if masked[i] != "<":
            i += 1
            continue
        if masked.startswith("<!", i):
            end = _declaration_end(masked, i)
            raw = masked[i:end]
            if raw.strip():
                units.append("decl:" + " ".join(raw.split()))
            i = end
            continue
        if masked.startswith("<?", i):
            end = masked.find("?>", i + 2)
            end = n if end < 0 else end + 2
            units.append("pi:" + " ".join(masked[i:end].split()))
            i = end
            continue
        end = _tag_end(masked, i)
        raw = masked[i:end]
        name = _tag_name(raw)
        if name and not raw.lstrip().startswith("</"):
            units.append("tag:" + " ".join(raw.split()))
        i = end
    return units


def _declaration_end(text: str, start: int) -> int:
    i = start
    depth = 0
    quote = ""
    while i < len(text):
        ch = text[i]
        if quote:
            if ch == quote:
                quote = ""
            i += 1
            continue
        if ch in "'\"":
            quote = ch
        elif ch == "[":
            depth += 1
        elif ch == "]" and depth:
            depth -= 1
        elif ch == ">" and depth == 0:
            return i + 1
        i += 1
    return len(text)


def _tag_end(text: str, start: int) -> int:
    i = start
    quote = ""
    while i < len(text):
        ch = text[i]
        if quote:
            if ch == quote:
                quote = ""
            i += 1
            continue
        if ch in "'\"":
            quote = ch
        elif ch == ">":
            return i + 1
        i += 1
    return len(text)


def _tag_name(raw: str) -> str:
    match = re.match(r"<\s*/?\s*([A-Za-z][\w:.-]*)", raw)
    return match.group(1).lower() if match else ""


def _blank_css(text: str, notes: list[str]):
    chars = list(text)
    code_lines: set[int] = set()
    comment_lines: set[int] = set()
    line = 1
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == "\n":
            line += 1
            i += 1
            continue
        if ch.isspace():
            i += 1
            continue
        if ch == "/" and i + 1 < n and text[i + 1] == "*":
            chars[i] = chars[i + 1] = " "
            i += 2
            closed = False
            while i < n:
                if text[i] == "\n":
                    line += 1
                    i += 1
                    continue
                if text[i] == "*" and i + 1 < n and text[i + 1] == "/":
                    comment_lines.add(line)
                    chars[i] = chars[i + 1] = " "
                    i += 2
                    closed = True
                    break
                if not text[i].isspace():
                    comment_lines.add(line)
                chars[i] = " "
                i += 1
            if not closed:
                notes.append("unclosed css comment")
            continue
        if ch in "'\"":
            quote = ch
            code_lines.add(line)
            chars[i] = " "
            i += 1
            while i < n and text[i] != "\n":
                code_lines.add(line)
                if text[i] == "\\":
                    chars[i] = " "
                    i += 1
                    if i < n and text[i] != "\n":
                        chars[i] = " "
                        i += 1
                    continue
                if text[i] == quote:
                    chars[i] = " "
                    i += 1
                    break
                chars[i] = " "
                i += 1
            continue
        code_lines.add(line)
        i += 1
    return "".join(chars), code_lines, comment_lines


def _css_units(blanked: str) -> list[str]:
    units: list[str] = []
    stack: list[str] = []
    paren = 0
    last = 0
    i = 0
    n = len(blanked)

    def prelude() -> str:
        return blanked[last:i]

    while i < n:
        ch = blanked[i]
        if ch == "(":
            paren += 1
        elif ch == ")":
            paren = max(0, paren - 1)
        elif ch == "{" and paren == 0:
            _open_block(prelude(), stack, units)
            last = i + 1
        elif ch == "}" and paren == 0:
            if stack and stack[-1] == "decl":
                _emit_declarations(prelude(), units)
            if stack:
                stack.pop()
            last = i + 1
        elif ch == ";" and paren == 0:
            chunk = prelude()
            if stack and stack[-1] == "decl":
                _emit_declarations(chunk, units)
            elif chunk.strip():
                units.append("at:" + " ".join(chunk.split()))
            last = i + 1
        i += 1
    return units


def _open_block(chunk: str, stack: list[str], units: list[str]) -> None:
    text = " ".join(chunk.split())
    low = text.lower()
    if any(low.startswith(prefix) for prefix in _GROUP_AT):
        units.append("at:" + text)
        stack.append("keyframe" if low.startswith("@keyframes") else "group")
        return
    if stack and stack[-1] == "keyframe":
        _emit_selectors(text, units)
        stack.append("decl")
        return
    _emit_selectors(text, units)
    stack.append("decl")


def _emit_selectors(text: str, units: list[str]) -> None:
    if not text.strip():
        return
    for part in _split_selector_commas(text):
        part = " ".join(part.split())
        if part:
            units.append("sel:" + part.lower())


def _emit_declarations(chunk: str, units: list[str]) -> None:
    text = " ".join(chunk.split())
    if ":" in text:
        units.append("decl:" + text)


def _split_selector_commas(text: str) -> list[str]:
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
