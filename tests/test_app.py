"""Crawler, snapshots, diff, and the local report."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from uccskill.cli import main
from uccskill.crawl import crawl, crawl_git
from uccskill.diff import diff_files
from uccskill.header import extract_header
from uccskill.report_html import render_page
from uccskill.reuse import classify
from uccskill.server import ReportState, serve, serve_state
from uccskill.snapshot import load_snapshots, save_snapshot


class AppTests(unittest.TestCase):
    def test_crawl_skips_noise_and_ignore_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "pkg").mkdir()
            (root / "pkg" / "app.py").write_text("x = 1\n", encoding="utf-8")
            (root / "node_modules").mkdir()
            (root / "node_modules" / "lib.js").write_text("const a = 1;\n", encoding="utf-8")
            (root / "skip_me").mkdir()
            (root / "skip_me" / "hidden.py").write_text("y = 2\n", encoding="utf-8")
            (root / ".uccignore").write_text("skip_me\n", encoding="utf-8")
            (root / "page.html").write_text("<p>Hi</p>\n", encoding="utf-8")
            records = crawl(root)
            self.assertEqual(sorted(record.path for record in records), ["page.html", "pkg/app.py"])

    def test_diff_marks_modified_new_and_unmodified(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.py").write_text("x = 1\ny = 2\n", encoding="utf-8")
            old = crawl(root)
            (root / "a.py").write_text("x = 1\ny = 3\n", encoding="utf-8")
            (root / "b.py").write_text("z = 4\n", encoding="utf-8")
            new = crawl(root)
            result = diff_files(old, new)
            self.assertEqual(result["total"]["unmodified"], 1)
            self.assertEqual(result["total"]["modified"], 1)
            self.assertEqual(result["total"]["new"], 1)
            self.assertEqual(result["total"]["deleted"], 0)

    def test_report_and_server_show_two_snapshots(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            history = root / ".ucc-history"
            (root / "a.py").write_text("x = 1\n\n# c\n", encoding="utf-8")
            (root / "node_modules").mkdir()
            (root / "node_modules" / "b.py").write_text("y = 2\n", encoding="utf-8")
            first = crawl(root)
            save_snapshot(history, first, root=str(root), label="one")
            (root / "a.py").write_text("x = 1\nz = 3\n", encoding="utf-8")
            second = crawl(root)
            save_snapshot(history, second, root=str(root), label="two")
            snapshots = load_snapshots(history)
            page = render_page(snapshots, None)
            self.assertIn("one", page)
            self.assertIn("two", page)
            self.assertIn("a.py", page)
            self.assertNotIn("node_modules", page)
            self.assertIn("data-logical='2'", page)
            httpd = serve(history, port=0, open_browser=False)
            try:
                url = f"http://127.0.0.1:{httpd.server_address[1]}"
                html = urllib.request.urlopen(url + "/").read().decode("utf-8")
                self.assertIn("data-logical='2'", html)
                rules = urllib.request.urlopen(url + "/rules").read().decode("utf-8")
                self.assertIn("Physical", rules)
                exported = urllib.request.urlopen(url + "/export.csv?snapshot=" + snapshots[-1]["id"])
                self.assertIn(b"a.py", exported.read())
                payload = json.loads(urllib.request.urlopen(url + "/export.json").read().decode("utf-8"))
                self.assertEqual(payload["files"][0]["path"], "a.py")
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    urllib.request.urlopen(url + "/missing")
                self.assertEqual(caught.exception.code, 404)
            finally:
                httpd.shutdown()
                httpd.server_close()

    def test_cli_saves_without_serving(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.sql").write_text("SELECT 1;\n", encoding="utf-8")
            code = main([str(root), "--no-serve", "--label", "cli"])
            self.assertEqual(code, 0)
            saved = list((root / ".ucc-history").glob("*.json"))
            self.assertEqual(len(saved), 1)
            self.assertIn("cli", saved[0].read_text(encoding="utf-8"))

    def test_git_ref(self):
        git = __import__("shutil").which("git")
        if not git:
            self.skipTest("git is not installed")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.py").write_text("x = 1\n", encoding="utf-8")
            _git(root, "init")
            _git(root, "add", "a.py")
            _git(root, "-c", "user.email=ucc@example.com", "-c", "user.name=ucc", "commit", "-m", "one")
            (root / "a.py").write_text("x = 1\ny = 2\n", encoding="utf-8")
            committed = crawl_git(root, "HEAD")
            working = crawl(root)
            self.assertEqual(sum(part.logical for record in committed for part in record.parts), 1)
            self.assertEqual(sum(part.logical for record in working for part in record.parts), 2)


    def test_progress_page_shows_the_file_count(self):
        state = ReportState()
        httpd = serve_state(state, port=0, open_browser=False)
        try:
            url = f"http://127.0.0.1:{httpd.server_address[1]}/"
            state.scanning(r"D:\Javex\hub")
            finding = urllib.request.urlopen(url).read().decode("utf-8")
            self.assertIn('data-progress="finding"', finding)
            self.assertIn("Finding files", finding)
            self.assertIn("<progress", finding)
            self.assertIn(r"D:\Javex\hub", finding)
            state.found(4)
            state.tick(1, "pkg/a.py")
            counting = urllib.request.urlopen(url).read().decode("utf-8")
            self.assertIn('data-progress="1/4"', counting)
            self.assertIn("1 / 4", counting)
            self.assertIn("value='1'", counting)
            self.assertIn("max='4'", counting)
            state.finish([])
            done = urllib.request.urlopen(url).read().decode("utf-8")
            self.assertIn("No snapshots yet", done)
            self.assertNotIn('http-equiv="refresh"', done)
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_crawl_counts_files_before_parsing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.py").write_text("x = 1\n", encoding="utf-8")
            (root / "b.js").write_text("const a = 1;\n", encoding="utf-8")
            (root / "notes.txt").write_text("skip\n", encoding="utf-8")
            state = ReportState()
            records = crawl(root, progress=state)
            self.assertEqual(state.total, 2)
            self.assertEqual(state.done, 2)
            self.assertEqual(sorted(record.path for record in records), ["a.py", "b.js"])

    def test_straight_reuse_is_two_percent_and_header_opens(self):
        body = '"""Alpha.\n"""\nx = 1\n'
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = root / "pkg"
            package.mkdir()
            (package / "a.py").write_text(body, encoding="utf-8", newline="\n")
            (package / "z.py").write_bytes(body.replace("\n", "\r\n").encode("utf-8"))
            records = crawl(root)
            info = classify(records)
            self.assertEqual(info["pkg/a.py"].role, "exemplar")
            self.assertEqual(info["pkg/z.py"].role, "copy")
            self.assertEqual(str(info["pkg/a.py"].esloc), "1")
            self.assertEqual(str(info["pkg/z.py"].esloc), "0.02")
            self.assertEqual(records[0].header, "Alpha.")
            history = root / ".ucc-history"
            save_snapshot(history, records, root=str(root), label="reuse")
            snapshots = load_snapshots(history)
            page = render_page(snapshots, None)
            self.assertIn("data-esloc='1.02'", page)
            self.assertIn("straight reuse of pkg/a.py", page)
            self.assertIn(">header</a>", page)
            self.assertIn("1.02 ESLOC", page)
            httpd = serve(history, port=0, open_browser=False)
            try:
                url = f"http://127.0.0.1:{httpd.server_address[1]}"
                snapshot_id = snapshots[-1]["id"]
                header_url = f"{url}/header?snapshot={snapshot_id}&path=pkg/a.py"
                opened = urllib.request.urlopen(header_url).read().decode("utf-8")
                self.assertIn("Alpha.", opened)
                self.assertIn("pkg/a.py", opened)
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    urllib.request.urlopen(url + "/header?path=missing.py")
                self.assertEqual(caught.exception.code, 404)
            finally:
                httpd.shutdown()
                httpd.server_close()

    def test_changed_byte_is_not_reuse(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.py").write_text("x = 1\n", encoding="utf-8")
            (root / "b.py").write_text("x = 2\n", encoding="utf-8")
            info = classify(crawl(root))
            self.assertEqual(info["a.py"].role, "unique")
            self.assertEqual(info["b.py"].role, "unique")

    def test_header_text_by_language(self):
        self.assertEqual(extract_header("python", '"""Alpha.\n\nBeta."""\nx = 1\n'), "Alpha.\n\nBeta.")
        self.assertEqual(extract_header("python", "# Alpha\n# Beta\n\nx = 1\n"), "Alpha\nBeta")
        self.assertEqual(extract_header("python", "x = 1\n# later\n"), "")
        self.assertEqual(
            extract_header("javascript", "/* Alpha */\nconst a = 1;\n"),
            "Alpha",
        )
        self.assertEqual(
            extract_header("javascript", "// Alpha\n// Beta\nconst a = 1;\n"),
            "Alpha\nBeta",
        )
        self.assertEqual(extract_header("sql", "-- Alpha\nSELECT 1;\n"), "Alpha")
        self.assertEqual(extract_header("html", "<!-- Alpha -->\n<p>Hi</p>\n"), "Alpha")
        self.assertEqual(extract_header("html", "<!DOCTYPE html>\n<p></p>\n"), "")
        self.assertEqual(
            extract_header("css", "/* Alpha */\nbody { color: black; }\n"),
            "Alpha",
        )
        self.assertEqual(
            extract_header("python", "#!/usr/bin/env python\n\"\"\"Alpha\"\"\"\nx = 1\n"),
            "Alpha",
        )


def _git(root: Path, *args: str) -> None:
    import subprocess

    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


if __name__ == "__main__":
    unittest.main()
