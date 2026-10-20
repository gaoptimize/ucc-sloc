"""JavaScript and TypeScript physical and logical SLOC.

UCC 2018 publishes no JavaScript or TypeScript standard. The rules follow the
C-family shape used in the UCC Python standard:

- if, for, while, do, switch, catch, try, finally, function, class, with,
  interface, enum, and namespace each count once
- else counts zero
- case and default each count once
- each other statement counts once, whether it ends with a semicolon or a
  line break
- the semicolons inside a for (...) header do not count
- the while that closes a do-while, and its semicolon, do not count again
- braces are not an extra count
- a method inside a class counts once
- a function expression counts once in addition to the statement that holds it
- enum members count once each
- an interface counts once plus once per member

JSX elements are one token, so a semicolon inside JSX text does not start a
statement. Type aliases are ordinary statements.
"""

from __future__ import annotations

from uccskill.model import Part, make_part, rollup

_HEADERS = {
    "if",
    "for",
    "while",
    "do",
    "switch",
    "catch",
    "try",
    "finally",
    "function",
    "class",
    "interface",
    "enum",
    "namespace",
    "with",
}
_RESTRICTED = {"return", "throw", "break", "continue", "yield"}
_JSX_WORDS = {"return", "throw", "yield", "case"}
_JSX_OPS = {"=", "(", "[", "{", ",", "?", ":", "=>", "&&", "||", "??", "!"}
_ENDERS = {"ident", "number", "string", "regex", "jsx", ")", "]"}
_CONTINUES = {
    "+", "-", "*", "/", "%", "=", "==", "===", "!=", "!==", "<", ">", "<=",
    ">=", "&&", "||", "??", "?.", "&", "|", "^", "!", "~", "?", ":", ",", ".",
    "=>", "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", "<<=", ">>=", ">>>=",
    "++", "--", "**", "(", "[", "{", "\\",
}


def count_script(text: str, language: str) -> Part:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    notes: list[str] = []
    code_lines, comment_lines, tokens = _lex(text, notes)
    lines, blank, comment, physical = rollup(text, code_lines, comment_lines)
    units = _Parser(tokens).parse()
    return make_part(language, lines, blank, comment, physical, units, notes)


