/**
 * Dashboard Shell — presentation layer (Section 3 of design doc).
 *
 * STATUS:
 *   - AdminConsole is built and backed by real data.
 *   - Top topics is real: /results counts topic_results on each request.
 *     When it can't (no database, an empty table), the section shows
 *     the reason the API gave instead of a chart.
 *   - Sentiment and the article table still render hardcoded /results
 *     data, labelled as placeholder rather than left to look real:
 *     nothing aggregates those tables into /results yet, so the figures
 *     are invented, not stale.
 *
 * NOT built yet: FilterPanel, ExportControls. See design doc Section 2
 * for what each needs to do.
 */
import { useEffect } from "react";
import { useViewState } from "../state/ViewStateContext";
import AdminConsole from "./AdminConsole";
import { SentimentDonut, TopTopicsBar } from "./VisualizationViews";

export default function DashboardShell() {
  const { results, loading, error, loadResults } = useViewState();

  useEffect(() => {
    loadResults();
  }, [loadResults]);

  return (
    <div style={{ fontFamily: "Arial, sans-serif", padding: "24px" }}>
      <header style={{ background: "#1F4E79", color: "#fff", padding: "14px 20px", borderRadius: "4px" }}>
        <strong>ClassroomScope</strong>
        <span style={{ marginLeft: "16px", fontSize: "13px", opacity: 0.8 }}>
          (in progress — no filters or login yet)
        </span>
      </header>

      <main style={{ marginTop: "20px" }}>
        {loading && <p>Loading results…</p>}
        {error && <p style={{ color: "#B85450" }}>Error: {error}</p>}

        {results && (
          <>
            <section>
              <h3 style={{ marginBottom: "4px" }}>Sentiment toward GAI in education</h3>
              <PlaceholderNote>
                Placeholder figures, hardcoded in the <code>/results</code> stub — not computed
                from the corpus. Nothing aggregates <code>sentiment_results</code> into this
                endpoint yet.
              </PlaceholderNote>
              <SentimentDonut distribution={results.sentiment_distribution} />
            </section>

            <section style={{ marginTop: "20px" }}>
              <h3 style={{ marginBottom: "4px" }}>Top topics</h3>
              <TopTopics facet={results.top_topics} />
            </section>

            <section style={{ marginTop: "20px" }}>
              <h3 style={{ marginBottom: "4px" }}>Articles</h3>
              <PlaceholderNote>
                Two hardcoded rows. The pipeline has 814 real articles, but nothing
                aggregates them into this endpoint yet.
              </PlaceholderNote>
              <table style={{ borderCollapse: "collapse", width: "100%" }}>
                <thead>
                  <tr style={{ textAlign: "left", borderBottom: "1px solid #ccc" }}>
                    <th>Title</th><th>Source</th><th>Stakeholder</th><th>Sentiment</th>
                  </tr>
                </thead>
                <tbody>
                  {results.articles.map((a) => (
                    <tr key={a.id} style={{ borderBottom: "1px solid #eee" }}>
                      <td>{a.title}</td>
                      <td>{a.source}</td>
                      <td>{a.stakeholder}</td>
                      <td>{a.sentiment}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          </>
        )}

        <AdminConsole />
      </main>
    </div>
  );
}

/**
 * Topic counts from the topic agent, or the reason there are none.
 * Says how many articles fit no topic: over half do, and a chart of
 * only the assigned ones would hide that.
 */
function TopTopics({ facet }) {
  if (!facet.available) return <PlaceholderNote>{facet.reason}</PlaceholderNote>;
  const total = facet.counted + facet.unassigned;
  return (
    <>
      <p style={{ fontSize: "12px", color: "#666", margin: "0 0 8px" }}>
        From the topic agent: {facet.counted} of {total} analysed article(s) have a topic;{" "}
        {facet.unassigned} don't fit any topic yet.
      </p>
      <TopTopicsBar topics={facet.items} />
    </>
  );
}

/** Marks a section as showing data the pipeline did not produce. */
function PlaceholderNote({ children }) {
  return (
    <p
      style={{
        fontSize: "12px",
        color: "#8A5A00",
        background: "#FDF1DC",
        border: "1px solid #F0D9A8",
        borderRadius: "3px",
        padding: "6px 10px",
        margin: "0 0 10px",
        maxWidth: "70ch",
      }}
    >
      {children}
    </p>
  );
}
