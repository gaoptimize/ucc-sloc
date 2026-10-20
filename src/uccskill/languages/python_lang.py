"""Python physical and logical SLOC.

Logical counts follow the UCC Python examples (Counting_Standards_Python, 2007/2013):

- if, elif, for, while, try, except, finally, with, and def each count once
- else counts zero (the statements in its body still count)
- a class header counts zero (UCC data-declaration example DDL1)
- each simple statement counts once, including pass, import, and assignment
- a header and a simple statement on the same line both count
- a statement joined with a backslash or with brackets is one statement
- a bare string expression is a comment, including docstrings
- decorators count once each (they are not in the 2007 standard)

When the file does not parse, each physical line becomes one logical unit and
the part carries a parse_error note. That keeps a broken file visible.
"""

from __future__ import annotations

import ast
import io
import tokenize

from uccskill.model import Part, make_part, rollup

_CODE_TOKENS = {
    tokenize.NAME,
    tokenize.NUMBER,
    tokenize.OP,
    tokenize.STRING,
}


def count_python(text: str) -> Part:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    notes: list[str] = []
    tree = None
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        notes.append(f"parse_error: {exc.msg}")

    doc_lines = _string_expr_lines(tree) if tree is not None else set()
    code_lines: set[int] = set()
    comment_lines: set[int] = set()
    try:
        _mark_tokens(text, doc_lines, code_lines, comment_lines)
    except (tokenize.TokenError, IndentationError, SyntaxError, TabError) as exc:
        notes.append(f"tokenize_error: {exc}")
        return _fallback(text, notes)

    lines, blank, comment, physical = rollup(text, code_lines, comment_lines)
    if tree is None:
        units = [
            "unparsed:" + " ".join(text.splitlines()[index - 1].split())
            for index in range(1, lines + 1)
            if text.splitlines()[index - 1].strip() and index in code_lines
        ]
        notes.append("logical counts each physical line because the file did not parse")
    else:
        units = _logical_units(tree)
    return make_part("python", lines, blank, comment, physical, units, notes)


def _mark_tokens(text, doc_lines, code_lines, comment_lines) -> None:
    for tok in tokenize.generate_tokens(io.StringIO(text).readline):
        if tok.type in {
            tokenize.ENCODING,
            tokenize.ENDMARKER,
            tokenize.INDENT,
            tokenize.DEDENT,
            tokenize.NL,
            tokenize.NEWLINE,
        }:
            continue
        start, end = tok.start[0], tok.end[0]
        if start <= 0:
            continue
        if tok.type == tokenize.COMMENT:
            comment_lines.update(range(start, end + 1))
            continue
        if tok.type not in _CODE_TOKENS:
            continue
        for line_no in range(start, end + 1):
            if line_no in doc_lines and tok.type == tokenize.STRING:
                comment_lines.add(line_no)
            elif line_no not in doc_lines:
                code_lines.add(line_no)


def _fallback(text: str, notes: list[str]) -> Part:
    units: list[str] = []
    code_lines: set[int] = set()
    comment_lines: set[int] = set()
    for index, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            comment_lines.add(index)
        else:
            code_lines.add(index)
            units.append("unparsed:" + " ".join(stripped.split()))
    notes.append("logical counts each physical line because the file did not parse")
    lines, blank, comment, physical = rollup(text, code_lines, comment_lines)
    return make_part("python", lines, blank, comment, physical, units, notes)


def _string_expr_lines(tree: ast.AST) -> set[int]:
    lines: set[int] = set()

    def walk(node: ast.AST) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.Expr) and _is_string_constant(child):
                end = child.end_lineno or child.lineno
                lines.update(range(child.lineno, end + 1))
            walk(child)

    walk(tree)
    return lines


def _is_string_constant(stmt: ast.stmt) -> bool:
    return (
        isinstance(stmt, ast.Expr)
        and isinstance(stmt.value, ast.Constant)
        and isinstance(stmt.value.value, str)
    )


def _dump(node) -> str:
    if node is None:
        return ""
    if isinstance(node, list):
        return "[" + ",".join(_dump(item) for item in node) + "]"
    return ast.dump(node, include_attributes=False)


def _logical_units(tree: ast.AST) -> list[str]:
    units: list[str] = []

    def add(fingerprint: str) -> None:
        units.append(fingerprint)

    def walk_body(body: list[ast.stmt]) -> None:
        for stmt in body:
            walk_stmt(stmt)

    def walk_stmt(stmt: ast.stmt) -> None:
        if _is_string_constant(stmt):
            return
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for decorator in stmt.decorator_list:
                add("decorator:" + _dump(decorator))
            kind = "asyncdef" if isinstance(stmt, ast.AsyncFunctionDef) else "def"
            returns = _dump(stmt.returns) if stmt.returns else ""
            type_params = _dump(getattr(stmt, "type_params", []) or [])
            add(f"{kind}:{stmt.name}:{_dump(stmt.args)}:{returns}:{type_params}")
            walk_body(stmt.body)
            return
        if isinstance(stmt, ast.ClassDef):
            for decorator in stmt.decorator_list:
                add("decorator:" + _dump(decorator))
            walk_body(stmt.body)
            return
        if isinstance(stmt, ast.If):
            add("if:" + _dump(stmt.test))
            walk_body(stmt.body)
            if len(stmt.orelse) == 1 and isinstance(stmt.orelse[0], ast.If):
                walk_stmt(stmt.orelse[0])
            else:
                walk_body(stmt.orelse)
            return
        if isinstance(stmt, (ast.For, ast.AsyncFor)):
            kind = "asyncfor" if isinstance(stmt, ast.AsyncFor) else "for"
            add(f"{kind}:{_dump(stmt.target)}:{_dump(stmt.iter)}")
            walk_body(stmt.body)
            walk_body(stmt.orelse)
            return
        if isinstance(stmt, ast.While):
            add("while:" + _dump(stmt.test))
            walk_body(stmt.body)
            walk_body(stmt.orelse)
            return
        if isinstance(stmt, (ast.With, ast.AsyncWith)):
            kind = "asyncwith" if isinstance(stmt, ast.AsyncWith) else "with"
            add(f"{kind}:{_dump(stmt.items)}")
            walk_body(stmt.body)
            return
        try_types = (ast.Try,)
        if hasattr(ast, "TryStar"):
            try_types = (ast.Try, ast.TryStar)
        if isinstance(stmt, try_types):
            add("try")
            walk_body(stmt.body)
            for handler in stmt.handlers:
                add("except:" + (_dump(handler.type) if handler.type else ""))
                walk_body(handler.body)
            walk_body(stmt.orelse)
            if stmt.finalbody:
                add("finally")
                walk_body(stmt.finalbody)
            return
        if isinstance(stmt, ast.Match):
            add("match:" + _dump(stmt.subject))
            for case in stmt.cases:
                add("case:" + _dump(case.pattern))
                walk_body(case.body)
            return
        if isinstance(stmt, ast.TypeAlias):
            add(f"type:{stmt.name.id}:{_dump(stmt.value)}")
            return
        add(_dump(stmt))

    walk_body(tree.body)
    return units