def _lex(text: str, notes: list[str]):
    code_lines: set[int] = set()
    comment_lines: set[int] = set()
    tokens: list[tuple] = []
    i = 0
    n = len(text)
    line = 1
    mode: list[tuple] = [("code", 0)]
    prev_kind = None
    prev_word = ""
    newline_before = True

    def mark(at: int) -> None:
        code_lines.add(at)

    while i < n:
        if mode[-1][0] == "template" and mode[-1][1] == 0:
            start_line = line
            while i < n:
                ch = text[i]
                if ch == "\n":
                    line += 1
                    i += 1
                    continue
                if ch == "\\":
                    mark(line)
                    i += 2 if i + 1 < n else 1
                    continue
                if ch == "`":
                    mark(line)
                    i += 1
                    mode.pop()
                    tokens.append(("string", "``", start_line, False))
                    prev_kind = "string"
                    prev_word = ""
                    newline_before = False
                    break
                if ch == "$" and i + 1 < n and text[i + 1] == "{":
                    mark(line)
                    i += 2
                    mode[-1] = ("template", 1)
                    break
                if not ch.isspace():
                    mark(line)
                i += 1
            else:
                notes.append("unclosed template")
            continue

        ch = text[i]
        if ch == "\n":
            line += 1
            i += 1
            newline_before = True
            continue
        if ch in " \t\f\v":
            i += 1
            continue

        if mode[-1][0] == "template" and ch == "}":
            depth = mode[-1][1] - 1
            i += 1
            if depth == 0:
                mode[-1] = ("template", 0)
            else:
                mode[-1] = ("template", depth)
                tokens.append(("punct", "}", line, newline_before))
                prev_kind = "}"
                prev_word = ""
                newline_before = False
            continue

        if ch == "/" and i + 1 < n and text[i + 1] == "/":
            comment_lines.add(line)
            while i < n and text[i] != "\n":
                i += 1
            continue
        if ch == "/" and i + 1 < n and text[i + 1] == "*":
            i += 2
            closed = False
            while i < n:
                if text[i] == "\n":
                    line += 1
                    i += 1
                    continue
                if text[i] == "*" and i + 1 < n and text[i + 1] == "/":
                    comment_lines.add(line)
                    i += 2
                    closed = True
                    break
                if not text[i].isspace():
                    comment_lines.add(line)
                i += 1
            if not closed:
                notes.append("unclosed block comment")
            continue

        if ch in "'\"":
            quote = ch
            mark(line)
            i += 1
            closed = False
            while i < n and text[i] != "\n":
                if text[i] == "\\":
                    mark(line)
                    i += 2 if i + 1 < n else 1
                    continue
                if text[i] == quote:
                    i += 1
                    closed = True
                    break
                if not text[i].isspace():
                    mark(line)
                i += 1
            if not closed:
                notes.append("unclosed string")
            tokens.append(("string", quote, line, newline_before))
            prev_kind = "string"
            prev_word = ""
            newline_before = False
            continue

        if ch == "`":
            mark(line)
            i += 1
            mode.append(("template", 0))
            continue

        jsx_ok = prev_word in _JSX_WORDS or prev_kind in _JSX_OPS or prev_kind is None
        if ch == "<" and jsx_ok and _starts_jsx(text, i):
            token_line = line
            i, line, closed = _read_jsx(text, i, line, code_lines, notes)
            tokens.append(("jsx", "<jsx>", token_line, newline_before))
            prev_kind = "jsx"
            prev_word = ""
            newline_before = False
            if not closed:
                notes.append("unclosed jsx")
            continue

        if ch == "/" and prev_kind not in {"ident", "number", "string", "regex", "jsx", ")", "]"}:
            mark(line)
            i += 1
            in_class = False
            closed = False
            while i < n and text[i] != "\n":
                if text[i] == "\\":
                    i += 2 if i + 1 < n else 1
                    continue
                if in_class:
                    if text[i] == "]":
                        in_class = False
                    i += 1
                    continue
                if text[i] == "[":
                    in_class = True
                    i += 1
                    continue
                if text[i] == "/":
                    i += 1
                    closed = True
                    break
                i += 1
            while i < n and text[i].isalpha():
                i += 1
            if not closed:
                notes.append("unclosed regex")
            tokens.append(("regex", "/", line, newline_before))
            prev_kind = "regex"
            prev_word = ""
            newline_before = False
            continue

        if ch.isalpha() or ch in "_$":
            start = i
            i += 1
            while i < n and (text[i].isalnum() or text[i] in "_$"):
                i += 1
            word = text[start:i]
            mark(line)
            tokens.append(("ident", word, line, newline_before))
            prev_kind = "ident"
            prev_word = word
            newline_before = False
            continue

        if ch.isdigit() or (
            ch == "."
            and i + 1 < n
            and text[i + 1].isdigit()
            and prev_kind not in {"ident", "number", ")", "]"}
        ):
            start = i
            i += 1
            while i < n and (text[i].isalnum() or text[i] in "._"):
                if text[i] in "eE" and i + 1 < n and text[i + 1] in "+-":
                    i += 2
                    continue
                i += 1
            mark(line)
            tokens.append(("number", text[start:i], line, newline_before))
            prev_kind = "number"
            prev_word = ""
            newline_before = False
            continue

        op = _read_operator(text, i)
        if op:
            mark(line)
            i += len(op)
            tokens.append(("punct", op, line, newline_before))
            prev_kind = op
            prev_word = ""
            newline_before = False
            if mode and mode[-1][0] == "template" and op == "{":
                mode[-1] = ("template", mode[-1][1] + 1)
            continue

        mark(line)
        i += 1

    return code_lines, comment_lines, tokens


def _starts_jsx(text: str, i: int) -> bool:
    j = i + 1
    if j >= len(text):
        return False
    return text[j].isalpha() or text[j] in "_$>/"


def _read_jsx(text, i, line, code_lines, notes):
    """Consume one JSX element starting at '<'. Returns (index, line, closed)."""
    n = len(text)
    depth = 0
    expr = 0
    closed = False
    while i < n:
        ch = text[i]
        if ch == "\n":
            line += 1
            i += 1
            continue
        if not ch.isspace():
            code_lines.add(line)
        if expr == 0 and ch == "<":
            if i + 1 < n and text[i + 1] == "/":
                depth -= 1
                i += 2
                while i < n and text[i] not in ">\n":
                    if not text[i].isspace():
                        code_lines.add(line)
                    i += 1
                if i < n and text[i] == ">":
                    i += 1
                if depth <= 0:
                    closed = True
                    break
                continue
            depth += 1
            i += 1
            continue
        if ch in "'\"":
            quote = ch
            i += 1
            while i < n and text[i] != "\n":
                if text[i] == "\\":
                    i += 2 if i + 1 < n else 1
                    continue
                if not text[i].isspace():
                    code_lines.add(line)
                if text[i] == quote:
                    i += 1
                    break
                i += 1
            continue
        if ch == "{":
            expr += 1
            i += 1
            continue
        if ch == "}":
            expr = max(0, expr - 1)
            i += 1
            continue
        if expr == 0 and ch == "/" and i + 1 < n and text[i + 1] == ">":
            depth -= 1
            i += 2
            if depth <= 0:
                closed = True
                break
            continue
        if expr == 0 and ch == ">":
            i += 1
            continue
        i += 1
    return i, line, closed


