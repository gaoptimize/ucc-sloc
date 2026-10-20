---
name: ucc-sloc
description: >
  Count physical and logical source lines for Python, JavaScript, TypeScript,
  SQL, HTML, and CSS with the ucc-sloc tool, then read its snapshot report.
  Use when the user asks for SLOC, logical lines, physical lines, a code-size
  or productivity count, a UCC-style count, or runs /ucc-sloc.
---

# UCC-style SLOC

When the user wants a size or productivity number, run this counter. Do not estimate lines by eye, and do not invent a total from a file listing.

## Run

From this repo, with `src` on `PYTHONPATH`:

```powershell
$env:PYTHONPATH = "src"
python -m uccskill <path> --no-serve
```

On the machine where this counter was written, the same command is:

```powershell
$env:PYTHONPATH = "D:\UCCSkill\src"
D:\Python312\python.exe -m uccskill <path> --no-serve
```

`<path>` is the tree to measure, not the tool repo, unless the user asked to measure the tool. Add `--label "what changed"` when the run should show up later beside earlier runs.

Start the local report only when the user wants the browser view:

```powershell
python -m uccskill <path> --no-browser
```

The report is at `http://127.0.0.1:8765/` (or the next free port the command prints). While the count is still running, that page shows files finished over files found and a progress bar. Leave the process running until the user is done with the page.

Use `--git <ref>` to count a commit instead of the working tree. Use `--exclude <name>` or a `.uccignore` file to skip another directory.

## Read the result

Quote the tool's physical, logical, and ESLOC totals, and the per-language rows. If more than one snapshot exists, quote the four-way row (new, modified, deleted, unmodified) and the signed delta. Those numbers are the comparison. ESLOC for a straight-reuse copy follows the rate in `docs/COUNTING.md`. Quote the reuse set name when a file is a copy.

A `parse_error` note means that file did not parse. Say so. Its logical count is one per physical line until it parses.

## Before explaining why a line counted

Read `docs/COUNTING.md` in this repo. The counting notes are the rules. In particular, do not treat a Python `class` line as a logical line, and do not call a JavaScript or TypeScript count an official UCC language standard. UCC published no JavaScript standard in the 2018 mirror.

## Do not

- Do not present the result as an Aerospace or USC UCC certificate. Say it is a UCC-style count from this tool.
- Do not add C, C++, or other languages by relaxing the extension list.
- Do not compare the number with `cloc` or `scc` as if the rules were the same.
- Do not count a straight-reuse copy at full ESLOC.
- Do not invent a feature name. ESLOC rolls up on the directory module that contains the file.
