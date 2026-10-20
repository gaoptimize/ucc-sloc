"""Server-rendered local report. The page works without client-side script."""

from __future__ import annotations

import html
from decimal import Decimal
from pathlib import Path
from urllib.parse import quote

from uccskill.report import build_columns, build_tree, language_names, notes_for
from uccskill.reuse import format_esloc, straight_reuse_sets


def render_page(snapshots: list[dict], selected_id: str | None, rules_href: str = "/rules") -> str:
    columns = build_columns(snapshots)
    selected = _selected(columns, selected_id)
    detail_files = []
    if selected is not None:
        for snapshot in snapshots:
            if snapshot["id"] == selected["id"]:
                detail_files = snapshot["files"]
                break
    tree = build_tree(detail_files) if detail_files else None
    notes = notes_for(detail_files)
    title = selected["label"] or selected["id"] if selected else "SLOC"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SLOC {html.escape(title)}</title>
<style>
:root {{
  --paper: #f3efe4;
  --card: #fffdf8;
  --ink: #1c1915;
  --muted: #5e584e;
  --line: #ddd4c4;
  --green: #1f6b4a;
  --green-soft: #e5f2eb;
  --red: #8c2f2f;
  --red-soft: #f8e8e4;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  background: var(--paper);
  color: var(--ink);
  font: 16px/1.45 Palatino Linotype, Palatino, Georgia, serif;
}}
header {{
  padding: 28px 32px 18px;
  border-bottom: 1px solid var(--line);
}}
header h1 {{
  margin: 0;
  font-size: 28px;
  font-weight: 600;
  letter-spacing: -0.02em;
}}
header p {{ margin: 6px 0 0; color: var(--muted); }}
main {{ padding: 22px 32px 48px; }}
.scroll {{ overflow-x: auto; border: 1px solid var(--line); background: var(--card); }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{
  padding: 8px 12px;
  text-align: right;
  border-bottom: 1px solid var(--line);
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
  font-family: Consolas, "Cascadia Mono", ui-monospace, monospace;
  font-size: 14px;
}}
th:first-child, td:first-child {{ text-align: left; font-family: Palatino Linotype, Palatino, Georgia, serif; }}
th a {{ color: inherit; }}
th.selected {{ background: var(--green-soft); }}
.up {{ color: var(--green); }}
.down {{ color: var(--red); }}
.cards {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 12px;
  margin: 22px 0;
}}
.card {{
  background: var(--card);
  border: 1px solid var(--line);
  padding: 14px 16px;
}}
.card span {{ display: block; color: var(--muted); font-size: 13px; }}
.card strong {{
  display: block;
  margin-top: 4px;
  font-family: Consolas, "Cascadia Mono", ui-monospace, monospace;
  font-size: 28px;
  font-weight: 500;
}}
h2 {{ font-size: 20px; margin: 28px 0 10px; }}
details {{ background: var(--card); border: 1px solid var(--line); margin-top: -1px; }}
summary {{ cursor: pointer; padding: 8px 12px; }}
summary .nums, .file .nums {{
  float: right;
  font-family: Consolas, "Cascadia Mono", ui-monospace, monospace;
  color: var(--muted);
}}
.file {{ padding: 6px 12px 6px 28px; border-top: 1px solid var(--line); }}
.nested {{ margin-left: 16px; }}
.notes {{ background: var(--red-soft); border: 1px solid var(--line); padding: 10px 14px; }}
footer {{ color: var(--muted); margin-top: 28px; }}
a {{ color: var(--green); }}
</style>
</head>
<body>
<header>
  <h1>Source lines</h1>
  <p>Physical lines exclude blanks and comments. Logical lines follow the counting notes. ESLOC sums on the directory module that holds each file. An identical copy counts at 2% of its logical size. Snapshots run left to right.</p>
</header>
<main>
{_columns_html(columns, selected["id"] if selected else None)}
{_detail_html(selected, tree, notes, detail_files)}
<footer>
  <a href="{html.escape(rules_href)}">Counting rules</a>
  · This report is UCC-style. It is not an official Unified Code Counter certificate.
