"""Language dispatch. Extension decides the language. No content sniffing."""

from __future__ import annotations

from uccskill.model import Part

from .js_lang import count_script
from .markup import count_css, count_html
from .python_lang import count_python
from .sql_lang import count_sql

EXTENSIONS = {
    ".py": "python",
    ".pyw": "python",
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".mts": "typescript",
    ".cts": "typescript",
    ".sql": "sql",
    ".html": "html",
    ".htm": "html",
    ".css": "css",
}


def language_for(suffix: str) -> str | None:
    return EXTENSIONS.get(suffix.lower())


def count_source(language: str, text: str) -> list[Part]:
    if language == "python":
        return [count_python(text)]
    if language in {"javascript", "typescript"}:
        return [count_script(text, language)]
    if language == "sql":
        return [count_sql(text)]
    if language == "css":
        return [count_css(text)]
    if language == "html":
        return count_html(text)
    raise ValueError(f"unsupported language: {language}")
