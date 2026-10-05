/**
 * How run and stage statuses look.
 *
 * Kept in one file so the console, the run list and anything added later
 * agree — a stage that reads "failed" in the table and amber in the list
 * is worse than no colour at all.
 *
 * The strings are the backend's, from orchestrator/stages.py (RunStatus
 * and StageStatus). Adding a status there means adding it here.
 *
 * Colour is never the only signal: every badge shows its label as text,
 * so the meaning survives a monochrome screen or a red-green colour
 * vision deficiency.
 */

export const GREY = { fg: "#4A4A4A", bg: "#ECECEC", border: "#D4D4D4" };
export const BLUE = { fg: "#1F4E79", bg: "#E1EDF8", border: "#B9D4EC" };
export const GREEN = { fg: "#1E6B3A", bg: "#E4F3E9", border: "#BFE0CB" };
const AMBER = { fg: "#8A5A00", bg: "#FDF1DC", border: "#F0D9A8" };
export const RED = { fg: "#A33A34", bg: "#FBE7E6", border: "#F0C4C1" };

export const RUN_STATUS = {
  running: { ...BLUE, label: "running" },
  completed: { ...GREEN, label: "completed" },
  completed_with_errors: { ...AMBER, label: "completed with errors" },
  failed: { ...RED, label: "failed" },
};

export const STAGE_STATUS = {
  pending: { ...GREY, label: "pending" },
  running: { ...BLUE, label: "running" },
  succeeded: { ...GREEN, label: "succeeded" },
  failed: { ...RED, label: "failed" },
  // 'skipped' is not a failure: an earlier stage ended the run before this
  // one could go. Grey, so it does not read as an error in the table.
  skipped: { ...GREY, label: "skipped" },
};

/** Falls back to a neutral badge so an unknown status still renders. */
export function statusStyle(map, status) {
  return map[status] || { ...GREY, label: status || "unknown" };
}

/** Local time, or an em dash when the timestamp is null. */
export function formatTime(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "—" : d.toLocaleString();
}

/** "1.2s" / "45s" / "3m 20s" between two timestamps. */
export function formatDuration(startIso, endIso) {
  if (!startIso) return "—";
  const start = new Date(startIso).getTime();
  const end = endIso ? new Date(endIso).getTime() : Date.now();
  if (Number.isNaN(start) || Number.isNaN(end)) return "—";

  const seconds = Math.max(0, (end - start) / 1000);
  if (seconds < 10) return `${seconds.toFixed(1)}s`;
  if (seconds < 90) return `${Math.round(seconds)}s`;
  const m = Math.floor(seconds / 60);
  return `${m}m ${Math.round(seconds - m * 60)}s`;
}
