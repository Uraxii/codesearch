"""
codesearch — string and AST structural code search

Usage:
  codesearch "pattern" [path ...]
  codesearch --query "function where name = \\"WebRequest\\"" [path ...]
  codesearch --ast "(function_definition name: (identifier) @name)" [path ...]
  codesearch --regex "def \\w+" [path ...]
  codesearch --filter-file queries.ini [path ...]
  codesearch --lang python "pattern" [path ...]
  codesearch --files-only "pattern" [path ...]
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import TextLexer, get_lexer_for_filename
from pygments.util import ClassNotFound

from .ast_search import search_ast
from .filter_file import FilterQuery, parse_filter_file
from .languages import get_language_name, should_process
from .models import ParseWarning, SearchResult
from .query_dsl import _LANG_ALIASES, compile_query, parse_query, rename_captures
from .report import generate_html
from .string_search import search_string


def _lang_matches(file_lang: str | None, query_lang: str) -> bool:
    """Return True if file_lang satisfies a query's lang requirement."""
    if file_lang is None:
        return False
    normalized = _LANG_ALIASES.get(query_lang.lower(), query_lang.lower())
    return file_lang.lower() in (normalized, query_lang.lower())


def _iter_files(paths: list[Path], lang_hint: str | None):
    """
    Yield (file_path, language_or_None) pairs for all files under the given paths.

    language_or_None is None for extensionless files with a lang_hint — those
    are yielded so the caller can attempt a parse-and-ignore-failure approach.
    """
    for root in paths:
        if root.is_file():
            lang = should_process(root, lang_hint)
            if lang is not None or (lang_hint is not None and root.suffix == ""):
                yield root, lang
        elif root.is_dir():
            for file in sorted(root.rglob("*")):
                if not file.is_file():
                    continue
                lang = should_process(file, lang_hint)
                if lang is not None or (lang_hint is not None and file.suffix == ""):
                    yield file, lang
        else:
            print(f"warning: {root} does not exist", file=sys.stderr)


def _format_result(result: SearchResult, files_only: bool) -> str:
    if files_only:
        return str(result.file)
    prefix = f"{result.file}:{result.line}:{result.col}"
    if result.capture:
        label = f"{result.capture}/{result.severity}" if result.severity else result.capture
        return f"{prefix}: [{label}] {result.text}"
    return f"{prefix}: {result.text}"


