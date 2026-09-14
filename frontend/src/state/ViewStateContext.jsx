/**
 * View-State Store — browser-memory state only (Section 3 of design doc).
 *
 * Holds the results returned from the API client so presentation
 * components render from state instead of fetching data themselves.
 *
 * STATUS: skeleton only.
 *   - Holds results + loading/error state. Works end-to-end with the stub.
 *   - Does NOT yet hold active filters or run status (both TODO).
 */
import { createContext, useContext, useState, useCallback } from "react";
import { getResults } from "../api/apiClient";

const ViewStateContext = createContext(null);

export function ViewStateProvider({ children }) {
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // TODO: accept filters once FilterPanel is built
  const loadResults = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getResults();
      setResults(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  // TODO: activeFilters state + setFilters()
  // TODO: runStatus state, updated by the run-status poller

  const value = { results, loading, error, loadResults };
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
