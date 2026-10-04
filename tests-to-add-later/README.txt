TESTS TO ADD LATER - ClassroomScope pipeline coordinator
=========================================================

Each folder holds the tests for one upcoming feature. When that feature
is built:

  1. Copy the folder's .py file(s) into backend/tests/
  2. From the backend folder, run:  python -m pytest tests

Each file works on its own. They only rely on conftest.py and
helpers.py, which are already in the repo.


Folder                                  Add when...                                   Tests
-------------------------------------   -------------------------------------------   -----
3_when_dashboard_polls_run_status       the dashboard shows run progress                 4
4_when_retry_settings_are_final         the team settles retry counts and wait times     3
5_when_scheduling_or_reruns_are_added   scheduled runs or single-stage re-runs exist     2
                                                                                        ---
                                                                                          9


ALREADY LANDED

Group 1 (when_supabase_tables_exist, 11 tests) and group 2
(when_real_agents_are_plugged_in, 8 tests) have been moved into
backend/tests/. Their triggers were met: app.py selects
SupabaseRunStore from the environment, and real collection, security
and classification agents have replaced their stubs.

Two more files were written alongside them, covering the integration
itself rather than an upcoming feature:

  test_agent_adapters.py   the adapters between the team's modules and
                           the coordinator's contract
  test_registry_wiring.py  which agent each stage gets, and how the
                           environment decides

backend/tests/ now holds 95 tests. None of them touch the network.


NOTES

Group 4 - if the team changes the retry numbers in orchestrator/retry.py,
two tests in the repo also check them: test_flaky_collection_is_retried_and_recovers
and test_collection_that_keeps_failing_stops_the_run (they expect waits of
2s and 4s). Update those along with adding this group.

The note that used to be here about group 1's test_schema_sync.py no
longer applies - that test is in backend/tests/ and passing, so
docs/pipeline_tables.sql and the code agree. The DEPLOYED schema still
differs from both; see docs/pipeline-coordinator.md.
