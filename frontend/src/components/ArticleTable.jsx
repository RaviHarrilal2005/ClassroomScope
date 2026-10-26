/**
 * The analysable articles that match the filters, newest first.
 *
 * Sentiment is the corpus's one result per article (RoBERTa's first); an
 * em dash where none exists yet.
 *
 * MVP (README, "MVP features — come back to these"): every match is
 * rendered, with no paging. Fine at a few hundred rows.
 */
import { articlesCsv, download, exportFileName } from "../csv";
import { useViewState } from "../state/ViewStateContext";
import { Highlight, formatDate, humanize } from "./text";

export default function ArticleTable() {
  const { results, filters } = useViewState();
  const articles = results?.articles;
  if (!articles) return null;
  if (!articles.available) return <p className="empty-note">{articles.reason}</p>;

  return (
    <>
      <div className="table-meta">
        <p>
          Showing {articles.total} of {articles.corpus} articles
        </p>
        {/* Exactly the rows below: built from what the page already has (src/csv.js). */}
        <button
          type="button"
          className="secondary"
          disabled={articles.items.length === 0}
          onClick={() =>
            download(articlesCsv(articles.items, { withSnippet: Boolean(filters.q) }), exportFileName(filters))
          }
        >
          Export CSV
        </button>
      </div>
      {articles.items.length === 0 ? (
        <p className="empty-note">No articles match these filters.</p>
      ) : (
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                <th scope="col">Title</th>
                <th scope="col">Date</th>
                <th scope="col">Source</th>
                <th scope="col">Source type</th>
                <th scope="col">Stakeholder</th>
                <th scope="col">Topic</th>
                <th scope="col">Sentiment</th>
              </tr>
            </thead>
            <tbody>
              {articles.items.map((a) => {
                const title = <Highlight text={a.title || "Untitled"} query={filters.q} />;
                return (
                  <tr key={a.id}>
                    <td>
                      {/* Only http(s) becomes a link; javascript: and the like stay plain text. */}
                      {/^https?:\/\//i.test(a.url) ? (
                        <a href={a.url} target="_blank" rel="noreferrer">
                          {title}
                        </a>
                      ) : (
                        title
                      )}
                      {a.snippet && (
                        <p className="snippet">
                          <Highlight text={a.snippet} query={filters.q} />
                        </p>
                      )}
                    </td>
                    <td>{formatDate(a.published_date)}</td>
                    <td>{a.source || "—"}</td>
                    <td>{humanize(a.source_type)}</td>
                    <td>{humanize(a.stakeholder)}</td>
                    <td>{a.topic || "—"}</td>
                    <td>{humanize(a.sentiment)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
