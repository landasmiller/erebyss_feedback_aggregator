"use client";

import { useState } from "react";

export default function RunPreprocessButton({ runId }: { runId: string }) {
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  async function runPreprocess() {
    setLoading(true);
    setMsg(null);

    try {
      const res = await fetch(`http://localhost:8000/runs/${runId}/preprocess`, {
        method: "POST",
      });

      const data = await res.json().catch(() => ({}));

      if (!res.ok) {
        throw new Error(data?.detail || JSON.stringify(data) || "Request failed");
      }

      setMsg("Preprocess started/completed ✅ Refresh the page to see artifacts.");
    } catch (e: any) {
      setMsg(`Error: ${e.message}`);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ marginTop: 10, marginBottom: 10 }}>
      <button
        onClick={runPreprocess}
        disabled={loading}
        style={{
          padding: "10px 14px",
          borderRadius: 10,
          border: "1px solid #ddd",
          fontWeight: 700,
          cursor: loading ? "not-allowed" : "pointer",
        }}
      >
        {loading ? "Running Preprocess..." : "Run Preprocess"}
      </button>

      {msg ? (
        <div style={{ marginTop: 8, fontSize: 13, opacity: 0.85 }}>{msg}</div>
      ) : null}
    </div>
  );
}