def _search_file_with_query(
    fq: FilterQuery,
    file_path: Path,
    source_bytes: bytes,
    language,
    ignore_case: bool,
    compiled_query_cache: dict[tuple[str, str], str | None] | None = None,
) -> tuple[list[SearchResult], list[ParseWarning]]:
    """Run a single FilterQuery against one file, returning (results, warnings).

    Returns empty lists if the query does not apply to this file's language.

    compiled_query_cache: maps (fq.name, lang_key) -> compiled S-expression string or None.
        When provided, DSL compile results are read from and written to this cache.
    """
    # Per-query file exclusion — skip this file entirely for this rule
    if fq.exclude_files and re.search(fq.exclude_files, str(file_path), re.IGNORECASE):
        return [], []

    # Per-query language filter
    if fq.lang is not None:
        file_lang = get_language_name(file_path)
        if not _lang_matches(file_lang, fq.lang):
            return [], []

    results: list[SearchResult] = []
    warnings: list[ParseWarning] = []

    if fq.type == "query":
        if language is None:
            return [], []
        lang_key = get_language_name(file_path)
        if lang_key is None:
            return [], []
        cache_key = (fq.name, lang_key)
        if compiled_query_cache is not None and cache_key in compiled_query_cache:
            ast_query = compiled_query_cache[cache_key]
        else:
            try:
                parsed_dsl = parse_query(fq.pattern)
            except ValueError as e:
                raise ValueError(f"Query [{fq.name}]: {e}") from e
            ast_query = compile_query(parsed_dsl, lang_key)
            if compiled_query_cache is not None:
                compiled_query_cache[cache_key] = ast_query
        if not ast_query:
            return [], []
        file_results, file_warnings = search_ast(
            source_bytes, language, ast_query, file_path
        )
        for r in file_results:
            r.capture = fq.name
            r.severity = fq.severity
        results.extend(file_results)
        warnings.extend(file_warnings)

    elif fq.type == "ast":
        if language is None:
            return [], []
        file_results, file_warnings = search_ast(
            source_bytes, language, fq.pattern, file_path
        )
        if fq.captures is not None:
            file_results = [r for r in file_results if r.capture in fq.captures]
        for r in file_results:
            r.capture = fq.name
            r.severity = fq.severity
        results.extend(file_results)
        warnings.extend(file_warnings)

    else:  # "string" or "regex"
        try:
            source_text = source_bytes.decode("utf-8", errors="replace")
        except Exception:
            return [], []
        file_results = search_string(
            source_text,
            fq.pattern,
            file_path,
            regex=(fq.type == "regex"),
            ignore_case=ignore_case,
        )
        for r in file_results:
            r.capture = fq.name
            r.severity = fq.severity
        results.extend(file_results)

    # Per-query result exclusion — drop results whose matched text matches
    if fq.exclude:
        results = [r for r in results if not re.search(fq.exclude, r.text, re.IGNORECASE)]

    return results, warnings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="codesearch",
        description="Search code with string patterns or tree-sitter AST queries.",
    )
    parser.add_argument(
        "pattern",
        nargs="?",
        default=None,
        help="Search pattern, DSL query, or raw AST query string",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        default=[],
        metavar="path",
        help="Files or directories to search (default: current directory)",
    )
    parser.add_argument(
        "--query", "-q",
        action="store_true",
        help=(
            'Treat pattern as a DSL query, e.g.: '
            '"function where name = \\"WebRequest\\""'
        ),
    )
    parser.add_argument(
        "--ast",
        action="store_true",
        help="Treat pattern as a raw tree-sitter S-expression query",
    )
    parser.add_argument(
        "--regex", "-e",
        action="store_true",
        help="Treat pattern as a regular expression (string search only)",
    )
    parser.add_argument(
        "--filter-file",
        action="append",
        metavar="FILE",
        dest="filter_files",
        help=(
            "INI file of named queries to run. May be repeated. "
            "Cannot be combined with --query, --ast, or --regex."
        ),
    )
    parser.add_argument(
        "--ignore-case", "-i",
        action="store_true",
        help="Case-insensitive matching (string and regex search only)",
    )
    parser.add_argument(
        "--lang",
        metavar="LANG",
        help="Restrict search to files of this language (python, javascript, typescript, c_sharp)",
    )
    parser.add_argument(
        "--files-only", "-l",
        action="store_true",
        help="Print only filenames of files with matches",
    )
    parser.add_argument(
        "--output", "-O",
        choices=["text", "json", "html"],
        default="text",
        help="Output format: text (default), json, or html (self-contained dashboard)",
    )
    parser.add_argument(
        "--context", "-C",
        type=int,
        default=3,
        metavar="N",
        help="Lines of context shown in json/html output (default: 3)",
    )

    args = parser.parse_args(argv)

    # --- Validate argument combinations ---
    using_filter = bool(args.filter_files)
    mode_flags = sum([args.query, args.ast, args.regex])

    if using_filter:
        # argparse's nargs="?" greedily consumes the first positional as
        # 'pattern' even when no pattern is intended.  Move it to paths.
        if args.pattern is not None:
            args.paths = [args.pattern] + list(args.paths)
            args.pattern = None
        if mode_flags > 0:
            parser.error("--filter-file cannot be combined with --query, --ast, or --regex")

    if not using_filter and args.pattern is None:
        parser.error("a pattern is required (or use --filter-file)")
    if not using_filter and mode_flags > 1:
        parser.error("--query, --ast, and --regex are mutually exclusive")

    search_paths = [Path(p) for p in (args.paths or ["."])]
    lang_hint = args.lang.lower() if args.lang else None

    # --- Build the list of named queries to run ---
    filter_queries: list[FilterQuery] = []

    if using_filter:
        for ff_path in args.filter_files:
            try:
                filter_queries.extend(parse_filter_file(Path(ff_path)))
            except ValueError as e:
                print(f"error: {e}", file=sys.stderr)
                return 2
        if not filter_queries:
            print("error: filter file(s) contain no queries", file=sys.stderr)
            return 2
    else:
        # Wrap the inline pattern as a synthetic FilterQuery so the loop below
        # can treat both modes uniformly.
        if args.query:
            q_type = "query"
        elif args.ast:
            q_type = "ast"
        elif args.regex:
            q_type = "regex"
        else:
            q_type = "string"
        filter_queries.append(
            FilterQuery(
                name="",          # no label for inline queries
                type=q_type,
                pattern=args.pattern,
                lang=lang_hint,
            )
        )

    # Pre-validate DSL queries up front so errors surface immediately.
    # The compiled_query_cache is populated lazily on first hit per (fq.name, lang_key);
    # subsequent files with the same language reuse the compiled S-expression.
    _compiled_query_cache: dict[tuple[str, str], str | None] = {}
    for fq in filter_queries:
        if fq.type == "query":
            try:
                parse_query(fq.pattern)
            except ValueError as e:
                label = f"[{fq.name}] " if fq.name else ""
                print(f"error: {label}{e}", file=sys.stderr)
                return 2

    results: list[SearchResult] = []
    warnings: list[ParseWarning] = []
    exit_code = 0
    # Cache file lines for context in json/html output modes.
    file_lines_cache: dict[Path, list[str]] = {}
    file_highlighted_cache: dict[Path, list[str]] = {}
    _hl_formatter = HtmlFormatter(nowrap=True)

    for file_path, language in _iter_files(search_paths, lang_hint):
        try:
            source_bytes = file_path.read_bytes()
        except OSError as e:
            print(f"warning: cannot read {file_path}: {e}", file=sys.stderr)
            continue

        if args.output in ("json", "html"):
            decoded = source_bytes.decode("utf-8", errors="replace")
            file_lines_cache[file_path] = decoded.splitlines()

        if args.output == "html":
            try:
                lexer = get_lexer_for_filename(str(file_path), stripall=False)
            except ClassNotFound:
                lexer = TextLexer()
            hl = highlight(decoded, lexer, _hl_formatter)
            hl_lines = hl.split("\n")
            if hl_lines and hl_lines[-1] == "":
                hl_lines.pop()
            file_highlighted_cache[file_path] = hl_lines

        for fq in filter_queries:
            try:
                file_results, file_warnings = _search_file_with_query(
                    fq, file_path, source_bytes, language, args.ignore_case,
                    _compiled_query_cache,
                )
            except ValueError as e:
                print(f"error: {e}", file=sys.stderr)
                return 2

            # For inline (non-filter-file) queries, apply the existing
            # capture-rename logic so output labels match prior behaviour.
            if not using_filter and fq.type == "query":
                parsed_dsl = parse_query(fq.pattern)
                for r in file_results:
                    r.capture = rename_captures(
                        {r.capture: []}, parsed_dsl.concept
                    ).popitem()[0] if r.capture else r.capture
            elif not using_filter and fq.type in ("string", "regex"):
                # String search has no capture label in non-filter mode.
                for r in file_results:
                    r.capture = ""

            results.extend(file_results)
            warnings.extend(file_warnings)

    # When multiple queries ran, results from the same file may be interleaved;
    # sort everything by (file, line, col) for consistent, grep-like output.
    if using_filter:
        results.sort(key=lambda r: (str(r.file), r.line, r.col))

    # Emit parse warnings to stderr
    for warning in warnings:
        print(f"warning: {warning.file}: {warning.message}", file=sys.stderr)

    if args.output in ("json", "html"):
        ctx_n = args.context
        result_dicts = []
        for r in results:
            lines = file_lines_cache.get(r.file, [])
            ctx_lines = file_highlighted_cache.get(r.file, lines) if args.output == "html" else lines
            before_start = max(0, r.line - 1 - ctx_n)      # 0-based
            match_idx = r.line - 1                           # 0-based
            after_end = min(len(lines), r.line + ctx_n)     # exclusive
            context_before = ctx_lines[before_start:match_idx]
            context_after = ctx_lines[match_idx + 1:after_end]
            context_match_line = ctx_lines[match_idx] if match_idx < len(ctx_lines) else r.text
            result_dicts.append({
                "file": str(r.file),
                "line": r.line,
                "col": r.col,
                "text": r.text,
                "match_type": r.match_type,
                "capture": r.capture,
                "severity": r.severity,
                "context_before": context_before,
                "context_after": context_after,
                "context_start_line": before_start + 1,     # 1-based
                "context_match_line": context_match_line,
            })

        unique_rules = {r["capture"] for r in result_dicts if r["capture"]}
        unique_files = {r["file"] for r in result_dicts}
        rules_meta = {
            fq.name: {"description": fq.description, "fix": fq.fix, "severity": fq.severity}
            for fq in filter_queries
            if fq.name
        }
        data = {
            "summary": {
                "total": len(result_dicts),
                "files": len(unique_files),
                "rules": len(unique_rules),
                "paths": [str(p) for p in search_paths],
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            },
            "rules": rules_meta,
            "results": result_dicts,
        }

        if args.output == "json":
            print(json.dumps(data, indent=2))
        else:
            print(generate_html(data))

    else:
        # Text output (default)
        seen_files: set[Path] = set()
        if args.files_only:
            for result in results:
                if result.file not in seen_files:
                    seen_files.add(result.file)
                    print(str(result.file))
        else:
            for result in results:
                print(_format_result(result, files_only=False))

    if not results:
        exit_code = 1

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
