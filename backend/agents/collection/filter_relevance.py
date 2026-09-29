# filter_relevance.py
"""Mark articles as relevant (GenAI + education) or not.
Reads all rows where is_relevant IS NULL, checks keywords, writes the flag.
Usage:
    python filter_relevance.py
"""

from ..supabase_client import get_client

# Must hit at least one from each list to qualify.
GAI_TERMS = [
    "generative ai", "genai", "gen ai", "chatgpt", "gpt-4", "gpt-3",
    "llm", "large language model", "claude", "gemini", "copilot",
    "artificial intelligence", "ai tool", "ai model", "ai",
]

EDU_TERMS = [
    "education", "school", "student", "teacher", "faculty", "classroom",
    "university", "college", "curriculum", "higher ed", "k-12",
    "academic", "professor", "campus", "learning", "elementary",
]


def is_relevant(title, content):
    text = f"{title or ''} {content or ''}".lower()
    has_gai = any(term in text for term in GAI_TERMS)
    has_edu = any(term in text for term in EDU_TERMS)
    return has_gai and has_edu


def run(article_ids=None):
    """
    Set is_relevant on rows that do not have it yet.

    article_ids narrows the work to one run's articles; without it the
    whole unclassified backlog is checked.
    """
    if article_ids is not None and not article_ids:
        print("Checking 0 unclassified articles...")
        return {"checked": 0, "relevant": 0, "irrelevant": 0}

    query = (
        get_client().table("articles")
        .select("id, title, content")
        .is_("is_relevant", "null")
    )
    if article_ids is not None:
        query = query.in_("id", list(article_ids))
    response = query.execute()
    rows = response.data or []
    print(f"Checking {len(rows)} unclassified articles...")

    relevant_count = 0
    for row in rows:
        flag = is_relevant(row.get("title"), row.get("content"))
        get_client().table("articles").update(
            {"is_relevant": flag}
        ).eq("id", row["id"]).execute()
        relevant_count += int(flag)

    print(f"Marked {relevant_count} as relevant, "
          f"{len(rows) - relevant_count} as irrelevant.")
    return {"checked": len(rows), "relevant": relevant_count,
            "irrelevant": len(rows) - relevant_count}


if __name__ == "__main__":
    run()