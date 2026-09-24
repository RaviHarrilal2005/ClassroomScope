-- Align pipeline_stage_runs.stage_name with the agreed pipeline order.
--
-- The deployed table was created from the original proposal. Two agreed
-- changes never reached it (see the header of docs/pipeline_tables.sql):
--   * 'security' added: Collection -> Security -> Analysis -> Aggregation
--   * the final stage renamed from 'aggregate' to 'aggregation'
--
-- backend/orchestrator/stages.py already uses the new names, so every run
-- fails at the security stage until this is applied.

alter table public.pipeline_stage_runs
  drop constraint if exists pipeline_stage_runs_stage_name_check;

update public.pipeline_stage_runs
   set stage_name = 'aggregation'
 where stage_name = 'aggregate';

alter table public.pipeline_stage_runs
  add constraint pipeline_stage_runs_stage_name_check
  check (stage_name in ('collection', 'security', 'sentiment', 'topic',
                        'classification', 'stance', 'aggregation'));
