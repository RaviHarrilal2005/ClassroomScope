/**
 * Dashboard Shell — presentation layer (Section 3 of design doc).
 *
 * STATUS: skeleton only.
 *   - Renders sentiment distribution and article list from the stub endpoint.
 *   - No filter panel, no charts library yet — just proving the three
 *     layers (this component -> ViewStateContext -> apiClient -> Flask)
 *     are actually wired together.
 *
 * NOT built yet: FilterPanel, VisualizationViews (real charts),
 * ExportControls, AdminConsole. See design doc Section 2 for what
 * each of those needs to do.
 */
import { useEffect } from "react";
import { useViewState } from "../state/ViewStateContext";

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
          (skeleton — guest view only, no filters/admin yet)
        </span>
      </header>

      <main style={{ marginTop: "20px" }}>
        {loading && <p>Loading results…</p>}
        {error && <p style={{ color: "#B85450" }}>Error: {error}</p>}

        {results && (
          <>
            <section>
              <h3>Sentiment toward GAI in education</h3>
              <ul>
                <li>Positive: {(results.sentiment_distribution.positive * 100).toFixed(0)}%</li>
                <li>Neutral: {(results.sentiment_distribution.neutral * 100).toFixed(0)}%</li>
                <li>Negative: {(results.sentiment_distribution.negative * 100).toFixed(0)}%</li>
              </ul>
              {/* TODO: replace this list with the real donut chart component */}
            </section>

            <section style={{ marginTop: "20px" }}>
              <h3>Articles</h3>
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
      </main>
    </div>
  );
}
