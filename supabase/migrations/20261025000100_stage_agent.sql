-- Record which agent ran each stage, and whether it was a stub.
--
-- The pipeline console tagged stages as stubs from a fixed list in the
-- front end, which was wrong on any machine where topic or sentiment
-- could not load its model or libraries. The coordinator now writes the
-- agent's name and stub flag when a stage starts, and the fallback's if
-- the fallback saved the stage.
--
-- Apply this BEFORE merging the code that writes these columns: until it
-- is applied, every stage update from that code is rejected and runs fail.
-- Both columns are nullable; rows from earlier runs keep nulls and show
-- no tag.

alter table public.pipeline_stage_runs
  add column if not exists agent text,
  add column if not exists stub  boolean;
