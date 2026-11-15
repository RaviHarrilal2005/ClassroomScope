/**
 * Filter panel: narrows the article table, the topic chart and the
 * comment search.
 *
 * Dropdowns apply as soon as they change, dates once typing pauses
 * (ViewStateContext.jsx). The search box applies on Enter (or its
 * button), so each keystroke isn't a request. The filters and the tab
 * are kept in the URL, so a filtered view can be shared or bookmarked.
 * The options come from the corpus (/results filter_options), not from
 * a list kept here.
 *
 * MVP (README, "MVP features — come back to these"): one value per
 * filter.
 */
import { useEffect, useState } from "react";
import { useViewState } from "../state/ViewStateContext";
import { humanize } from "./text";

export default function FilterPanel() {
  const { filters, setFilters, clearFilters, results } = useViewState();
  const options = results?.filter_options;

  // The search box edits a draft; the q filter changes only on submit.
  const [draft, setDraft] = useState(filters.q);
  useEffect(() => setDraft(filters.q), [filters.q]);

  const field = (key) => ({
    id: `filter-${key}`,
    value: filters[key],
    onChange: (event) => setFilters({ [key]: event.target.value }),
  });
  const anySet = Object.values(filters).some(Boolean);

  return (
    <form
      className="filter-panel"
      role="search"
      aria-label="Filter articles"
      onSubmit={(event) => {
        event.preventDefault();
        const q = draft.trim();
        if (q.length === 1) {
          // minLength counts the untrimmed draft (" a" passes), but the
          // backend rejects a 1-character term, so flag it here.
          const input = event.currentTarget.elements["filter-q"];
          input.setCustomValidity("Search terms must be 2 to 100 characters.");
          input.reportValidity();
          return;
        }
        setFilters({ q });
      }}
    >
      <IgnoredNotice />
      <h2>Filters</h2>

      <div className="field">
        <label htmlFor="filter-q">Search articles and comments</label>
        <input
          id="filter-q"
          type="search"
          placeholder="e.g. cheating"
          minLength={2}
          maxLength={100}
          value={draft}
          onChange={(event) => {
            event.target.setCustomValidity("");
            setDraft(event.target.value);
          }}
        />
        <button type="submit">Search</button>
      </div>

      <div className="field-row">
        <div className="field">
          <label htmlFor="filter-from">From</label>
          <input
            type="date"
            min={options?.date_min || undefined}
            max={filters.to || options?.date_max || undefined}
            {...field("from")}
          />
        </div>
        <div className="field">
          <label htmlFor="filter-to">To</label>
          <input
            type="date"
            min={filters.from || options?.date_min || undefined}
            max={options?.date_max || undefined}
            {...field("to")}
          />
        </div>
      </div>

      <Choice
        label="Source type"
        field={field("source_type")}
        choices={(options?.source_types ?? []).map((value) => ({ value, label: humanize(value) }))}
      />
      <Choice
        label="Stakeholder"
        field={field("stakeholder")}
        choices={(options?.stakeholders ?? []).map((value) => ({ value, label: humanize(value) }))}
      />
      <Choice
        label="Topic"
        field={field("topic")}
        choices={(options?.topics ?? []).map((t) => ({ value: t.id, label: t.label }))}
      />

      <button
        type="button"
        className="secondary"
        disabled={!anySet && !draft}
        onClick={() => {
          setDraft("");
          clearFilters();
        }}
      >
        Clear filters
      </button>
    </form>
  );
}

const FILTER_NAMES = { source_type: "source type", stakeholder: "stakeholder", topic: "topic" };

/**
 * Says which link values were dropped because the corpus lacks them. The
 * empty status container renders first and the text after, so a screen
 * reader announces it even when it was set before this panel mounted
 * (a link that opens on the Pipeline runs tab).
 */
function IgnoredNotice() {
  const { ignoredFilters, dismissIgnored } = useViewState();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  const names = Object.entries(ignoredFilters);
  return (
    <div className="ignored-notice" role="status">
      {mounted && names.length > 0 && (
        <div className="notice">
          <p>Cleared, not in the data: {names.map(([key, value]) => `${FILTER_NAMES[key]} “${value}”`).join(", ")}.</p>
          <button type="button" className="secondary" onClick={dismissIgnored}>
            Dismiss
          </button>
        </div>
      )}
    </div>
  );
}

function Choice({ label, field, choices }) {
  return (
    <div className="field">
      <label htmlFor={field.id}>{label}</label>
      <select {...field}>
        <option value="">All</option>
        {choices.map(({ value, label: text }) => (
          <option key={value} value={value}>
            {text}
          </option>
        ))}
      </select>
    </div>
  );
}
