/**
 * Admin Console — start a pipeline run and watch it progress.
 *
 * This is the one dashboard view backed by real data today. It reads
 * pipeline_runs and pipeline_stage_runs through the run endpoints, which
 * return genuine rows. Of the results views above it, only top topics is
 * real so far; sentiment and articles still render hardcoded /results
 * data, because no aggregation agent exists yet.
 *
 * Three things the backend does that this UI has to account for:
 *
 *   * POST /runs returns 202 immediately and the pipeline keeps going on
 *     a server thread. So starting a run shows it at 'running' with every
 *     stage 'pending' — that is correct, not a stall. The poller in
 *     ViewStateContext fills it in.
 *   * Only one run may be active. A second POST returns 409 with the
 *     active run's id; the store switches to that run rather than just
 *     showing an error.
 *   * Three of the seven stages are stubs (sentiment, stance,
 *     aggregation). They succeed in about a millisecond without doing
 *     anything, which looks identical to real work from here — hence the
 *     note under the stage table.
 *
 * TODO(auth): the whole panel should be admin-only once login (SS-5)
 * exists. The backend has the matching TODO on POST /runs.
 */
import { useViewState } from "../state/ViewStateContext";
import StatusBadge from "./StatusBadge";
import {
  RUN_STATUS,
  STAGE_STATUS,
  formatDuration,
  formatTime,
} from "./statusStyles";

// Stages that are stubs everywhere today: sentiment is a standalone
// script the pipeline can't call yet, and stance and aggregation have
// no implementation. Flagged so nobody reads "succeeded" as "analysed
// something". Topic is left out: it runs for real wherever its model
// was pulled with Git LFS. Where it wasn't, topic is a stub this list
// can't see; the fix is for the backend to report which agent ran.
const STUBBED_STAGES = ["sentiment", "stance", "aggregation"];

const card = {
  border: "1px solid #DDD",
  borderRadius: "4px",
  background: "#FFF",
  padding: "16px",
};

const th = {
  textAlign: "left",
  borderBottom: "1px solid #CCC",
  padding: "6px 8px",
  fontSize: "12px",
  textTransform: "uppercase",
  letterSpacing: "0.03em",
  color: "#555",
};

const td = { padding: "6px 8px", borderBottom: "1px solid #EEE", fontSize: "14px" };

export default function AdminConsole() {
  const {
    runs,
    activeRunId,
    selectedRun,
    runsError,
    starting,
    selectRun,
    triggerRun,
  } = useViewState();

  const isActive = activeRunId !== null;

  return (
    <section style={{ marginTop: "28px" }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: "12px", flexWrap: "wrap" }}>
        <h3 style={{ margin: 0 }}>Admin console</h3>
        <span style={{ fontSize: "13px", color: "#666" }}>
          Pipeline runs — live data from <code>pipeline_runs</code>
        </span>
      </div>

      <div style={{ display: "flex", gap: "12px", alignItems: "center", margin: "12px 0", flexWrap: "wrap" }}>
        <button
          onClick={() => triggerRun("manual")}
          disabled={starting || isActive}
          style={{
            padding: "8px 16px",
            fontSize: "14px",
            fontWeight: 600,
            borderRadius: "4px",
            border: "none",
            color: "#FFF",
            background: starting || isActive ? "#9BB4C9" : "#1F4E79",
            cursor: starting || isActive ? "not-allowed" : "pointer",
          }}
        >
          {starting ? "Starting…" : isActive ? "Run in progress…" : "Start a run"}
        </button>

        {isActive && (
          <span style={{ fontSize: "13px", color: "#666" }}>
            Only one run may be active at a time.
          </span>
        )}
      </div>

      {runsError && (
        <p
          role="status"
          style={{
            color: "#8A5A00",
            background: "#FDF1DC",
            border: "1px solid #F0D9A8",
            padding: "8px 12px",
            borderRadius: "4px",
            fontSize: "14px",
          }}
        >
          {runsError}
        </p>
      )}

      <div style={{ display: "flex", gap: "16px", alignItems: "flex-start", flexWrap: "wrap" }}>
        <RunDetail run={selectedRun} />
        <RunList runs={runs} selectedId={selectedRun?.id} activeRunId={activeRunId} onSelect={selectRun} />
      </div>
    </section>
  );
}

