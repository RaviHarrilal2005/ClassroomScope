// Run with `npm test` (Node's built-in runner; no dependency).
import assert from "node:assert/strict";
import { test } from "node:test";
import { EMPTY_FILTERS, keepKnown, parseQuery, toQuery } from "./urlState.js";

const filters = { from: "2026-09-01", to: "2026-10-31", source_type: "news_outlet", stakeholder: "students", topic: "T004", q: "cheating & tests" };

test("filters and tab round-trip through the query string", () => {
  assert.deepEqual(parseQuery(toQuery(filters, "runs")), { filters, view: "runs" });
});

test("defaults and empty values are left out", () => {
  assert.equal(toQuery(EMPTY_FILTERS, "dashboard"), "");
  assert.equal(toQuery({ ...EMPTY_FILTERS, stakeholder: "students" }, "dashboard"), "?stakeholder=students");
  assert.deepEqual(parseQuery(""), { filters: EMPTY_FILTERS, view: "dashboard" });
});

test("garbage is ignored", () => {
  const { filters: parsed, view } = parseQuery(
    "?from=2026-02-30&to=yesterday&q=a&topic=" + "x".repeat(101) + "&view=admin&utm_source=mail&stakeholder=%20students%20"
  );
  assert.deepEqual(parsed, { ...EMPTY_FILTERS, stakeholder: "students" });
  assert.equal(view, "dashboard");
  // 'from' after 'to' is a 400 from the backend, so the later bound goes.
  assert.equal(parseQuery("?from=2026-10-02&to=2026-10-01").filters.to, "");
});

test("dropdown values the corpus lacks are dropped, but only once the options are known", () => {
  const options = { source_types: ["news_outlet"], stakeholders: ["students"], topics: [{ id: "T004", label: "Integrity" }] };
  assert.equal(keepKnown(filters, options), filters);
  assert.deepEqual(keepKnown({ ...filters, topic: "T999" }, options), { ...filters, topic: "" });
  const bogus = { ...filters, source_type: "nope" };
  assert.equal(keepKnown(bogus, { source_types: [], stakeholders: [], topics: [] }), bogus);
});
