"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useMemo, useState } from "react";

export default function CreateRunButton({ workspaceId }: { workspaceId: string }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const filters = useMemo(() => {
    const intent = searchParams.get("intent");
    const sentiment = searchParams.get("sentiment");
    const source = searchParams.get("source");

    const f: Record<string, string> = {};
    if (intent && intent !== "all") f.intent = intent;
    if (sentiment && sentiment !== "all") f.sentiment = sentiment;
    if (source && source !== "all") f.source = source;

    return f;
  }, [searchParams]);

  async function onCreateRun() {
    setIsLoading(true);
    setError(null);

    try {
      const base = process.env.NEXT_PUBLIC_API_BASE_URL;
      if (!base) throw new Error("NEXT_PUBLIC_API_BASE_URL is missing in apps/web/.env.local");

      const res = await fetch(`${base}/runs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          workspace_id: workspaceId,
          name: "Themes Run",
          filters,
          limit: 200,
        }),
      });

      const json = await res.json().catch(() => ({}));

      if (!res.ok) {
        throw new Error(json?.detail?.message || json?.detail || "Failed to create run");
      }

      const runId = json?.run_id;
      if (!runId) throw new Error("API did not return run_id");

      router.push(`/runs/${runId}`);
    } catch (e: any) {
      setError(e?.message ?? "Unknown error");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div style={{ marginTop: 12, marginBottom: 12 }}>
      <button
        onClick={onCreateRun}
        disabled={isLoading}
        style={{
          padding: "10px 14px",
          borderRadius: 8,
          border: "1px solid #ddd",
          background: isLoading ? "#f3f3f3" : "white",
          cursor: isLoading ? "not-allowed" : "pointer",
          fontWeight: 600,
        }}
      >
        {isLoading ? "Creating run..." : "Create Analysis Run"}
      </button>

      <div style={{ fontSize: 12, opacity: 0.75, marginTop: 6 }}>
        Uses filters: {Object.keys(filters).length ? JSON.stringify(filters) : "none"}
      </div>

      {error ? (
        <div style={{ marginTop: 8, color: "crimson", fontSize: 13 }}>
          {error}
        </div>
      ) : null}
    </div>
  );
}
