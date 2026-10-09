"""
The session's results file: one row per check, the database footprint,
and the failures with their screenshots.

Pure functions, so the offline suite can test the formatting; conftest.py
feeds them from pytest's reports.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Check:
    name: str
    outcome: str = "passed"      # passed, failed, skipped or error
    seconds: float = 0.0
    notes: List[str] = field(default_factory=list)
    screenshots: List[str] = field(default_factory=list)
    error: str = ""


@dataclass
class Footprint:
    before: Dict[str, int]       # row count per table
    after: Dict[str, int]
    rewritten_classifications: int
    run_ids: List[int]
    article_ids: List[int]


def duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes, rest = divmod(round(seconds), 60)
    return f"{minutes}m {rest}s"


def cell(text: str) -> str:
    """Text that is safe inside a Markdown table cell."""
    return text.replace("|", "\\|").replace("\n", " ")


def change(before: int, after: int) -> str:
    delta = after - before
    return f"{delta:+d}" if delta else "0"


def render(header: Dict[str, str], checks: List[Check], footprint: Optional[Footprint],
           stopped: Optional[str] = None) -> str:
    counts = Counter(c.outcome for c in checks)
    failed = counts["failed"] + counts["error"]
    lines = [f"# End-to-end results, {header.get('Date', '')}", "", "| | |", "|---|---|"]
    lines += [f"| {key} | {cell(value)} |" for key, value in header.items() if key != "Date"]
    lines += ["", f"**{counts['passed']} passed, {failed} failed, {counts['skipped']} skipped** "
                  f"in {duration(sum(c.seconds for c in checks))}"]
    if stopped:
        lines += ["", "## Stopped early", "", stopped]

    lines += ["", "## Checks", "", "| Check | Result | Time | Notes |", "|---|---|---|---|"]
    lines += [f"| {c.name} | {c.outcome} | {duration(c.seconds)} | {cell('; '.join(c.notes))} |"
              for c in checks]

    if footprint is not None:
        lines += ["", "## Database footprint", "", "| Table | Before | After | Change |", "|---|---|---|---|"]
        for table, before in footprint.before.items():
            after = footprint.after.get(table, before)
            lines.append(f"| {table} | {before} | {after} | {change(before, after)} |")
        runs = ", ".join(f"#{i}" for i in footprint.run_ids) or "none"
        articles = ", ".join(str(i) for i in footprint.article_ids) or "none"
        lines += ["", f"- Classification rows re-written: {footprint.rewritten_classifications}",
                  f"- Runs created: {runs}", f"- New articles: {articles}"]

    failures = [c for c in checks if c.outcome in ("failed", "error")]
    if failures:
        lines += ["", "## Failures"]
        for c in failures:
            lines += ["", f"### {c.name}", "", "```", c.error.rstrip(), "```"]
            lines += [f"Screenshot: {name}" for name in c.screenshots]
    return "\n".join(lines) + "\n"
