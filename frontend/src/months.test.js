// Run with `npm test` (Node's built-in runner; no dependency).
import assert from "node:assert/strict";
import { test } from "node:test";
import { bucketByQuarter, monthlyShares, monthSpan } from "./months.js";

const row = (label, positive, neutral, negative) =>
  ({ label, positive, neutral, negative, total: positive + neutral + negative });

test("counts become shares of the month's total", () => {
  assert.deepEqual(monthlyShares([row("2026-09", 1, 2, 1)]),
                   [{ label: "2026-09", total: 4, positive: 0.25, neutral: 0.5, negative: 0.25 }]);
});

test("fills the months between, across a new year, with empty months", () => {
  const months = monthlyShares([row("2025-11", 1, 0, 0), row("2026-02", 0, 0, 1)]);
  assert.deepEqual(months.map((m) => m.label), ["2025-11", "2025-12", "2026-01", "2026-02"]);
  assert.deepEqual(months[1], { label: "2025-12", total: 0, positive: 0, neutral: 0, negative: 0 });
});

test("no rows, no months", () => {
  assert.deepEqual(monthlyShares([]), []);
});

test("a malformed last label stops the fill instead of looping", () => {
  assert.ok(monthlyShares([row("2026-09", 1, 0, 0), row("unknown", 1, 0, 0)]).length <= 1201);
});

test("quarter step fills empty quarters across a new year", () => {
  const quarters = monthlyShares([row("2025-10", 1, 0, 0), row("2026-04", 0, 0, 1)], 3);
  assert.deepEqual(quarters.map((q) => q.label), ["2025-10", "2026-01", "2026-04"]);
  assert.deepEqual(quarters[1], { label: "2026-01", total: 0, positive: 0, neutral: 0, negative: 0 });
});

test("bucketByQuarter sums months into quarters labelled by their first month", () => {
  const quarters = bucketByQuarter([
    row("2025-11", 1, 0, 0), row("2025-12", 0, 1, 0), row("2026-01", 0, 0, 2),
    row("2026-03", 1, 1, 1), row("2026-04", 3, 0, 0),
  ]);
  assert.deepEqual(quarters, [
    { label: "2025-10", positive: 1, neutral: 1, negative: 0, total: 2 },
    { label: "2026-01", positive: 1, neutral: 1, negative: 3, total: 5 },
    { label: "2026-04", positive: 3, neutral: 0, negative: 0, total: 3 },
  ]);
});

test("bucketByQuarter keeps December and January in different quarters", () => {
  assert.deepEqual(bucketByQuarter([row("2025-12", 1, 0, 0), row("2026-01", 1, 0, 0)]).map((q) => q.label),
                   ["2025-10", "2026-01"]);
});

test("monthSpan counts calendar months, both ends included", () => {
  assert.equal(monthSpan([]), 0);
  assert.equal(monthSpan([row("2026-09", 1, 0, 0)]), 1);
  assert.equal(monthSpan([row("2025-11", 1, 0, 0), row("2026-02", 1, 0, 0)]), 4);
  assert.equal(monthSpan([row("2022-11", 1, 0, 0), row("2026-11", 1, 0, 0)]), 49);
});
