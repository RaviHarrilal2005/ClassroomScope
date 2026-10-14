"""R1: the results endpoint's topic counts against Supabase's own counts."""
import requests

from e2e import database


def test_r1_topic_counts_match_the_database(backend, environment, record_property):
    facet = requests.get(f"{backend.url}/api/v1/results", timeout=60).json()["top_topics"]
    expected = database.topic_facet(environment.client)
    record_property("note", f"{expected['counted']} articles with a topic, {expected['unassigned']} unassigned")
    assert facet["available"] is True, facet.get("reason")
    assert (facet["counted"], facet["unassigned"]) == (expected["counted"], expected["unassigned"])
    assert facet["items"] == expected["items"]
