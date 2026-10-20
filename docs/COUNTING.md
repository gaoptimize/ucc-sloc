# Counting rules

This tool measures source size in the spirit of the Unified Code Counter (UCC), using the public counting standards mirrored with UCC 2018.07. It is a separate program. It does not wrap the C++ UCC or the Java UCC-J, and a number from this tool is not an official UCC certificate.

The rules below are the behavior of the code. When a result looks wrong, start here.

## Surprises

- A Python `class` line is physical SLOC and zero logical SLOC. That is UCC example DDL1. The statements inside the class still count. Decorators on the class do count.
- A bare Python string, including a docstring, is a comment. A string on the right-hand side of an assignment is code.
- `else` is not a logical line. `elif` is. `if` and a statement on the same line both count, so `if __name__ == "__main__": main()` is 2 logical lines and 1 physical line.
- A statement spread across several physical lines is still one logical line.
- JavaScript and TypeScript have no UCC standard in the 2018 mirror. Their rules follow the same C-family shape as the Python standard, and they are the main place this tool simplifies.
- HTML counts a start tag once and does not count the end tag. CSS counts each selector and each declaration. Text and braces are not logical lines.
- A `<script>` or `<style>` body on its own lines is counted as JavaScript or CSS. The tags stay HTML. A body written on the same line as its tag stays in the HTML count.
- Logical diff matches statement fingerprints in order. A renamed file is a deletion plus an addition.
- Language is decided by extension only.

## Physical SLOC

One physical line is one source line that is not blank and not a comment. A blank line is whitespace only. A comment line has no code on it. Code with a trailing comment is physical. This is UCC definition 1.2, and it is what the requirements ask for. A line that is only `}` or only text is physical when it is not a comment.

## Python

Source: UCC *Python CodeCount Counting Standard* (2007, template revision 2013).

Counted once:

- `if`, `elif`, `for`, `async for`, `while`, `try`, `except`, `finally`, `with`, `async with`, `match`, `case`
- `def` and `async def`
- each simple statement: assignment, annotated assignment, call, `return`, `raise`, `assert`, `import`, `pass`, `break`, `continue`, `delete`, `global`, `nonlocal`, and a type alias
- each decorator

Counted zero:

- `else`
- the `class` header
- a bare string expression

A backslash continuation or an expression inside `()`, `[]`, or `{}` is one statement. When the file does not parse, each physical line is reported as one logical line and the file is marked `parse_error`, so a broken file does not disappear.

## JavaScript and TypeScript

Extensions: `.js`, `.mjs`, `.cjs`, `.jsx`, `.ts`, `.tsx`, `.mts`, `.cts`.

Counted once:

- `if`, `for`, `while`, `do`, `switch`, `catch`, `try`, `finally`, `function`, `class`, `with`, `interface`, `enum`, `namespace`
- `case` and `default`
- every other statement, including one that ends by a line break instead of a semicolon
- an empty statement (a bare semicolon)
- a method or constructor inside a class
- a function expression, in addition to the statement that contains it
- each interface member and each enum member

Counted zero:

- `else`
- braces
- the semicolons inside `for (...)`
- the `while` that closes `do ... while`, and the semicolon after it

A semicolon, comment marker, or regex marker inside a string or a regex does not end a statement. A JSX element is one token, so a semicolon in JSX text does not start a statement. `export function` and `export class` count as the function or class, not as a second statement.

## SQL

Source: UCC *SQL CodeCount Counting Standard* (2007, revisions through 2014).

Each of these keywords counts once per occurrence outside comments and strings, including inside a nested query: `SELECT`, `INSERT`, `UPDATE`, `DELETE`, `CREATE`, `ALTER`, `DROP`, `TRUNCATE`, `RENAME`, `GRANT`, `REVOKE`, `DECLARE`, `FETCH`, `CLOSE`, `COMMIT`, `ROLLBACK`, `WHERE`, `HAVING`, `LIMIT`, `JOIN`, `UNION`, `IF`, `ELSIF`, `ELSEIF`, `ELSE`, `WHEN`, `LOOP`, `CONTINUE`, `EXIT`, `FOR`, `EXCEPTION`.

`GROUP BY` and `ORDER BY` count as one each. `IF` in `END IF` does not count. `CREATE OR REPLACE` counts as one `CREATE`. A comment or string hides the words inside it.

