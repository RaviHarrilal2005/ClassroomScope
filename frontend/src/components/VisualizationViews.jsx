/**
 * Visualization Views — the dashboard's charts (Section 2 of design doc).
 *
 * Each chart takes plain data rather than the /results payload, so the
 * caller decides what to draw. Today that is the stub's figures; once
 * the aggregation snapshot replaces the stub, its topics sit under
 * `top_topics.items` instead of `top_topics`.
 *
 * Every value is printed on the chart as text, so colour is never the
 * only signal — the same rule statusStyles.js follows for badges.
 *
 * accessibilityLayer is off because these charts have no tooltip to
 * navigate. Recharts' default would make each one a tab stop that does
 * nothing, with role="application" — which switches a screen reader out
 * of the reading mode it needs to hear the labels that carry the values.
 */
import { Bar, BarChart, LabelList, Pie, PieChart, ResponsiveContainer, XAxis, YAxis } from "recharts";
import { BLUE, GREEN, GREY, RED } from "./statusStyles";

const SENTIMENTS = [
  { field: "positive", name: "Positive", fill: GREEN.fg },
  { field: "neutral", name: "Neutral", fill: GREY.fg },
  { field: "negative", name: "Negative", fill: RED.fg },
];

/** Positive / neutral / negative shares (0–1) as a donut, each slice labelled. */
export function SentimentDonut({ distribution }) {
  const data = SENTIMENTS.map(({ field, name, fill }) => ({
    name,
    value: distribution[field],
    fill,
  }));

  return (
    <div style={{ maxWidth: "480px" }}>
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
            label={({ name, value }) => `${name} ${(value * 100).toFixed(0)}%`}
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}

/** [{ label, count }] as horizontal bars, in the order given. */
export function TopTopicsBar({ topics }) {
  return (
    <div style={{ maxWidth: "640px" }}>
      <ResponsiveContainer width="100%" height={topics.length * 44 + 10}>
        <BarChart data={topics} layout="vertical" margin={{ right: 40 }} accessibilityLayer={false}>
          <XAxis type="number" hide />
          <YAxis type="category" dataKey="label" width={170} />
          <Bar dataKey="count" fill={BLUE.fg}>
            <LabelList dataKey="count" position="right" />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
