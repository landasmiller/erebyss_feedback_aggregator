"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";


const INTENTS = [
  { value: "all", label: "All intents" },
  { value: "feature_request", label: "Feature request" },
  { value: "bug_report", label: "Bug report" },
  { value: "usability_issue", label: "Usability issue" },
  { value: "praise", label: "Praise" },
  { value: "other", label: "Other" },
] as const;

const SENTIMENTS = [
  { value: "all", label: "All sentiments" },
  { value: "positive", label: "Positive" },
  { value: "neutral", label: "Neutral" },
  { value: "negative", label: "Negative" },
  { value: "mixed", label: "Mixed" },
  { value: "unknown", label: "Unknown" },
] as const;

// These must match sources.type values in your DB
const SOURCES = [
  { value: "all", label: "All sources" },
  { value: "app_store", label: "App Store" },
  { value: "play_store", label: "Play Store" },
  { value: "zendesk", label: "Zendesk" },
  { value: "intercom", label: "Intercom" },
  { value: "reddit", label: "Reddit" },
  { value: "discord", label: "Discord" },
  { value: "email", label: "Email" },
  { value: "survey", label: "Survey" },
] as const;

export default function Filters() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const intent = searchParams.get("intent") ?? "all";
  const sentiment = searchParams.get("sentiment") ?? "all";
  const source = searchParams.get("source") ?? "all";

  function updateParam(key: "intent" | "sentiment" | "source", value: string) {
    const params = new URLSearchParams(searchParams.toString());

    if (!value || value === "all") params.delete(key);
    else params.set(key, value);

    const query = params.toString();
    router.push(query ? `${pathname}?${query}` : pathname);
  }

  function clearAll() {
    router.push(pathname);
  }

  return (
    <div style={{ marginTop: 12, marginBottom: 16 }}>
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
        <div>
          <label style={{ fontSize: 12, opacity: 0.8 }}>Intent</label>
          <div>
            <select
              value={intent}
              onChange={(e) => updateParam("intent", e.target.value)}
              style={{ padding: 8, borderRadius: 6, border: "1px solid #ddd" }}
            >
              {INTENTS.map((i) => (
                <option key={i.value} value={i.value}>
                  {i.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div>
          <label style={{ fontSize: 12, opacity: 0.8 }}>Sentiment</label>
          <div>
            <select
              value={sentiment}
              onChange={(e) => updateParam("sentiment", e.target.value)}
              style={{ padding: 8, borderRadius: 6, border: "1px solid #ddd" }}
            >
              {SENTIMENTS.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div>
          <label style={{ fontSize: 12, opacity: 0.8 }}>Source</label>
          <div>
            <select
              value={source}
              onChange={(e) => updateParam("source", e.target.value)}
              style={{ padding: 8, borderRadius: 6, border: "1px solid #ddd" }}
            >
              {SOURCES.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div style={{ alignSelf: "end" }}>
          <button
            onClick={clearAll}
            style={{
              padding: "8px 12px",
              borderRadius: 6,
              border: "1px solid #ddd",
              background: "white",
              cursor: "pointer",
            }}
          >
            Clear
          </button>
        </div>
      </div>
    </div>
  );
}
