/**
 * View-State Store — browser-memory state only (Section 3 of design doc).
 *
 * Holds what the API client returned so presentation components render
 * from state instead of fetching data themselves.
 *
 * STATUS:
 *   - filters and the open tab: held here and mirrored in the query
 *     string (src/urlState.js); results and comment search reload
 *     whenever the filters change. /results serves real articles, topic
 *     counts and sentiment figures.
 *   - run status + the run-status poller: real, reading pipeline_runs.
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import { getResults, getRun, getRuns, searchComments, startRun } from "../api/apiClient";
import { EMPTY_FILTERS, keepKnown, parseQuery, toQuery } from "../urlState";

const ViewStateContext = createContext(null);

// How often the poller asks for the active run's progress. A full run
// takes minutes and stages are recorded as they finish, so a couple of
// seconds is responsive without hammering the backend.
const POLL_INTERVAL_MS = 2000;

// Statuses the backend never moves a run out of (orchestrator/stages.py,
// RunStatus.FINISHED). Reaching one of these is how the poller knows to stop.
const TERMINAL_STATUSES = ["completed", "completed_with_errors", "failed"];

// Typing a year into a date input fires a change per digit (0002, 0020,
// 0202, 2026), so a date waits this long for the next one before loading.
const DATE_DEBOUNCE_MS = 400;

export function isFinished(run) {
  return !!run && TERMINAL_STATUSES.includes(run.status);
}

export function ViewStateProvider({ children }) {
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // --- filters and comment search ---------------------------------------
  // Filters and tab start from the URL, so a shared link opens the same view.
  const [filters, setFilterState] = useState(() => parseQuery(window.location.search).filters);
  const [view, setView] = useState(() => parseQuery(window.location.search).view);
  const [commentResults, setCommentResults] = useState(null);
  const [commentsLoading, setCommentsLoading] = useState(false);
  const [commentsError, setCommentsError] = useState(null);

  // Each load aborts the one before it, and a response that lands anyway
  // (read before the abort) is dropped: a slow early response must not
  // overwrite a later one.
  const resultsRequest = useRef(null);
  const commentsRequest = useRef(null);
  const lastLoaded = useRef(null); // the filters the load effect last saw

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

  const loadResults = useCallback(async (activeFilters = EMPTY_FILTERS) => {
    resultsRequest.current?.abort();
    const { signal } = (resultsRequest.current = new AbortController());
    setLoading(true);
    setError(null);
    try {
      const data = await getResults(activeFilters, signal);
      if (signal.aborted) return;
      setResults(data);
      // A link naming a source, stakeholder or topic the corpus lacks: drop it.
      setFilterState((current) => keepKnown(current, data?.filter_options));
    } catch (err) {
      // Keep the last good results on screen; the error says why they didn't change.
      if (!signal.aborted) setError(err.message);
    } finally {
      if (!signal.aborted) setLoading(false);
    }
  }, []);

  const loadComments = useCallback(async (activeFilters) => {
    commentsRequest.current?.abort();
    const { signal } = (commentsRequest.current = new AbortController());
    setCommentsError(null);
    if (!activeFilters.q) {
      setCommentResults(null);
      setCommentsLoading(false);
      return;
    }
    // Drop the previous query's comments so they never sit under the new heading.
    setCommentResults(null);
    setCommentsLoading(true);
    try {
      const data = await searchComments(activeFilters, signal);
      if (!signal.aborted) setCommentResults(data);
    } catch (err) {
      if (!signal.aborted) {
        setCommentResults(null);
        setCommentsError(err.message);
      }
    } finally {
      if (!signal.aborted) setCommentsLoading(false);
    }
  }, []);

  // Results and comments follow the filters, including the first load.
  // A newly set date waits for typing to pause; anything else loads at once.
  useEffect(() => {
    const last = lastLoaded.current;
    lastLoaded.current = filters;
    const typing = last && ["from", "to"].some((key) => filters[key] && filters[key] !== last[key]);
    const timer = setTimeout(() => {
      loadResults(filters);
      loadComments(filters);
    }, typing ? DATE_DEBOUNCE_MS : 0);
    return () => clearTimeout(timer);
  }, [filters, loadResults, loadComments]);

  // The query string mirrors the filters and tab. replaceState, so a
  // filter change doesn't add a Back-button step. Params the page doesn't
  // own (utm_*) are dropped; the #hash is kept.
  useEffect(() => {
    window.history.replaceState(null, "", (toQuery(filters, view) || window.location.pathname) + window.location.hash);
  }, [filters, view]);

  /** Merge a change into the filters, e.g. setFilters({ stakeholder: "educators" }). */
  const setFilters = useCallback((patch) => setFilterState((current) => ({ ...current, ...patch })), []);
  const clearFilters = useCallback(() => setFilterState(EMPTY_FILTERS), []);

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
    async (triggerType = "manual", backlog = false) => {
      setStarting(true);
      setRunsError(null);
      try {
        const run = await startRun(triggerType, backlog);
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

  const value = {
    results,
    loading,
    error,
    loadResults,
    filters,
    setFilters,
    clearFilters,
    view,
    setView,
    commentResults,
    commentsLoading,
    commentsError,
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
