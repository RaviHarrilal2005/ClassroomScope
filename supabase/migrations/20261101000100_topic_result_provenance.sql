-- Nullable fields preserve historical rows without inventing provenance.
ALTER TABLE public.topic_results
    ADD COLUMN IF NOT EXISTS mapping_version text,
    ADD COLUMN IF NOT EXISTS unassigned_reason text
        CHECK (unassigned_reason IN ('insufficient_content', 'outside_groups', 'uncertain_fit'));

COMMENT ON COLUMN public.topic_results.mapping_version IS
    'SHA-256 of canonical category definitions, model topic mapping and display labels. NULL for legacy rows.';
COMMENT ON COLUMN public.topic_results.unassigned_reason IS
    'Reason for Unassigned; model outliers use uncertain_fit. NULL for assigned or legacy rows. Other reasons require explicit assessment.';
