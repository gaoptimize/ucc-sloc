# ucc-sloc

A local counter for physical and logical source lines of code. It counts Python, JavaScript, TypeScript, SQL, HTML, and CSS.

The counting rules follow the public Unified Code Counter standards shipped with UCC 2018.07. This program does not wrap UCC or UCC-J, and it is not a fork of either one. A result is a UCC-style measurement, not an official UCC certificate. The rules, including the places they simplify, are in [docs/COUNTING.md](docs/COUNTING.md).

You get what you measure. Run the same counter on every snapshot and the productivity claim becomes a column in a table.

## Run

Python 3.11 or newer. No third-party packages.

```powershell
python -m pip install -e .
ucc-sloc D:\some\project
```

That prints a table, saves a snapshot under `D:\some\project\.ucc-history\`, and opens the report at `http://127.0.0.1:8765/`. The page is up while the count runs. It first finds the files, then shows files finished over that file count and a progress bar. When the snapshot is written, the same address becomes the report.

From a checkout, without installing:

```powershell
$env:PYTHONPATH = "src"
python -m uccskill D:\some\project
```

```powershell
ucc-sloc D:\some\project --no-serve
ucc-sloc D:\some\project --no-browser
ucc-sloc D:\some\project --git HEAD --label "at HEAD"
ucc-sloc D:\some\project --exclude vendor --csv size.csv
```

## Report

Snapshots are columns from left to right, oldest first. Each later column shows the change in physical, logical, and ESLOC lines, and a four-way logical diff: new, modified, deleted, unmodified. Click a column for that run's language cards, module tree, and CSV or JSON export. ESLOC sums on the directory that holds each file. An identical copy is straight reuse at 2% of its logical size. A file header, when the file has one, is a link on that row. The page is rendered by the process; it does not use a network font or a front-end build.

## What is counted

| Extension | Language |
| --- | --- |
| `.py` `.pyw` | Python |
| `.js` `.mjs` `.cjs` `.jsx` | JavaScript |
| `.ts` `.tsx` `.mts` `.cts` | TypeScript |
| `.sql` | SQL |
| `.html` `.htm` | HTML, plus `<script>` and `<style>` bodies |
| `.css` | CSS |

These directories are skipped: `venv`, `.venv`, `env`, `node_modules`, `__pycache__`, `.git`, `dist`, `build`, `.tox`, `.mypy_cache`, `.ucc-history`, and the other cache names listed in `docs/COUNTING.md`. Add names or relative prefixes in `.uccignore`.

## Tests

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
```

## Documentation

[docs/COUNTING.md](docs/COUNTING.md) is the counting reference: physical lines, logical lines, straight reuse, ESLOC, headers, and the diff. [NOTICE](NOTICE) names the UCC license that governs the Unified Code Counter itself.

## Skill

Grok loads `.grok/skills/ucc-sloc/SKILL.md` when this repo is the workspace. The skill tells the model to run the counter instead of guessing a line count.

## License

Copyright (c) 2026 Thomas Mark Schaefer. This repository is MIT. See [LICENSE](LICENSE).

UCC is a separate program, Copyright (C) 2006–2018, Center for Systems and Software Engineering, University of Southern California. UCC is distributed under the USC-CSSE Limited Public License, version 1 or any later version. The text shipped with the UCC 2018.07 sources is [license.txt in the public source mirror](https://github.com/cl0ne/Unified-Code-Counter/blob/master/license.txt). That license governs UCC. It does not govern this repository, which contains no UCC source.
