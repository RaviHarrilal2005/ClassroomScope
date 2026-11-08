"""comments.comment_id is text but comment_sentiment_results.comment_id is
bigint, so Supabase hands done ids back as ints. find_done must still match
them against the string ids from comments, or every run re-labels and
re-inserts every comment."""
from types import SimpleNamespace

from agents.sentiment import comment_sentiment_agent as agent


class ResultsTable:
    """Answers find_done's query the way the real bigint column does."""

    def __init__(self, ids):
        self.ids = ids
        self.inserted = []

    def table(self, name):
        return self

    def select(self, columns):
        return self

    def in_(self, column, values):
        self.wanted = {int(v) for v in values}
        return self

    def eq(self, column, value):
        return self

    def insert(self, rows):
        self.inserted.extend(rows)
        return self

    def execute(self):
        return SimpleNamespace(data=[{"comment_id": i} for i in self.ids if i in self.wanted])


def test_done_ids_match_the_string_ids_comments_use():
    database = ResultsTable([160745544])
    assert agent.find_done(database, ["160745544", "160745545"]) == {"160745544"}


def test_save_results_skips_comments_already_saved():
    database = ResultsTable([160745544])
    row = {"comment_id": "160745544", "article_id": 5265, "sentiment": "neutral",
           "confidence": 0.9, "method": agent.METHOD}
    assert agent.save_results(database, [row]) == 0
    assert database.inserted == []
