-- Preserve legacy assignments; their original model identity is unknown.
ALTER TABLE public.topic_results
    ADD COLUMN IF NOT EXISTS stable_topic_id text,
    ADD COLUMN IF NOT EXISTS model_version text;

COMMENT ON COLUMN public.topic_results.topic_id IS
    'Internal BERTopic cluster ID; interpret only with model_version.';
COMMENT ON COLUMN public.topic_results.stable_topic_id IS
    'Permanent reviewed topic catalog ID. NULL for unassigned or unversioned legacy results.';
COMMENT ON COLUMN public.topic_results.model_version IS
    'Registered model version that produced this assignment. NULL for legacy results.';
