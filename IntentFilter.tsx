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

export default function IntentFilter() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const current = searchParams.get("intent") ?? "all";

  function onChange(nextValue: string) {
    const params = new URLSearchParams(searchParams.toString());

    if (!nextValue || nextValue === "all") {
      params.delete("intent");
    } else {
      params.set("intent", nextValue);
    }

    const query = params.toString();
    router.push(query ? `${pathname}?${query}` : pathname);
  }

  return (
    <div style={{ marginTop: 12, marginBottom: 12 }}>
      <label style={{ fontSize: 12, opacity: 0.8 }}>Intent</label>
      <div>
        <select
          value={current}
          onChange={(e) => onChange(e.target.value)}
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
  );
}
