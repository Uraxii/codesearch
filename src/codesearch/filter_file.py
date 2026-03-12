"""Parser for named-query filter files (INI format).

Filter files let you define a collection of named queries in a single file
and run all of them in one invocation.  Each match is labelled with the
query name rather than the internal capture name.

File format (INI / configparser)::

    [query-name]
    type     = query | regex | ast | string
    pattern  = <pattern or DSL expression>
    lang     = c_sharp          # optional — restrict to one language
    captures = _param, _name   # optional — ast only; which captures to output

    [another-query]
    type    = regex
    pattern = some_pattern

``type`` defaults to ``string`` if omitted.
``lang`` accepts the same values as the ``--lang`` CLI flag.
``captures`` is only meaningful for ``type = ast`` queries.  It is a
comma-separated list of tree-sitter capture names (without the ``@`` sigil).
When set, only captures whose names appear in this list are included in the
output; other captures are used purely as filters inside the query predicate
and suppressed from results.  When omitted, all captures are output.
"""

from __future__ import annotations

import configparser
from dataclasses import dataclass, field
from pathlib import Path

_VALID_TYPES = frozenset({"query", "regex", "ast", "string"})


@dataclass
class FilterQuery:
    name: str
    type: str              # "query" | "regex" | "ast" | "string"
    pattern: str
    lang: str | None
    captures: frozenset[str] | None = field(default=None)  # None = all captures


def parse_filter_file(path: Path) -> list[FilterQuery]:
    """Parse a filter file and return a list of named queries.

    Raises:
        ValueError: if the file cannot be read or contains invalid entries.
    """
    cp = configparser.ConfigParser(interpolation=None)
    try:
        with path.open(encoding="utf-8") as fh:
            cp.read_file(fh)
    except OSError as e:
        raise ValueError(f"Cannot read filter file {path}: {e}") from e
    except configparser.Error as e:
        raise ValueError(f"Invalid filter file {path}: {e}") from e

    queries: list[FilterQuery] = []
    for section in cp.sections():
        entry = cp[section]

        if "pattern" not in entry:
            raise ValueError(
                f"Filter file {path}: [{section}] is missing required field 'pattern'"
            )

        query_type = entry.get("type", "string").lower()
        if query_type not in _VALID_TYPES:
            raise ValueError(
                f"Filter file {path}: [{section}] has unknown type {query_type!r}. "
                f"Valid types: {', '.join(sorted(_VALID_TYPES))}"
            )

        lang = entry.get("lang") or None

        captures: frozenset[str] | None = None
        if raw_captures := entry.get("captures"):
            captures = frozenset(c.strip() for c in raw_captures.split(",") if c.strip())

        queries.append(
            FilterQuery(
                name=section,
                type=query_type,
                pattern=entry["pattern"],
                lang=lang,
                captures=captures,
            )
        )

    return queries
