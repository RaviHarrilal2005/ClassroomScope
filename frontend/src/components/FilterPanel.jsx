/**
 * Filter panel: narrows the article table, the topic chart and the
 * comment search.
 *
 * Dropdowns and dates apply as soon as they change. The search box
 * applies on Enter (or its button), so each keystroke isn't a request.
 * The options come from the corpus (/results filter_options), not from
 * a list kept here.
 *
 * MVP (README, "MVP features — come back to these"): one value per
 * filter, and the filters are not kept in the URL.
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
        setFilters({ q: draft.trim() });
      }}
    >
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
          onChange={(event) => setDraft(event.target.value)}
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
