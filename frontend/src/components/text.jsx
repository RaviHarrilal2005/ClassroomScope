/**
 * Small text helpers shared by the filter panel, article table and
 * comment results.
 */

/** "trade_publication" → "Trade publication"; an em dash for nothing. */
export function humanize(code) {
  if (!code) return "—";
  const words = code.replace(/_/g, " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

/**
 * "2026-08-17T10:00:00+00:00" → "17 Aug 2026" in the viewer's locale; an em dash when missing.
 * Shown in UTC, not local time: the backend filters on the UTC date part,
 * so a local date could disagree with the From/To filter.
 */
export function formatDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? "—"
    : d.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
}

/** `text` with every case-insensitive occurrence of `query` wrapped in <mark>. */
export function Highlight({ text, query }) {
  if (!text) return null;
  if (!query) return text;
  const haystack = text.toLowerCase();
  const needle = query.toLowerCase();
  const parts = [];
  let at = 0;
  for (let hit = haystack.indexOf(needle); hit !== -1; hit = haystack.indexOf(needle, at)) {
    parts.push(text.slice(at, hit), <mark key={hit}>{text.slice(hit, hit + needle.length)}</mark>);
    at = hit + needle.length;
  }
  parts.push(text.slice(at));
  return <>{parts}</>;
}
