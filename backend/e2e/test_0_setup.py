"""S1-S3 run in the `environment` fixture (conftest.py); this records what they found."""


def test_s_setup_checks_passed(environment, record_property):
    record_property("note", f"database {environment.database}")
    record_property("note", f"classifier: {environment.classifier}")
    record_property("note", f"topic model: {environment.topic_model}")
