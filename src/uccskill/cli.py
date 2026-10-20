"""Command line for the SLOC counter."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from uccskill.crawl import crawl, crawl_git
from uccskill.report import format_table
from uccskill.server import ReportState, serve_state
from uccskill.snapshot import load_snapshots, save_snapshot, snapshot_document


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ucc-sloc",
        description="Count physical and logical SLOC and open a local report.",
    )
    parser.add_argument("path", nargs="?", default=".", help="File or directory to count")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-serve", action="store_true", help="Print the table and do not start the report")
    parser.add_argument("--no-browser", action="store_true", help="Start the report without opening a browser")
    parser.add_argument("--no-save", action="store_true", help="Do not write a snapshot")
    parser.add_argument("--history", help="Snapshot directory (default: <path>/.ucc-history)")
    parser.add_argument("--exclude", action="append", default=[], help="Directory name or relative prefix to skip")
    parser.add_argument("--git", help="Count the tree at this git ref instead of the working tree")
    parser.add_argument("--label", default="", help="Name for this snapshot column")
    parser.add_argument("--csv", help="Also write a CSV file")
    parser.add_argument("--json", help="Also write the snapshot JSON to this path")
    args = parser.parse_args(argv)

    root = Path(args.path).resolve()
    if not root.exists():
        print(f"Path not found: {root}", file=sys.stderr)
        return 1
    state = None
    httpd = None
    if not args.no_serve:
        state = ReportState(echo=True)
        try:
            httpd = serve_state(state, port=args.port, open_browser=not args.no_browser)
        except OSError as exc:
            print(str(exc), file=sys.stderr)
            return 1
    try:
        if args.git:
            if not root.is_dir():
                print("--git needs a repository directory", file=sys.stderr)
                if httpd is not None:
                    httpd.shutdown()
                return 1
            files = crawl_git(root, args.git, args.exclude, progress=state)
        else:
            files = crawl(root, args.exclude, progress=state)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        if httpd is not None:
            httpd.shutdown()
        return 1

    print(format_table(files))
    history = Path(args.history).resolve() if args.history else _default_history(root)
    saved = None
    if not args.no_save:
        if state is not None:
            state.saving()
        saved = save_snapshot(
            history,
            files,
            root=str(root),
            label=args.label,
            git_ref=args.git,
        )
        print(f"Snapshot {saved}")
    if args.csv:
        _write_csv(Path(args.csv), files)
    if args.json:
        document = snapshot_document(
            files,
            root=str(root),
            label=args.label,
            git_ref=args.git,
            snapshot_id=saved.stem if saved is not None else None,
        )
        Path(args.json).write_text(json.dumps(document, indent=2), encoding="utf-8")
    if args.no_serve:
        return 0
    if args.no_save and not history.is_dir():
        print("Nothing to serve. Save a snapshot or drop --no-save.", file=sys.stderr)
        httpd.shutdown()
        return 1
    state.finish(load_snapshots(history))
    try:
        httpd.report_thread.join()
    except KeyboardInterrupt:
        print("\nStopped.")
        httpd.shutdown()
    return 0


def _default_history(root: Path) -> Path:
    base = root if root.is_dir() else root.parent
    return base / ".ucc-history"


def _write_csv(path: Path, files) -> None:
    from uccskill.report import csv_rows

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        csv.writer(handle).writerows(csv_rows(files))


if __name__ == "__main__":
    sys.exit(main())
