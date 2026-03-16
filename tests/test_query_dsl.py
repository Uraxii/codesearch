from pathlib import Path

import pytest

from codesearch.query_dsl import ParsedQuery, Predicate, compile_query, parse_query
from helpers import run_main

FIXTURES = Path(__file__).parent / "fixtures"
FILTERS  = Path(__file__).parent / "filters"


# ---------------------------------------------------------------------------
# parse_query tests
# ---------------------------------------------------------------------------

def test_parse_concept_only():
    q = parse_query("function")
    assert q.concept == "function"
    assert q.predicates == []


def test_parse_method_alias():
    q = parse_query("method")
    assert q.concept == "function"


def test_parse_name_eq():
    q = parse_query('function where name = "WebRequest"')
    assert q.concept == "function"
    assert len(q.predicates) == 1
    assert q.predicates[0] == Predicate(field="name", op="eq", value="WebRequest")


def test_parse_is_alias():
    q = parse_query('class where name is "MyClass"')
    assert q.predicates[0].op == "eq"


def test_parse_contains():
    q = parse_query('class where name contains "Request"')
    assert q.predicates[0].op == "contains"


def test_parse_starts_with():
    q = parse_query('function where name starts_with "Get"')
    assert q.predicates[0].op == "starts_with"


def test_parse_multiple_predicates():
    q = parse_query('function where name starts_with "Get" and name ends_with "Async"')
    assert len(q.predicates) == 2
    assert q.predicates[0].op == "starts_with"
    assert q.predicates[1].op == "ends_with"


def test_parse_unknown_concept_raises():
    with pytest.raises(ValueError, match="Unknown concept"):
        parse_query("widget where name = \"Foo\"")


def test_parse_bad_predicate_raises():
    with pytest.raises(ValueError, match="Cannot parse predicate"):
        parse_query('function where nameWebRequest')


# ---------------------------------------------------------------------------
# compile_query tests
# ---------------------------------------------------------------------------

def test_compile_no_predicate():
    q = parse_query("function")
    ts = compile_query(q, "c_sharp")
    assert "method_declaration" in ts
    assert "@_name" in ts


def test_compile_name_eq():
    q = parse_query('function where name = "Greet"')
    ts = compile_query(q, "c_sharp")
    assert '#eq? @_name "Greet"' in ts


def test_compile_contains():
    q = parse_query('class where name contains "Request"')
    ts = compile_query(q, "c_sharp")
    assert "#match?" in ts
    assert "Request" in ts


def test_compile_unknown_lang_returns_empty():
    q = parse_query("function")
    assert compile_query(q, "cobol") == ""


def test_compile_identifier():
    q = parse_query('identifier where text = "WebRequest"')
    ts = compile_query(q, "c_sharp")
    assert "(identifier)" in ts
    assert "@_name" in ts


# ---------------------------------------------------------------------------
# End-to-end: DSL query via filter file on C# fixture
# ---------------------------------------------------------------------------

def test_find_methods_named_greet_csharp():
    output = run_main(["--filter-file", str(FILTERS / "dsl-greet-cs.ini"), str(FIXTURES / "sample.cs")])
    assert "Greet" in output


def test_find_all_methods_csharp():
    output = run_main(["--filter-file", str(FILTERS / "dsl-all-functions-cs.ini"), str(FIXTURES / "sample.cs")])
    assert "Main" in output
    assert "Greet" in output
    assert "ProcessRequest" in output
    assert "Execute" in output


def test_find_class_named_webrequest():
    output = run_main(["--filter-file", str(FILTERS / "dsl-webrequest-class.ini"), str(FIXTURES / "sample.cs")])
    assert "WebRequestExample" in output


def test_find_classes_containing_request():
    output = run_main(["--filter-file", str(FILTERS / "dsl-request-classes.ini"), str(FIXTURES / "sample.cs")])
    assert "WebRequestExample" in output
    assert "HttpRequest" in output


def test_find_parameters_typed_webrequest():
    output = run_main(["--filter-file", str(FILTERS / "dsl-webrequest-param.ini"), str(FIXTURES / "sample.cs")])
    assert "WebRequest" in output


def test_find_identifier_webrequest_csharp():
    output = run_main(["--filter-file", str(FILTERS / "dsl-webrequest-id.ini"), str(FIXTURES / "sample.cs")])
    assert "WebRequest" in output


def test_find_methods_starts_with_process():
    output = run_main(["--filter-file", str(FILTERS / "dsl-process-fns.ini"), str(FIXTURES / "sample.cs")])
    assert "ProcessRequest" in output
    assert "ProcessHttp" in output


# ---------------------------------------------------------------------------
# Cross-language: same DSL query on Python file
# ---------------------------------------------------------------------------

def test_same_query_python():
    output = run_main(["--filter-file", str(FILTERS / "find-greet.ini"), str(FIXTURES / "sample.py")])
    assert "greet" in output
