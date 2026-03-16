"""Shared test helpers for filter-file-based integration tests."""

import io
from unittest.mock import patch

from codesearch.__main__ import main


def run_main(argv: list[str]) -> str:
    """Run main() capturing stdout and returning it as a string."""
    buf = io.StringIO()
    with patch("sys.stdout", buf):
        try:
            main(argv)
        except SystemExit:
            pass
    return buf.getvalue()
