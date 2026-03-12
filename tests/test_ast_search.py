from pathlib import Path

import pytest
import tree_sitter_python as tspython
import tree_sitter_typescript as tstypescript
from tree_sitter import Language

from codesearch.ast_search import search_ast

PY_LANG = Language(tspython.language())
TS_LANG = Language(tstypescript.language_typescript())

FIXTURES = Path(__file__).parent / "fixtures"
PY_SOURCE = (FIXTURES / "sample.py").read_bytes()
TS_SOURCE = (FIXTURES / "sample.ts").read_bytes()
BROKEN_SOURCE = (FIXTURES / "broken.py").read_bytes()
PY_PATH = FIXTURES / "sample.py"
TS_PATH = FIXTURES / "sample.ts"
BROKEN_PATH = FIXTURES / "broken.py"


# --- Python AST queries ---

def test_find_all_function_defs():
    results, warnings = search_ast(
        PY_SOURCE,
        PY_LANG,
        "(function_definition name: (identifier) @name)",
        PY_PATH,
    )
    names = [r.text for r in results]
    assert "greet" in names
    assert "add" in names
    assert "use_web_request" in names
    assert warnings == []


def test_find_functions_with_string_param():
    # Find parameters typed as 'str'
    results, warnings = search_ast(
        PY_SOURCE,
        PY_LANG,
        """
        (function_definition
          parameters: (parameters
            (typed_parameter
              type: (type [(identifier)] @type_name)
            )
          )
        )
        """,
        PY_PATH,
    )
    type_names = [r.text for r in results]
    assert "str" in type_names


def test_find_webrequest_references():
    results, _ = search_ast(
        PY_SOURCE,
        PY_LANG,
        "(identifier) @name",
        PY_PATH,
    )
    webrequest_hits = [r for r in results if r.text == "WebRequest"]
    assert len(webrequest_hits) >= 1


def test_parse_error_produces_warning():
    results, warnings = search_ast(
        BROKEN_SOURCE,
        PY_LANG,
        "(identifier) @name",
        BROKEN_PATH,
    )
    assert len(warnings) == 1
    assert "syntax errors" in warnings[0].message
    # Still returns partial results
    assert len(results) > 0


def test_invalid_query_raises_value_error():
    with pytest.raises(ValueError, match="Invalid tree-sitter query"):
        search_ast(PY_SOURCE, PY_LANG, "(not_a_real_node_type_xyz @bad", PY_PATH)


def test_results_are_sorted_by_position():
    results, _ = search_ast(
        PY_SOURCE,
        PY_LANG,
        "(identifier) @name",
        PY_PATH,
    )
    positions = [(r.line, r.col) for r in results]
    assert positions == sorted(positions)


def test_result_fields():
    results, _ = search_ast(
        PY_SOURCE,
        PY_LANG,
        "(function_definition name: (identifier) @func_name)",
        PY_PATH,
    )
    assert len(results) > 0
    r = results[0]
    assert r.match_type == "ast"
    assert r.capture == "func_name"
    assert r.line >= 1
    assert r.col >= 1
    assert r.file == PY_PATH


# --- TypeScript AST queries ---

def test_typescript_function_names():
    results, warnings = search_ast(
        TS_SOURCE,
        TS_LANG,
        "(function_declaration name: (identifier) @name)",
        TS_PATH,
    )
    names = [r.text for r in results]
    assert "makeWebRequest" in names
    assert "makeHttpRequest" in names
    assert "acceptsString" in names
    assert warnings == []


def test_typescript_class_names():
    results, _ = search_ast(
        TS_SOURCE,
        TS_LANG,
        "(class_declaration name: (type_identifier) @name)",
        TS_PATH,
    )
    names = [r.text for r in results]
    assert "WebRequest" in names
    assert "HttpRequest" in names
