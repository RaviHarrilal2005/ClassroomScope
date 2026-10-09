"""D1-D3: the dashboard in Chromium, against the real backend."""
import re

from playwright.sync_api import expect

from e2e import database
from e2e.browser import CLIPPED_LABELS, screenshot, watch_console
from e2e.settings import PAGE_TIMEOUT, RUN_TIMEOUT


def test_d1_dashboard_shows_real_topics_and_marks_placeholders(
        page, frontend, environment, results_dir, record_property):
    problems = watch_console(page)
    page.goto(frontend.url, timeout=PAGE_TIMEOUT)
    expect(page.get_by_text("From the topic agent:")).to_be_visible(timeout=PAGE_TIMEOUT)
    expected = database.topic_facet(environment.client)

    expect(page.locator("svg.recharts-surface")).to_have_count(2)
    assert (page.locator(".recharts-yAxis-tick-labels text").all_text_contents()
            == [item["label"] for item in expected["items"]])
    assert (page.locator(".recharts-label-list text").all_text_contents()
            == [str(item["count"]) for item in expected["items"]])
    assert page.evaluate(CLIPPED_LABELS) == []
    expect(page.get_by_text("Placeholder figures, hardcoded")).to_be_visible()
    expect(page.get_by_text("Two hardcoded rows.")).to_be_visible()
    screenshot(page, results_dir, "D1-dashboard.png", record_property)
    assert problems == []


def test_d2_admin_console_lists_the_api_run(page, frontend, api_run):
    run_id = api_run.first.json()["id"]
    page.goto(frontend.url, timeout=PAGE_TIMEOUT)
    entry = page.get_by_role("button", name=re.compile(rf"^#{run_id}\b"))
    expect(entry).to_contain_text("completed", timeout=PAGE_TIMEOUT)


def test_d3_start_a_run_from_the_dashboard(page, frontend, api_run, results_dir, record_property):
    problems = watch_console(page)
    page.goto(frontend.url, timeout=PAGE_TIMEOUT)
    button = page.get_by_role("button", name=re.compile("^(Start a run|Starting…|Run in progress…)$"))
    expect(button).to_have_text("Start a run", timeout=PAGE_TIMEOUT)

    button.click()
    expect(button).to_be_disabled(timeout=PAGE_TIMEOUT)
    title = page.locator("strong", has_text=re.compile(r"^Run #\d+$"))
    expect(title).not_to_have_text(f"Run #{api_run.first.json()['id']}", timeout=PAGE_TIMEOUT)
    status = title.locator("xpath=following-sibling::span[1]")
    expect(status).to_have_text("running", timeout=PAGE_TIMEOUT)
    screenshot(page, results_dir, "D3-running.png", record_property)

    expect(status).to_have_text("completed", timeout=RUN_TIMEOUT * 1000)
    statuses = page.locator("table").filter(has_text="Attempt").locator("tbody tr td:nth-child(2)")
    expect(statuses).to_have_text(["succeeded"] * 7)
    expect(button).to_have_text("Start a run")
    expect(button).to_be_enabled()
    record_property("note", title.text_content() or "")
    screenshot(page, results_dir, "D3-finished.png", record_property)
    assert problems == []
