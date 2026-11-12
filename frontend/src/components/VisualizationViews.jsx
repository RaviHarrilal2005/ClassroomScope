/**
 * Visualization Views — the dashboard's charts (Section 2 of design doc).
 *
 * Each chart takes plain data rather than the /results payload, so the
 * caller decides what to draw.
 *
 * Every value is printed as text (on the chart, or in the month-by-month
 * list under the monthly one), so colour is never the only signal — the
 * same rule statusStyles.js follows for badges.
 *
 * Sentiment is blue / light grey / red, not green / grey / red: red and
 * green are about ΔE 5 apart for a deuteranope, blue and red about 20.
 * Neutral is light so the 70%-neutral bars show their lean, not a grey wall.
 *
 * Tooltips are a mouse and touch extra: what they show is also printed,
 * or in the month-by-month list under the monthly chart. So
 * accessibilityLayer is off: Recharts' default would make each chart a
 * tab stop with role="application", which switches a screen reader out of
 * the reading mode it needs to hear the labels that carry the values.
 */
import { Bar, BarChart, Cell, LabelList, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { monthlyShares } from "../months";
import { BLUE, GREY, RED } from "./statusStyles";

const SENTIMENTS = [
  { field: "positive", name: "Positive", fill: "#2A6BB0", ink: "#fff" },
  { field: "neutral", name: "Neutral", fill: GREY.border, ink: "var(--text)" },
  { field: "negative", name: "Negative", fill: RED.fg, ink: "#fff" },
];

// Stance uses the same three colours: for reads like positive, against like negative.
export const STANCES = [
  { field: "favor", name: "For", fill: SENTIMENTS[0].fill },
  { field: "neutral", name: "Neutral", fill: SENTIMENTS[1].fill },
  { field: "against", name: "Against", fill: SENTIMENTS[2].fill },
];

/** "favor" -> "For": the API sends the SemEval labels, the page says them plainly. */
export const stanceName = (stance) => STANCES.find((s) => s.field === stance)?.name ?? "—";

// Mirrors MIN_ARTICLES_TO_NAME in agents/aggregation/compute.py: rows
// smaller than this are faded, as the headline never names them.
export const MIN_ARTICLES_TO_NAME = 20;

/** A 0–1 share as a whole percentage, rounded the way the donut rounds it. */
export const percent = (share) => `${(share * 100).toFixed(0)}%`;

/**
 * Shares (0–1) as a donut, each slice labelled: positive / neutral /
 * negative by default, or the `slices` given (STANCES).
 * A 0% share gets no slice: Recharts still labels an empty slice, and two of
 * them land on the same spot, unreadable.
 */
export function SentimentDonut({ distribution, slices = SENTIMENTS }) {
  const data = slices.map(({ field, name, fill }) => ({
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

// The band behind the hovered bar or column: a step off the card, not Recharts' grey.
const HOVER_BAND = { fill: "var(--line-soft)" };

/** The hovered topic's full name, which the axis may clip, and its count. */
function TopicTip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const { label, count } = payload[0].payload;
  return (
    <div className="chart-tooltip">
      <p><strong>{count}</strong> article(s)</p>
      <p className="muted">{label}</p>
    </div>
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
          <Tooltip content={TopicTip} cursor={HOVER_BAND} />
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
      <SplitLegend />
    </div>
  );
}

function SplitLegend() {
  return (
    <p className="chart-legend">
      {SPLIT_ORDER.map(({ field, name, fill }) => (
        <span key={field}>
          <span className="swatch" style={{ background: fill }} aria-hidden="true" /> {name}
        </span>
      ))}
      <span className="muted">Faded: fewer than {MIN_ARTICLES_TO_NAME} articles</span>
    </p>
  );
}

/** "2026-09" as a date, for its month name and year. */
const monthDate = (label) => new Date(`${label}-01T00:00`);

/** "2026-09" -> "September 2026". */
export const monthName = (label) => monthDate(label).toLocaleString("en", { month: "long", year: "numeric" });

/** Under each column: its article count, the month, and the year at both ends and every January. */
function MonthTick({ x, y, payload, index, months }) {
  const { total } = months[index];
  const d = monthDate(payload.value);
  return (
    <text x={x} y={y} textAnchor="middle" className="recharts-text" style={{ fill: "var(--muted)" }}>
      <tspan x={x} dy="0.8em" style={total >= MIN_ARTICLES_TO_NAME ? { fill: "var(--text)" } : undefined}>{total}</tspan>
      <tspan x={x} dy="1.3em">{d.toLocaleString("en", { month: "short" })}</tspan>
      {(index === 0 || index === months.length - 1 || d.getMonth() === 0) && <tspan x={x} dy="1.2em">{d.getFullYear()}</tspan>}
    </text>
  );
}

/** The hovered month's count and shares, top of the column first. */
function MonthTip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const m = payload[0].payload;
  return (
    <div className="chart-tooltip">
      <p><strong>{monthName(m.label)}</strong> · {m.total} article(s)</p>
      {m.total > 0 && SENTIMENTS.map(({ field, name, fill }) => (
        <p key={field}>
          <span className="swatch" style={{ background: fill }} aria-hidden="true" /> <strong>{percent(m[field])}</strong> {name}
        </p>
      ))}
    </div>
  );
}

/**
 * sentiment_over_time ([{ label: "YYYY-MM", ...counts }]) as one 100%
 * column per month, negative at the bottom. Shares, not counts, so one
 * busy month doesn't flatten the rest; each month's count is printed under
 * its column, and months under MIN_ARTICLES_TO_NAME are faded. Too many
 * months for a phone scroll sideways rather than squeeze the labels.
 */
export function SentimentByMonth({ rows }) {
  const months = monthlyShares(rows);
  return (
    <div className="chart">
      <div className="chart-scroll">
        <ResponsiveContainer width="100%" height={270} minWidth={months.length * 36 + 48}>
          <BarChart data={months} margin={{ top: 8, right: 8, left: 0, bottom: 0 }} accessibilityLayer={false}>
            <XAxis dataKey="label" interval={0} height={56} tickLine={false} axisLine={false}
                   tick={(props) => <MonthTick {...props} months={months} />} />
            <YAxis domain={[0, 1]} ticks={[0, 0.5, 1]} tickFormatter={percent} width={40}
                   tickLine={false} axisLine={false} />
            <Tooltip content={MonthTip} cursor={HOVER_BAND} />
            {SPLIT_ORDER.map(({ field, fill }) => (
              // A surface-coloured stroke is the 2px gap between segments.
              <Bar key={field} dataKey={field} stackId="month" fill={fill} stroke="var(--surface)" strokeWidth={2}
                   maxBarSize={24} radius={field === "positive" ? [4, 4, 0, 0] : 0}>
                {months.map((m) => <Cell key={m.label} fillOpacity={m.total < MIN_ARTICLES_TO_NAME ? 0.45 : 1} />)}
              </Bar>
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
      <SplitLegend />
    </div>
  );
}
