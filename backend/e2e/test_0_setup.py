"""S1-S3 run in the `environment` fixture (conftest.py); this records what they found."""
import requests
from playwright.sync_api import expect

from e2e.settings import PAGE_TIMEOUT


def test_s_setup_checks_passed(environment, record_property):
    record_property("note", f"database {environment.database}")
    record_property("note", f"classifier: {environment.classifier}")
    record_property("note", f"topic model: {environment.topic_model}")


def test_h1_backend_and_frontend_start(backend, frontend, page):
    assert requests.get(f"{backend.url}/api/v1/health", timeout=30).json() == {"status": "ok"}
    page.goto(frontend.url, timeout=PAGE_TIMEOUT)
    expect(page.get_by_text("ClassroomScope", exact=True)).to_be_visible(timeout=PAGE_TIMEOUT)
