"""Optional post-swap verification and summary reporting."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from file_loader import FileLoader

MATH_SPLIT_PATTERN = re.compile(r"([+\-/*^();,\s]+)")
NUMBER_PATTERN = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]\d+)?$")


@dataclass
class SwapSummary:
    mapping_size: int = 0
    cells_processed: int = 0
    cells_changed: int = 0
    replacement_counts: dict[str, int] = field(default_factory=dict)
    failed_unmapped: int = 0
    naming_collisions: int = 0
    standard_unique: int | None = None
    target_unique: int | None = None
    shared_overlap: int | None = None
    standard_only: int | None = None
    target_only: int | None = None
    detail_file: str | None = None

    @property
    def cells_unchanged(self) -> int:
        return self.cells_processed - self.cells_changed

    @property
    def rename_pct(self) -> float:
        if self.cells_processed == 0:
            return 0.0
        return 100.0 * self.cells_changed / self.cells_processed

    @property
    def overlap_pct(self) -> float | None:
        if self.standard_unique in (None, 0) or self.shared_overlap is None:
            return None
        return 100.0 * self.shared_overlap / self.standard_unique


def extract_identifier_tokens(value: str) -> set[str]:
    if not isinstance(value, str) or not value.strip():
        return set()

    tokens: set[str] = set()
    for part in MATH_SPLIT_PATTERN.split(value):
        part = part.strip()
        if not part or NUMBER_PATTERN.fullmatch(part):
            continue
        tokens.add(part)
    return tokens


def collect_unique_strings(frames: list[pd.DataFrame]) -> set[str]:
    unique: set[str] = set()
    for frame in frames:
        for value in frame.to_numpy().ravel().tolist():
            unique.update(extract_identifier_tokens(value))
    return unique


def count_mapping_collisions(name_map: dict[str, str]) -> int:
    seen: dict[str, list[str]] = {}
    for old, new in name_map.items():
        seen.setdefault(new, []).append(old)
    return sum(1 for olds in seen.values() if len(olds) > 1)


def count_unmapped_old_names(name_map: dict[str, str], target_strings: set[str]) -> int:
    return sum(1 for old in name_map if old in target_strings)


def run_verification(
    config,
    name_map: dict[str, str],
    output_frames: list[pd.DataFrame],
    summary: SwapSummary,
) -> SwapSummary:
    verify = config.config.get("verify", {})
    if not verify or not verify.get("enabled", False):
        summary.failed_unmapped = count_unmapped_old_names(
            name_map, collect_unique_strings(output_frames)
        )
        summary.naming_collisions = count_mapping_collisions(name_map)
        return summary

    standard_path = config.resolve(verify["standard_file"])
    standard_column = verify.get("standard_column", verify.get("column", "speciesId"))
    standard_frame = FileLoader.load_table(standard_path)
    if standard_column not in standard_frame.columns:
        raise ValueError(
            f"Verification column '{standard_column}' not found in {standard_path}"
        )

    standard_strings = set(standard_frame[standard_column].dropna().astype(str))
    target_strings = collect_unique_strings(output_frames)

    shared = standard_strings & target_strings
    summary.standard_unique = len(standard_strings)
    summary.target_unique = len(target_strings)
    summary.shared_overlap = len(shared)
    summary.standard_only = len(standard_strings - target_strings)
    summary.target_only = len(target_strings - standard_strings)
    summary.failed_unmapped = count_unmapped_old_names(name_map, target_strings)
    summary.naming_collisions = count_mapping_collisions(name_map)

    detail_name = verify.get("detail_output")
    if detail_name:
        detail_path = config.resolve(detail_name)
        detail_path.parent.mkdir(parents=True, exist_ok=True)
        detail = pd.DataFrame(
            {
                "category": ["standard_only"] * summary.standard_only
                + ["target_only"] * summary.target_only,
                "string_id": sorted(standard_strings - target_strings)
                + sorted(target_strings - standard_strings),
            }
        )
        detail.to_csv(detail_path, sep="\t", index=False)
        summary.detail_file = str(detail_path)

    return summary


def format_summary_report(summary: SwapSummary) -> str:
    lines = [
        "+--------------------------------------------------+",
        "| String Harmonization Summary                     |",
        "+--------------------------------------------------+",
        f"| Mapping entries loaded       : {summary.mapping_size:,}".ljust(51) + "|",
        f"| Target entries processed     : {summary.cells_processed:,}".ljust(51) + "|",
        f"| Entries renamed              : {summary.cells_changed:,} ({summary.rename_pct:.1f}%)".ljust(51) + "|",
        f"| Entries unchanged            : {summary.cells_unchanged:,}".ljust(51) + "|",
        f"| Failed / unmapped renames    : {summary.failed_unmapped:,}".ljust(51) + "|",
        f"| Naming collisions detected   : {summary.naming_collisions:,}".ljust(51) + "|",
    ]

    if summary.standard_unique is not None:
        overlap_pct = summary.overlap_pct if summary.overlap_pct is not None else 0.0
        lines.extend(
            [
                f"| Standard unique strings      : {summary.standard_unique:,}".ljust(51) + "|",
                f"| Target unique strings        : {summary.target_unique:,}".ljust(51) + "|",
                f"| Shared overlap               : {summary.shared_overlap:,} ({overlap_pct:.1f}% std)".ljust(51) + "|",
                f"| Standard-only / Target-only  : {summary.standard_only:,} / {summary.target_only:,}".ljust(51) + "|",
            ]
        )

    detail = summary.detail_file or "none"
    lines.append(f"| Detail files                 : {detail}".ljust(51) + "|")
    lines.append("+--------------------------------------------------+")
    return "\n".join(lines)


def print_summary_report(summary: SwapSummary) -> None:
    print(format_summary_report(summary))
