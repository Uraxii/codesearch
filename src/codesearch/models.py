from dataclasses import dataclass
from pathlib import Path


@dataclass
class SearchResult:
    file: Path
    line: int       # 1-based
    col: int        # 1-based
    text: str       # matched line text (string) or node text (AST)
    match_type: str # "string" | "ast"
    capture: str    # capture name for AST results, "" for string results
    severity: str = "medium"  # critical | high | medium | low | info


@dataclass
class ParseWarning:
    file: Path
    message: str
