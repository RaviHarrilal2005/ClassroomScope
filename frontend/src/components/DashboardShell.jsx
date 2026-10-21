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
 * and the sentiment share (agents/aggregation/compute.py).
 *
 * NOT built yet: ExportControls, login. See design doc Section 2.
 */
import { useState } from "react";
import { useViewState } from "../state/ViewStateContext";
import AdminConsole from "./AdminConsole";
import ArticleTable from "./ArticleTable";
import CommentResults from "./CommentResults";
import FilterPanel from "./FilterPanel";
import { SentimentDonut, TopTopicsBar } from "./VisualizationViews";

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
