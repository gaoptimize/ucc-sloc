"""Counting rules locked to the UCC examples cited in docs."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from uccskill.languages import count_source
from uccskill.languages.markup import count_css, count_html
from uccskill.languages.python_lang import count_python
from uccskill.languages.sql_lang import count_sql
from uccskill.languages.js_lang import count_script


def _show(part):
    return (
        f"logical={part.logical} physical={part.physical} "
        f"blank={part.blank} comment={part.comment} lines={part.lines}\n"
        f"units={part.units}\nnotes={part.notes}"
    )


def assert_part(testcase, part, logical, physical, blank=None, comment=None):
    testcase.assertEqual(part.blank + part.comment + part.physical, part.lines, _show(part))
    testcase.assertEqual(part.logical, logical, _show(part))
    testcase.assertEqual(part.physical, physical, _show(part))
    if blank is not None:
        testcase.assertEqual(part.blank, blank, _show(part))
    if comment is not None:
        testcase.assertEqual(part.comment, comment, _show(part))


class PythonTests(unittest.TestCase):
    def test_if_else_ess1(self):
        src = 'if password == "name":\n    print("Access Granted")\nelse:\n    print("Access Denied")\n'
        # if, print, else=0, print
        assert_part(self, count_python(src), logical=3, physical=4)

    def test_elif_chain(self):
        src = (
            "if num > 0:\n"
            "    print('positive')\n"
            "elif num < 0:\n"
            "    print('negative')\n"
            "else:\n"
            "    print('zero')\n"
        )
        assert_part(self, count_python(src), logical=5, physical=6)

    def test_class_header_is_not_logical(self):
        src = "class MyClass:\n    i = 12345\n    def f(self):\n        return 'hello'\n"
        assert_part(self, count_python(src), logical=3, physical=4)

    def test_def_counts(self):
        src = (
            "def knights():\n"
            "    title = 'Sir'\n"
            "    action = (lambda x: title + ' ' + x)\n"
            "    return action\n"
            "act = knights()\n"
            "print(act('robin'))\n"
        )
        assert_part(self, count_python(src), logical=6, physical=6)

    def test_backslash_continuation_is_one_statement(self):
        src = (
            "bar = 'this is ' \\\n"
            "      'one long string ' \\\n"
            "      'that is split ' \\\n"
            "      'across multiple lines'\n"
            "print(bar)\n"
        )
        assert_part(self, count_python(src), logical=2, physical=5)

    def test_implicit_join(self):
        src = "day = ['mon', 'tue',\n    'wed', 'thur', 'fri',\n    'sat', 'sun']\n"
        assert_part(self, count_python(src), logical=1, physical=3)

    def test_return_dict_is_one_statement(self):
        src = (
            "def node(name):\n"
            "    return {\n"
            "        'Parent': None,\n"
            "        'Name': name,\n"
            "    }\n"
        )
        assert_part(self, count_python(src), logical=2, physical=5)

    def test_docstring_is_comment(self):
        src = 'def f():\n    """doc\n    line\n    """\n    return 1\n'
        assert_part(self, count_python(src), logical=2, physical=2, comment=3, blank=0)

    def test_blank_line(self):
        src = "x = 1\n\ny = 2\n"
        assert_part(self, count_python(src), logical=2, physical=2, blank=1, comment=0)

    def test_inline_comment_stays_physical(self):
        src = "# hi\nx = 1  # no\n"
        assert_part(self, count_python(src), logical=1, physical=1, comment=1)

    def test_header_and_statement_on_one_line(self):
        src = 'if __name__ == "__main__": outahere()\n'
        assert_part(self, count_python(src), logical=2, physical=1)

    def test_pass_and_else(self):
        src = "if month == 1:\n    pass\nelse:\n    print('late')\n"
        assert_part(self, count_python(src), logical=3, physical=4)

    def test_try_except(self):
        src = "try:\n    1/0\nexcept ZeroDivisionError:\n    print('e')\n"
        assert_part(self, count_python(src), logical=4, physical=4)

    def test_decorator_extension(self):
        src = "@property\ndef f(self):\n    return 1\n"
        assert_part(self, count_python(src), logical=3, physical=3)

    def test_parse_error_does_not_drop_the_file(self):
        part = count_python("def f(:\n    return 1\n")
        self.assertTrue(any("parse_error" in note for note in part.notes))
        self.assertGreater(part.physical, 0)
        self.assertEqual(part.logical, part.physical)

    def test_assignment_string_is_code(self):
        src = 'x = """\nhello\n"""\n'
        part = count_python(src)
        self.assertEqual(part.logical, 1, _show(part))
        self.assertGreaterEqual(part.physical, 2, _show(part))


class ScriptTests(unittest.TestCase):
    def test_function_and_return(self):
        src = "function f() {\n  return 1;\n}\n"
        assert_part(self, count_script(src, "javascript"), logical=2, physical=3)

    def test_if_else(self):
        src = (
            'if (password == "name") {\n'
            '  console.log("Access Granted");\n'
            "} else {\n"
            '  console.log("Access Denied");\n'
            "}\n"
        )
        assert_part(self, count_script(src, "javascript"), logical=3, physical=5)

    def test_for_header_semicolons_do_not_count(self):
        src = "for (let i = 0; i < n; i++) {\n  total += i;\n}\n"
        assert_part(self, count_script(src, "javascript"), logical=2, physical=3)

    def test_array_is_one_statement(self):
        src = "const day = [\n  'mon', 'tue',\n  'wed'\n];\n"
        assert_part(self, count_script(src, "javascript"), logical=1, physical=4)

    def test_semicolon_inside_string_and_regex(self):
        src = 'const s = ";";\nconst re = /;/;\n'
        assert_part(self, count_script(src, "javascript"), logical=2, physical=2)

    def test_asi(self):
        src = "const a = 1\nconst b = 2\n"
        assert_part(self, count_script(src, "javascript"), logical=2, physical=2)

    def test_continuation(self):
        src = "const a = 1 +\n  2\n"
        assert_part(self, count_script(src, "javascript"), logical=1, physical=2)

    def test_comment(self):
        src = "// only\nconst a = 1;\n"
        assert_part(self, count_script(src, "javascript"), logical=1, physical=1, comment=1)

    def test_class_method(self):
        src = "class A {\n  m() {\n    return 1;\n  }\n}\n"
        assert_part(self, count_script(src, "typescript"), logical=3, physical=5)

    def test_jsx_semicolon_is_text(self):
        src = "function App() {\n  return <div>a; b</div>;\n}\n"
        assert_part(self, count_script(src, "typescript"), logical=2, physical=3)

    def test_interface_members(self):
        src = "interface Foo {\n  a: string;\n  b: number;\n}\n"
        assert_part(self, count_script(src, "typescript"), logical=3, physical=4)

    def test_do_while_counts_once(self):
        src = "do {\n  work();\n} while (ready);\n"
        assert_part(self, count_script(src, "javascript"), logical=2, physical=3)


class SqlTests(unittest.TestCase):
    def test_nested_select(self):
        src = (
            "SELECT city FROM cities\n"
            "WHERE city IN\n"
            "( SELECT city FROM country\n"
            "  WHERE id='1')\n"
        )
        assert_part(self, count_sql(src), logical=4, physical=4)

    def test_insert_is_one(self):
        src = "INSERT INTO colors (cnum, color) VALUES\n('C1', 'green');\n"
        assert_part(self, count_sql(src), logical=1, physical=2)

    def test_create_table_columns(self):
        src = (
            "CREATE TABLE locals\n"
            "(ct VARCHAR(5) NOT NULL\n"
            " PRIMARY KEY,\n"
            " name VARCHAR(16),\n"
            " city VARCHAR(16)\n"
            ");\n"
        )
        assert_part(self, count_sql(src), logical=4, physical=6)

    def test_comment_and_keyword_in_string(self):
        src = "-- comment\nSELECT 'SELECT' AS label;\n"
        assert_part(self, count_sql(src), logical=1, physical=1, comment=1)

    def test_end_if_does_not_count_if(self):
        src = "IF ready THEN\n  SELECT 1;\nEND IF;\n"
        part = count_sql(src)
        kinds = [unit.split(":", 1)[0] for unit in part.units]
        self.assertEqual(kinds.count("IF"), 1, _show(part))
        self.assertIn("SELECT", kinds)


class MarkupTests(unittest.TestCase):
    def test_html_tags_count_pairs_once(self):
        src = (
            '<note date="12/11/2002">\n'
            "<to>Tove</to>\n"
            "<from>Jani</from>\n"
            "<heading>Reminder</heading>\n"
            "<body>Don't forget me this weekend!</body>\n"
            "</note>\n"
        )
        parts = count_html(src)
        self.assertEqual(len(parts), 1)
        assert_part(self, parts[0], logical=5, physical=6)

    def test_html_comment(self):
        src = "<!-- comment -->\n<p>Hi</p>\n"
        parts = count_html(src)
        assert_part(self, parts[0], logical=1, physical=1, comment=1)

    def test_embedded_script(self):
        src = "<script>\nfunction f() {\n  return 1;\n}\n</script>\n"
        parts = count_html(src)
        by_lang = {part.language: part for part in parts}
        self.assertIn("html", by_lang)
        self.assertIn("javascript", by_lang)
        assert_part(self, by_lang["javascript"], logical=2, physical=3)
        self.assertEqual(by_lang["html"].logical, 1, _show(by_lang["html"]))
        self.assertEqual(sum(part.lines for part in parts), 5)

    def test_css_selectors_and_declarations(self):
        src = "h1, h2 {\n  color: red;\n  margin: 0\n}\n"
        assert_part(self, count_css(src), logical=4, physical=4)

    def test_css_ignores_comma_inside_function(self):
        src = "div:is(h1, h2) { color: red; }\n"
        part = count_css(src)
        selectors = [unit for unit in part.units if unit.startswith("sel:")]
        self.assertEqual(len(selectors), 1, _show(part))
        self.assertEqual(part.logical, 2, _show(part))

    def test_css_media_and_comment(self):
        src = "/* head */\n@media screen {\n  h1 { color: red; }\n}\n"
        part = count_css(src)
        self.assertEqual(part.comment, 1, _show(part))
        self.assertEqual(part.logical, 3, _show(part))

    def test_dispatch_by_language(self):
        parts = count_source("python", "x = 1\n")
        self.assertEqual(parts[0].logical, 1)


if __name__ == "__main__":
    unittest.main()
