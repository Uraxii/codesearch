from pathlib import Path

from tree_sitter import Language, Parser, Query, QueryCursor

from .models import ParseWarning, SearchResult


def search_ast(
    source: bytes,
    language: Language,
    query_str: str,
    path: Path,
) -> tuple[list[SearchResult], list[ParseWarning]]:
    """
    Parse source with tree-sitter and run a structured query against the AST.

    Args:
        source: file contents as bytes
        language: tree-sitter Language instance
        query_str: tree-sitter S-expression query string
        path: file path (used in results and warnings only)

    Returns:
        (results, warnings) — results are one per capture per match;
        warnings are non-empty when the file has parse errors but a partial
        AST was still produced.

    Raises:
        ValueError: if query_str is not valid tree-sitter query syntax
    """
    parser = Parser(language)
    tree = parser.parse(source)
    root = tree.root_node

    warnings: list[ParseWarning] = []
    if root.has_error:
        warnings.append(
            ParseWarning(
                file=path,
                message="File contains syntax errors; results are from a partial AST.",
            )
        )

    try:
        query = Query(language, query_str)
    except Exception as e:
        raise ValueError(f"Invalid tree-sitter query: {e}") from e

    cursor = QueryCursor(query)
    # captures() returns {capture_name: [Node, ...], ...}
    captures: dict[str, list] = cursor.captures(root)

    results: list[SearchResult] = []
    for capture_name, nodes in captures.items():
        for node in nodes:
            row, col = node.start_point  # (0-based row, 0-based col)
            node_text = node.text
            if isinstance(node_text, bytes):
                node_text = node_text.decode("utf-8", errors="replace")
            results.append(
                SearchResult(
                    file=path,
                    line=row + 1,
                    col=col + 1,
                    text=node_text,
                    match_type="ast",
                    capture=capture_name,
                )
            )

    # Sort by position
    results.sort(key=lambda r: (r.line, r.col))
    return results, warnings
