# fetchers.py
"""
Article fetchers for ClassroomScope.
Each function returns a list of dicts with a consistent shape:
    {
        "title": str,
        "author": str | None,
        "published_date": str | None,
        "source": str,
        "url": str,
        "content": str,
    }
"""

import os
import time

import feedparser
import requests

from ..supabase_client import ENV_PATH


def _api_key(name):
    """
    Read an API key when it is needed, not when the module is imported.

    These were module-level constants read after a bare load_dotenv(),
    which only finds .env when the process happens to start in the right
    directory. Imported by the pipeline rather than run as a script, that
    left both keys permanently None.
    """
    try:
        from dotenv import load_dotenv
    except ImportError:
        pass
    else:
        load_dotenv(ENV_PATH)
    return os.environ.get(name)

SEARCH_QUERIES = [
    "generative AI education",
    "ChatGPT education",
    "artificial intelligence classroom",
    "AI cheating university",
    "LLM college students",
]

RSS_FEEDS = [
    "https://hechingerreport.org/feed/",
    "https://www.insidehighered.com/rss.xml",
    "https://www.edsurge.com/articles_rss",
    "https://www.highereddive.com/feeds/news/",
    "https://www.eschoolnews.com/feed/",
    "https://theconversation.com/articles.atom?section=education",
]

def fetch_from_newsapi(page_size=100):
    news_api_key = _api_key("NEWS_API_KEY")
    if not news_api_key:
        print("NEWS_API_KEY not set in .env")
        return []

    url = "https://newsapi.org/v2/everything"
    articles = []

    for query in SEARCH_QUERIES:
        time.sleep(1)
        params = {
            "q": query,
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": page_size,
            "apiKey": news_api_key,
        }
        try:
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            print(f"NewsAPI error for '{query}': {e}")
            continue

        for item in data.get("articles", []):
            articles.append({
                "title": item.get("title"),
                "author": item.get("author"),
                "published_date": item.get("publishedAt"),
                "source": (item.get("source") or {}).get("name"),
                "url": item.get("url"),
                "content": item.get("content") or item.get("description") or "",
            })

    return articles

def fetch_from_gnews(max_articles=10):
    gnews_api_key = _api_key("GNEWS_API_KEY")
    if not gnews_api_key:
        print("GNEWS_API_KEY not set in .env")
        return []

    url = "https://gnews.io/api/v4/search"
    articles = []

    for query in SEARCH_QUERIES:
        time.sleep(2)   # GNews free tier is ~1 req/sec
        params = {
            "q": query,
            "lang": "en",
            "max": max_articles,
            "apikey": gnews_api_key,
        }
        try:
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            print(f"GNews error for '{query}': {e}")
            continue

        for item in data.get("articles", []):
            articles.append({
                "title": item.get("title"),
                "author": None,
                "published_date": item.get("publishedAt"),
                "source": (item.get("source") or {}).get("name"),
                "url": item.get("url"),
                "content": item.get("content") or item.get("description") or "",
            })

    return articles

def fetch_from_rss(feeds=RSS_FEEDS):
    articles = []
    for feed_url in feeds:
        feed = feedparser.parse(feed_url)
        feed_title = feed.feed.get("title", feed_url)

        if feed.bozo and not feed.entries:
            print(f"RSS parse issue for {feed_url}: {feed.bozo_exception}")

        for entry in feed.entries:
            articles.append({
                "title": entry.get("title"),
                "author": entry.get("author"),
                "published_date": entry.get("published"),
                "source": feed_title,
                "url": entry.get("link"),
                "content": entry.get("summary", ""),
            })
    return articles