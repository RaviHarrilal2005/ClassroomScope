TESTS TO ADD LATER - ClassroomScope pipeline coordinator
=========================================================

These are NOT part of this week's commit. Each folder holds the tests
for one upcoming feature. When that feature is built:

  1. Copy the folder's .py file(s) into backend/tests/
  2. From the backend folder, run:  python -m pytest tests

Each file works on its own. They only rely on conftest.py and
helpers.py, which are already in the repo.


Folder                                  Add when...                                   Tests
-------------------------------------   -------------------------------------------   -----
1_when_supabase_tables_exist            app.py switches to SupabaseRunStore             11
2_when_real_agents_are_plugged_in       the first real agent replaces a stub             8
3_when_dashboard_polls_run_status       the dashboard shows run progress                 4
4_when_retry_settings_are_final         the team settles retry counts and wait times     3
5_when_scheduling_or_reruns_are_added   scheduled runs or single-stage re-runs exist     2
                                                                                        ---
                                                                                         28

This week's 20 + these 28 = 48.


NOTES

Group 1 - test_schema_sync.py compares docs/pipeline_tables.sql with the
code. If the SQL changes when the tables are actually created, this test
will point out exactly what differs; update models.py / stages.py to match.

Group 4 - if the team changes the retry numbers in orchestrator/retry.py,
two tests in the repo also check them: test_flaky_collection_is_retried_and_recovers
and test_collection_that_keeps_failing_stops_the_run (they expect waits of
2s and 4s). Update those along with adding this group.
