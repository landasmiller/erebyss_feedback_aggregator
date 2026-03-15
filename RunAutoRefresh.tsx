"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

type Step = { step_name: string; status: string };

type Props = {
  runId: string;
  initialStatus?: string | null;
};

export default function RunAutoRefresh({ runId, initialStatus }: Props) {
  const router = useRouter();
  const [status, setStatus] = useState<string>(initialStatus ?? "unknown");
  const [steps, setSteps] = useState<Step[]>([]);
  const [error, setError] = useState<string | null>(null);

  const timerRef = useRef<number | null>(null);

  const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  const shouldPoll = status === "queued" || status === "running";

  useEffect(() => {
    async function tick() {
      try {
        setError(null);

        const res = await fetch(`${API_BASE}/runs/${runId}/status`, {
          cache: "no-store",
        });

        if (!res.ok) {
          const text = await res.text();
          throw new Error(text || `HTTP ${res.status}`);
        }

        const data = await res.json();
        const nextStatus = (data?.status || "unknown") as string;
        const nextSteps = (data?.steps || []) as Step[];

        setStatus(nextStatus);
        setSteps(nextSteps);

        // Refresh the server component data (themes/insights/etc)
        router.refresh();

        // Stop polling once finished
        if (nextStatus !== "queued" && nextStatus !== "running") {
          if (timerRef.current) window.clearInterval(timerRef.current);
          timerRef.current = null;
        }
      } catch (e: any) {
        setError(e?.message || "Polling failed");
      }
    }

    // Start polling only if run is queued/running
    if (shouldPoll) {
      tick();
      timerRef.current = window.setInterval(tick, 2000);
    }

    return () => {
      if (timerRef.current) window.clearInterval(timerRef.current);
      timerRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId, shouldPoll]);

  if (!shouldPoll && (steps?.length ?? 0) === 0) return null;

  return (
    <div style={{ marginTop: 12, padding: 12, border: "1px solid #eee", borderRadius: 10 }}>
      <div style={{ fontSize: 13, opacity: 0.9 }}>
        <strong>Auto-refresh:</strong>{" "}
        {shouldPoll ? "ON (polling every 2s)" : "OFF"} • <strong>Status:</strong> {status}
      </div>

      {steps?.length ? (
        <div style={{ marginTop: 10, display: "flex", gap: 8, flexWrap: "wrap" }}>
          {steps.map((s) => (
            <div
              key={s.step_name}
              style={{
                fontSize: 12,
                padding: "6px 10px",
                borderRadius: 999,
                border: "1px solid #ddd",
                background: "#fafafa",
              }}
            >
              <strong>{s.step_name}</strong>: {s.status}
            </div>
          ))}
        </div>
      ) : null}

      {error ? (
        <div style={{ marginTop: 10, fontSize: 12, color: "crimson" }}>
          {error}
        </div>
      ) : null}
    </div>
  );
}