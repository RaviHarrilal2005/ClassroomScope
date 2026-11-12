/**
 * The API's sentiment_over_time rows (counts, ascending "YYYY-MM") as
 * shares (0–1), with every month from the first to the last.
 *
 * A month with no articles stays in as an empty column with total 0, so
 * the x-axis spaces months evenly: dropping it would draw June beside
 * September as if nothing happened between them. `step` is the gap
 * between periods: 3 when the rows are quarters (see bucketByQuarter).
 */
export function monthlyShares(rows, step = 1) {
  if (rows.length === 0) return [];
  const byMonth = new Map(rows.map((r) => [r.label, r]));
  const last = rows[rows.length - 1].label;
  let [y, m] = rows[0].label.split("-").map(Number);
  const months = [];
  for (;;) {
    const label = `${y}-${String(m).padStart(2, "0")}`;
    const r = byMonth.get(label) ?? { positive: 0, neutral: 0, negative: 0, total: 0 };
    const share = (field) => (r.total ? r[field] / r.total : 0);
    months.push({ label, total: r.total, positive: share("positive"), neutral: share("neutral"), negative: share("negative") });
    if (label >= last || months.length > 1200) return months; // 1200: a malformed label can't loop forever
    const next = y * 12 + (m - 1) + step;
    [y, m] = [Math.floor(next / 12), (next % 12) + 1];
  }
}

/** Past this many months the chart bins by quarter, so 49 months don't scroll sideways. */
export const SPAN_LIMIT = 20; // 20 columns = 768px, fits the card at 1280

/** Calendar months from the first label to the last, both included; 0 for no rows. */
export function monthSpan(rows) {
  if (rows.length === 0) return 0;
  const [y1, m1] = rows[0].label.split("-").map(Number);
  const [y2, m2] = rows[rows.length - 1].label.split("-").map(Number);
  return (y2 - y1) * 12 + (m2 - m1) + 1;
}

/**
 * Monthly rows summed into calendar quarters, each labelled by its first
 * month ("2026-07" for Q3 2026), so Q1 is "YYYY-01" and Q4 is "YYYY-10".
 */
export function bucketByQuarter(rows) {
  const byQuarter = new Map();
  for (const r of rows) {
    const [y, m] = r.label.split("-");
    const label = `${y}-${String(Math.floor((Number(m) - 1) / 3) * 3 + 1).padStart(2, "0")}`;
    const q = byQuarter.get(label) ?? { label, positive: 0, neutral: 0, negative: 0, total: 0 };
    q.positive += r.positive;
    q.neutral += r.neutral;
    q.negative += r.negative;
    q.total += r.total;
    byQuarter.set(label, q);
  }
  return [...byQuarter.values()];
}
