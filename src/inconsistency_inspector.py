"""Backward-compatible entry point for optional output verification."""

from swap_report import (
    SwapSummary,
    format_summary_report,
    print_summary_report,
    run_verification,
)

__all__ = [
    "SwapSummary",
    "format_summary_report",
    "print_summary_report",
    "run_verification",
]
