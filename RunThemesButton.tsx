"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

export default function RunThemesButton({ runId }: { runId: string }) {
  const router = useRouter();
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onRun() {
    setIsLoading(true);
    setError(null);

    try {
      const base = process.env.NEXT_PUBLIC_API_BASE_URL;
      if (!base) throw new Error("NEXT_PUBLIC_API_BASE_URL is missing in apps/web/.env.local");

      const res = await fetch(`${base}/runs/${runId}/themes`, {
        method: "POST",
      });

      const json = await res.json().catch(() => ({}));

      if (!res.ok) {
        throw new Error(json?.detail?.error || json?.detail?.message || json?.detail || "Failed to run themes");
      }

      // Refresh the server page so themes/steps re-fetch from Supabase
      router.refresh();
    } catch (e: any) {
      setError(e?.message ?? "Unknown error");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div style={{ marginTop: 12, marginBottom: 12 }}>
      <button
        onClick={onRun}
        disabled={isLoading}
        style={{
          padding: "10px 14px",
          borderRadius: 8,
          border: "1px solid #ddd",
          background: isLoading ? "#f3f3f3" : "white",
          cursor: isLoading ? "not-allowed" : "pointer",
          fontWeight: 700,
        }}
      >
        {isLoading ? "Running themes..." : "Run Themes"}
      </button>

      {error ? (
        <div style={{ marginTop: 8, color: "crimson", fontSize: 13 }}>
          {error}
        </div>
      ) : null}
    </div>
  );
}
