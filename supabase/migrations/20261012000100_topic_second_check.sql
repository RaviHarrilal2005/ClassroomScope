-- Advisory second check; existing assignments and legacy rows are preserved.
ALTER TABLE public.topic_results
    ADD COLUMN IF NOT EXISTS suggested_topic text,
    ADD COLUMN IF NOT EXISTS suggested_stable_topic_id text,
    ADD COLUMN IF NOT EXISTS suggested_topic_similarity double precision,
    ADD COLUMN IF NOT EXISTS suggested_topic_gap double precision,
    ADD COLUMN IF NOT EXISTS suggestion_method text;

COMMENT ON COLUMN public.topic_results.suggested_stable_topic_id IS
    'Advisory topic for Unassigned articles only; excluded from official topic counts.';
COMMENT ON COLUMN public.topic_results.suggested_topic_similarity IS
    'Best cosine similarity from the second check, not a confidence probability; recorded even if no suggestion qualifies.';
COMMENT ON COLUMN public.topic_results.suggested_topic_gap IS
    'Difference between the best and second-best cosine similarities.';
COMMENT ON COLUMN public.topic_results.suggestion_method IS
    'Versioned second-check policy; NULL when no second check was run.';