def _read_operator(text: str, i: int) -> str:
    for candidate in (
        ">>>=", ">>=", "<<=", "===", "!==", ">>>", "=>", "==", "!=", "<=",
        ">=", "&&", "||", "??", "?.", "++", "--", "+=", "-=", "*=", "/=",
        "%=", "&=", "|=", "^=", "**", "<<", ">>",
    ):
        if text.startswith(candidate, i):
            return candidate
    if text[i] in "{}()[];,.:?+-*/%&|^~!<>=\\":
        return text[i]
    return ""


class _Parser:
    def __init__(self, tokens: list[tuple]):
        self.tokens = tokens
        self.i = 0
        self.units: list[str] = []

    def parse(self) -> list[str]:
        while self.peek():
            before = self.i
            self.parse_statement()
            if self.i == before:
                self.pop()
        return self.units

    def peek(self):
        if self.i < len(self.tokens):
            return self.tokens[self.i]
        return None

    def pop(self):
        token = self.peek()
        if token is not None:
            self.i += 1
        return token

    def next_val(self) -> str:
        token = self.peek()
        return token[1] if token else ""

    def parse_statement(self) -> None:
        token = self.peek()
        if token is None:
            return
        val = token[1]
        if val == ";":
            self.pop()
            self.units.append("empty:;")
            return
        if val == "{":
            self.parse_block()
            return
        if val == "async" and self._ahead(1) == "function":
            self.pop()
            self.parse_function()
            return
        if val in {"export", "import"}:
            self._parse_import_export()
            return
        if val == "function":
            self.parse_function()
            return
        if val == "class":
            self.parse_class()
            return
        if val == "interface":
            self.parse_interface()
            return
        if val == "enum":
            self.parse_enum()
            return
        if val == "namespace":
            self.parse_namespace()
            return
        if val == "type" and self._is_type_alias():
            self._read_until_end("stmt")
            return
        if val == "do":
            self.pop()
            self.units.append("do:do")
            self.parse_statement()
            if self.next_val() == "while":
                self.pop()
                self._skip_parens()
                if self.next_val() == ";":
                    self.pop()
            return
        if val == "try":
            self.pop()
            self.units.append("try:try")
            self.parse_statement()
            while self.next_val() in {"catch", "finally"}:
                keyword = self.pop()[1]
                extra = self._skip_parens() if keyword == "catch" and self.next_val() == "(" else ""
                self.units.append(f"{keyword}:{keyword} {extra}".strip())
                self.parse_statement()
            return
        if val == "if":
            self._header_with_paren("if")
            self.parse_statement()
            if self.next_val() == "else":
                self.pop()
                self.parse_statement()
            return
        if val in {"while", "for", "switch", "with"}:
            self._header_with_paren(val)
            self.parse_statement()
            return
        if val in {"case", "default"}:
            self._parse_case(val)
            return
        if val == "}":
            return
        self._read_until_end("stmt")

    def parse_block(self) -> None:
        if self.next_val() != "{":
            self.parse_statement()
            return
        self.pop()
        while self.peek() and self.next_val() != "}":
            before = self.i
            self.parse_statement()
            if self.i == before:
                self.pop()
        if self.next_val() == "}":
            self.pop()

    def parse_function(self) -> None:
        self.pop()
        buf = ["function"]
        while self.peek() and self.next_val() not in {"(", "{", ";"}:
            buf.append(self.pop()[1])
            if len(buf) > 12:
                break
        buf.append(self._skip_parens())
        self.units.append("function:" + " ".join(part for part in buf if part))
        if self.next_val() == "{":
            self.parse_block()
        elif self.next_val() == ";":
            self.pop()

    def parse_class(self) -> None:
        self.pop()
        buf = ["class"]
        while self.peek() and self.next_val() not in {"{", ";"}:
            buf.append(self.pop()[1])
            if len(buf) > 16:
                break
        self.units.append("class:" + " ".join(buf))
        self._parse_class_body()

    def parse_interface(self) -> None:
        self.pop()
        buf = ["interface"]
        while self.peek() and self.next_val() not in {"{", ";"}:
            buf.append(self.pop()[1])
            if len(buf) > 16:
                break
        self.units.append("interface:" + " ".join(buf))
        if self.next_val() != "{":
            return
        self.pop()
        member: list[str] = []
        depth = 0
        while self.peek() and not (self.next_val() == "}" and depth == 0):
            val = self.pop()[1]
            if val in "([{":
                depth += 1
                member.append(val)
            elif val in ")]}":
                depth = max(0, depth - 1)
                member.append(val)
            elif val == ";" and depth == 0:
                text = " ".join(member).strip()
                if text:
                    self.units.append("stmt:" + text)
                member = []
            else:
                member.append(val)
        text = " ".join(member).strip()
        if text:
            self.units.append("stmt:" + text)
        if self.next_val() == "}":
            self.pop()

    def parse_enum(self) -> None:
        self.pop()
        buf = ["enum"]
        while self.peek() and self.next_val() not in {"{", ";"}:
            buf.append(self.pop()[1])
            if len(buf) > 8:
                break
        self.units.append("enum:" + " ".join(buf))
        if self.next_val() != "{":
            return
        self.pop()
        body: list[str] = []
        depth = 0
        while self.peek() and not (self.next_val() == "}" and depth == 0):
            val = self.pop()[1]
            if val in "([{":
                depth += 1
            elif val in ")]}":
                depth = max(0, depth - 1)
            body.append(val)
        if self.next_val() == "}":
            self.pop()
        for piece in _split_commas(" ".join(body)):
            piece = piece.strip()
            if piece:
                self.units.append("enum:" + piece)

    def parse_namespace(self) -> None:
        self.pop()
        buf = ["namespace"]
        while self.peek() and self.next_val() not in {"{", ";"}:
            buf.append(self.pop()[1])
            if len(buf) > 8:
                break
        self.units.append("namespace:" + " ".join(buf))
        self.parse_block()

    def _parse_class_body(self) -> None:
        if self.next_val() != "{":
            return
        self.pop()
        while self.peek() and self.next_val() != "}":
            if self.next_val() == ";":
                self.pop()
                self.units.append("empty:;")
                continue
            if self._looks_like_method():
                name = self._method_name()
                self.units.append("method:" + name)
                self._consume_signature()
                self.parse_block()
                continue
            before = self.i
            self._read_until_end("stmt")
            if self.i == before:
                self.pop()
        if self.next_val() == "}":
            self.pop()

    def _parse_import_export(self) -> None:
        keyword = self.next_val()
        lookahead = self._ahead(1)
        if keyword == "export" and lookahead == "default":
            after = self._ahead(2)
            if after == "function":
                self.pop()
                self.pop()
                self.parse_function()
                return
            if after == "class":
                self.pop()
                self.pop()
                self.parse_class()
                return
        if keyword == "export" and lookahead == "function":
            self.pop()
            self.parse_function()
            return
        if keyword == "export" and lookahead == "class":
            self.pop()
            self.parse_class()
            return
        if keyword == "export" and lookahead == "interface":
            self.pop()
            self.parse_interface()
            return
        if keyword == "export" and lookahead == "enum":
            self.pop()
            self.parse_enum()
            return
        if keyword == "export" and lookahead == "namespace":
            self.pop()
            self.parse_namespace()
            return
        if keyword == "export" and lookahead == "type" and self._is_type_alias(skip=1):
            self.pop()
            self._read_until_end("stmt")
            return
        self._read_until_end("stmt")

    def _parse_case(self, keyword: str) -> None:
        self.pop()
        buf = [keyword]
        while self.peek() and self.next_val() not in {":", "}"}:
            buf.append(self.pop()[1])
            if len(buf) > 24:
                break
        if self.next_val() == ":":
            self.pop()
        self.units.append(keyword + ":" + " ".join(buf))
        while self.peek() and self.next_val() not in {"case", "default", "}"}:
            before = self.i
            self.parse_statement()
            if self.i == before:
                self.pop()

    def _header_with_paren(self, keyword: str) -> None:
        self.pop()
        extra = self._skip_parens()
        self.units.append(f"{keyword}:{keyword} {extra}".strip())

    def _skip_parens(self) -> str:
        if self.next_val() != "(":
            return ""
        buf = []
        depth = 0
        while self.peek():
            val = self.pop()[1]
            buf.append(val)
            if val == "(":
                depth += 1
            elif val == ")":
                depth -= 1
                if depth == 0:
                    break
        return " ".join(buf)

    def _read_until_end(self, kind: str) -> None:
        buf: list[str] = []
        paren = bracket = brace = 0
        while self.peek():
            token = self.peek()
            val = token[1]
            newline_before = token[3]
            if (
                newline_before
                and paren == bracket == brace == 0
                and buf
                and self._ends(buf)
                and val not in _CONTINUES
                and not (buf[-1] in _RESTRICTED and False)
            ):
                break
            if buf and newline_before and paren == bracket == brace == 0 and buf[-1] in _RESTRICTED:
                break
            if val == ";" and paren == bracket == brace == 0:
                self.pop()
                break
            if val == "}" and paren == bracket == brace == 0:
                break
            self.pop()
            if val == "function":
                buf.append("function")
                self._finish_nested_function(buf)
                continue
            if val == "class":
                buf.append("class")
                self._finish_nested_class(buf)
                continue
            if val == "=>" and self.next_val() == "{":
                buf.append("=>")
                self.parse_block()
                continue
            buf.append(val)
            if val == "(":
                paren += 1
            elif val == ")":
                paren = max(0, paren - 1)
            elif val == "[":
                bracket += 1
            elif val == "]":
                bracket = max(0, bracket - 1)
            elif val == "{":
                brace += 1
            elif val == "}":
                brace = max(0, brace - 1)
        text = " ".join(buf).strip()
        if text:
            self.units.append(kind + ":" + text)

    def _finish_nested_function(self, buf: list[str]) -> None:
        signature = ["function"]
        while self.peek() and self.next_val() not in {"(", "{", ";"}:
            signature.append(self.pop()[1])
        extra = self._skip_parens()
        if extra:
            signature.append(extra)
        self.units.append("function:" + " ".join(signature))
        if self.next_val() == "{":
            self.parse_block()

    def _finish_nested_class(self, buf: list[str]) -> None:
        signature = ["class"]
        while self.peek() and self.next_val() not in {"{", ";"}:
            signature.append(self.pop()[1])
            if len(signature) > 16:
                break
        self.units.append("class:" + " ".join(signature))
        self._parse_class_body()

    def _ends(self, buf: list[str]) -> bool:
        if not buf:
            return False
        last = buf[-1]
        if last in _CONTINUES:
            return False
        return True

    def _is_type_alias(self, skip: int = 0) -> bool:
        name = self._ahead(skip + 1)
        if not name or not (name[0].isalpha() or name[0] in "_$"):
            return False
        depth = 0
        for offset in range(skip + 1, skip + 12):
            val = self._ahead(offset)
            if not val:
                break
            if val in "([{":
                depth += 1
            elif val in ")]}":
                depth = max(0, depth - 1)
            elif val == "=" and depth == 0:
                return True
            elif val in "{;" and depth == 0:
                return False
        return False

    def _looks_like_method(self) -> bool:
        paren = brace = bracket = 0
        seen_paren = False
        for offset in range(0, len(self.tokens) - self.i):
            val = self._ahead(offset)
            if not val:
                return False
            if val == "(" and brace == bracket == 0:
                seen_paren = True
                paren += 1
                continue
            if val == "(":
                paren += 1
                continue
            if val == ")":
                paren -= 1
                if seen_paren and paren == 0 and brace == bracket == 0:
                    return self._ahead(offset + 1) == "{"
                continue
            if val == "=" and paren == brace == bracket == 0 and not seen_paren:
                return False
            if val in "{;" and paren == brace == bracket == 0 and not seen_paren:
                return False
            if val == "{":
                brace += 1
            elif val == "}":
                if brace == 0:
                    return False
                brace -= 1
            elif val == "[":
                bracket += 1
            elif val == "]":
                bracket = max(0, bracket - 1)
        return False

    def _method_name(self) -> str:
        names = []
        for offset in range(0, 12):
            val = self._ahead(offset)
            if not val or val == "(":
                break
            if val not in {"async", "static", "get", "set", "public", "private", "protected", "readonly", "abstract", "*"}:
                names.append(val)
        return names[-1] if names else "anonymous"

    def _consume_signature(self) -> None:
        while self.peek() and self.next_val() != "(":
            if self.next_val() in {"{", ";"}:
                return
            self.pop()
        self._skip_parens()

    def _ahead(self, offset: int) -> str:
        index = self.i + offset
        if index < len(self.tokens):
            return self.tokens[index][1]
        return ""


def _split_commas(text: str) -> list[str]:
    parts: list[str] = []
    depth = 0
    start = 0
    for index, ch in enumerate(text):
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth = max(0, depth - 1)
        elif ch == "," and depth == 0:
            parts.append(text[start:index])
            start = index + 1
    parts.append(text[start:])
    return parts
