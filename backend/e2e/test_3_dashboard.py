"""D1-D4: the dashboard in Chromium, against the real backend."""
import re
from decimal import ROUND_HALF_UP, Decimal

import requests
from playwright.sync_api import expect

from e2e import database
from e2e.browser import CLIPPED_LABELS, screenshot, watch_console
from e2e.settings import PAGE_TIMEOUT, RUN_TIMEOUT


def squash(text: str) -> str:
    """Axis labels wrap onto two lines with no space between them in the text; compare without spaces."""
    return re.sub(r"\s+", "", text)


def percent(share: float) -> int:
    """A share as the donut labels it: JavaScript's toFixed(0), which rounds halves up."""
    return int(Decimal(share * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def open_pipeline_runs(page):
    page.get_by_role("navigation", name="Views").get_by_role("button", name="Pipeline runs").click()


def test_d1_dashboard_shows_real_topics_and_sentiment(
        page, frontend, environment, results_dir, record_property):
    problems = watch_console(page)
    page.goto(frontend.url, timeout=PAGE_TIMEOUT)
    expected = database.topic_facet(environment.client)
    counted, unassigned = expected["counted"], expected["unassigned"]
    total = counted + unassigned
    expect(page.get_by_text(f"{counted} of {total} matching article(s) have a topic; "
                            f"{unassigned} don't fit any topic yet.")).to_be_visible(timeout=PAGE_TIMEOUT)

    expect(page.locator("svg.recharts-surface")).to_have_count(2)
    labels = page.locator(".recharts-yAxis-tick-labels text")
    expect(labels).to_have_count(len(expected["items"]))
    assert ([squash(text) for text in labels.all_text_contents()]
            == [squash(item["label"]) for item in expected["items"]])
    assert (page.locator(".recharts-label-list text").all_text_contents()
            == [str(item["count"]) for item in expected["items"]])
    assert page.evaluate(CLIPPED_LABELS) == []
    sentiment = database.sentiment_facet(environment.client)
    expect(page.get_by_text("Placeholder figures")).to_have_count(0)
    expect(page.get_by_text(f"Share of the {sentiment['analysed']} matching article(s) "
                            "with a sentiment result.")).to_be_visible()
    for name, share in sentiment["shares"].items():
        expect(page.get_by_text(f"{name.capitalize()} {percent(share)}%", exact=True)).to_be_visible()
    expect(page.get_by_text(f"Showing {total} of {total} articles")).to_be_visible()
    expect(page.locator("table.data-table tbody tr")).to_have_count(total)
    screenshot(page, results_dir, "D1-dashboard.png", record_property)
    assert problems == []


def test_d4_a_search_with_one_sentiment_labels_only_its_slice(page, frontend, backend, environment):
    # Filters can leave a sentiment at 0%; a zero slice's label is drawn on
    # top of the other zero slice's. Search for one article's title so some
    # share is zero, then expect a label only for each share above zero.
    titles = [row["title"] for row in environment.client.table("articles").select("title")
              .eq("llm_relevant", True).eq("processing_status", "success").order("id", desc=True)
              .limit(20).execute().data if 25 <= len(row["title"] or "") <= 100]
    for title in titles:
        body = requests.get(f"{backend.url}/api/v1/results", params={"q": title}, timeout=60).json()
        if body["analysed"] and 0 in body["sentiment_distribution"].values():
            break
    else:
        raise AssertionError("no recent title gives a search with a zero sentiment share")
    shown = {name: share for name, share in body["sentiment_distribution"].items() if share > 0}

    page.goto(frontend.url, timeout=PAGE_TIMEOUT)
    page.get_by_placeholder("e.g. cheating").fill(title)
    page.get_by_role("button", name="Search").click()
    expect(page.get_by_text(f"Share of the {body['analysed']} matching article(s)")).to_be_visible(timeout=PAGE_TIMEOUT)
    expect(page.locator(".recharts-pie-label-text")).to_have_text(
        [f"{name.capitalize()} {percent(share)}%" for name, share in shown.items()])


def test_d2_admin_console_lists_the_api_run(page, frontend, api_run):
    run_id = api_run.first.json()["id"]
    page.goto(frontend.url, timeout=PAGE_TIMEOUT)
    open_pipeline_runs(page)
    entry = page.get_by_role("button", name=re.compile(rf"^#{run_id}\b"))
    expect(entry.locator(".badge")).to_have_text("completed", timeout=PAGE_TIMEOUT)


def test_d3_start_a_run_from_the_dashboard(page, frontend, api_run, results_dir, record_property):
    problems = watch_console(page)
    page.goto(frontend.url, timeout=PAGE_TIMEOUT)
    open_pipeline_runs(page)
    title = page.locator(".run-title")
    # The console selects the newest run as it loads; clicking before that
    # lets the late selection replace the run this test starts.
    expect(title).to_be_visible(timeout=PAGE_TIMEOUT)
    button = page.get_by_role("button", name=re.compile("^(Start a run|Starting…|Run in progress…)$"))
    expect(button).to_have_text("Start a run", timeout=PAGE_TIMEOUT)

    button.click()
    expect(button).to_be_disabled(timeout=PAGE_TIMEOUT)
    expect(title).not_to_have_text(f"Run #{api_run.first.json()['id']}", timeout=PAGE_TIMEOUT)
    status = title.locator("xpath=following-sibling::span[1]")
    expect(status).to_have_text("running", timeout=PAGE_TIMEOUT)
    screenshot(page, results_dir, "D3-running.png", record_property)

    # Any final state ends the wait; only "completed" passes.
    expect(status).to_have_text(re.compile("^(completed|completed with errors|failed)$"), timeout=RUN_TIMEOUT * 1000)
    expect(status).to_have_text("completed")
    statuses = page.locator("table.data-table tbody tr td:nth-child(2)")
    expect(statuses).to_have_text(["succeeded"] * 7)
    expect(button).to_have_text("Start a run")
    expect(button).to_be_enabled()
    record_property("note", title.text_content() or "")
    screenshot(page, results_dir, "D3-finished.png", record_property)
    assert problems == []
