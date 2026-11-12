/**
 * The filters and the open tab, to and from the page's query string, so a
 * filtered view can be bookmarked, shared or survive a refresh.
 * ViewStateContext.jsx reads it on load and writes it on every change.
 *
 * A hand-edited or stale link must not break the page: parseQuery keeps
 * only what the backend would accept (orchestrator/corpus.py,
 * parse_filters), and keepKnown drops dropdown values the corpus lacks.
 */
export const EMPTY_FILTERS = { from: "", to: "", source_type: "", stakeholder: "", topic: "", q: "" };
export const DEFAULT_VIEW = "dashboard";
const VIEWS = [DEFAULT_VIEW, "runs"];

// 2026-02-30 parses (it rolls over to March), so the round trip checks it is a real day.
const isDay = (value) =>
  /^\d{4}-\d{2}-\d{2}$/.test(value) && !Number.isNaN(Date.parse(value)) && new Date(value).toISOString().startsWith(value);

/** { filters, view } from a query string like location.search. */
export function parseQuery(search) {
  const params = new URLSearchParams(search);
  const filters = { ...EMPTY_FILTERS };
  for (const key of Object.keys(EMPTY_FILTERS)) {
    const value = (params.get(key) ?? "").trim();
    if (value.length <= 100) filters[key] = value;
  }
  for (const key of ["from", "to"]) if (!isDay(filters[key])) filters[key] = "";
  if (filters.from && filters.to && filters.from > filters.to) filters.to = "";
  if (filters.q.length < 2) filters.q = "";
  const view = VIEWS.includes(params.get("view")) ? params.get("view") : DEFAULT_VIEW;
  return { filters, view };
}

/** The query string for these filters and tab, defaults left out; "" when nothing is set. */
export function toQuery(filters, view) {
  const params = new URLSearchParams(Object.entries(filters).filter(([, value]) => value));
  if (view !== DEFAULT_VIEW) params.set("view", view);
  const query = params.toString();
  return query ? `?${query}` : "";
}

/**
 * The filters without dropdown values missing from the corpus's options
 * (/results filter_options). Returns the same object when nothing is
 * dropped. An empty option list (no corpus, e.g. run_dev_server.py) proves
 * nothing, so it drops nothing.
 */
export function keepKnown(filters, options) {
  const known = {
    source_type: options?.source_types,
    stakeholder: options?.stakeholders,
    topic: options?.topics?.map((t) => t.id),
  };
  const unknown = Object.keys(known).filter((key) => filters[key] && known[key]?.length && !known[key].includes(filters[key]));
  return unknown.length ? { ...filters, ...Object.fromEntries(unknown.map((key) => [key, ""])) } : filters;
}
