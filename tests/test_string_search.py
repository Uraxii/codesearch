from pathlib import Path

import pytest

from codesearch.string_search import search_string

FIXTURE = Path(__file__).parent / "fixtures" / "sample.py"
SOURCE = FIXTURE.read_text()


def test_literal_match():
    results = search_string(SOURCE, "WebRequest", FIXTURE)
    assert len(results) >= 1
    assert all(r.match_type == "string" for r in results)
    assert all("WebRequest" in r.text for r in results)


def test_literal_no_match():
    results = search_string(SOURCE, "NonExistentSymbol12345", FIXTURE)
    assert results == []


def test_case_insensitive():
    results_sensitive = search_string(SOURCE, "webrequest", FIXTURE, ignore_case=False)
    results_insensitive = search_string(SOURCE, "webrequest", FIXTURE, ignore_case=True)
    assert results_sensitive == []
    assert len(results_insensitive) >= 1


def test_regex_match():
    results = search_string(SOURCE, r"def \w+\(", FIXTURE, regex=True)
    assert len(results) >= 3  # greet, add, use_web_request, use_http_client


def test_regex_invalid():
    with pytest.raises(ValueError, match="Invalid regex"):
        search_string(SOURCE, "[unclosed", FIXTURE, regex=True)


def test_line_col_are_one_based():
    results = search_string(SOURCE, "def greet", FIXTURE)
    assert len(results) == 1
    assert results[0].line >= 1
    assert results[0].col >= 1


def test_col_points_to_match_start():
    results = search_string(SOURCE, "greet", FIXTURE)
    first = results[0]
    line_text = SOURCE.splitlines()[first.line - 1]
    # col is 1-based, so col-1 is the 0-based index
    assert line_text[first.col - 1:first.col - 1 + len("greet")] == "greet"


def test_capture_is_empty_for_string_results():
    results = search_string(SOURCE, "import", FIXTURE)
    assert all(r.capture == "" for r in results)
