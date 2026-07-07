"use client";

import { Line, LineChart, ResponsiveContainer, YAxis } from "recharts";

export default function Sparkline({
  data,
  color,
  height = 32,
}: {
  data: number[];
  color?: string;
  height?: number;
}) {
  if (!data || data.length < 2) {
    return <div style={{ height }} className="opacity-30 text-xs">—</div>;
  }
  const up = data[data.length - 1] >= data[0];
  const clr = color ?? (up ? "var(--signal-long)" : "var(--signal-short)");
  const points = data.map((v, i) => ({ i, v }));

  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={points} margin={{ top: 2, right: 0, bottom: 2, left: 0 }}>
        <YAxis hide domain={["dataMin", "dataMax"]} />
        <Line
          type="monotone"
          dataKey="v"
          stroke={clr}
          strokeWidth={1.25}
          dot={false}
          isAnimationActive={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
