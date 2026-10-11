"use client";

import type { ReactElement } from "react";
import { CartesianGrid, Line, LineChart, ReferenceArea, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import type { Trend, TrendPoint } from "../lib/api/types";

interface DotProps {
  cx?: number;
  cy?: number;
  index?: number;
  payload?: TrendPoint;
}

export function niceTicks(lo: number, hi: number): number[] {
  const span = hi - lo;
  const step = span <= 6 ? 1 : span <= 20 ? 5 : 10;
  const out: number[] = [];
  for (let t = Math.ceil(lo / step) * step; t <= hi; t += step) out.push(t);
  return out;
}

export function TrendChart({ title, trend }: { title: string; trend: Trend }) {
  const vals = trend.points.map((p) => p.value);
  if (vals.length === 0) return <div className="muted">{title}: no data</div>;
  const { min, max } = trend.target;
  const lo = Math.floor(Math.min(...vals, min) - 0.5);
  const hi = Math.ceil(Math.max(...vals) + 0.5);
  const inRange = (v: number) => v >= min && v <= max;
  const first = trend.points[0];
  const last = trend.points[trend.points.length - 1];

  const renderDot = (props: DotProps): ReactElement => (
    <circle
      key={`dot-${props.index}`}
      cx={props.cx ?? 0}
      cy={props.cy ?? 0}
      r={5}
      fill={props.payload && !inRange(props.payload.value) ? "#D97706" : "#0E7C86"}
      stroke="#fff"
      strokeWidth={2}
    />
  );

  return (
    <div>
      <div className="row">
        <b>{title}</b>
        <span className="muted">Shaded = target range. Amber = out of range.</span>
      </div>
      <div role="img" aria-label={`${title} over ${trend.points.length} visits, from ${first.value} on ${first.label} to ${last.value} on ${last.label}`} style={{ height: 180 }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={trend.points} margin={{ top: 16, right: 16, bottom: 4, left: 0 }}>
            <CartesianGrid stroke="#EEF3F6" vertical={false} />
            <ReferenceArea y1={Math.max(min, lo)} y2={Math.min(max, hi)} fill="#E6F2F3" fillOpacity={1} ifOverflow="hidden" />
            <XAxis dataKey="label" tick={{ fontSize: 11, fill: "#5B6B7A" }} />
            <YAxis domain={[lo, hi]} ticks={niceTicks(lo, hi)} tick={{ fontSize: 11, fill: "#5B6B7A" }} width={34} />
            <Tooltip
              formatter={(value) => [String(value), title]}
              labelFormatter={(_label, payload) => payload?.[0]?.payload?.date ?? ""}
            />
            <Line type="monotone" dataKey="value" stroke="#1F4E79" strokeWidth={2.5} dot={renderDot} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
