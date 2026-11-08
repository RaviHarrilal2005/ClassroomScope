-- Comment screening columns, and comment ids stored as text everywhere.
--
-- 1. The security stage screens comments (PR #30) using three columns
--    that were added in the dashboard and never recorded here. They
--    already exist on the shared project, so this part is a no-op there;
--    it is for anyone building the schema from these files. The policies
--    that hide unscreened and quarantined comments also live only in the
--    dashboard.
--
-- 2. comments.comment_id is text (the Guardian's id), but
--    comment_sentiment_results.comment_id was bigint. Looking up a comment
--    whose id is not a number (the PLANTED_TEST_* rows the security tests
--    use) failed with 22P02 and stopped the comment sentiment agent.
--    Existing rows keep their ids, written as text.
--
-- Safe to apply before or after merging: the agent compares ids as
-- strings either way.

alter table public.comments
  add column if not exists screened    boolean not null default false,
  add column if not exists quarantined boolean not null default false,
  add column if not exists screened_at timestamptz;

alter table public.comment_sentiment_results
  alter column comment_id type text using comment_id::text;
