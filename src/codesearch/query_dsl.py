"""
Query DSL for human-readable code search queries.

Syntax:
    <concept> [where <field> <op> <value> [and <field> <op> <value>]*]

Concepts:
    function / method   — function or method declarations
    class               — class declarations
    identifier          — any identifier (variable, type reference, etc.)
    call                — function or method call expressions
    parameter           — function/method parameters

Fields:
    name        — declared name of the node (function name, class name, etc.)
    text        — synonym for name; the text of the primary identifier
    type        — type annotation of a parameter or return

Operators:
    =  / is              — exact match
    != / is not          — not equal
    contains             — substring match
    matches              — regex match
    starts_with          — prefix match
    ends_with            — suffix match

Examples:
    function where name = "WebRequest"
    class where name contains "Request"
    parameter where type = "string"
    identifier where text = "WebRequest"
    function where name starts_with "Get" and name ends_with "Async"
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Schema: concept → language → list of (node_type, name_capture_expr)
#
# name_capture_expr is the fragment that binds @_name inside the node pattern.
# Special value "_self" means the node itself is the capture (identifier concept).
# "_type" is used for parameter type captures.
# ---------------------------------------------------------------------------

_SCHEMA: dict[str, dict[str, list[tuple[str, str]]]] = {
    "function": {
        "python": [
            ("function_definition",         "name: (identifier) @_name"),
        ],
        "javascript": [
            ("function_declaration",        "name: (identifier) @_name"),
            ("function_expression",         "name: (identifier) @_name"),
            ("method_definition",           "name: (property_identifier) @_name"),
        ],
        "typescript": [
            ("function_declaration",        "name: (identifier) @_name"),
            ("function_expression",         "name: (identifier) @_name"),
            ("method_definition",           "name: (property_identifier) @_name"),
        ],
        "tsx": [
            ("function_declaration",        "name: (identifier) @_name"),
            ("function_expression",         "name: (identifier) @_name"),
            ("method_definition",           "name: (property_identifier) @_name"),
        ],
        "c_sharp": [
            ("method_declaration",          "name: (identifier) @_name"),
            ("constructor_declaration",     "name: (identifier) @_name"),
            ("local_function_statement",    "name: (identifier) @_name"),
        ],
    },
    "class": {
        "python":     [("class_definition",  "name: (identifier) @_name")],
        "javascript": [("class_declaration", "name: (identifier) @_name")],
        "typescript": [("class_declaration", "name: (type_identifier) @_name")],
        "tsx":        [("class_declaration", "name: (type_identifier) @_name")],
        "c_sharp":    [("class_declaration", "name: (identifier) @_name")],
    },
    "identifier": {
        "python":     [("identifier", "_self")],
        "javascript": [("identifier", "_self")],
        "typescript": [("identifier", "_self")],
        "tsx":        [("identifier", "_self")],
        "c_sharp":    [("identifier", "_self")],
    },
    "call": {
        "python": [
            ("call", "function: (identifier) @_name"),
            ("call", "function: (attribute attribute: (identifier) @_name)"),
        ],
        "javascript": [
            ("call_expression", "function: (identifier) @_name"),
            ("call_expression", "function: (member_expression property: (property_identifier) @_name)"),
        ],
        "typescript": [
            ("call_expression", "function: (identifier) @_name"),
            ("call_expression", "function: (member_expression property: (property_identifier) @_name)"),
        ],
        "tsx": [
            ("call_expression", "function: (identifier) @_name"),
            ("call_expression", "function: (member_expression property: (property_identifier) @_name)"),
        ],
        "c_sharp": [
            ("invocation_expression", "function: (identifier) @_name"),
            ("invocation_expression", "function: (member_access_expression name: (identifier) @_name)"),
        ],
    },
    "parameter": {
        "python": [
            ("identifier", "_self"),  # plain param: def f(x) — captures x
            ("typed_parameter", "type: (type (identifier) @_name)"),
        ],
        "javascript": [
            ("identifier", "_self"),
        ],
        "typescript": [
            ("required_parameter", "name: (identifier) @_name type: (type_annotation (type_identifier) @_type)"),
            ("optional_parameter", "name: (identifier) @_name type: (type_annotation (type_identifier) @_type)"),
        ],
        "tsx": [
            ("required_parameter", "name: (identifier) @_name type: (type_annotation (type_identifier) @_type)"),
            ("optional_parameter", "name: (identifier) @_name type: (type_annotation (type_identifier) @_type)"),
        ],
        "c_sharp": [
            # user-defined types: WebRequest, HttpClient, etc.
            ("parameter", "type: (identifier) @_type name: (identifier) @_name"),
            # built-in types: string, int, bool, etc.
            ("parameter", "type: (predefined_type) @_type name: (identifier) @_name"),
        ],
    },
}

# Aliases for concept names
_CONCEPT_ALIASES: dict[str, str] = {
    "method": "function",
    "func":   "function",
    "fn":     "function",
}

# Aliases for language names (must match keys in _SCHEMA values)
_LANG_ALIASES: dict[str, str] = {
    "csharp":  "c_sharp",
    "cs":      "c_sharp",
    "js":      "javascript",
    "ts":      "typescript",
    "py":      "python",
}


# ---------------------------------------------------------------------------
# AST of the parsed query
# ---------------------------------------------------------------------------

@dataclass
class Predicate:
    field: str      # "name", "text", "type"
    op: str         # "eq", "neq", "contains", "matches", "starts_with", "ends_with"
    value: str


@dataclass
class ParsedQuery:
    concept: str
    predicates: list[Predicate] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

_OP_MAP: dict[str, str] = {
    "=":           "eq",
    "is":          "eq",
    "!=":          "neq",
    "is not":      "neq",
    "contains":    "contains",
    "matches":     "matches",
    "starts_with": "starts_with",
    "starts with": "starts_with",
    "ends_with":   "ends_with",
    "ends with":   "ends_with",
}

# Pattern to tokenise a single predicate: field OP "value"
_PRED_RE = re.compile(
    r'(\w+)\s+'                                    # field name
    r'(is not|is|!=|=|contains|matches|starts_with|starts with|ends_with|ends with)\s+'
    r'"([^"]*)"',
    re.IGNORECASE,
)


def parse_query(dsl: str) -> ParsedQuery:
    """Parse a DSL query string into a ParsedQuery.

    Raises ValueError on syntax errors.
    """
    dsl = dsl.strip()

    # Split at 'where' (case-insensitive)
    where_split = re.split(r'\bwhere\b', dsl, maxsplit=1, flags=re.IGNORECASE)
    concept_part = where_split[0].strip().lower()
    predicate_part = where_split[1].strip() if len(where_split) > 1 else ""

    concept = _CONCEPT_ALIASES.get(concept_part, concept_part)
    if concept not in _SCHEMA:
        known = sorted(set(list(_SCHEMA.keys()) + list(_CONCEPT_ALIASES.keys())))
        raise ValueError(
            f"Unknown concept {concept_part!r}. Known concepts: {', '.join(known)}"
        )

    predicates: list[Predicate] = []
    if predicate_part:
        # Split on ' and ' between predicates
        clauses = re.split(r'\band\b', predicate_part, flags=re.IGNORECASE)
        for clause in clauses:
            clause = clause.strip()
            m = _PRED_RE.match(clause)
            if not m:
                raise ValueError(
                    f"Cannot parse predicate {clause!r}. "
                    f'Expected: <field> <op> "<value>" '
                    f'(e.g., name = "WebRequest")'
                )
            f_name, op_str, value = m.group(1).lower(), m.group(2).lower(), m.group(3)
            op = _OP_MAP.get(op_str)
            if op is None:
                raise ValueError(f"Unknown operator {op_str!r}")
            predicates.append(Predicate(field=f_name, op=op, value=value))

    return ParsedQuery(concept=concept, predicates=predicates)


# ---------------------------------------------------------------------------
# Compiler: ParsedQuery → tree-sitter S-expression string for one language
# ---------------------------------------------------------------------------

def _pred_to_ts(op: str, capture: str, value: str) -> str:
    """Convert a predicate to a tree-sitter predicate clause."""
    escaped = re.escape(value)
    match op:
        case "eq":
            return f'(#eq? {capture} "{value}")'
        case "neq":
            return f'(#not-eq? {capture} "{value}")'
        case "contains":
            return f'(#match? {capture} "{escaped}")'
        case "matches":
            return f'(#match? {capture} "{value}")'
        case "starts_with":
            return f'(#match? {capture} "^{escaped}")'
        case "ends_with":
            return f'(#match? {capture} "{escaped}$")'
        case _:
            raise ValueError(f"Unknown op: {op}")


def _field_to_capture(field_name: str) -> str:
    """Map DSL field name to a tree-sitter capture variable."""
    if field_name in ("name", "text"):
        return "@_name"
    if field_name == "type":
        return "@_type"
    raise ValueError(
        f"Unknown field {field_name!r}. Supported fields: name, text, type"
    )


def compile_query(pq: ParsedQuery, lang_name: str) -> str:
    """
    Compile a ParsedQuery to a tree-sitter S-expression string for the given language.

    Returns an empty string if the concept has no schema entry for this language.
    Raises ValueError on compilation errors.
    """
    lang = _LANG_ALIASES.get(lang_name.lower(), lang_name.lower())
    entries = _SCHEMA.get(pq.concept, {}).get(lang, [])
    if not entries:
        return ""

    # Build tree-sitter predicates from DSL predicates
    ts_preds: list[str] = []
    for pred in pq.predicates:
        capture = _field_to_capture(pred.field)
        ts_preds.append(_pred_to_ts(pred.op, capture, pred.value))

    pred_str = " ".join(ts_preds)

    patterns: list[str] = []
    for node_type, capture_expr in entries:
        if capture_expr == "_self":
            # The node itself is the capture
            inner = f"({node_type}) @_name"
        else:
            inner = f"({node_type} {capture_expr})"

        if pred_str:
            pattern = f"({inner} {pred_str})" if capture_expr == "_self" else f"({node_type} {capture_expr} {pred_str})"
        else:
            pattern = f"({node_type} {capture_expr})" if capture_expr != "_self" else f"({node_type}) @_name"

        patterns.append(pattern)

    return "\n".join(patterns)


def rename_captures(raw_captures: dict, concept: str) -> dict[str, list]:
    """
    Rename internal capture names (_name, _type) to user-visible names
    based on the concept being searched.
    """
    label_map = {
        "@_name": concept,
        "@_type": f"{concept}.type",
        "_name":  concept,
        "_type":  f"{concept}.type",
    }
    result: dict[str, list] = {}
    for k, v in raw_captures.items():
        label = label_map.get(k, k)
        result.setdefault(label, []).extend(v)
    return result
