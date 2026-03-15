import { supabase } from "@/lib/supabase";
import RunThemesButton from "./RunThemesButton";
import RunPreprocessButton from "./RunPreprocessButton";
import RunInsightsButton from "./RunInsightsButton";
import RunAnalysisButton from "./RunAnalysisButton";
import RunAutoRefresh from "./RunAutoRefresh";



interface PageProps {
  params: Promise<{ runId: string }>;
}

export default async function RunDetailPage({ params }: PageProps) {
  const { runId } = await params;

  // Load run
  const { data: run, error: runError } = await supabase
    .from("analysis_runs")
    .select("id, name, status, created_at, workspace_id, input_snapshot, model_config")
    .eq("id", runId)
    .single();

  if (runError) {
    return (
      <div style={{ padding: 24 }}>
        <h1>Run</h1>
        <pre>{JSON.stringify(runError, null, 2)}</pre>
      </div>
    );
  }

  // Load steps
  const { data: steps, error: stepsError } = await supabase
    .from("run_steps")
    .select("*")
    .eq("run_id", runId);

// Load themes
const { data: themes, error: themesError } = await supabase
  .from("themes")
  .select("id, title, description, evidence_feedback_ids, created_at")
  .eq("run_id", runId);

// Load Insights 

const { data: insights, error: insightsError } = await supabase
  .from("run_insights")
  .select("id, theme_id, insight, recommendation, priority, evidence_feedback_ids, created_at")
  .eq("run_id", runId)
  .order("priority", { ascending: false })
  .order("created_at", { ascending: false });

  // Load artifacts (for debugging, and to show any intermediate outputs in the future)
const { data: artifacts, error: artifactsError } = await supabase
  .from("run_artifacts")
  .select("id, kind, version, payload, created_at")
  .eq("run_id", runId)
  .order("created_at", { ascending: false });


// Collect all evidence feedback IDs across themes
const evidenceIds = Array.from(
  new Set(
    (themes ?? [])
      .flatMap((t: any) => (t.evidence_feedback_ids ?? []) as string[])
      .filter(Boolean)
  )
);

// Fetch evidence feedback items in one query
const { data: evidenceRows, error: evidenceError } = evidenceIds.length
  ? await supabase
      .from("feedback_items")
      .select("id, raw_text, source_id, occurred_at")
      .in("id", evidenceIds)
  : { data: [], error: null };

// Build a quick map: feedbackId -> feedback row
const evidenceById = new Map<string, any>();
(evidenceRows ?? []).forEach((r: any) => evidenceById.set(r.id, r));

// OPTIONAL: Fetch sources so we can show the source name next to each quote
const sourceIds = Array.from(
  new Set((evidenceRows ?? []).map((r: any) => r.source_id).filter(Boolean))
);

const { data: sourceRows, error: sourceError } = sourceIds.length
  ? await supabase.from("sources").select("id, name").in("id", sourceIds)
  : { data: [], error: null };

const sourceNameById = new Map<string, string>();
(sourceRows ?? []).forEach((s: any) => sourceNameById.set(s.id, s.name));

  return (
    <div style={{ padding: 24 }}>
      <h1>Run Detail</h1>

      <div style={{ marginTop: 12, marginBottom: 12, fontSize: 14 }}>
        <div>
          <strong>Name:</strong> {run.name}
        </div>
        <div>
          <strong>Status:</strong> {run.status}
        </div>
        <div>
          <strong>Run ID:</strong> <code>{run.id}</code>
        </div>
        <div>
          <strong>Workspace:</strong> <code>{run.workspace_id}</code>
        </div>
      </div>

      {/* Button to run themes (no more curl) */}
      {/*<RunThemesButton runId={runId} /> */}
      {/*<RunPreprocessButton runId={runId} />*/}
      <RunAnalysisButton runId={runId} />
      <RunAutoRefresh runId={runId} initialStatus={run.status} />


      <h2 style={{ marginTop: 18 }}>Steps</h2>
      {stepsError ? (
        <pre>{JSON.stringify(stepsError, null, 2)}</pre>
      ) : (
        <ul style={{ marginTop: 12 }}>
          {(steps ?? []).map((s: any) => (
            <li key={s.id} style={{ marginBottom: 10 }}>
              <strong>{s.step_name}</strong> — {s.status}
            </li>
          ))}
        </ul>
      )}

      <h2 style={{ marginTop: 22 }}>Themes</h2>
      {themesError ? (
        <pre>{JSON.stringify(themesError, null, 2)}</pre>
      ) : (themes ?? []).length === 0 ? (
        <div style={{ opacity: 0.75 }}>No themes yet. Click “Run Themes”.</div>
      ) : (
        <div style={{ marginTop: 12 }}>
          {(themes ?? []).map((t: any) => (
            <div
              key={t.id}
              style={{
                border: "1px solid #eee",
                borderRadius: 10,
                padding: 12,
                marginBottom: 12,
              }}
            >
              <div style={{ fontWeight: 800, fontSize: 16 }}>{t.title}</div>

              {t.description ? (
                <div style={{ marginTop: 6, opacity: 0.9 }}>{t.description}</div>
              ) : null}

<div style={{ marginTop: 10 }}>
  <div style={{ fontSize: 12, fontWeight: 700, opacity: 0.8 }}>Evidence</div>

  {evidenceError ? (
    <pre style={{ marginTop: 6 }}>{JSON.stringify(evidenceError, null, 2)}</pre>
  ) : (
    <ul style={{ marginTop: 8, paddingLeft: 18 }}>
      {((t.evidence_feedback_ids ?? []) as string[])
        .slice(0, 3)
        .map((fid: string) => {
          const row = evidenceById.get(fid);

          const sourceName = 
            row?.source_id ? sourceNameById.get(row.source_id) ?? "Unknown" : "Unkown";
          return (
            <li key={fid} style={{ marginBottom: 8, fontSize: 13, opacity: 0.95 }}>
              {row?.raw_text ? (
                <span>{row.raw_text}</span>
              ) : (
                <span style={{ opacity: 0.6 }}>Missing feedback text for {fid}</span>
              )}
            </li>
          );
        })}
    </ul>
  )}

{sourceError ? (
    <pre style={{ marginTop: 6 }}>{JSON.stringify(sourceError, null, 2)}</pre>
  ) : null}  
</div>

            </div>
          ))}
        </div>
      )}

      <h2 style={{ marginTop: 22 }}>Insights</h2>

        <RunInsightsButton runId={runId} />

        {insightsError ? (
          <pre>{JSON.stringify(insightsError, null, 2)}</pre>
        ) : (insights ?? []).length === 0 ? (
          <div style={{ opacity: 0.75 }}>
            No insights yet. Click “Run Insights”.
          </div>
        ) : (
          <div style={{ marginTop: 12 }}>
            {(insights ?? []).map((ins: any) => {
              const evidenceIds: string[] = (ins.evidence_feedback_ids ?? []) as string[];

              return (
                <div
                  key={ins.id}
                  style={{
                    border: "1px solid #eee",
                    borderRadius: 10,
                    padding: 12,
                    marginBottom: 12,
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
                    <div style={{ fontWeight: 900, fontSize: 15 }}>
                      Priority: {ins.priority}
                    </div>
                    <div style={{ fontSize: 12, opacity: 0.7 }}>
                      {ins.created_at ? new Date(ins.created_at).toLocaleString() : ""}
                    </div>
                  </div>

                  <div style={{ marginTop: 10, fontSize: 14, fontWeight: 800 }}>
                    Insight
                  </div>
                  <div style={{ marginTop: 6, fontSize: 14, opacity: 0.95 }}>
                    {ins.insight}
                  </div>

                  {ins.recommendation ? (
                    <>
                      <div style={{ marginTop: 12, fontSize: 14, fontWeight: 800 }}>
                        Recommendation
                      </div>
                      <div style={{ marginTop: 6, fontSize: 14, opacity: 0.95 }}>
                        {ins.recommendation}
                      </div>
                    </>
                  ) : null}

                  <div style={{ marginTop: 12 }}>
                    <div style={{ fontSize: 12, fontWeight: 800, opacity: 0.8 }}>
                      Evidence
                    </div>

                    {evidenceIds.length === 0 ? (
                      <div style={{ marginTop: 6, fontSize: 13, opacity: 0.7 }}>
                        No evidence IDs found.
                      </div>
                    ) : (
                      <ul style={{ marginTop: 8, paddingLeft: 18 }}>
                        {evidenceIds.slice(0, 3).map((fid: string) => {
                          const row = evidenceById.get(fid);
                          const sourceName = row?.source_id
                            ? sourceNameById.get(row.source_id) ?? "Unknown"
                            : "Unknown";

                          return (
                            <li key={fid} style={{ marginBottom: 10, fontSize: 13 }}>
                              <div style={{ fontWeight: 800, opacity: 0.85 }}>
                                {sourceName}
                              </div>
                              <div style={{ opacity: 0.95 }}>
                                {row?.raw_text ? row.raw_text : `Missing feedback text for ${fid}`}
                              </div>
                            </li>
                          );
                        })}
                      </ul>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}

      <h2 style={{ marginTop: 22 }}>Artifacts</h2>

      {artifactsError ? (
      <pre>{JSON.stringify(artifactsError, null, 2)}</pre>
      ) : (artifacts ?? []).length === 0 ? (
        <div style={{ opacity: 0.75 }}>No artifacts yet.</div>
      ) : (
        <div style={{ marginTop: 12 }}>
        {(artifacts ?? []).map((a: any) => (
        <div
          key={a.id}
          style={{
            border: "1px solid #eee",
            borderRadius: 10,
            padding: 12,
            marginBottom: 12,
          }}
        >
        <div style={{ fontWeight: 800 }}>
          {a.step_name} • {a.artifact_type}
        </div>
        <div style={{ marginTop: 8, fontSize: 12, opacity: 0.8 }}>
          {a.created_at ? new Date(a.created_at).toLocaleString() : ""}
        </div>
        <pre style={{ marginTop: 10, background: "#f7f7f7", padding: 10, borderRadius: 8 }}>
          {JSON.stringify(a.payload, null, 2)}
        </pre>
      </div>
    ))}
  </div>
)}


      <h2 style={{ marginTop: 18 }}>Input Snapshot</h2>
      <pre style={{ background: "#f7f7f7", padding: 12, borderRadius: 8 }}>
        {JSON.stringify(run.input_snapshot, null, 2)}
      </pre>

      <h2 style={{ marginTop: 18 }}>Model Config</h2>
      <pre style={{ background: "#f7f7f7", padding: 12, borderRadius: 8 }}>
        {JSON.stringify(run.model_config, null, 2)}
      </pre>
    </div>
  );
}

