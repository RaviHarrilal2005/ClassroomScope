/**
 * A status pill. Always shows the status as text — colour is a second
 * signal, never the only one.
 */
import { statusStyle } from "./statusStyles";

export default function StatusBadge({ map, status, title }) {
  const s = statusStyle(map, status);
  return (
    <span
      title={title}
      style={{
        display: "inline-block",
        padding: "2px 8px",
        borderRadius: "10px",
        fontSize: "12px",
        fontWeight: 600,
        lineHeight: "18px",
        whiteSpace: "nowrap",
        color: s.fg,
        background: s.bg,
        border: `1px solid ${s.border}`,
      }}
    >
      {s.label}
    </span>
  );
}
