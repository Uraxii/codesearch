from pathlib import Path

import pytest
import tree_sitter_c_sharp as tscsharp
import tree_sitter_python as tspython
from tree_sitter import Language

from codesearch.ast_search import search_ast
from codesearch.query_dsl import ParsedQuery, Predicate, compile_query, parse_query

FIXTURES = Path(__file__).parent / "fixtures"
CS_LANG = Language(tscsharp.language())
PY_LANG = Language(tspython.language())
CS_SOURCE = (FIXTURES / "sample.cs").read_bytes()
PY_SOURCE = (FIXTURES / "sample.py").read_bytes()
CS_PATH = FIXTURES / "sample.cs"
PY_PATH = FIXTURES / "sample.py"


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
# End-to-end: DSL query → AST search on C# fixture
# ---------------------------------------------------------------------------

def test_find_methods_named_greet_csharp():
    q = parse_query('function where name = "Greet"')
    ts = compile_query(q, "c_sharp")
    results, warnings = search_ast(CS_SOURCE, CS_LANG, ts, CS_PATH)
    names = [r.text for r in results]
    assert "Greet" in names
    assert warnings == []


def test_find_all_methods_csharp():
    q = parse_query("function")
    ts = compile_query(q, "c_sharp")
    results, _ = search_ast(CS_SOURCE, CS_LANG, ts, CS_PATH)
    names = [r.text for r in results]
    assert "Main" in names
    assert "Greet" in names
    assert "ProcessRequest" in names
    assert "Execute" in names


def test_find_class_named_webrequest():
    q = parse_query('class where name = "WebRequestExample"')
    ts = compile_query(q, "c_sharp")
    results, _ = search_ast(CS_SOURCE, CS_LANG, ts, CS_PATH)
    assert any(r.text == "WebRequestExample" for r in results)


def test_find_classes_containing_request():
    q = parse_query('class where name contains "Request"')
    ts = compile_query(q, "c_sharp")
    results, _ = search_ast(CS_SOURCE, CS_LANG, ts, CS_PATH)
    names = [r.text for r in results]
    assert "WebRequestExample" in names
    assert "HttpRequest" in names


def test_find_parameters_typed_webrequest():
    q = parse_query('parameter where type = "WebRequest"')
    ts = compile_query(q, "c_sharp")
    results, _ = search_ast(CS_SOURCE, CS_LANG, ts, CS_PATH)
    types = [r.text for r in results if r.capture == "_type"]
    assert "WebRequest" in types


def test_find_identifier_webrequest_csharp():
    q = parse_query('identifier where text = "WebRequest"')
    ts = compile_query(q, "c_sharp")
    results, _ = search_ast(CS_SOURCE, CS_LANG, ts, CS_PATH)
    assert len(results) >= 1
    assert all(r.text == "WebRequest" for r in results)


def test_find_methods_starts_with_process():
    q = parse_query('function where name starts_with "Process"')
    ts = compile_query(q, "c_sharp")
    results, _ = search_ast(CS_SOURCE, CS_LANG, ts, CS_PATH)
    names = [r.text for r in results]
    assert "ProcessRequest" in names
    assert "ProcessHttp" in names


# ---------------------------------------------------------------------------
# Cross-language: same DSL query on Python file
# ---------------------------------------------------------------------------

def test_same_query_python():
    q = parse_query('function where name = "greet"')
    ts = compile_query(q, "python")
    results, _ = search_ast(PY_SOURCE, PY_LANG, ts, PY_PATH)
    assert any(r.text == "greet" for r in results)
