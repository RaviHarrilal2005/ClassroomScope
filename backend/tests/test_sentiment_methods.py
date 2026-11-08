"""roberta_news and roberta_news_v2 are saved under different names, so
they must read the article differently: v2 adds the headline, the
original reads fixed token windows without it. A fake model records what
it read."""
from agents.sentiment import sentiment_agent as agent


class WordTokenizer:
    def encode(self, text, add_special_tokens=False):
        return text.split()

    def decode(self, tokens, skip_special_tokens=True):
        return " ".join(tokens)


def fake_roberta(seen):
    def model(texts, **kwargs):
        seen.extend(texts)
        return [[{"label": "neutral", "score": 1.0}] for _ in texts]
    return lambda: (model, WordTokenizer())


def test_original_method_reads_no_headline_and_fixed_windows(monkeypatch):
    seen = []
    monkeypatch.setattr(agent, "load_roberta", fake_roberta(seen))
    monkeypatch.setattr(agent, "ORIGINAL_CHUNK_SIZE", 3)
    assert agent.label_article("One two. Three four.", "roberta_news", title="Headline") == ("neutral", 1.0)
    assert seen == ["One two. Three", "four."]


def test_v2_reads_the_headline(monkeypatch):
    seen = []
    monkeypatch.setattr(agent, "load_roberta", fake_roberta(seen))
    agent.label_article("One two. Three four.", "roberta_news_v2", title="Headline")
    assert seen == ["Headline. One two. Three four."]
