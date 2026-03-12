import re
from pathlib import Path

from .models import SearchResult


def search_string(
    source: str,
    pattern: str,
    path: Path,
    *,
    regex: bool = False,
    ignore_case: bool = False,
) -> list[SearchResult]:
    """
    Search source text line-by-line for pattern.

    Args:
        source: file contents as a string
        pattern: literal string or regex pattern
        path: file path (used in results only)
        regex: treat pattern as a regular expression
        ignore_case: case-insensitive matching

    Returns:
        List of SearchResult, one per matching line (all occurrences on that line).
    """
    flags = re.IGNORECASE if ignore_case else 0

    if regex:
        try:
            compiled = re.compile(pattern, flags)
        except re.error as e:
            raise ValueError(f"Invalid regex pattern {pattern!r}: {e}") from e
    else:
        escaped = re.escape(pattern)
        compiled = re.compile(escaped, flags)

    results: list[SearchResult] = []
    for lineno, line in enumerate(source.splitlines(), start=1):
        for match in compiled.finditer(line):
            results.append(
                SearchResult(
                    file=path,
                    line=lineno,
                    col=match.start() + 1,  # 1-based
                    text=line,
                    match_type="string",
                    capture="",
                )
            )

    return results
