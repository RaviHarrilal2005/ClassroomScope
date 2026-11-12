-- Add 'comment_sentiment' to the pipeline's stages.
--
-- Comment sentiment (agents/sentiment/comment_sentiment_agent.py) now runs
-- as its own analysis stage, after security has screened the comments.
--
-- Apply this BEFORE merging the code that adds the stage: every run
-- creates a row per stage when it starts, so until this is applied the
-- new row is rejected and every run fails at once.

alter table public.pipeline_stage_runs
  drop constraint if exists pipeline_stage_runs_stage_name_check;

alter table public.pipeline_stage_runs
  add constraint pipeline_stage_runs_stage_name_check
  check (stage_name in ('collection', 'security', 'sentiment', 'topic',
                        'classification', 'stance', 'comment_sentiment',
                        'aggregation'));