</footer>
</main>
</body>
</html>
"""


def render_progress(phase: str, total: int, done: int, current: str) -> str:
    if phase == "saving":
        heading = "Writing the snapshot"
        fraction = f"{done} / {total}" if total else "Saving"
        bar = _progress_bar(done, total or 1)
    elif total:
        heading = "Counting files"
        percent = int(done * 100 / total)
        fraction = f"{done} / {total} · {percent}%"
        bar = _progress_bar(done, total)
    else:
        heading = "Finding files"
        fraction = "Looking through the tree"
        bar = "<progress aria-label='Finding files'></progress>"
    where = f"<p class='current'>{html.escape(current)}</p>" if current else ""
    marker = f"{done}/{total}" if total or phase == "saving" else "finding"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="1">
<title>{html.escape(heading)}</title>
<style>
:root {{
  --paper: #f3efe4;
  --card: #fffdf8;
  --ink: #1c1915;
  --muted: #5e584e;
  --line: #ddd4c4;
  --green: #1f6b4a;
}}
body {{
  margin: 0;
  background: var(--paper);
  color: var(--ink);
  font: 16px/1.45 Palatino Linotype, Palatino, Georgia, serif;
}}
main {{ max-width: 720px; margin: 48px auto; padding: 0 24px; }}
h1 {{ font-size: 28px; font-weight: 600; margin: 0 0 8px; }}
.fraction {{
  font: 28px/1.2 Consolas, "Cascadia Mono", ui-monospace, monospace;
  margin: 0 0 18px;
}}
.current {{ color: var(--muted); word-break: break-all; }}
progress {{
  width: 100%;
  height: 22px;
  border: 1px solid var(--line);
  background: var(--card);
  color: var(--green);
}}
progress::-webkit-progress-bar {{ background: var(--card); }}
progress::-webkit-progress-value {{ background: var(--green); }}
progress::-moz-progress-bar {{ background: var(--green); }}
</style>
</head>
<body data-progress="{marker}">
<main>
  <h1>{html.escape(heading)}</h1>
  <p class="fraction">{html.escape(fraction)}</p>
  {bar}
  {where}
</main>
</body>
</html>
"""


def _progress_bar(done: int, total: int) -> str:
    return (
        f"<progress value='{done}' max='{total}' "
        f"aria-label='{done} of {total} files'></progress>"
    )


def render_rules(markdown: str) -> str:
    body = html.escape(markdown)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Counting rules</title>
