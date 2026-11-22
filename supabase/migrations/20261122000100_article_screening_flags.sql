-- Article screening flags, mirroring comments.
--
-- The security stage already screens every collected article, but the
-- decision was never written down: a quarantined article was only left
-- out of that one run's approved_ids. The row stayed visible and the
-- next run picked it up again. These three columns make the decision
-- stick, the same way comments do (20261108000100).
--
-- The backfill matters. Every existing article has already been through
-- the pipeline, so they are marked screened here. Without it, the read
-- policies below would hide the entire corpus from the dashboard and
-- from every analysis agent at once.
--
-- NOTE: the policies are only half the protection. The pipeline connects
-- with the secret key, which bypasses RLS, so the analysis queries also
-- filter on quarantined explicitly. See corpus.py and the agent modules.

alter table public.articles
  add column if not exists screened    boolean not null default false,
  add column if not exists quarantined boolean not null default false,
  add column if not exists screened_at timestamptz;

create index if not exists articles_unscreened_idx
  on public.articles (id) where screened = false;

update public.articles
  set screened = true, screened_at = now()
  where screened = false;

-- The collection agent supplies the untrusted text, so it must not be
-- able to mark its own content as screened. Table-level UPDATE grants
-- extend to new columns automatically, so the grant is rebuilt by column.
revoke update on public.articles from collection_agent;
grant update (title, content, source, url, author, published_date,
              content_hash, clean_content, processing_status,
              processing_note, processed_at, is_relevant, llm_relevant,
              llm_relevance_reason, llm_verified_at,
              guardian_discussion_key, guardian_commentable)
  on public.articles to collection_agent;
grant select (screened, quarantined, screened_at)
  on public.articles to collection_agent;

-- anon_read_articles and guest_read_articles were both USING (true).
-- Permissive policies OR together, so tightening one while the other
-- stays open changes nothing. Drop the duplicate first.
drop policy if exists anon_read_articles on public.articles;

alter policy guest_read_articles on public.articles
  using (screened = true and quarantined = false);

alter policy classification_agent_select_articles on public.articles
  using (screened = true and quarantined = false);
alter policy sentiment_agent_select_articles on public.articles
  using (screened = true and quarantined = false);
alter policy stance_agent_select_articles on public.articles
  using (screened = true and quarantined = false);
alter policy topic_agent_select_articles on public.articles
  using (screened = true and quarantined = false);
alter policy aggregator_read_articles on public.articles
  using (screened = true and quarantined = false);

-- collection_agent_select_articles stays USING (true): collection needs
-- to see unscreened rows to know what it already inserted.
