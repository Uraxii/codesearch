"""Parser for named-query filter files (INI format).

Filter files let you define a collection of named queries in a single file
and run all of them in one invocation.  Each match is labelled with the
query name rather than the internal capture name.

File format (INI / configparser)::

    [query-name]
    type          = query | regex | ast | string
    pattern       = <pattern or DSL expression>
    lang          = c_sharp          # optional — restrict to one language
    captures      = _param, _name   # optional — ast only; which captures to output
    exclude       = mock|fake        # optional — drop results whose text matches (case-insensitive regex)
    exclude_files = test|mock        # optional — skip files whose path matches (case-insensitive regex)

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
``exclude`` and ``exclude_files`` are matched case-insensitively.  For string
and regex match types, ``exclude`` is tested against the full matched line.
For query and ast types it is tested against the captured node text.
"""

from __future__ import annotations

import configparser
import re
from dataclasses import dataclass, field
from pathlib import Path

_VALID_TYPES = frozenset({"query", "regex", "ast", "string"})
_VALID_SEVERITIES = frozenset({"critical", "high", "medium", "low", "info"})


@dataclass
class FilterQuery:
    name: str
    type: str              # "query" | "regex" | "ast" | "string"
    pattern: str
    lang: str | None
    captures: frozenset[str] | None = field(default=None)  # None = all captures
    description: str = ""
    fix: str = ""
    severity: str = "medium"  # critical | high | medium | low | info
    exclude: str = ""        # regex (case-insensitive): drop results whose matched text matches
    exclude_files: str = ""  # regex (case-insensitive): skip files whose path matches


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

        severity = entry.get("severity", "medium").lower()
        if severity not in _VALID_SEVERITIES:
            raise ValueError(
                f"Filter file {path}: [{section}] has invalid severity {severity!r}. "
                f"Valid values: {', '.join(sorted(_VALID_SEVERITIES))}"
            )

        exclude       = entry.get("exclude", "")
        exclude_files = entry.get("exclude_files", "")

        for field_name, value in (("exclude", exclude), ("exclude_files", exclude_files)):
            if value:
                try:
                    re.compile(value, re.IGNORECASE)
                except re.error as e:
                    raise ValueError(
                        f"Filter file {path}: [{section}] invalid {field_name} pattern: {e}"
                    ) from e

        queries.append(
            FilterQuery(
                name=section,
                type=query_type,
                pattern=entry["pattern"],
                lang=lang,
                captures=captures,
                description=entry.get("description", ""),
                fix=entry.get("fix", ""),
                severity=severity,
                exclude=exclude,
                exclude_files=exclude_files,
            )
        )

    return queries
