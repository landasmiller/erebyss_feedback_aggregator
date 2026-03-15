import CreateRunButton from "./CreateRunButton";
import { supabase } from "@/lib/supabase";
import Filters from "./Filters";


interface PageProps {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ intent?: string; sentiment?: string; source?: string }>;
}

export default async function FeedbackPage({ params, searchParams }: PageProps) {
  const { id: workspaceId } = await params;
  const { intent, sentiment, source } = await searchParams;

  if (!workspaceId) {
    return (
      <div style={{ padding: 24 }}>
        <h1>Feedback</h1>
        <CreateRunButton workspaceId={workspaceId} />
        <p>Missing workspace ID.</p>
      </div>
    );
  }

  let query = supabase
    .from("feedback_items")
    .select(
      `
      id,
      raw_text,
      intent,
      sentiment,
      occurred_at,
      metadata,
      sources (
        type
      )
    `
    )
    .eq("workspace_id", workspaceId)
    .order("occurred_at", { ascending: false })
    .limit(50);

  // Intent filter
  if (intent && intent !== "all") {
    query = query.eq("intent", intent);
  }

  // Sentiment filter
  if (sentiment && sentiment !== "all") {
    query = query.eq("sentiment", sentiment);
  }

  // Source filter (join filter on related table)
  // In Supabase PostgREST, you can filter embedded relations like: sources.type
  if (source && source !== "all") {
    query = query.eq("sources.type", source);
  }

  const { data, error } = await query;

  if (error) {
    return (
      <div style={{ padding: 24 }}>
        <h1>Feedback</h1>
        <pre>{JSON.stringify(error, null, 2)}</pre>
      </div>
    );
  }

  const activeFilters = [
    intent && intent !== "all" ? `intent=${intent}` : null,
    sentiment && sentiment !== "all" ? `sentiment=${sentiment}` : null,
    source && source !== "all" ? `source=${source}` : null,
  ].filter(Boolean);

  return (
    <div style={{ padding: 24 }}>
      <h1>Feedback</h1>
      <div style={{ padding: 10, border: "0px solid black", marginBottom: 12 }}>
        
        
         <CreateRunButton workspaceId={workspaceId} />
         <div style={{ marginBottom: 12 }}>
  <a
    href={`/workspaces/${workspaceId}/runs`}
    style={{ fontSize: 14, textDecoration: "underline" }}
  >
    View all analysis runs →
  </a>
</div>

<a
  href={`/workspaces/${workspaceId}/runs`}
  style={{
    display: "inline-block",
    marginLeft: 10,
    padding: "8px 12px",
    borderRadius: 10,
    border: "1px solid #ddd",
    textDecoration: "none",
    fontWeight: 700,
  }}
>
  View Runs
</a>


        </div>

        

      <Filters />

      <div style={{ fontSize: 12, opacity: 0.75, marginBottom: 12 }}>
        Showing {(data ?? []).length} items
        {activeFilters.length > 0 ? ` · Filters: ${activeFilters.join(", ")}` : ""}
      </div>

      <ul>
        {(data ?? []).map((f) => (
          <li
            key={f.id}
            style={{
              padding: 12,
              border: "1px solid #ddd",
              borderRadius: 6,
              marginBottom: 12,
            }}
          >
            <div style={{ fontSize: 14, marginBottom: 6 }}>
              <strong>Intent:</strong> {f.intent} ·{" "}
              <strong>Sentiment:</strong> {f.sentiment}
            </div>

            <div style={{ marginBottom: 6 }}>{f.raw_text}</div>

            <div style={{ fontSize: 12, opacity: 0.7 }}>
              {f.sources?.type ?? "unknown"} ·{" "}
              {f.occurred_at
                ? new Date(f.occurred_at).toLocaleDateString()
                : "unknown date"}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
