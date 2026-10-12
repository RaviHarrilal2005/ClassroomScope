"""
Juan's Guardian modules, as they sit inside the backend package.

They were written to run as scripts from the old collection/ folder, so
what can break here is the move itself: an import that only works from
that folder, or a key read once at import time instead of when needed.
"""
import importlib
import sys
from types import SimpleNamespace


def fresh_import(name):
    sys.modules.pop(name, None)
    return importlib.import_module(name)


def test_both_modules_import_from_the_package():
    fresh_import("agents.collection.guardian_fetcher")
    fresh_import("agents.collection.guardian_comments")


def test_the_api_key_is_read_when_fetching_not_on_import(monkeypatch):
    monkeypatch.delenv("GUARDIAN_API_KEY", raising=False)
    guardian = fresh_import("agents.collection.guardian_fetcher")

    page = {"response": {"pages": 1, "results": [
        {"webTitle": "Schools and ChatGPT", "webUrl": "https://www.theguardian.com/x",
         "fields": {"shortUrl": "https://www.theguardian.com/p/x5m583", "commentable": "true"}},
    ]}}
    calls = []

    def fake_get(url, params, timeout):
        calls.append(params["api-key"])
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: page)

    monkeypatch.setattr(guardian.requests, "get", fake_get)
    monkeypatch.setenv("GUARDIAN_API_KEY", "key-set-after-import")

    articles = guardian.fetch_from_guardian(max_pages=1)
    assert calls == ["key-set-after-import"]
    assert articles[0]["guardian_discussion_key"] == "/p/x5m583"
    assert articles[0]["guardian_commentable"] is True
