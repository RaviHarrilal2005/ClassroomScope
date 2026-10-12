/**
 * Comments that mention the search term, on the articles the other
 * filters allow. Renders nothing until there is a search.
 *
 * MVP (README, "MVP features — come back to these"): the newest 50
 * matches only, no paging, and plain substring matching.
 */
import { useViewState } from "../state/ViewStateContext";
import { Highlight, formatDate } from "./text";

export default function CommentResults() {
  const { filters, commentResults, commentsLoading, commentsError } = useViewState();
  if (!filters.q) return null;

  return (
    <section className="card" aria-labelledby="comments-heading" aria-busy={commentsLoading}>
      <h2 id="comments-heading">Comments</h2>
      {commentsLoading && <p className="table-meta">Searching comments…</p>}
      {commentsError && <p className="empty-note">{commentsError}</p>}
      {!commentsLoading && commentResults && !commentResults.available && (
        <p className="empty-note">{commentResults.reason}</p>
      )}
      {!commentsLoading && commentResults?.available && (
        <CommentList results={commentResults} query={filters.q} />
      )}
    </section>
  );
}

function CommentList({ results, query }) {
  const { total, comments } = results;
  if (total === 0) return <p className="empty-note">No comments mention “{query}”.</p>;
  return (
    <>
      <p className="table-meta">
        {total} comment{total === 1 ? "" : "s"} mention “{query}”
        {total > comments.length && ` (showing the newest ${comments.length})`}
      </p>
      <ul className="comment-list">
        {comments.map((c) => (
          <li key={c.comment_id} className="comment">
            <p className="snippet">
              <Highlight text={c.snippet} query={query} />
            </p>
            <p className="comment-meta">
              On <em>{c.article_title || `article ${c.article_id}`}</em> · {formatDate(c.created_at)} ·{" "}
              {c.recommendation_count ?? 0} recommend{c.recommendation_count === 1 ? "" : "s"}
            </p>
          </li>
        ))}
      </ul>
    </>
  );
}
