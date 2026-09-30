/**
 * Dashboard Shell — presentation layer (Section 3 of design doc).
 *
 * STATUS:
 *   - AdminConsole is built and backed by real data.
 *   - The results section below still renders the hardcoded /results
 *     payload. It is labelled as placeholder rather than left to look
 *     real: sentiment_results has no rows and no sentiment agent exists,
 *     so those percentages are invented, not stale.
 *
 * NOT built yet: FilterPanel, VisualizationViews (real charts),
 * ExportControls. See design doc Section 2 for what each needs to do.
 */
import { useEffect } from "react";
import { useViewState } from "../state/ViewStateContext";
import AdminConsole from "./AdminConsole";

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
                Placeholder figures. <code>sentiment_results</code> is empty and no sentiment
                agent exists yet, so these percentages are invented — not computed from the
                corpus.
              </PlaceholderNote>
              <ul>
                <li>Positive: {(results.sentiment_distribution.positive * 100).toFixed(0)}%</li>
                <li>Neutral: {(results.sentiment_distribution.neutral * 100).toFixed(0)}%</li>
                <li>Negative: {(results.sentiment_distribution.negative * 100).toFixed(0)}%</li>
              </ul>
              {/* TODO: replace this list with the real donut chart component */}
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
