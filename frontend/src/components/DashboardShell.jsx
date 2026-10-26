/**
 * Dashboard Shell — page layout (Section 3 of design doc).
 *
 * Two views behind a pair of tabs: the dashboard (filters, charts,
 * articles, comment search) and the pipeline runs console. Everything
 * reads from ViewStateContext, which reloads whenever the filters
 * change; nothing here fetches.
 *
 * STATUS: everything shown is real and filtered by the backend: top
 * topics, the article table and comment search (orchestrator/corpus.py),
 * and the sentiment share, its breakdowns and the headline's picks
 * (agents/aggregation/compute.py).
 *
 * NOT built yet: login. See design doc Section 2. Export is the article
 * table's Export CSV button (src/csv.js).
 */
import { useState } from "react";
import { useViewState } from "../state/ViewStateContext";
import AdminConsole from "./AdminConsole";
import ArticleTable from "./ArticleTable";
import CommentResults from "./CommentResults";
import FilterPanel from "./FilterPanel";
import { humanize } from "./text";
import { SentimentDonut, SentimentSplitBar, TopTopicsBar, percent } from "./VisualizationViews";

const VIEWS = [
  { id: "dashboard", label: "Dashboard" },
  { id: "runs", label: "Pipeline runs" },
];

export default function DashboardShell() {
  const [view, setView] = useState("dashboard");

  return (
    <>
      <header className="topbar">
        <div className="brand">
          <h1 className="brand-name">ClassroomScope</h1>
          <span className="brand-tagline">Generative AI in education, as the news and its readers see it</span>
        </div>
        <nav className="tabs" aria-label="Views">
          {VIEWS.map((v) => (
            <button
              key={v.id}
              type="button"
              className="tab"
              aria-pressed={view === v.id}
              onClick={() => setView(v.id)}
            >
              {v.label}
            </button>
          ))}
        </nav>
      </header>

      {view === "dashboard" ? (
        <Dashboard />
      ) : (
        <div className="page">
          <AdminConsole />
        </div>
      )}
    </>
  );
}

function Dashboard() {
  const { results, loading, error } = useViewState();

  return (
    <div className="layout">
      <aside className="sidebar card">
        <FilterPanel />
      </aside>

      <main className={`main${loading && results ? " is-loading" : ""}`} aria-busy={loading}>
        {error && (
          <p className="notice error" role="alert">
            {error}
          </p>
        )}
        {!results && loading && <p className="empty-note">Loading results…</p>}

        {results && (
          <>
            <Headline results={results} />

            <div className="chart-row">
              <section className="card">
                <h2>Sentiment toward GAI in education</h2>
                <Sentiment results={results} />
              </section>

              <section className="card">
                <h2>Top topics</h2>
                <TopTopics facet={results.top_topics} />
              </section>
            </div>

            {results.analysed > 0 && (
              <>
                <section className="card">
                  <h2>Sentiment by stakeholder</h2>
                  <ByStakeholder results={results} />
                </section>

                <section className="card">
                  <h2>Sentiment by topic</h2>
                  <ByTopic rows={results.sentiment_by_topic} />
                </section>
              </>
            )}

            <section className="card">
              <h2>Articles</h2>
              <ArticleTable />
            </section>

            <CommentResults />
          </>
        )}
      </main>
    </div>
  );
}

/**
 * Topic counts for the filtered articles, or the reason there are none.
 * Says how many fit no topic: over half do, and a chart of only the
 * assigned ones would hide that.
 */
function TopTopics({ facet }) {
  if (!facet.available) return <p className="empty-note">{facet.reason}</p>;
  const total = facet.counted + facet.unassigned;
  return (
    <>
      <p className="card-subtitle">
        {facet.counted} of {total} matching article(s) have a topic; {facet.unassigned} don't fit any
        topic yet.
      </p>
      <TopTopicsBar topics={facet.items} />
    </>
  );
}

/**
 * Which group and topic the filtered news is most negative about. The
 * backend picks them (agents/aggregation/compute.py) and sends null when
 * there's nothing to compare, e.g. under a one-stakeholder filter.
 */
function Headline({ results }) {
  const { most_negative_stakeholder: who, most_negative_topic: topic } = results;
  if (!who && !topic) return null;
  return (
    <section className="card headline">
      {who && (
        <p>
          News about <strong>{humanize(who.label).toLowerCase()}</strong> is the most negative:{" "}
          {percent(who.negative / who.total)} of {who.total} articles, against{" "}
          {percent(results.sentiment_distribution.negative)} overall.
        </p>
      )}
      {topic && (
        <p>
          Of the topics, <strong>{topic.label}</strong> is the most negative:{" "}
          {percent(topic.negative / topic.total)} of {topic.total}.
        </p>
      )}
    </section>
  );
}

/** Counts summed over breakdown rows, as a bold baseline row. */
function baseline(label, rows) {
  const sum = (field) => rows.reduce((n, r) => n + r[field], 0);
  return { label, positive: sum("positive"), neutral: sum("neutral"), negative: sum("negative"),
           total: sum("total"), baseline: true };
}

const byNegativeShare = (a, b) => b.negative / b.total - a.negative / a.total || b.total - a.total;

/** Every analysed article is in the baseline; undetermined isn't a group, so it has no row of its own. */
function ByStakeholder({ results }) {
  const all = results.sentiment_by_stakeholder;
  const groups = all.filter((r) => r.label !== "undetermined").sort(byNegativeShare);
  const left = results.analysed - groups.reduce((n, r) => n + r.total, 0);
  return (
    <>
      <p className="card-subtitle">
        Share of each group's articles that are negative, neutral and positive, most negative first.
        {left > 0 && ` ${left} article(s) with no clear stakeholder are in "All articles" only.`}
      </p>
      <SentimentSplitBar rows={[baseline("All articles", all), ...groups.map((r) => ({ ...r, label: humanize(r.label) }))]} />
    </>
  );
}

function ByTopic({ rows }) {
  if (rows.length === 0) return <p className="empty-note">None of the matching articles has a topic yet.</p>;
  const base = baseline("All with a topic", rows);
  return (
    <>
      <p className="card-subtitle">
        Only the {base.total} analysed article(s) with a topic are counted, most negative topic first.
      </p>
      <SentimentSplitBar rows={[base, ...[...rows].sort(byNegativeShare)]} />
    </>
  );
}

/**
 * The sentiment share of the filtered articles, or the reason there is
 * none: with no analysed articles, a donut of zeros would draw nothing.
 */
function Sentiment({ results }) {
  if (results.analysed === 0) return <p className="empty-note">{results.sentiment_reason}</p>;
  return (
    <>
      <p className="card-subtitle">
        Share of the {results.analysed} matching article(s) with a sentiment result.
      </p>
      <SentimentDonut distribution={results.sentiment_distribution} />
    </>
  );
}
