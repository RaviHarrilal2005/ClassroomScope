"""Small helpers for the dashboard checks."""
from __future__ import annotations

from pathlib import Path
from typing import Any, List

# Every chart label whose box pokes outside its <svg>. SVG clips to its
# viewport, so these are cut off on screen.
CLIPPED_LABELS = """() => [...document.querySelectorAll("svg.recharts-surface")].flatMap((svg) => {
  const s = svg.getBoundingClientRect();
  return [...svg.querySelectorAll("text")]
    .filter((t) => {
      const r = t.getBoundingClientRect();
      return r.left < s.left || r.top < s.top || r.right > s.right || r.bottom > s.bottom;
    })
    .map((t) => t.textContent);
})"""


def watch_console(page: Any) -> List[str]:
    """Collects console errors and uncaught page errors for the rest of the test."""
    problems: List[str] = []
    page.on("console", lambda msg: problems.append(f"console {msg.type}: {msg.text}")
            if msg.type == "error" else None)
    page.on("pageerror", lambda exc: problems.append(f"page error: {exc}"))
    return problems


def screenshot(page: Any, results_dir: Path, name: str, record_property: Any) -> None:
    page.screenshot(path=str(results_dir / name), full_page=True)
    record_property("screenshot", name)
