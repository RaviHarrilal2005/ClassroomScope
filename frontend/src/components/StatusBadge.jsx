/**
 * A status pill. Always shows the status as text — colour is a second
 * signal, never the only one.
 */
import { statusStyle } from "./statusStyles";

export default function StatusBadge({ map, status, title }) {
  const s = statusStyle(map, status);
  // Shape lives in styles.css (.badge); only the status colours are computed here.
  return (
    <span title={title} className="badge" style={{ color: s.fg, background: s.bg, borderColor: s.border }}>
      {s.label}
    </span>
  );
}
