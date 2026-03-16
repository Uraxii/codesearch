"""Tests for filter_file.py — named-query filter file parsing and end-to-end search."""

from pathlib import Path

import pytest

from codesearch.filter_file import FilterQuery, parse_filter_file
from codesearch.__main__ import main
from helpers import run_main

FIXTURES = Path(__file__).parent / "fixtures"
FILTERS  = Path(__file__).parent / "filters"
DEMO     = Path(__file__).parent.parent / "demo"


# ---------------------------------------------------------------------------
# parse_filter_file — unit tests
# ---------------------------------------------------------------------------

def test_parse_basic_string_query():
    queries = parse_filter_file(FILTERS / "find-todo.ini")
    assert len(queries) == 1
    assert queries[0] == FilterQuery(name="find-todo", type="string", pattern="TODO", lang=None, captures=None)


def test_parse_captures_field():
    q = parse_filter_file(FILTERS / "captures-with-field.ini")[0]
    assert q.captures == frozenset({"_name", "_type"})


def test_parse_captures_none_when_omitted():
    assert parse_filter_file(FILTERS / "captures-no-field.ini")[0].captures is None


def test_parse_default_type_is_string():
    queries = parse_filter_file(FILTERS / "default-type.ini")
    assert queries[0].type == "string"


def test_parse_query_type():
    queries = parse_filter_file(FILTERS / "weak-md5.ini")
    assert queries[0].type == "query"
    assert queries[0].pattern == 'identifier where text = "MD5"'
    assert queries[0].lang == "c_sharp"


def test_parse_regex_type():
    queries = parse_filter_file(FILTERS / "sql-regex.ini")
    assert queries[0].type == "regex"


def test_parse_multiple_queries():
    queries = parse_filter_file(FILTERS / "two-queries.ini")
    assert [q.name for q in queries] == ["q1", "q2"]


def test_parse_no_lang_is_none():
    assert parse_filter_file(FILTERS / "minimal.ini")[0].lang is None


def test_missing_pattern_raises():
    with pytest.raises(ValueError, match="missing required field 'pattern'"):
        parse_filter_file(FILTERS / "missing-pattern.ini")


def test_unknown_type_raises():
    with pytest.raises(ValueError, match="unknown type"):
        parse_filter_file(FILTERS / "unknown-type.ini")


def test_missing_file_raises(tmp_path):
    with pytest.raises(ValueError, match="Cannot read filter file"):
        parse_filter_file(tmp_path / "nonexistent.ini")


# ---------------------------------------------------------------------------
# end-to-end: --filter-file via main()
# ---------------------------------------------------------------------------

def test_filter_file_labels_results():
    """Results from a filter file carry the query name as the capture label."""
    output = run_main(["--filter-file", str(FILTERS / "find-greet.ini"), str(FIXTURES / "sample.py")])
    assert "find-greet" in output
    assert "greet" in output


def test_filter_file_multiple_queries():
    """Multiple named queries each label their own matches."""
    output = run_main(["--filter-file", str(FILTERS / "fn-greet-and-add.ini"), str(FIXTURES / "sample.py")])
    assert "fn-greet" in output
    assert "fn-add" in output


def test_filter_file_lang_restricts_results():
    """A query with lang=python does not match .cs files."""
    output = run_main(["--filter-file", str(FILTERS / "find-greet.ini"), str(FIXTURES / "sample.cs")])
    assert "find-greet" not in output


def test_filter_file_regex_query():
    """Regex queries in a filter file work and use the query name as label."""
    output = run_main(["--filter-file", str(FILTERS / "todo-comment.ini"), str(FIXTURES / "todo.py")])
    assert "todo-comment" in output
    assert "TODO" in output


def test_ast_captures_field_suppresses_unwanted_captures():
    """captures= restricts output to the named captures only."""
    output = run_main(["--filter-file", str(FILTERS / "secrets-in-get-with-captures.ini"), str(FIXTURES / "http_get.cs")])
    assert "password" in output
    assert "secrets-in-get" in output
    assert "HttpGet" not in output


def test_ast_captures_none_outputs_all_captures():
    """When captures= is omitted, all capture nodes appear in output."""
    output = run_main(["--filter-file", str(FILTERS / "secrets-in-get-all-captures.ini"), str(FIXTURES / "http_get.cs")])
    assert "password" in output
    assert "HttpGet" in output


def test_secrets_in_get_filter_file():
    """The real secrets-in-get.ini filter correctly identifies GET endpoints with sensitive params."""
    output = run_main(["--filter-file", str(DEMO / "secrets-in-get.ini"), str(FIXTURES / "auth_controller.cs")])
    assert "password" in output
    assert "apiKey" in output
    assert output.count("password") == 1
    assert "query" not in output


def test_secrets_in_get_expanded_params():
    """Expanded parameter list catches otp, pin, pwd, ssn, auth, cvv in GET endpoints."""
    output = run_main(["--filter-file", str(DEMO / "secrets-in-get.ini"), str(FIXTURES / "otp_controller.cs")])
    assert "otp" in output
    assert "pin" in output
    assert "pwd" in output
    assert "auth" in output
    assert "ssn" in output
    assert "cvv" in output
    assert "userId" not in output
    assert "page" not in output


def test_hardcoded_readonly_secret():
    """hardcoded-readonly-secret detects static readonly string fields with secret-like names."""
    output = run_main(["--filter-file", str(DEMO / "csharp-security.ini"), str(FIXTURES / "readonly_secret.cs")])
    assert "hardcoded-readonly-secret" in output
    assert "JwtSecret" in output
    assert output.count("hardcoded-readonly-secret") == 1


