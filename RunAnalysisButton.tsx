"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function RunAnalysisButton({ runId }: { runId: string }) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  async function onClick() {
    setLoading(true);
    setError(null);

    try {
      const res = await fetch(`${API_BASE}/runs/${runId}/execute`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });

      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `HTTP ${res.status}`);
      }

      // Pipeline is queued in the background
      router.refresh();
    } catch (e: any) {
      setError(e?.message || "Failed to run analysis");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ marginTop: 10, marginBottom: 14 }}>
      <button
        onClick={onClick}
        disabled={loading}
        style={{
          padding: "10px 14px",
          borderRadius: 10,
          border: "1px solid #ddd",
          background: loading ? "#f3f3f3" : "#111",
          color: loading ? "#333" : "#fff",
          cursor: loading ? "not-allowed" : "pointer",
          fontWeight: 800,
        }}
      >
        {loading ? "Running..." : "Run Analysis"}
      </button>

      {error ? (
        <div style={{ marginTop: 8, color: "crimson", fontSize: 13 }}>
          {error}
        </div>
      ) : null}

      <div style={{ marginTop: 8, fontSize: 12, opacity: 0.7 }}>
        Runs preprocess → themes → insights in the background.
      </div>
    </div>
  );
}
