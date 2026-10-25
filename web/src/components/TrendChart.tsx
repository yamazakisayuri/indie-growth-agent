"use client";

/** Small SVG line chart for a daily series. Missing days break the line (missing ≠ zero). */
export interface TrendPoint {
  date: string;
  value: number | null;
}

const WIDTH = 320;
const HEIGHT = 140;
const PAD = { top: 12, right: 10, bottom: 22, left: 40 };

function shortDate(iso: string): string {
  const [, month, day] = iso.split("-");
  return month && day ? `${Number(month)}/${Number(day)}` : iso;
}

export function TrendChart({
  title,
  points,
  highlightFrom,
  markers,
  format,
}: {
  title: string;
  points: TrendPoint[];
  /** First date of the shaded (current) period. */
  highlightFrom: string | null;
  /** Dates with a dashed line and a number label. */
  markers: { date: string; label: string }[];
  format: (value: number) => string;
}) {
  const values = points.map((p) => p.value).filter((v): v is number => v !== null);
  const max = values.length > 0 ? Math.max(...values) : 0;
  const top = max > 0 ? max * 1.1 : 1;
  const innerW = WIDTH - PAD.left - PAD.right;
  const innerH = HEIGHT - PAD.top - PAD.bottom;
  const step = points.length > 1 ? innerW / (points.length - 1) : 0;
  const x = (index: number) => PAD.left + index * step;
  const y = (value: number) => PAD.top + innerH - (value / top) * innerH;

  const segments: string[] = [];
  let current: string[] = [];
  points.forEach((point, index) => {
    if (point.value === null) {
      if (current.length > 0) segments.push(current.join(" "));
      current = [];
      return;
    }
    current.push(`${x(index).toFixed(1)},${y(point.value).toFixed(1)}`);
  });
  if (current.length > 0) segments.push(current.join(" "));

  const highlightIndex = highlightFrom ? points.findIndex((p) => p.date === highlightFrom) : -1;
  const first = points[0];
  const last = points.at(-1);
  const summary =
    first && last
      ? `${title}: ${shortDate(first.date)}–${shortDate(last.date)}, max ${format(max)}`
      : title;

  return (
    <figure className="trend-chart">
      <figcaption className="trend-chart__title">{title}</figcaption>
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        className="trend-chart__svg"
        role="img"
        aria-label={summary}
      >
        {highlightIndex >= 0 ? (
          <rect
            className="trend-chart__highlight"
            x={x(highlightIndex) - step / 2}
            y={PAD.top}
            width={WIDTH - PAD.right - (x(highlightIndex) - step / 2)}
            height={innerH}
          />
        ) : null}
        <line
          className="trend-chart__axis"
          x1={PAD.left}
          x2={WIDTH - PAD.right}
          y1={PAD.top + innerH}
          y2={PAD.top + innerH}
        />
        <text className="trend-chart__tick" x={PAD.left - 6} y={y(max) + 3} textAnchor="end">
          {format(max)}
        </text>
        <text className="trend-chart__tick" x={PAD.left - 6} y={PAD.top + innerH} textAnchor="end">
          0
        </text>
        {markers.map((marker) => {
          const index = points.findIndex((p) => p.date === marker.date);
          if (index < 0) {
            return null;
          }
          return (
            <g key={`${marker.date}-${marker.label}`}>
              <line
                className="trend-chart__marker"
                x1={x(index)}
                x2={x(index)}
                y1={PAD.top}
                y2={PAD.top + innerH}
              />
              <text className="trend-chart__marker-label" x={x(index) + 3} y={PAD.top + 9}>
                {marker.label}
              </text>
            </g>
          );
        })}
        {segments.map((segment, i) => (
          <polyline key={i} className="trend-chart__line" points={segment} />
        ))}
        {points.map((point, index) =>
          point.value === null ? null : (
            <circle
              key={point.date}
              className="trend-chart__dot"
              cx={x(index)}
              cy={y(point.value)}
              r={2}
            />
          ),
        )}
        {first ? (
          <text className="trend-chart__tick" x={x(0)} y={HEIGHT - 6} textAnchor="start">
            {shortDate(first.date)}
          </text>
        ) : null}
        {highlightIndex > 0 ? (
          <text
            className="trend-chart__tick"
            x={x(highlightIndex)}
            y={HEIGHT - 6}
            textAnchor="middle"
          >
            {shortDate(points[highlightIndex].date)}
          </text>
        ) : null}
        {last && points.length > 1 ? (
          <text
            className="trend-chart__tick"
            x={x(points.length - 1)}
            y={HEIGHT - 6}
            textAnchor="end"
          >
            {shortDate(last.date)}
          </text>
        ) : null}
      </svg>
    </figure>
  );
}
