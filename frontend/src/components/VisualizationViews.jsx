/**
 * Visualization Views — the dashboard's charts (Section 2 of design doc).
 *
 * Each chart takes plain data rather than the /results payload, so the
 * caller decides what to draw.
 *
 * Every value is printed on the chart as text, so colour is never the
 * only signal — the same rule statusStyles.js follows for badges.
 *
 * Sentiment is blue / light grey / red, not green / grey / red: red and
 * green are about ΔE 5 apart for a deuteranope, blue and red about 20.
 * Neutral is light so the 70%-neutral bars show their lean, not a grey wall.
 *
 * accessibilityLayer is off because these charts have no tooltip to
 * navigate. Recharts' default would make each one a tab stop that does
 * nothing, with role="application" — which switches a screen reader out
 * of the reading mode it needs to hear the labels that carry the values.
 */
import { Bar, BarChart, LabelList, Pie, PieChart, ResponsiveContainer, XAxis, YAxis } from "recharts";
import { BLUE, GREY, RED } from "./statusStyles";

const SENTIMENTS = [
  { field: "positive", name: "Positive", fill: "#2A6BB0", ink: "#fff" },
  { field: "neutral", name: "Neutral", fill: GREY.border, ink: "var(--text)" },
  { field: "negative", name: "Negative", fill: RED.fg, ink: "#fff" },
];

// Mirrors MIN_ARTICLES_TO_NAME in agents/aggregation/compute.py: rows
// smaller than this are faded, as the headline never names them.
export const MIN_ARTICLES_TO_NAME = 20;

/** A 0–1 share as a whole percentage, rounded the way the donut rounds it. */
export const percent = (share) => `${(share * 100).toFixed(0)}%`;

/**
 * Positive / neutral / negative shares (0–1) as a donut, each slice labelled.
 * A 0% share gets no slice: Recharts still labels an empty slice, and two of
 * them land on the same spot, unreadable.
 */
export function SentimentDonut({ distribution }) {
  const data = SENTIMENTS.map(({ field, name, fill }) => ({
    name,
    value: distribution[field],
    fill,
  })).filter((slice) => slice.value > 0);

  return (
    <div className="chart chart-donut">
      <ResponsiveContainer width="100%" height={260}>
        <PieChart accessibilityLayer={false}>
          <Pie
            data={data}
            dataKey="value"
            // Labels sit 20px outside the ring; any larger and the top
            // one is cut off by the edge of the SVG.
            innerRadius="48%"
            outerRadius="70%"
            // The API's own share, not Recharts' `percent`: that one is
            // re-normalised over the slices drawn, so it would disagree
            // with the API whenever the three shares don't sum to 1.
            // Text ink, not the slice's colour: light-grey neutral text would be unreadable.
            label={({ x, y, textAnchor, name, value }) => (
              <text x={x} y={y} textAnchor={textAnchor} dominantBaseline="central"
                    className="recharts-text recharts-pie-label-text" fill="var(--text)">
                {`${name} ${percent(value)}`}
              </text>
            )}
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Axis label wrapped onto up to two lines (a row is 44px tall). */
function WrappedTick({ x, y, payload }) {
  const lines = [""];
  for (const word of String(payload.value).split(" ")) {
    const last = lines.length - 1;
    if (lines[last] && lines[last].length + word.length >= 28 && last < 1) lines.push(word);
    else lines[last] = lines[last] ? `${lines[last]} ${word}` : word;
  }
  return (
    <text x={x - 6} y={y} textAnchor="end" className="recharts-text" style={{ fill: "var(--muted)" }}>
      {lines.map((line, i) => (
        <tspan key={i} x={x - 6} dy={i === 0 ? (lines.length > 1 ? "-0.2em" : "0.35em") : "1.15em"}>
          {line}
        </tspan>
      ))}
    </text>
  );
}

/** [{ label, count }] as horizontal bars, in the order given. */
export function TopTopicsBar({ topics }) {
  return (
    <div className="chart">
      <ResponsiveContainer width="100%" height={topics.length * 44 + 10}>
        <BarChart data={topics} layout="vertical" margin={{ right: 40 }} accessibilityLayer={false}>
          <XAxis type="number" hide />
          {/* Real topic names run to ~50 characters: a fixed width, wrapped, so a
              phone-width card keeps room for the bars. */}
          <YAxis type="category" dataKey="label" width={190} tick={WrappedTick} />
          <Bar dataKey="count" fill={BLUE.fg}>
            <LabelList dataKey="count" position="right" />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

const SPLIT_ORDER = ["negative", "neutral", "positive"].map((f) => SENTIMENTS.find((s) => s.field === f));

/**
 * [{ label, positive, neutral, negative, total, baseline? }] (counts) as
 * one 100% bar per row: negative, neutral, positive.
 *
 * Plain HTML, not Recharts: Recharts gives the labels fixed-width axes,
 * which leave no room for the bars on a phone. Here each row's label and
 * shares sit on a line above its bar and wrap. A segment under 8% is too
 * thin for its label; the line above still gives its share. The bar is
 * hidden from screen readers, as that line carries the numbers.
 */
export function SentimentSplitBar({ rows }) {
  return (
    <div className="chart">
      {rows.map((r) => {
        const share = (field) => r[field] / r.total;
        const faded = !r.baseline && r.total < MIN_ARTICLES_TO_NAME;
        return (
          <div key={r.label} className={`split-row${r.baseline ? " is-baseline" : ""}${faded ? " is-faded" : ""}`}>
            <p className="split-head">
              <span>
                {r.label} <span className="muted">({r.total})</span>
              </span>
              <span className="muted">
                {percent(share("negative"))} negative · {percent(share("positive"))} positive
              </span>
            </p>
            <div className="split-bar" aria-hidden="true">
              {SPLIT_ORDER.map(({ field, fill, ink }) =>
                r[field] > 0 && (
                  <span key={field} style={{ flexGrow: share(field), background: fill, color: ink }}>
                    {share(field) >= 0.08 && percent(share(field))}
                  </span>
                )
              )}
            </div>
          </div>
        );
      })}
      <p className="chart-legend">
        {SPLIT_ORDER.map(({ field, name, fill }) => (
          <span key={field}>
            <span className="swatch" style={{ background: fill }} aria-hidden="true" /> {name}
          </span>
        ))}
        <span className="muted">Faded: fewer than {MIN_ARTICLES_TO_NAME} articles</span>
      </p>
    </div>
  );
}