function RunDetail({ run }) {
  if (!run) {
    return (
      <div style={{ ...card, flex: "2 1 460px", color: "#666" }}>
        No runs yet. Start one to see it here.
      </div>
    );
  }

  const stubbedThatRan = run.stages.filter(
    (s) => STUBBED_STAGES.includes(s.stage_name) && s.status === "succeeded"
  );

  return (
    <div style={{ ...card, flex: "2 1 460px" }}>
      <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
        <strong style={{ fontSize: "15px" }}>Run #{run.id}</strong>
        <StatusBadge map={RUN_STATUS} status={run.status} />
        <span style={{ fontSize: "13px", color: "#666" }}>
          {run.trigger_type} · started {formatTime(run.started_at)} ·{" "}
          {formatDuration(run.started_at, run.finished_at)}
          {run.articles_collected != null && ` · ${run.articles_collected} article(s)`}
        </span>
      </div>

      {run.notes && (
        <p style={{ fontSize: "13px", color: "#444", margin: "10px 0 0" }}>{run.notes}</p>
      )}

      <table style={{ borderCollapse: "collapse", width: "100%", marginTop: "12px" }}>
        <thead>
          <tr>
            <th style={th}>Stage</th>
            <th style={th}>Status</th>
            <th style={th}>Attempt</th>
            <th style={th}>Duration</th>
          </tr>
        </thead>
        <tbody>
          {run.stages.map((stage) => (
            <tr key={stage.id}>
              <td style={td}>
                {stage.stage_name}
                {STUBBED_STAGES.includes(stage.stage_name) && (
                  <span
                    title="No agent implementation yet — this stage reports success without doing work"
                    style={{ marginLeft: "6px", fontSize: "11px", color: "#8A5A00" }}
                  >
                    stub
                  </span>
                )}
              </td>
              <td style={td}>
                <StatusBadge map={STAGE_STATUS} status={stage.status} />
              </td>
              <td style={{ ...td, color: stage.attempt > 1 ? "#8A5A00" : "inherit" }}>
                {stage.attempt || "—"}
                {stage.attempt > 1 && " (retried)"}
              </td>
              <td style={td}>{formatDuration(stage.started_at, stage.finished_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <StageDetails stages={run.stages} />

      {stubbedThatRan.length > 0 && (
        <p style={{ fontSize: "12px", color: "#8A5A00", marginTop: "12px" }}>
          {stubbedThatRan.length} stage(s) marked <em>stub</em> reported success without
          analysing anything — no agent is implemented for them yet.
        </p>
      )}
    </div>
  );
}

/**
 * The text the coordinator recorded against a stage.
 *
 * `error_detail` is not only set on failures. When a stage's primary
 * agent fails and its fallback succeeds, the coordinator records *why*
 * the fallback was needed — on a stage whose status is 'succeeded'.
 * Listing that under a heading called "Errors" would report a recovery
 * as a failure, so the two are separated.
 */
function StageDetails({ stages }) {
  const withDetail = stages.filter((s) => s.error_detail);
  if (withDetail.length === 0) return null;

  const failures = withDetail.filter((s) => s.status === "failed");
  const recoveries = withDetail.filter((s) => s.status !== "failed");

  return (
    <>
      {failures.length > 0 && (
        <DetailBlock title="Errors" stages={failures} tone="#A33A34" />
      )}
      {recoveries.length > 0 && (
        <DetailBlock title="Recovered" stages={recoveries} tone="#8A5A00" />
      )}
    </>
  );
}

function DetailBlock({ title, stages, tone }) {
  return (
    <div style={{ marginTop: "12px" }}>
      <strong style={{ fontSize: "13px", color: tone }}>{title}</strong>
      {stages.map((s) => (
        <p
          key={s.id}
          style={{
            fontSize: "12px",
            fontFamily: "Consolas, monospace",
            background: "#FAFAFA",
            border: "1px solid #EEE",
            borderLeft: `3px solid ${tone}`,
            borderRadius: "3px",
            padding: "6px 8px",
            margin: "6px 0 0",
            whiteSpace: "pre-wrap",
            wordBreak: "break-word",
          }}
        >
          <strong>{s.stage_name}:</strong> {s.error_detail}
        </p>
      ))}
    </div>
  );
}

function RunList({ runs, selectedId, activeRunId, onSelect }) {
  return (
    <div style={{ ...card, flex: "1 1 260px", padding: "12px" }}>
      <strong style={{ fontSize: "13px" }}>Recent runs</strong>
      {runs.length === 0 && (
        <p style={{ fontSize: "13px", color: "#666" }}>None yet.</p>
      )}
      <ul style={{ listStyle: "none", padding: 0, margin: "8px 0 0" }}>
        {runs.map((run) => (
          <li key={run.id}>
            <button
              onClick={() => onSelect(run.id)}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                gap: "8px",
                width: "100%",
                textAlign: "left",
                padding: "7px 8px",
                marginBottom: "2px",
                fontSize: "13px",
                border: "1px solid transparent",
                borderRadius: "3px",
                cursor: "pointer",
                background: run.id === selectedId ? "#E1EDF8" : "transparent",
                borderColor: run.id === selectedId ? "#B9D4EC" : "transparent",
              }}
            >
              <span>
                #{run.id}
                {run.id === activeRunId && (
                  <span style={{ color: "#1F4E79", fontWeight: 600 }}> · live</span>
                )}
                <span style={{ display: "block", color: "#777", fontSize: "11px" }}>
                  {formatTime(run.started_at)}
                </span>
              </span>
              <StatusBadge map={RUN_STATUS} status={run.status} />
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
