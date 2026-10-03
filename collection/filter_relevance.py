# filter_relevance.py
"""Relevance filter (F.3) — refined to reduce false positives.

Strategy: an article is relevant only if at least one sentence contains
BOTH a GenAI signal AND an education signal. Ambiguous words like
"classroom" and "learning" are removed from the education list because
they appear in non-educational contexts (corporate training rooms,
machine learning papers, museum tours).
"""

import re
from db import _supabase

# Strong signals — specific to generative AI in education contexts.
GAI_STRONG = [
    "generative ai", "genai", "gen ai", "chatgpt", "gpt-4", "gpt-3",
    "large language model", "llm", "claude ai", "google gemini",
    "ai chatbot", "ai writing", "ai essay", "ai cheating",
    "ai plagiarism", "ai detection", "ai tutor", "ai teaching assistant",
]

# Weaker but still indicative — must co-occur with a STRONG education term.
GAI_WEAK = [
    "artificial intelligence", "ai tool", "ai model", "ai system",
    "ai assistant", "machine learning", "neural network",
]

# Education signals — specific to educational contexts.
EDU_STRONG = [
    "student", "teacher", "professor", "faculty", "curriculum",
    "classroom", "university", "college", "higher education",
    "higher ed", "k-12", "school district", "academic integrity",
    "essay", "homework", "assignment", "exam", "coursework",
    "dean", "provost", "school board", "education",
]

# Anything matching here forces relevance to FALSE, regardless of score.
DISQUALIFIERS = [
    "fire safety", "firefighter", "military training", "corporate training",
    "healthcare", "hospital", "medical diagnosis", "clinical trial",
    "customer service", "sales team", "supply chain", "manufacturing",
    "cybersecurity", "autonomous vehicle", "self-driving",
]


def _has_any(text, terms):
    return any(t in text for t in terms)


def _split_sentences(text):
    """Naive sentence splitter."""
    return re.split(r"(?<=[.!?])\s+", text)


def is_relevant(title, content):
    """Returns True if any sentence contains both a GenAI and an
    education signal, and no disqualifier matches."""
    text = f"{title or ''} {content or ''}".lower()

    if _has_any(text, DISQUALIFIERS):
        return False

    for sentence in _split_sentences(text):
        sent = sentence.lower()
        has_gai = _has_any(sent, GAI_STRONG) or _has_any(sent, GAI_WEAK)
        has_edu = _has_any(sent, EDU_STRONG)
        if has_gai and has_edu:
            # If we only have a WEAK GenAI term, require a STRONG edu term too.
            if (_has_any(sent, GAI_WEAK)
                    and not _has_any(sent, GAI_STRONG)
                    and not _has_any(sent, ["student", "teacher",
                                            "education", "university",
                                            "college", "school"])):
                continue
            return True
    return False


def run():
    response = (
        _supabase.table("articles")
        .select("id, title, content")
        .is_("is_relevant", "null")
        .execute()
    )
    rows = response.data or []
    print(f"Checking {len(rows)} unclassified articles...")

    relevant = 0
    for row in rows:
        flag = is_relevant(row.get("title"), row.get("content"))
        _supabase.table("articles").update(
            {"is_relevant": flag}
        ).eq("id", row["id"]).execute()
        relevant += int(flag)

    print(f"Marked {relevant} relevant, {len(rows) - relevant} irrelevant.")
    return {"checked": len(rows), "relevant": relevant,
            "irrelevant": len(rows) - relevant}


if __name__ == "__main__":
    run()
