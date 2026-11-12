// Run with `npm test` (Node's built-in runner; no dependency).
import assert from "node:assert/strict";
import { test } from "node:test";
import { monthlyShares } from "./months.js";

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
