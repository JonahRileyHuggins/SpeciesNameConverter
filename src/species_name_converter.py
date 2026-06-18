#!/usr/bin/env python3
"""
Replace string identifiers across tabular files using an index-aligned swap table.

Run with a YAML or JSON config file that lists input files, output paths, and the
swap reference table (old column -> new column by row index).
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

from file_loader import Config, FileLoader
from name_replacer import ReplacementStats, replace_dataframe, replace_text_content
from swap_report import SwapSummary, print_summary_report, run_verification
from utils import parse_kwargs

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def collect_protected_paths(config: Config, settings: dict) -> list[Path]:
    """Paths and directories that must never be overwritten by outputs."""
    protected: list[Path] = []

    swap_ref = settings["swap_reference"]["file"]
    protected.append(config.resolve(swap_ref))

    for entry in settings.get("protected_paths", []):
        protected.append(config.resolve(entry))

    for target in settings["outputs"]:
        protected.append(config.resolve(target["input"]))

    return protected


def validate_output_path(
    output_path: Path,
    input_path: Path,
    protected_paths: list[Path],
) -> None:
    output_resolved = output_path.resolve()
    input_resolved = input_path.resolve()

    if output_resolved == input_resolved:
        raise ValueError(
            f"Output path cannot overwrite input file: {output_resolved}"
        )

    for protected in protected_paths:
        protected_resolved = protected.resolve()
        if output_resolved == protected_resolved:
            raise ValueError(
                f"Output path cannot overwrite protected file: {output_resolved}"
            )
        if protected_resolved.is_dir() and protected_resolved in output_resolved.parents:
            raise ValueError(
                f"Output path cannot be written inside protected directory "
                f"{protected_resolved}: {output_resolved}"
            )


def normalize_config(raw_config) -> dict:
    """Accept current and legacy config layouts."""
    if "swap_reference" in raw_config:
        ref = raw_config.swap_reference
        outputs = []
        for item in raw_config.get("outputs", []):
            entry = {
                "input": item["input"],
                "output": item["output"],
                "format": item.get("format", "table"),
            }
            if "header" in item:
                entry["header"] = item["header"]
            outputs.append(entry)
        return {
            "base_dir": raw_config.get("base_dir", raw_config.get("location", ".")),
            "swap_reference": {
                "file": ref["file"],
                "old_column": ref.get("old_column", ref.get("column", "old")),
                "new_column": ref.get("new_column", "new"),
            },
            "outputs": outputs,
            "verify": raw_config.get("verify", {"enabled": False}),
            "protected_paths": raw_config.get("protected_paths", []),
            "load_kwargs": raw_config.get("load_kwargs", {}),
            "save_kwargs": raw_config.get("save_kwargs", {}),
        }

    swap_files = raw_config.swap_files
    outputs = []
    update = swap_files.get("update", {})
    if isinstance(update, dict):
        for entry in update.values():
            item = {
                "input": entry["filename"],
                "output": entry["output"],
                "format": entry.get("format", "table"),
            }
            if "header" in entry:
                item["header"] = entry["header"]
            outputs.append(item)
    else:
        for entry in update:
            if isinstance(entry, dict):
                payload = {k: v for k, v in entry.items() if k not in {"filename", "output"}}
                item = {
                    "input": entry["filename"],
                    "output": entry["output"],
                    "format": payload.get("format", "table"),
                }
                if "header" in payload:
                    item["header"] = payload["header"]
                outputs.append(item)

    old = swap_files.old
    new = swap_files.new
    ref_file = old.filename if old.filename == new.filename else old.filename
    return {
        "base_dir": raw_config.get("base_dir", raw_config.get("location", ".")),
        "swap_reference": {
            "file": ref_file,
            "old_column": old.column,
            "new_column": new.column,
        },
        "outputs": outputs,
        "verify": raw_config.get("verify", {"enabled": False}),
        "protected_paths": raw_config.get("protected_paths", []),
        "load_kwargs": raw_config.get("load_kwargs", {}),
        "save_kwargs": raw_config.get("save_kwargs", {}),
    }


def build_name_map(config: Config, settings: dict, **kwargs) -> dict[str, str]:
    ref = settings["swap_reference"]
    ref_path = config.resolve(ref["file"])
    load_kwargs = {**settings.get("load_kwargs", {}), **kwargs}

    table = FileLoader.load_table(ref_path, **load_kwargs)
    if ref["old_column"] not in table.columns or ref["new_column"] not in table.columns:
        raise ValueError(
            f"Swap reference {ref_path} must contain columns "
            f"'{ref['old_column']}' and '{ref['new_column']}'"
        )

    old_names = table[ref["old_column"]].dropna().astype(str)
    new_names = table[ref["new_column"]].astype(str)[: len(old_names)]
    if len(old_names) != len(new_names):
        raise ValueError(
            f"Swap reference row mismatch in {ref_path}: "
            f"{len(old_names)} old values vs {len(new_names)} new values"
        )

    name_map = dict(zip(old_names.tolist(), new_names.tolist(), strict=True))
    logger.info("Loaded %d swap mappings from %s", len(name_map), ref_path)
    return name_map


def process_target_file(
    input_path: Path,
    name_map: dict[str, str],
    target: dict,
    load_kwargs: dict,
    stats: ReplacementStats,
) -> tuple[pd.DataFrame | None, str | None]:
    """Load and transform one target file in table or text mode."""
    mode = target.get("format", "table")
    table_kwargs = dict(load_kwargs)
    if target.get("header") is not None:
        table_kwargs["header"] = target["header"]

    if mode == "text":
        content = Path(input_path).read_text(encoding="utf-8")
        updated_text = replace_text_content(content, name_map, stats)
        return None, updated_text

    try:
        frame = FileLoader.load_table(input_path, **table_kwargs)
    except pd.errors.ParserError as exc:
        logger.warning(
            "Could not parse %s as a table (%s); using text mode instead.",
            input_path,
            exc,
        )
        content = Path(input_path).read_text(encoding="utf-8")
        updated_text = replace_text_content(content, name_map, stats)
        return None, updated_text

    updated = replace_dataframe(frame, name_map, stats)
    return updated, None


def save_target_file(
    output_path: Path,
    target: dict,
    load_kwargs: dict,
    save_kwargs: dict,
    frame: pd.DataFrame | None,
    text: str | None,
) -> None:
    if text is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text, encoding="utf-8")
        return

    write_kwargs = dict(save_kwargs)
    write_kwargs.setdefault("sep", "\t")
    write_kwargs.setdefault("index", False)
    if "header" not in write_kwargs:
        if "header" in target:
            write_kwargs["header"] = target["header"] is not None
        elif load_kwargs.get("header") is None and "header" in load_kwargs:
            write_kwargs["header"] = False
        else:
            write_kwargs["header"] = True

    FileLoader.save_table(output_path, frame, **write_kwargs)


def convert(config_path: str | Path, verbose: bool = False, **kwargs) -> SwapSummary:
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    config = Config(config_path)
    settings = normalize_config(config.config)
    config.config = config.config.__class__(
        {**config.config, **settings, "base_dir": settings["base_dir"]}
    )

    logger.info("Starting string swap using config: %s", config.config_path)
    name_map = build_name_map(config, settings, **kwargs)
    protected_paths = collect_protected_paths(config, settings)

    load_kwargs = {**settings.get("load_kwargs", {}), **kwargs}
    save_kwargs = settings.get("save_kwargs", {})
    stats = ReplacementStats()
    output_frames: list[pd.DataFrame] = []

    for index, target in enumerate(settings["outputs"], start=1):
        input_path = config.resolve(target["input"])
        output_path = config.resolve(target["output"])
        validate_output_path(output_path, input_path, protected_paths)
        logger.info(
            "Processing file [%d/%d]: %s -> %s",
            index,
            len(settings["outputs"]),
            input_path,
            output_path,
        )

        frame, text = process_target_file(
            input_path, name_map, target, load_kwargs, stats
        )
        if frame is not None:
            output_frames.append(frame)
        save_target_file(output_path, target, load_kwargs, save_kwargs, frame, text)
        logger.info("Saved updated file to: %s", output_path)

    summary = SwapSummary(
        mapping_size=len(name_map),
        cells_processed=stats.cells_processed,
        cells_changed=stats.cells_changed,
        replacement_counts=stats.replacement_counts,
    )
    summary = run_verification(config, name_map, output_frames, summary)
    print_summary_report(summary)
    logger.info("All files processed successfully.")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="species_name_converter",
        description="Replace strings in tabular files using an index-aligned swap table.",
    )
    parser.add_argument(
        "--path",
        "-p",
        required=True,
        help="Path to YAML or JSON configuration file.",
    )
    parser.add_argument(
        "--catchall",
        "-c",
        metavar="KEY=VALUE",
        nargs="*",
        help="Optional key=value pairs forwarded to tabular file loading.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )
    args = parser.parse_args(argv)
    extra_kwargs = parse_kwargs(args.catchall) if args.catchall else {}

    try:
        convert(args.path, args.verbose, **extra_kwargs)
    except (ValueError, FileNotFoundError, ImportError) as exc:
        logger.error("%s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