Each column in a `CREATE TABLE` column list counts once. A column is a top-level item that starts with a name and a type. `PRIMARY KEY`, `FOREIGN KEY`, `UNIQUE`, `CHECK`, and `CONSTRAINT` items are not extra columns.

`SET` and `WITH` are not in the UCC list, so they add a logical line only when the statement also contains a listed keyword. `{ ... }` is not treated as a SQL comment. Line comments are `--`. Block comments are `/* */`.

## HTML

Extensions: `.html`, `.htm`.

Source: UCC *HTML/XML CodeCount Counting Standard* (2007, revisions through 2013).

Counted once:

- a start tag, including a start tag with attributes
- an empty tag such as `<br>` or `<br/>`
- a declaration (`<!DOCTYPE`, `<!ELEMENT`, `<!ATTLIST`, `<!ENTITY`, and the other `<!` forms)
- a processing instruction (`<? ... ?>`)

An end tag is not counted. The logical line is the whole tag, even when the tag spans several physical lines. Comments are `<!-- -->`.

## CSS

Extension: `.css`.

Source: UCC *Cascading Style Sheets CodeCount Counting Standard* (2008, template revision 2013).

A selector counts once. Commas split selectors, except a comma inside parentheses, so `div:is(h1, h2)` is one selector. Each declaration counts once, including the last declaration in a block when it has no semicolon. `@media`, `@supports`, `@container`, `@layer`, `@keyframes`, and `@font-feature-values` count once, and the rules inside them count as well. `@import` and `@charset` count once. Comments are `/* */`.

## What is skipped

The crawler skips these directory names, in any case: `venv`, `.venv`, `env`, `node_modules`, `__pycache__`, `.git`, `dist`, `build`, `.tox`, `.mypy_cache`, `.ucc-history`, `.hg`, `.svn`, `site-packages`, `htmlcov`, `.pytest_cache`, `.ruff_cache`, `.eggs`, and any directory whose name ends in `.egg-info`.

Add more names, or a relative path prefix, in `.uccignore` (one entry per line, `#` starts a comment) or with `--exclude`. A file with a null byte in its first 8 KB is treated as binary and skipped. Files in another language are not counted.

## ESLOC and straight reuse

Effectively new source lines (ESLOC) are the size used for effort. Logical lines stay in the report unchanged.

The counted source has no feature field. Each file's ESLOC is added to the directory module that contains it, and those directories sum upward. The report does not invent a feature name from a folder title or a comment.

A straight-reuse set is two or more counted files whose normalized text is identical. Normalization joins lines with `\n`, so a carriage-return difference does not make a second original. The exemplar is the first path in lexicographic order. Its ESLOC equals its logical size. Each other copy's ESLOC is 2% of that copy's logical size. The 2% is the non-coding cost of the additional unit test and of the final integration that forced the copy. A file that differs, even by one character, keeps its full logical size.

The set name is the exemplar path, `#`, and the first 12 hex digits of the SHA-256 of the normalized text. A file that could not be read has no content id and is never placed in a set.

## Header text

The report stores the leading header with the snapshot and offers it as an ordinary link on the file row.

- Python: the module docstring. When there is no docstring, a leading `#` block. When both exist, the `#` block comes first and the docstring follows.
- JavaScript and TypeScript: a leading `//` block or a leading `/* */` block.
- SQL: a leading `--` block or a leading `/* */` block.
- CSS: a leading `/* */` block.
- HTML: a leading `<!-- -->` block.

A shebang is skipped. A comment that follows code is not a header. The stored text is capped at 20,000 characters. The link reads the snapshot. It does not open the file on disk.

## Snapshots and diff

Each saved run is a JSON file in `.ucc-history`. The report puts runs in time order from left to right. The signed number under a later column is that column minus the one before it.

The four-way row is a diff of logical statement fingerprints, not a diff of physical text:

- unmodified: the same statement in both snapshots
- modified: a statement in the same position whose fingerprint changed
- new: a statement only in the later snapshot
- deleted: a statement only in the earlier snapshot

Changing only a `class` header can leave the logical diff unmodified, because that header is not a logical line. The physical total still moves.

## Out of scope

C, C++, Java, and the other historical UCC languages. Cyclomatic complexity. Generated-code policies beyond the directory exclusions. Byte-for-byte agreement with every UCC edge case. Remote dashboards.
