-- The topic agent does not populate this optional run-link field.
-- Guard against deleting values added since the November 1 inspection.
-- No CASCADE: dependent views or constraints outside this table must be reviewed.
BEGIN;
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'topic_results'
          AND column_name = 'run_id'
    ) THEN
        IF EXISTS (SELECT 1 FROM public.topic_results WHERE run_id IS NOT NULL) THEN
            RAISE EXCEPTION 'run_id contains data; aborting column removal';
        END IF;
        ALTER TABLE public.topic_results DROP COLUMN run_id RESTRICT;
    END IF;
END $$;
COMMIT;
