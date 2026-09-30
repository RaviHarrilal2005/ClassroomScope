"""
Reading optional credentials out of the environment.

Every key in .env.example ships with a placeholder. A caller that only
checks whether the variable is set treats "your-newsapi-key" as a real
key, and the result is never a clear error — it is five 401s a second
apart from the news fetcher, or an LLM classifier that burns its
retries before falling back to the keyword scorer.

`optional_key()` treats a placeholder as absent, which is what the
person who copied the example file meant.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

# backend/.env, whatever the working directory.
ENV_PATH = Path(__file__).resolve().parents[1] / ".env"

# Lowercase prefixes that mark a value as "fill this in". Anchored at
# the start so a real key that happens to contain one of these words is
# not thrown away.
PLACEHOLDER_PREFIXES = ("your-", "your_", "yourkey", "<", "changeme", "replace-", "replace_", "xxx")


def load_env() -> None:
    """Load backend/.env if python-dotenv is available. Real env vars win."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(ENV_PATH)


def is_placeholder(value: Optional[str]) -> bool:
    """Whether a value is empty or an unfilled example value."""
    text = (value or "").strip()
    if not text:
        return True
    lowered = text.lower()
    return any(lowered.startswith(prefix) for prefix in PLACEHOLDER_PREFIXES)


def optional_key(name: str) -> Optional[str]:
    """An environment value, or None if it is missing or a placeholder."""
    load_env()
    value = os.environ.get(name)
    return None if is_placeholder(value) else value
