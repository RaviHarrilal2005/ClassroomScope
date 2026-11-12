/**
 * The API's sentiment_over_time rows (counts, ascending "YYYY-MM") as
 * shares (0–1), with every month from the first to the last.
 *
 * A month with no articles stays in as an empty column with total 0, so
 * the x-axis spaces months evenly: dropping it would draw June beside
 * September as if nothing happened between them.
 */
export function monthlyShares(rows) {
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
    [y, m] = m === 12 ? [y + 1, 1] : [y, m + 1];
  }
}