<style>
body {{ margin: 32px; background: #f3efe4; color: #1c1915; font: 16px/1.45 Palatino Linotype, Palatino, Georgia, serif; }}
pre {{ white-space: pre-wrap; font: 14px/1.45 Consolas, ui-monospace, monospace; }}
a {{ color: #1f6b4a; }}
</style>
</head>
<body>
<p><a href="/">Back to the report</a></p>
<pre>{body}</pre>
</body>
</html>
"""


def rules_text() -> str:
    candidate = Path(__file__).resolve().parents[2] / "docs" / "COUNTING.md"
    if candidate.is_file():
        return candidate.read_text(encoding="utf-8")
    return "Counting rules file was not found next to this installation.\n"


def _selected(columns: list[dict], selected_id: str | None) -> dict | None:
    if not columns:
        return None
    if selected_id:
        for column in columns:
            if column["id"] == selected_id:
                return column
    return columns[-1]


def _columns_html(columns: list[dict], selected_id: str | None) -> str:
    if not columns:
        return "<p>No snapshots yet.</p>"
    languages: set[str] = set()
    for column in columns:
        languages.update(column["by_language"])
    names = language_names(languages)
    head = ["<div class='scroll'><table>", "<thead><tr><th>Measure</th>"]
    for column in columns:
        klass = " class='selected'" if column["id"] == selected_id else ""
        label = column["label"] or _short_time(column["created"])
        head.append(
            f"<th{klass}><a href='?snapshot={html.escape(column['id'])}'>"
            f"{html.escape(label)}</a></th>"
        )
    head.append("</tr></thead><tbody>")
    rows = ["".join(head)]
    rows.append(_measure_row("Logical", columns, selected_id, "logical", "delta_logical"))
    rows.append(_measure_row("Physical", columns, selected_id, "physical", "delta_physical"))
    rows.append(_measure_row("ESLOC", columns, selected_id, "esloc", "delta_esloc"))
    rows.append(_plain_row("Files", [str(column["files"]) for column in columns], selected_id, columns))
    for name in names:
        cells = []
        for index, column in enumerate(columns):
            bucket = column["by_language"].get(name)
            value = bucket["logical"] if bucket else 0
            if index == 0:
                delta = None
            elif bucket is not None and bucket.get("delta_logical") is not None:
                delta = bucket["delta_logical"]
            else:
                earlier = columns[index - 1]["by_language"].get(name, {}).get("logical", 0)
                delta = value - earlier
            cells.append(_with_delta(value, delta))
        rows.append(_plain_row(name, cells, selected_id, columns, raw=True))
    rows.append(_diff_row("New", columns, selected_id, "new"))
    rows.append(_diff_row("Modified", columns, selected_id, "modified"))
    rows.append(_diff_row("Deleted", columns, selected_id, "deleted"))
    rows.append(_diff_row("Unmodified", columns, selected_id, "unmodified"))
    rows.append("</tbody></table></div>")
    if len(columns) == 1:
        rows.append("<p>One snapshot so far. The next run lines up beside this one.</p>")
    return "\n".join(rows)


def _measure_row(label, columns, selected_id, key, delta_key) -> str:
    cells = []
    for column in columns:
        cells.append(_with_delta(column[key], column[delta_key]))
    marker = ""
    if key in {"logical", "esloc"} and columns:
        current = next((column for column in columns if column["id"] == selected_id), columns[-1])
        shown = format_esloc(current[key]) if isinstance(current[key], Decimal) else current[key]
        marker = f" data-{key}='{shown}'"
    return _plain_row(label, cells, selected_id, columns, raw=True, attr=marker)


def _diff_row(label, columns, selected_id, key) -> str:
    cells = []
    for column in columns:
        if not column["diff"]:
            cells.append("—")
        else:
            cells.append(str(column["diff"]["total"][key]))
    return _plain_row(label, cells, selected_id, columns, raw=True)


def _plain_row(label, cells, selected_id, columns, raw=False, attr="") -> str:
    parts = [f"<tr{attr}><td>{html.escape(label)}</td>"]
    for column, cell in zip(columns, cells):
        klass = " class='selected'" if column["id"] == selected_id else ""
        shown = cell if raw else html.escape(cell)
        parts.append(f"<td{klass}>{shown}</td>")
    parts.append("</tr>")
    return "".join(parts)


def _with_delta(value, delta) -> str:
    shown = format_esloc(value) if isinstance(value, Decimal) else str(value)
    if delta is None:
        return shown
    if isinstance(delta, Decimal):
        sign = f"+{format_esloc(delta)}" if delta > 0 else format_esloc(delta)
    else:
        sign = f"+{delta}" if delta > 0 else str(delta)
    klass = "up" if delta > 0 else "down" if delta < 0 else ""
    return f"{shown} <span class='{klass}'>{sign}</span>"


def _detail_html(selected, tree, notes: list[str], files) -> str:
    if selected is None or tree is None:
        return ""
    languages = selected["by_language"]
    cards = [
        _card("Logical", selected["logical"]),
        _card("ESLOC", format_esloc(selected["esloc"])),
        _card("Physical", selected["physical"]),
        _card("Files", selected["files"]),
    ]
    for name in language_names(set(languages)):
        cards.append(_card(name, languages[name]["logical"]))
    export = (
        f"<p><a href='/export.csv?snapshot={html.escape(selected['id'])}'>CSV</a>"
        f" · <a href='/export.json?snapshot={html.escape(selected['id'])}'>JSON</a></p>"
    )
    note_html = ""
    if notes:
        items = "".join(f"<li>{html.escape(note)}</li>" for note in notes)
        note_html = f"<div class='notes'><ul>{items}</ul></div>"
    return (
        "<h2>This snapshot</h2>"
        + note_html
        + f"<div class='cards'>{''.join(cards)}</div>"
        + export
        + _reuse_html(files)
        + "<h2>Modules</h2>"
        + _tree_html(tree, selected["id"], open_root=True)
    )


def _card(label, value) -> str:
    return f"<div class='card'><span>{html.escape(label)}</span><strong>{value}</strong></div>"


def _reuse_html(files) -> str:
    sets = straight_reuse_sets(files)
    if not sets:
        return ""
    rows = []
    for item in sets:
        rows.append(
            "<div class='file'>"
            f"<span class='nums'>{item['copies']} copies · {format_esloc(item['copy_esloc'])} ESLOC</span>"
            f"{html.escape(item['name'])}"
            "</div>"
        )
    return (
        "<h2>Straight reuse</h2>"
        f"<details><summary>{len(sets)} sets at 2%</summary>"
        + "".join(rows)
        + "</details>"
    )


def _tree_html(node: dict, snapshot_id: str, open_root: bool = False) -> str:
    chunks = []
    directories = [node["dirs"][name] for name in sorted(node["dirs"], key=str.lower)]
    files = sorted(node["files"], key=lambda item: item["name"].lower())
    for child in directories:
        label = (
            f"<span class='nums'>{_size_label(child)}</span>"
            f"{html.escape(child['name'])}"
        )
        chunks.append(
            "<details>"
            f"<summary>{label}</summary>"
            f"<div class='nested'>{_tree_html(child, snapshot_id)}</div>"
            "</details>"
        )
    for item in files:
        parts = ", ".join(
            f"{html.escape(part['language'])} {part['logical']}"
            for part in item["parts"]
        )
        chunks.append(
            "<div class='file'>"
            f"<span class='nums'>{_size_label(item)}</span>"
            f"{html.escape(item['path'])}"
            f"{_header_link(snapshot_id, item)}"
            f"{_reuse_label(item)}"
            f"<div>{parts}</div>"
            "</div>"
        )
    body = "".join(chunks) or "<div class='file'>No counted files.</div>"
    if open_root:
        total = f"<span class='nums'>{_size_label(node)}</span>All files"
        return f"<details open><summary>{total}</summary>{body}</details>"
    return body


def _size_label(node: dict) -> str:
    return (
        f"{format_esloc(node['esloc'])} ESLOC · "
        f"{node['logical']} logical · {node['physical']} physical"
    )


def _header_link(snapshot_id: str, item: dict) -> str:
    if not item.get("header"):
        return ""
    href = (
        "/header?snapshot="
        + quote(snapshot_id, safe="")
        + "&path="
        + quote(item["path"], safe="")
    )
    return f" <a href='{html.escape(href)}'>header</a>"


def _reuse_label(item: dict) -> str:
    if item.get("role") == "copy":
        return f" <span class='reuse'>straight reuse of {html.escape(item['exemplar'])}</span>"
    if item.get("role") == "exemplar":
        return " <span class='reuse'>exemplar</span>"
    return ""


def render_header(path: str, header: str, back_href: str) -> str:
    body = html.escape(header) if header else "This file has no header."
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Header {html.escape(path)}</title>
<style>
body {{ margin: 32px; background: #f3efe4; color: #1c1915; font: 16px/1.45 Palatino Linotype, Palatino, Georgia, serif; }}
pre {{ white-space: pre-wrap; font: 15px/1.45 Palatino Linotype, Palatino, Georgia, serif; }}
a {{ color: #1f6b4a; }}
</style>
</head>
<body>
<p><a href="{html.escape(back_href)}">Back to the report</a></p>
<h1>{html.escape(path)}</h1>
<pre>{body}</pre>
</body>
</html>
"""


def _short_time(created: str) -> str:
    text = created.replace("T", " ")
    return text[:19] if text else "snapshot"