def test_hardcoded_secret_constant_case_insensitive():
    """hardcoded-secret-constant catches PascalCase variable names like WebhookSecret, ApiKey."""
    output = run_main(["--filter-file", str(DEMO / "gdvcsharp-security.ini"), str(FIXTURES / "pascalcase_secrets.cs")])
    assert "ApiKey" in output
    assert "WebhookSecret" in output


def test_hardcoded_password_constant_case_insensitive():
    """hardcoded-password-constant catches PascalCase names like AdminPassword."""
    output = run_main(["--filter-file", str(DEMO / "gdvcsharp-security.ini"), str(FIXTURES / "admin_password.cs")])
    assert "AdminPassword" in output
    assert "WelcomeMessage" not in output


def test_exclude_drops_matching_text():
    """exclude= drops results whose matched text contains the pattern (case-insensitive)."""
    output = run_main(["--filter-file", str(FILTERS / "dsl-functions-exclude-text.ini"), str(FIXTURES / "sample.cs")])
    # Functions not containing "Process" are present
    assert "Greet" in output
    assert "Main" in output
    # Functions whose name contains "Process" are suppressed
    assert "ProcessRequest" not in output
    assert "ProcessHttp" not in output


def test_exclude_is_case_insensitive():
    """exclude= matching is case-insensitive — lowercase pattern matches PascalCase name."""
    output = run_main(["--filter-file", str(FILTERS / "dsl-functions-exclude-text.ini"), str(FIXTURES / "sample.cs")])
    # The filter uses exclude = Process (PascalCase); confirm ProcessRequest is suppressed
    assert "ProcessRequest" not in output


def test_exclude_files_skips_matching_paths():
    """exclude_files= skips files whose path matches, leaving other files unaffected."""
    output = run_main([
        "--filter-file", str(FILTERS / "dsl-functions-exclude-files.ini"),
        str(FIXTURES / "http_get.cs"),   # path contains "http_get" — excluded
        str(FIXTURES / "sample.cs"),     # path does not match — included
    ])
    assert "Greet" in output          # from sample.cs
    assert "Login" not in output      # from http_get.cs, which was excluded


def test_exclude_fields_parsed():
    """FilterQuery.exclude and exclude_files are populated from the INI."""
    queries = parse_filter_file(FILTERS / "dsl-functions-exclude-text.ini")
    assert queries[0].exclude == "Process"
    assert queries[0].exclude_files == ""

    queries = parse_filter_file(FILTERS / "dsl-functions-exclude-files.ini")
    assert queries[0].exclude == ""
    assert queries[0].exclude_files == "http_get"


def test_invalid_exclude_pattern_raises(tmp_path):
    """An invalid regex in exclude= raises ValueError at parse time."""
    p = tmp_path / "bad.ini"
    p.write_text("[q]\npattern = TODO\nexclude = [unclosed\n")
    with pytest.raises(ValueError, match="invalid exclude pattern"):
        parse_filter_file(p)


def test_invalid_exclude_files_pattern_raises(tmp_path):
    """An invalid regex in exclude_files= raises ValueError at parse time."""
    p = tmp_path / "bad.ini"
    p.write_text("[q]\npattern = TODO\nexclude_files = [unclosed\n")
    with pytest.raises(ValueError, match="invalid exclude_files pattern"):
        parse_filter_file(p)


def test_severity_default_is_medium(tmp_path):
    """severity= defaults to 'medium' when omitted."""
    p = tmp_path / "q.ini"
    p.write_text("[my-rule]\npattern = TODO\n")
    queries = parse_filter_file(p)
    assert queries[0].severity == "medium"


def test_severity_field_parsed(tmp_path):
    """severity= is read from the INI and validated."""
    p = tmp_path / "q.ini"
    p.write_text("[my-rule]\npattern = TODO\nseverity = high\n")
    queries = parse_filter_file(p)
    assert queries[0].severity == "high"


def test_invalid_severity_raises(tmp_path):
    """An unknown severity value raises ValueError at parse time."""
    p = tmp_path / "q.ini"
    p.write_text("[my-rule]\npattern = TODO\nseverity = critical-high\n")
    with pytest.raises(ValueError, match="invalid severity"):
        parse_filter_file(p)


def test_severity_appears_in_text_output():
    """Text output shows [rule/severity] label format."""
    output = run_main(["--filter-file", str(FILTERS / "find-greet.ini"), str(FIXTURES / "sample.py")])
    assert "[find-greet/medium]" in output


def test_severity_appears_in_json_output():
    """JSON output includes a 'severity' field on each result."""
    import json as _json
    output = run_main(["--filter-file", str(FILTERS / "find-greet.ini"), "--output", "json", str(FIXTURES / "sample.py")])
    data = _json.loads(output)
    assert data["results"][0]["severity"] == "medium"
    assert data["rules"]["find-greet"]["severity"] == "medium"


def test_filter_file_cannot_combine_with_query_flag():
    """--filter-file + --query should error."""
    with pytest.raises(SystemExit) as exc:
        main(["--filter-file", str(FILTERS / "minimal.ini"), "--query", 'identifier where text = "x"'])
    assert exc.value.code != 0


def test_no_pattern_no_filter_errors():
    """Omitting both pattern and --filter-file should error."""
    rc = main([str(FIXTURES / "sample.py")])
    assert rc != 0


def test_multiple_filter_files():
    """Two --filter-file flags merge their queries."""
    output = run_main([
        "--filter-file", str(FILTERS / "fn-greet.ini"),
        "--filter-file", str(FILTERS / "fn-add.ini"),
        str(FIXTURES / "sample.py"),
    ])
    assert "fn-greet" in output
    assert "fn-add" in output
