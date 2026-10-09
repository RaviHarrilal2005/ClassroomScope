/**
 * View-State Store — browser-memory state only (Section 3 of design doc).
 *
 * Holds what the API client returned so presentation components render
 * from state instead of fetching data themselves.
 *
 * STATUS:
 *   - results + loading/error: works. /results counts top_topics from
 *     topic_results; sentiment and articles are still hardcoded (no
 *     aggregation agent yet).
 *   - run status + the run-status poller: real, reading pipeline_runs.
 *   - Does NOT yet hold active filters (TODO, needs FilterPanel).
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import { getResults, getRun, getRuns, startRun } from "../api/apiClient";

const ViewStateContext = createContext(null);

// How often the poller asks for the active run's progress. A full run
// takes minutes and stages are recorded as they finish, so a couple of
// seconds is responsive without hammering the backend.
const POLL_INTERVAL_MS = 2000;

// Statuses the backend never moves a run out of (orchestrator/stages.py,
// RunStatus.FINISHED). Reaching one of these is how the poller knows to stop.
const TERMINAL_STATUSES = ["completed", "completed_with_errors", "failed"];

export function isFinished(run) {
  return !!run && TERMINAL_STATUSES.includes(run.status);
}

export function ViewStateProvider({ children }) {
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // --- run state ------------------------------------------------------
  const [runs, setRuns] = useState([]);
  const [activeRunId, setActiveRunId] = useState(null);
  const [selectedRun, setSelectedRun] = useState(null); // one run + its stages
  const [runsError, setRunsError] = useState(null);
  const [starting, setStarting] = useState(false);

  // The run the poller is following. A ref rather than state because the
  // polling effect reads it on every tick, and making it a dependency
  // would tear down and rebuild the interval on each change.
  const watchedRunId = useRef(null);

  // TODO: accept filters once FilterPanel is built
  const loadResults = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setResults(await getResults());
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  const loadRuns = useCallback(async () => {
    try {
      const data = await getRuns(20);
      setRuns(data.runs);
      setActiveRunId(data.active_run_id);
      setRunsError(null);
      return data;
    } catch (err) {
      setRunsError(err.message);
      return null;
    }
  }, []);

  /** Load one run and show it. Also points the poller at it if unfinished. */
  const selectRun = useCallback(async (runId) => {
    try {
      const run = await getRun(runId);
      setSelectedRun(run);
      setRunsError(null);
      watchedRunId.current = isFinished(run) ? null : run.id;
      return run;
    } catch (err) {
      setRunsError(err.message);
      return null;
    }
  }, []);

  /**
   * Start a run and begin following it.
   *
   * A 409 means another run is already going — rather than just reporting
   * the error, switch to that run, since seeing it is what the person
   * wanted anyway.
   */
  const triggerRun = useCallback(
    async (triggerType = "manual") => {
      setStarting(true);
      setRunsError(null);
      try {
        const run = await startRun(triggerType);
        setSelectedRun(run);
        setActiveRunId(run.id);
        watchedRunId.current = run.id;
        await loadRuns();
        return run;
      } catch (err) {
        const otherRun = err.status === 409 ? err.body?.active_run_id : null;
        if (otherRun) {
          setRunsError(`A run is already in progress (run #${otherRun}). Showing it instead.`);
          await selectRun(otherRun);
        } else {
          setRunsError(err.message);
        }
        return null;
      } finally {
        setStarting(false);
      }
    },
    [loadRuns, selectRun]
  );

  // --- the run-status poller -------------------------------------------
  // One interval for the provider's lifetime rather than one per run:
  // starting and stopping intervals as runs come and go is where double
  // timers and leaks come from. Each tick decides whether there is
  // anything to do.
  useEffect(() => {
    const id = setInterval(async () => {
      const runId = watchedRunId.current;
      if (runId === null) return;

      let run;
      try {
        run = await getRun(runId);
      } catch {
        // A blip mid-run shouldn't clear the screen. Keep the last known
        // state and try again on the next tick; if the backend is really
        // gone, an action the person takes will surface it.
        return;
      }

      setSelectedRun(run);
      if (isFinished(run)) {
        watchedRunId.current = null;
        setActiveRunId(null);
        loadRuns(); // refresh the list so the finished run shows its outcome
      }
    }, POLL_INTERVAL_MS);

    return () => clearInterval(id);
  }, [loadRuns]);

  // On load, show the most recent run — and resume following it if the
  // server is mid-run, so a page refresh doesn't lose track of it.
  useEffect(() => {
    loadRuns().then((data) => {
      if (!data) return;
      const runId = data.active_run_id ?? data.runs[0]?.id;
      if (runId != null) selectRun(runId);
    });
  }, [loadRuns, selectRun]);

  // TODO: activeFilters state + setFilters()

  const value = {
    results,
    loading,
    error,
    loadResults,
    runs,
    activeRunId,
    selectedRun,
    runsError,
    starting,
    loadRuns,
    selectRun,
    triggerRun,
  };
  return (
    <ViewStateContext.Provider value={value}>
      {children}
    </ViewStateContext.Provider>
  );
}

export function useViewState() {
  const ctx = useContext(ViewStateContext);
  if (!ctx) throw new Error("useViewState must be used inside ViewStateProvider");
  return ctx;
}
