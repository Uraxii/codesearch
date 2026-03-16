from pathlib import Path

try:
    import tree_sitter_python as _tspython
except ImportError:
    _tspython = None  # type: ignore[assignment]

try:
    import tree_sitter_javascript as _tsjavascript
except ImportError:
    _tsjavascript = None  # type: ignore[assignment]

try:
    import tree_sitter_typescript as _tstypescript
except ImportError:
    _tstypescript = None  # type: ignore[assignment]

try:
    import tree_sitter_c_sharp as _tscsharp
except ImportError:
    _tscsharp = None  # type: ignore[assignment]

from tree_sitter import Language


def _py() -> Language:
    if _tspython is None:
        raise ImportError("tree-sitter-python is not installed")
    return Language(_tspython.language())


def _js() -> Language:
    if _tsjavascript is None:
        raise ImportError("tree-sitter-javascript is not installed")
    return Language(_tsjavascript.language())


def _ts() -> Language:
    if _tstypescript is None:
        raise ImportError("tree-sitter-typescript is not installed")
    return Language(_tstypescript.language_typescript())


def _tsx() -> Language:
    if _tstypescript is None:
        raise ImportError("tree-sitter-typescript is not installed")
    return Language(_tstypescript.language_tsx())


def _cs() -> Language:
    if _tscsharp is None:
        raise ImportError("tree-sitter-c-sharp is not installed")
    return Language(_tscsharp.language())


# Maps file extension → language name and factory
_EXT_MAP: dict[str, tuple[str, callable]] = {
    ".py":  ("python",     _py),
    ".js":  ("javascript", _js),
    ".ts":  ("typescript", _ts),
    ".tsx": ("tsx",        _tsx),
    ".cs":  ("c_sharp",    _cs),
}

# Maps language name → canonical extensions
_LANG_EXTENSIONS: dict[str, set[str]] = {
    "python":     {".py"},
    "javascript": {".js"},
    "typescript": {".ts", ".tsx"},
    "tsx":        {".tsx"},
    "c_sharp":    {".cs"},
    "csharp":     {".cs"},
    "cs":         {".cs"},
}


def get_language_name(path: Path) -> str | None:
    """Return the canonical language name for path based on its extension, or None if unknown."""
    entry = _EXT_MAP.get(path.suffix.lower())
    return entry[0] if entry else None


def get_language(path: Path) -> Language | None:
    """Return the Language for path based on its extension, or None if unknown."""
    entry = _EXT_MAP.get(path.suffix.lower())
    if entry is None:
        return None
    _, factory = entry
    return factory()


def should_process(path: Path, lang_hint: str | None) -> Language | None:
    """
    Return the Language to use when processing path, or None to skip.

    Rules:
    - lang_hint given + known extension that matches → use that language
    - lang_hint given + known extension that doesn't match → skip (return None)
    - lang_hint given + no extension → caller should attempt parse; returns language
    - lang_hint given + unknown extension → skip
    - no lang_hint + known extension → use registered language
    - no lang_hint + no/unknown extension → skip
    """
    suffix = path.suffix.lower()

    if lang_hint is not None:
        hint = lang_hint.lower()
        allowed_exts = _LANG_EXTENSIONS.get(hint)
        if allowed_exts is None:
            # Unknown lang hint — try to find by name match
            for lang_name, exts in _LANG_EXTENSIONS.items():
                if lang_name.startswith(hint):
                    allowed_exts = exts
                    hint = lang_name
                    break

        if suffix == "":
            # No extension: return the hinted language so caller can attempt parse
            entry = next(
                ((n, f) for ext, (n, f) in _EXT_MAP.items()
                 if n == hint or ext in (allowed_exts or set())),
                None,
            )
            return entry[1]() if entry else None

        if allowed_exts and suffix in allowed_exts:
            return _EXT_MAP[suffix][1]()

        return None  # extension doesn't match hint → skip

    # No hint: use extension registry
    return get_language(path)
