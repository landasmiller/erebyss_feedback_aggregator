"use client";

import { useState } from "react";

export default function RunInsightsButton({ runId }: { runId: string }) {
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  async function onClick() {
    setLoading(true);
    setMsg(null);

    try {
      const res = await fetch(`http://localhost:8000/runs/${runId}/insights`, {
        method: "POST",
      });

      const json = await res.json().catch(() => ({}));

      if (!res.ok) {
        setMsg(json?.detail ? String(json.detail) : "Failed to run insights.");
        return;
      }

      setMsg(`Insights created: ${json.insights_created ?? "ok"}`);

      // Refresh the page so the server component refetches insights
      window.location.reload();
    } catch (e: any) {
      setMsg(e?.message ?? "Network error calling API.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ marginTop: 12, marginBottom: 12 }}>
      <button
        onClick={onClick}
        disabled={loading}
        style={{
          padding: "10px 12px",
          borderRadius: 10,
          border: "1px solid #ddd",
          background: loading ? "#f3f3f3" : "#111",
          color: loading ? "#666" : "#fff",
          cursor: loading ? "not-allowed" : "pointer",
          fontWeight: 800,
        }}
      >
        {loading ? "Running Insights..." : "Run Insights"}
      </button>

      {msg ? (
        <div style={{ marginTop: 8, fontSize: 13, opacity: 0.85 }}>{msg}</div>
      ) : null}
    </div>
  );
}
