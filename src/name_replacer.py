"""Regex-based string replacement with safe token boundaries."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable

SCI_NOTATION_PATTERN = re.compile(r"(?<![\w.])\d+\.?\d*[Ee][-+]?\d+")


@dataclass
class ReplacementStats:
    cells_processed: int = 0
    cells_changed: int = 0
    replacement_counts: dict[str, int] = field(default_factory=dict)

    @property
    def cells_unchanged(self) -> int:
        return self.cells_processed - self.cells_changed


def build_token_pattern(old: str) -> str:
    """Build a regex that matches whole tokens, not partial compound identifiers."""
    left = r"(?<![A-Za-z0-9.])"
    escaped = re.escape(old)
    if old.endswith("_"):
        right = r"(?!_)"
    else:
        right = r"(?![A-Za-z0-9])"
    return left + escaped + right


def build_replacement_engine(name_map: dict[str, str]) -> tuple[re.Pattern[str], Callable[[re.Match[str]], str]]:
    """Compile one alternation regex sorted longest-first for efficient replacement."""
    ordered = sorted(name_map.items(), key=lambda item: len(item[0]), reverse=True)
    lookup = dict(ordered)
    patterns = [build_token_pattern(old) for old, _ in ordered]
    compiled = re.compile("|".join(f"({pattern})" for pattern in patterns))

    def replacer(match: re.Match[str]) -> str:
        matched = match.group(0)
        return lookup[matched]

    return compiled, replacer


def replace_names(
    expr: str,
    compiled: re.Pattern[str],
    replacer: Callable[[re.Match[str]], str],
    stats: ReplacementStats | None = None,
) -> str:
    if not isinstance(expr, str) or not expr:
        return expr

    protected: dict[str, str] = {}

    def protect(match: re.Match[str]) -> str:
        key = f"__PROTECTED__{len(protected)}__"
        protected[key] = match.group(0)
        return key

    expr_protected = SCI_NOTATION_PATTERN.sub(protect, expr)
    new_expr, count = compiled.subn(replacer, expr_protected)

    for key, val in protected.items():
        new_expr = new_expr.replace(key, val)

    if stats is not None and count:
        stats.cells_changed += 1

    return new_expr


def replace_text_content(
    content: str,
    name_map: dict[str, str],
    stats: ReplacementStats | None = None,
) -> str:
    """Replace identifiers in raw text while preserving line structure."""
    compiled, replacer = build_replacement_engine(name_map)
    if not content:
        return content

    lines = content.splitlines(keepends=True)
    if not lines:
        if stats is not None:
            stats.cells_processed += 1
        return replace_names(content, compiled, replacer, stats)

    updated_lines = []
    for line in lines:
        if stats is not None:
            stats.cells_processed += 1
        updated_lines.append(replace_names(line, compiled, replacer, stats))
    return "".join(updated_lines)


def replace_dataframe(
    frame,
    name_map: dict[str, str],
    stats: ReplacementStats | None = None,
):
    compiled, replacer = build_replacement_engine(name_map)

    def transform(cell):
        if stats is not None:
            stats.cells_processed += 1
        return replace_names(cell, compiled, replacer, stats)

    return frame.map(transform)
