/**
 * The article list as a CSV file, for researchers to keep or analyse in
 * Excel, R or pandas. Built in the browser from the articles the page
 * already has, so it holds exactly what the filters and search show.
 *
 * Snake-case headers and empty cells for missing values, so R and pandas
 * read them as NA without cleanup. A byte-order mark and CRLF line ends,
 * so Excel opens it as UTF-8 (accents, curly quotes) without an import
 * dialog.
 */

const COLUMNS = [
  ["id", "id"],
  ["title", "title"],
  ["url", "url"],
  ["source", "source"],
  ["published_date", "published_date"],
  ["source_type", "source_type"],
  ["stakeholder", "stakeholder"],
  ["topic_id", "stable_topic_id"],
  ["topic", "topic"],
  ["sentiment", "sentiment"],
];
const SNIPPET = ["snippet", "snippet"];

// The order of the dashboard's filters (orchestrator/corpus.py FILTER_KEYS).
const FILTER_ORDER = ["from", "to", "source_type", "stakeholder", "topic", "q"];

/**
 * One cell. Text from news sites is untrusted: a title starting with =,
 * +, - or @ would run as a formula when the file is opened in a
 * spreadsheet, so it gets a leading apostrophe (OWASP's CSV injection
 * advice). Numbers are left alone.
 */
function cell(value) {
  if (value === null || value === undefined) return "";
  let text = String(value);
  if (typeof value === "string" && /^[=+\-@\t\r]/.test(text)) text = `'${text}`;
  return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

/** The articles as CSV text; the snippet column only when a search made one. */
export function articlesCsv(articles, { withSnippet = false } = {}) {
  const columns = withSnippet ? [...COLUMNS, SNIPPET] : COLUMNS;
  const rows = [
    columns.map(([header]) => header),
    ...articles.map((a) => columns.map(([, field]) => cell(a[field]))),
  ];
  return "﻿" + rows.map((r) => r.join(",")).join("\r\n") + "\r\n";
}

const slug = (text) => String(text).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 40);

/** e.g. classroomscope-articles_stakeholder-students_2026-10-25.csv: a saved file still says what it holds. */
export function exportFileName(filters, now = new Date()) {
  const parts = FILTER_ORDER.filter((key) => filters[key]).map((key) => `${slug(key)}-${slug(filters[key])}`);
  // en-CA formats as YYYY-MM-DD, in local time: an evening export is named for today, not tomorrow's UTC date.
  return ["classroomscope-articles", ...parts, now.toLocaleDateString("en-CA")].join("_") + ".csv";
}

/** Hand `text` to the browser as a file download. */
export function download(text, fileName) {
  const url = URL.createObjectURL(new Blob([text], { type: "text/csv;charset=utf-8" }));
  const link = Object.assign(document.createElement("a"), { href: url, download: fileName });
  link.click();
  URL.revokeObjectURL(url);
}
