-- Preserve the raw model result separately from the final assignment.
ALTER TABLE public.topic_results
    ADD COLUMN IF NOT EXISTS original_topic_id integer,
    ADD COLUMN IF NOT EXISTS assignment_method text;

COMMENT ON COLUMN public.topic_results.original_topic_id IS
    'Original BERTopic result before the second check; -1 means Unassigned. NULL for legacy rows.';
COMMENT ON COLUMN public.topic_results.assignment_method IS
    'bertopic for original results, or the versioned fallback policy for second-check assignments. NULL for legacy rows.';
COMMENT ON COLUMN public.topic_results.suggested_stable_topic_id IS
    'Qualifying second-check topic, also written to the final topic fields and included in topic counts.';
