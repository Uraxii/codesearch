"""Tests for filter_file.py — named-query filter file parsing and end-to-end search."""

import textwrap
from pathlib import Path

import pytest

from codesearch.filter_file import FilterQuery, parse_filter_file
from codesearch.__main__ import main

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# parse_filter_file — unit tests
# ---------------------------------------------------------------------------

def _write_ini(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "queries.ini"
    p.write_text(textwrap.dedent(content))
    return p


def test_parse_basic_string_query(tmp_path):
    p = _write_ini(tmp_path, """
        [find-todo]
        type    = string
        pattern = TODO
    """)
    queries = parse_filter_file(p)
    assert len(queries) == 1
    assert queries[0] == FilterQuery(name="find-todo", type="string", pattern="TODO", lang=None, captures=None)


def test_parse_captures_field(tmp_path):
    p = _write_ini(tmp_path, """
        [q]
        type     = ast
        pattern  = (identifier) @_name
        captures = _name, _type
    """)
    q = parse_filter_file(p)[0]
    assert q.captures == frozenset({"_name", "_type"})


def test_parse_captures_none_when_omitted(tmp_path):
    p = _write_ini(tmp_path, """
        [q]
        type    = ast
        pattern = (identifier) @_name
    """)
    assert parse_filter_file(p)[0].captures is None


def test_parse_default_type_is_string(tmp_path):
    p = _write_ini(tmp_path, """
        [no-type]
        pattern = something
    """)
    queries = parse_filter_file(p)
    assert queries[0].type == "string"


def test_parse_query_type(tmp_path):
    p = _write_ini(tmp_path, """
        [weak-md5]
        type    = query
        pattern = identifier where text = "MD5"
        lang    = c_sharp
    """)
    queries = parse_filter_file(p)
    assert queries[0].type == "query"
    assert queries[0].pattern == 'identifier where text = "MD5"'
    assert queries[0].lang == "c_sharp"


def test_parse_regex_type(tmp_path):
    p = _write_ini(tmp_path, """
        [sql]
        type    = regex
        pattern = SELECT.*FROM
    """)
    queries = parse_filter_file(p)
    assert queries[0].type == "regex"


def test_parse_multiple_queries(tmp_path):
    p = _write_ini(tmp_path, """
        [q1]
        pattern = foo

        [q2]
        type    = regex
        pattern = bar.*baz
    """)
    queries = parse_filter_file(p)
    assert [q.name for q in queries] == ["q1", "q2"]


def test_parse_no_lang_is_none(tmp_path):
    p = _write_ini(tmp_path, """
        [q]
        pattern = x
    """)
    assert parse_filter_file(p)[0].lang is None


def test_missing_pattern_raises(tmp_path):
    p = _write_ini(tmp_path, """
        [bad]
        type = regex
    """)
    with pytest.raises(ValueError, match="missing required field 'pattern'"):
        parse_filter_file(p)


def test_unknown_type_raises(tmp_path):
    p = _write_ini(tmp_path, """
        [bad]
        type    = graphql
        pattern = foo
    """)
    with pytest.raises(ValueError, match="unknown type"):
        parse_filter_file(p)


def test_missing_file_raises(tmp_path):
    with pytest.raises(ValueError, match="Cannot read filter file"):
        parse_filter_file(tmp_path / "nonexistent.ini")


# ---------------------------------------------------------------------------
# end-to-end: --filter-file via main()
# ---------------------------------------------------------------------------

def test_filter_file_labels_results(tmp_path):
    """Results from a filter file carry the query name as the capture label."""
    ini = _write_ini(tmp_path, """
        [find-greet]
        type    = query
        pattern = function where name = "greet"
        lang    = python
    """)
    out = []
    # Patch stdout capture via argv
    captured = _run_main(["--filter-file", str(ini), str(FIXTURES / "sample.py")])
    assert "[find-greet]" in captured
    assert "greet" in captured


def test_filter_file_multiple_queries(tmp_path):
    """Multiple named queries each label their own matches."""
    ini = _write_ini(tmp_path, """
        [fn-greet]
        type    = query
        pattern = function where name = "greet"
        lang    = python

        [fn-add]
        type    = query
        pattern = function where name = "add"
        lang    = python
    """)
    captured = _run_main(["--filter-file", str(ini), str(FIXTURES / "sample.py")])
    assert "[fn-greet]" in captured
    assert "[fn-add]" in captured


def test_filter_file_lang_restricts_results(tmp_path):
    """A query with lang=python does not match .cs files."""
    ini = _write_ini(tmp_path, """
        [py-only]
        type    = query
        pattern = function where name = "greet"
        lang    = python
    """)
    captured = _run_main(["--filter-file", str(ini), str(FIXTURES / "sample.cs")])
    assert "[py-only]" not in captured


def test_filter_file_regex_query(tmp_path):
    """Regex queries in a filter file work and use the query name as label."""
    ini = _write_ini(tmp_path, """
        [todo-comment]
        type    = regex
        pattern = TODO
    """)
    # Write a temp file with a TODO comment
    src = tmp_path / "code.py"
    src.write_text("# TODO: fix this\nx = 1\n")
    captured = _run_main(["--filter-file", str(ini), str(src)])
    assert "[todo-comment]" in captured
    assert "TODO" in captured


def test_ast_captures_field_suppresses_unwanted_captures(tmp_path):
    """captures= restricts output to the named captures only."""
    src = tmp_path / "sample.cs"
    src.write_text(
        "public class C {\n"
        "    [HttpGet(\"login\")]\n"
        "    public IActionResult Login(string username, string password) { return Ok(); }\n"
        "}\n"
    )
    ini = _write_ini(tmp_path, """
        [secrets-in-get]
        type     = ast
        lang     = c_sharp
        captures = _param
        pattern  = (method_declaration
                      (attribute_list
                        (attribute
                          name: (identifier) @_attr
                          (#match? @_attr "^HttpGet")))
                      parameters: (parameter_list
                        (parameter
                          name: (identifier) @_param
                          (#match? @_param "(?i)password|secret|token"))))
    """)
    output = _run_main(["--filter-file", str(ini), str(src)])
    # Should find the sensitive parameter
    assert "password" in output
    assert "[secrets-in-get]" in output
    # Should NOT surface the HttpGet attribute node
    assert "HttpGet" not in output


def test_ast_captures_none_outputs_all_captures(tmp_path):
    """When captures= is omitted, all capture nodes appear in output."""
    src = tmp_path / "sample.cs"
    src.write_text(
        "public class C {\n"
        "    [HttpGet(\"login\")]\n"
        "    public IActionResult Login(string password) { return Ok(); }\n"
        "}\n"
    )
    ini = _write_ini(tmp_path, """
        [secrets-in-get]
        type    = ast
        lang    = c_sharp
        pattern = (method_declaration
                    (attribute_list
                      (attribute
                        name: (identifier) @_attr
                        (#match? @_attr "^HttpGet")))
                    parameters: (parameter_list
                      (parameter
                        name: (identifier) @_param
                        (#match? @_param "(?i)password"))))
    """)
    output = _run_main(["--filter-file", str(ini), str(src)])
    # Both captures appear when captures= is not set
    assert "password" in output
    assert "HttpGet" in output


def test_secrets_in_get_filter_file(tmp_path):
    """The real secrets-in-get.ini filter correctly identifies GET endpoints with sensitive params."""
    import pathlib
    filter_file = pathlib.Path(__file__).parent.parent / "demo" / "secrets-in-get.ini"
    src = tmp_path / "controller.cs"
    src.write_text(
        "using Microsoft.AspNetCore.Mvc;\n"
        "[ApiController]\n"
        "public class AuthController : ControllerBase {\n"
        "    [HttpGet(\"login\")]\n"
        "    public IActionResult Login(string username, string password, string apiKey) => Ok();\n"
        "    [HttpPost(\"register\")]\n"
        "    public IActionResult Register(string username, string password) => Ok();\n"
        "    [HttpGet(\"search\")]\n"
        "    public IActionResult Search(string query) => Ok();\n"
        "}\n"
    )
    output = _run_main(["--filter-file", str(filter_file), str(src)])
    # GET endpoint with sensitive params — flagged
    assert "password" in output
    assert "apiKey" in output
    # POST endpoint — not flagged even though it has 'password'
    assert output.count("password") == 1
    # GET endpoint with non-sensitive param — not flagged
    assert "query" not in output


def test_filter_file_cannot_combine_with_query_flag(tmp_path):
    """--filter-file + --query should error."""
    ini = _write_ini(tmp_path, "[q]\npattern = x\n")
    with pytest.raises(SystemExit) as exc:
        main(["--filter-file", str(ini), "--query", "identifier where text = \"x\""])
    assert exc.value.code != 0


def test_no_pattern_no_filter_errors():
    """Omitting both pattern and --filter-file should error."""
    rc = main([str(FIXTURES / "sample.py")])
    assert rc != 0


def test_multiple_filter_files(tmp_path):
    """Two --filter-file flags merge their queries."""
    ini1 = tmp_path / "a.ini"
    ini1.write_text("[fn-greet]\ntype = query\npattern = function where name = \"greet\"\nlang = python\n")
    ini2 = tmp_path / "b.ini"
    ini2.write_text("[fn-add]\ntype = query\npattern = function where name = \"add\"\nlang = python\n")
    captured = _run_main([
        "--filter-file", str(ini1),
        "--filter-file", str(ini2),
        str(FIXTURES / "sample.py"),
    ])
    assert "[fn-greet]" in captured
    assert "[fn-add]" in captured


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _run_main(argv: list[str]) -> str:
    """Run main() and capture stdout, returning it as a string."""
    import io
    from unittest.mock import patch

    buf = io.StringIO()
    with patch("sys.stdout", buf):
        try:
            main(argv)
        except SystemExit:
            pass
    return buf.getvalue()
