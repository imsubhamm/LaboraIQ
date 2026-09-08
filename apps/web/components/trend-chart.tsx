export function TrendChart({
  title,
  points,
  valueKey,
  emptyLabel
}: {
  title: string;
  points: Array<{ label: string } & Record<string, number | string | null>>;
  valueKey: string;
  emptyLabel: string;
}) {
  const values = points.map((point) => {
    const raw = point[valueKey];
    return typeof raw === "number" ? raw : null;
  });
  const numeric = values.filter((value): value is number => value != null);
  if (numeric.length === 0) {
    return (
      <article className="panel trend-panel">
        <div className="panel-title">
          <h2>{title}</h2>
        </div>
        <p className="empty-compact">{emptyLabel}</p>
      </article>
    );
  }
  const min = Math.min(0, ...numeric);
  const max = Math.max(...numeric, min + 1);
  const width = 320;
  const height = 92;
  const coords = values
    .map((value, index) => {
      if (value == null) return null;
      const x = (index / Math.max(points.length - 1, 1)) * (width - 8) + 4;
      const y = height - 8 - ((value - min) / (max - min)) * (height - 16);
      return `${x},${y}`;
    })
    .filter(Boolean)
    .join(" ");
  return (
    <article className="panel trend-panel">
      <div className="panel-title">
        <h2>{title}</h2>
        <small>
          {points[0]?.label} – {points[points.length - 1]?.label}
        </small>
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={title} className="trend-svg">
        <polyline fill="none" stroke="currentColor" strokeWidth="2" points={coords} />
      </svg>
    </article>
  );
}
