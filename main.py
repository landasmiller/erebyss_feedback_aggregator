import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from supabase import create_client
from typing import Any, Dict, List, Optional, Tuple
from collections import Counter, defaultdict
import re
import hashlib
from fastapi import HTTPException
from fastapi import FastAPI, HTTPException, Query
from typing import Optional
from collections import Counter, defaultdict
from typing import Dict, List
import os
import json
import traceback
from openai import OpenAI


load_dotenv(override=True)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
  raise RuntimeError("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in apps/api/.env")

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

import re
from typing import Optional

UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)

def is_uuid(value: str) -> bool:
    return bool(UUID_RE.match(value or ""))


def resolve_source_id(supabase, workspace_id: str, source_value: str) -> Optional[str]:
    """
    Accepts:
        - UUID
        - source name  ("App Store")
        - source type  ("app_store")

    Returns:
        sources.id UUID
    """

    if not source_value:
        return None

    if is_uuid(source_value):
        return source_value

    # 1️⃣ match by type
    res = (
        supabase.table("sources")
        .select("id")
        .eq("workspace_id", workspace_id)
        .eq("type", source_value)
        .limit(1)
        .execute()
    )
    if res.data:
        return res.data[0]["id"]

    # 2️⃣ match by name
    res = (
        supabase.table("sources")
        .select("id")
        .eq("workspace_id", workspace_id)
        .ilike("name", source_value)
        .limit(1)
        .execute()
    )
    if res.data:
        return res.data[0]["id"]

    return None


WORD_RE = re.compile(r"[a-z0-9']+")

STOPWORDS = {
    "the","a","an","and","or","but","if","then","so","to","of","in","on","for","with","at","by",
    "from","is","are","was","were","be","been","being","it","this","that","these","those","we","you",
    "i","our","your","they","them","as","not","no","do","does","did","can","could","should","would",
    "will","just","very","more","most","less","least","about","into","over","under","up","down","out"
}

def _is_good_theme_phrase(p: str) -> bool:
    if not p:
        return False
    p = p.strip()
    if len(p) < 4:
        return False
    if p in STOP_PHRASES:
        return False
    # reject phrases that are all stopwords
    parts = [w for w in p.split() if w]
    if not parts:
        return False
    if all(w in THEME_STOPWORDS for w in parts):
        return False
    # reject phrases that start/end with junk words
    if parts[0] in THEME_STOPWORDS or parts[-1] in THEME_STOPWORDS:
        return False
    return True

def extract_theme_candidates(items: list[dict], max_phrases: int = 8) -> list[str]:
    """
    Pull high-signal 2–3 word phrases from preprocess items.
    This beats single-token keywords like "raised" or "have".
    """
    phrase_counts = Counter()
    word_counts = Counter()

    for it in items:
        norm = normalize_text(it.get("raw_text") or "")
        toks = [t for t in norm.split() if t and t not in THEME_STOPWORDS and len(t) >= 3]
        if not toks:
            continue

        # track single words as fallback
        for t in toks:
            word_counts[t] += 1

        # bigrams
        for i in range(len(toks) - 1):
            p = f"{toks[i]} {toks[i+1]}"
            if _is_good_theme_phrase(p):
                phrase_counts[p] += 1

        # trigrams (optional but helps)
        for i in range(len(toks) - 2):
            p = f"{toks[i]} {toks[i+1]} {toks[i+2]}"
            if _is_good_theme_phrase(p):
                phrase_counts[p] += 1

    # prefer phrases first
    phrases = [p for p, _ in phrase_counts.most_common(max_phrases)]

    # if phrases are empty, fallback to words
    if not phrases:
        phrases = [w for w, _ in word_counts.most_common(max_phrases)]

    # final cleanup (avoid duplicates like "api token" + "token refresh" if desired later)
    return phrases

def normalize_text(s: str) -> str:
    s = (s or "").strip().lower()
    # remove most punctuation → keep words/numbers
    tokens = WORD_RE.findall(s)
    return " ".join(tokens)

def sha1_hex(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()

def counter_top(counter: Counter, n: int = 15) -> List[Dict[str, Any]]:
    return [{"key": k, "count": v} for k, v in counter.most_common(n)]

# Start of the FASTAPI app and endpoints

app = FastAPI()
RUN_STEPS_FK_COL = "run_id"        # <-- change if your run_steps FK is named differently
THEMES_FK_COL = "run_id"           # <-- change if your themes FK is named differently


# Allow Next.js dev server to call FastAPI locally
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok"}

class CreateRunRequest(BaseModel):
    workspace_id: str = Field(..., description="UUID of the workspace")
    name: str | None = Field(default=None, description="Optional run name")
    filters: dict = Field(default_factory=dict, description="Filters used to select feedback")
    limit: int = Field(default=200, ge=1, le=1000)


@app.post("/runs")
def create_run(payload: CreateRunRequest):
    run_name = payload.name or "Theme analysis run"

    run_insert = {
        "workspace_id": payload.workspace_id,
        "status": "queued",
        "name": run_name,
        "input_snapshot": {
            "filters": payload.filters,
            "limit": payload.limit,
        },
        "model_config": {
            "pipeline": "themes_v1",
        },
    }

    try:
        run_res = supabase.table("analysis_runs").insert(run_insert).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail={"message": "Supabase insert crashed", "error": str(e)})

    if not getattr(run_res, "data", None):
        # This will often include the exact db error message
        raise HTTPException(status_code=500, detail={"message": "Failed to create analysis run", "raw": str(run_res)})

    run = run_res.data[0]
    run_id = run["id"]

    steps = [
        {"run_id": run_id, "step_name": "preprocess", "status": "queued"},
        {"run_id": run_id, "step_name": "themes", "status": "queued"},
    ]

    try:
        steps_res = supabase.table("run_steps").insert(steps).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail={"message": "Supabase steps insert crashed", "error": str(e)})

    if steps_res.data is None:
        raise HTTPException(status_code=500, detail={"message": "Failed to create run steps", "raw": str(steps_res)})

    return {"run_id": run_id, "run": run}

import re
from collections import Counter
from typing import Any

def _normalize(text: str) -> list[str]:
    text = (text or "").lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    parts = [p for p in text.split() if len(p) >= 3]
    # tiny stopword list (enough for MVP)
    stop = set(["the","and","for","with","that","this","from","have","need","not","but","are","was","were","you","your","our","they","their","just","into","its","it's","too"])
    return [p for p in parts if p not in stop]

def _build_themes(feedback_rows: list[dict[str, Any]], max_themes: int = 6):
    """
    Heuristic theme generator that works without an LLM:
    - Extract common keywords
    - Group evidence by top keywords
    """
    tokens = []
    for r in feedback_rows:
        tokens.extend(_normalize(r.get("raw_text") or r.get("text") or ""))

    freq = Counter(tokens)
    top_keywords = [w for w, _ in freq.most_common(20)]
    if not top_keywords:
        return []

    themes = []
    used = set()

    for kw in top_keywords:
        if kw in used:
            continue

        evidence = []
        for r in feedback_rows:
            txt = (r.get("raw_text") or r.get("text") or "").lower()
            if kw in txt:
                evidence.append(r)

        if len(evidence) < 2:
            continue

        used.add(kw)
        themes.append({
            "title": kw.replace("_", " ").title(),
            "summary": f"Repeated feedback mentions '{kw}'.",
            "evidence_feedback_ids": [e["id"] for e in evidence[:8]],
        })

        if len(themes) >= max_themes:
            break

    return themes

# Added a helper to load preprocess artifact items
def load_preprocess_items(run_id: str):
    """
    Returns:
      payload (dict), items (list[dict])
    """
    art_res = (
        supabase.table("run_artifacts")
        .select("payload")
        .eq("run_id", run_id)
        .eq("kind", "preprocess")
        .eq("version", "v1")
        .single()
        .execute()
    )

    payload = art_res.data.get("payload") if art_res.data else None
    if not payload:
        raise HTTPException(
            status_code=400,
            detail="Preprocess artifact not found. Run /runs/{run_id}/preprocess first."
        )

    items = payload.get("items") or []
    if not isinstance(items, list) or len(items) == 0:
        raise HTTPException(
            status_code=400,
            detail="Preprocess artifact has no items. Ensure /preprocess writes payload.items."
        )

    return payload, items


@app.post("/runs/{run_id}/themes")
def run_themes(run_id: str, limit: int = 200):
    """
    Themes step (artifact-driven):
      - loads run
      - loads preprocess artifact (payload.items)
      - generates themes from items
      - inserts themes into themes table
      - marks run_steps('themes') as succeeded
    """

    # 1) Load run
    run_res = (
        supabase.table("analysis_runs")
        .select("id, workspace_id, status, input_snapshot")
        .eq("id", run_id)
        .single()
        .execute()
    )
    run = run_res.data
    if not run:
        raise HTTPException(status_code=404, detail="run_not_found")

    workspace_id = run["workspace_id"]

    # 2) Mark step running (use correct enum values)
    try:
        supabase.table("run_steps") \
            .update({"status": "running"}) \
            .eq("run_id", run_id) \
            .eq("step_name", "themes") \
            .execute()
    except Exception:
        pass

    try:
        # 3) Load preprocess artifact items (NO feedback_items query anymore)
        preprocess_payload, items = load_preprocess_items(run_id)

        # Respect preprocess limit if present; otherwise use query param limit
        preprocess_limit = int(preprocess_payload.get("limit") or 0)
        effective_limit = preprocess_limit if preprocess_limit > 0 else int(limit)
        items = items[:effective_limit]

        # 4) Build quick source name map (so evidence can show source name later)
        # items include source_id; sources table has id + name
        source_ids = list({it.get("source_id") for it in items if it.get("source_id")})
        source_name_by_id = {}
        if source_ids:
            src_res = (
                supabase.table("sources")
                .select("id, name")
                .in_("id", source_ids)
                .execute()
            )
            for s in (src_res.data or []):
                source_name_by_id[s["id"]] = s.get("name") or "Unknown"

        # 5) Generate themes (simple heuristic MVP)
        # Uses preprocess outputs if available, otherwise uses token counts from items.
        # - Choose top keywords (already computed in preprocess) and form themes around them.
        # Prefer phrase candidates from preprocess items
            keywords = extract_theme_candidates(items, max_phrases=8)

# (optional) if preprocess has top_keywords, use them only as a fallback
            if not keywords:
                top_keywords = preprocess_payload.get("top_keywords") or []
            keywords = [k["key"] for k in top_keywords[:6] if isinstance(k, dict) and k.get("key")]
            # VERY small fallback: pick frequent tokens from normalize_text
            token_counts = Counter()
            for it in items:
                norm = normalize_text(it.get("raw_text") or "")
                for w in norm.split():
                    if len(w) >= 3 and w not in STOPWORDS:
                        token_counts[w] += 1
            keywords = [k for k, _ in token_counts.most_common(6)]

        themes_to_insert = []

        for kw in keywords:
            # Evidence: pick first 3 feedback items containing keyword
            evidence = []
            for it in items:
                txt = (it.get("raw_text") or "").lower()
                if kw.lower() in txt:
                    evidence.append(it)
                if len(evidence) >= 3:
                    break

            if not evidence:
                continue

            evidence_ids = [e["id"] for e in evidence if e.get("id")]
            # Optional: include quotes in description (nice UX even before UI joins)
            quote_lines = []
            for e in evidence:
                sname = source_name_by_id.get(e.get("source_id"), "Unknown")
                quote_lines.append(f"- ({sname}) {e.get('raw_text','')}")
            description = f"Frequent mentions of '{kw}'.\n\nEvidence:\n" + "\n".join(quote_lines)

            themes_to_insert.append({
                "run_id": run_id,
                "workspace_id": workspace_id,
                "title": kw.replace("_", " ").title(),
                "description": description,
                "evidence_feedback_ids": evidence_ids,
            })

        # 6) Insert themes (clear old ones for this run first — optional but recommended)
        # If you want repeated runs to replace old themes:
        try:
            supabase.table("themes").delete().eq("run_id", run_id).execute()
        except Exception:
            pass

        if themes_to_insert:
            supabase.table("themes").insert(themes_to_insert).execute()

        # 7) Mark step succeeded
        try:
            supabase.table("run_steps") \
                .update({"status": "succeeded"}) \
                .eq("run_id", run_id) \
                .eq("step_name", "themes") \
                .execute()
        except Exception:
            pass

        return {
            "status": "ok",
            "themes_created": len(themes_to_insert),
            "keywords_used": keywords,
        }

    except Exception:
        # Mark failed
        try:
            supabase.table("run_steps") \
                .update({"status": "failed"}) \
                .eq("run_id", run_id) \
                .eq("step_name", "themes") \
                .execute()
        except Exception:
            pass
        raise


# New Insights endpoint that summarizes the preprocess results in a simple text format. This can be used by the UI to show a quick summary of the feedback without needing to build a full themes table or run an LLM.  

def _priority_from_evidence_text(evidence_texts: List[str]) -> int:
    """
    Simple MVP heuristic priority scoring:
    5 = critical, 4 = high, 3 = medium, 2 = low, 1 = very low
    """
    text = " ".join([t.lower() for t in evidence_texts if t]).strip()
    if not text:
        return 3

    critical_terms = ["crash", "crashes", "down", "outage", "cannot", "can't", "won't", "broken", "fails", "error"]
    high_terms = ["slow", "timeout", "doesn't work", "does not work", "stuck", "blocked", "login", "payment"]

    score = 3
    if any(term in text for term in critical_terms):
        score = max(score, 5)
    elif any(term in text for term in high_terms):
        score = max(score, 4)

    # cap 1..5
    return max(1, min(5, score))


def is_bad_theme(title: str) -> bool:
    if not title:
        return True
    if len(title) <= 3:
        return True
    if title.lower() in STOPWORDS:
        return True
    if title.lower() in {"issue", "problem", "thing"}:
        return True
    return False


def _recommendation_for_theme(title: str) -> str:
    """
    MVP: recommendation template.
    Later: replace with LLM generation for richer suggestions.
    """
    t = (title or "").lower()
    if "token" in t or "auth" in t or "login" in t:
        return "Investigate authentication flow, reproduce issue, add retries/backoff, and improve error handling + logging."
    if "crash" in t or "error" in t:
        return "Reproduce on latest environment, identify root cause, ship a hotfix, and add regression tests."
    if "slow" in t or "performance" in t:
        return "Profile bottlenecks, optimize slow endpoints, and add performance monitoring + alert thresholds."
    return "Validate with users, scope a fix/feature, estimate effort, and schedule into the next sprint planning."


# Impact Score on Insights for PMs 

def score_insight_attributes(theme_title: str, evidence_texts: list[str]) -> dict:
    text = " ".join([t.lower() for t in evidence_texts if t])

    impact_score = 3
    effort_estimate = "medium"
    customer_segment = "general"
    revenue_risk = "medium"

    if any(term in text for term in [
        "blocker", "cannot", "can't", "failed", "fails", "broken", "outage", "crash", "crashes"
    ]):
        impact_score = 5
    elif any(term in text for term in [
        "delay", "slower", "friction", "manual", "confusing", "unclear"
    ]):
        impact_score = 4
    elif any(term in text for term in [
        "nice to have", "wishlist", "would be helpful"
    ]):
        impact_score = 2

    if any(term in text for term in [
        "integration", "api", "auth", "token", "billing", "pricing", "rate limits"
    ]):
        effort_estimate = "high"
    elif any(term in text for term in [
        "dashboard", "date ranges", "export", "report", "filter"
    ]):
        effort_estimate = "medium"
    else:
        effort_estimate = "low"

    if any(term in text for term in [
        "api", "token", "oauth", "webhook", "integration", "zapier", "hubspot"
    ]):
        customer_segment = "developer"
    elif any(term in text for term in [
        "leadership", "contract", "billing", "pricing", "rollout", "admin"
    ]):
        customer_segment = "enterprise"
    elif any(term in text for term in [
        "small business", "startup", "simple", "affordable"
    ]):
        customer_segment = "smb"

    if any(term in text for term in [
        "competitor", "pricing", "cancel", "churn", "rollout", "blocked", "renewal"
    ]):
        revenue_risk = "high"
    elif any(term in text for term in [
        "delay", "manual", "confusing", "friction"
    ]):
        revenue_risk = "medium"
    else:
        revenue_risk = "low"

    return {
        "impact_score": max(1, min(5, impact_score)),
        "effort_estimate": effort_estimate,
        "customer_segment": customer_segment,
        "revenue_risk": revenue_risk,
    }



# ---------------------------
# 1) Heuristic cleanup helpers
# ---------------------------
INSIGHT_STOPWORDS = {
    "issue", "issues", "problem", "problems", "bug", "bugs",
    "user", "users", "customer", "customers", "team", "teams",
    "report", "reports", "reporting", "raised", "saying",
    "repeatedly", "often", "sometimes", "always", "mention", "mentions",
    "related", "regarding", "about", "around", "thing", "things",
    "not", "sure", "radar", "heads", "up", "weve", "we've",
    "its", "it's", "doesnt", "doesn't", "cant", "can't", "team", "raised", "problematic"
}

STOPWORDS_EXTRA = {
    "have", "has", "had",
    "make", "makes", "made",
    "issue", "issues",
    "team", "user", "users",
    "copy", "paste", "need",
    "right", "now", "note",
    "quick", "really",
    "something", "thing",
}
STOPWORDS = STOPWORDS.union(STOPWORDS_EXTRA)

THEME_STOPWORDS = set(STOPWORDS) | set(INSIGHT_STOPWORDS) | {
    # super common “non-theme” words that are not in your existing sets
    "issue", "issues", "problem", "problems",
    "team", "raised", "raise", "report", "reports", "reporting",
    "quick", "note", "right", "now", "fyi",
    "need", "needs", "want", "wants", "would", "could", "should",
    "make", "makes", "making", "work", "works", "working",
    "time", "today", "week", "daily", "every", "almost",
    "use", "using", "used", "user", "users",
}

STOP_PHRASES = {
    "quick note", "right now", "fyi", "not sure", "we see", "weve been", "we have",
    "our team", "team raised", "raised an issue", "this is starting", "almost every day",
}

def clean_theme_label(title: str) -> str:
    if not title:
        return "General"

    t = title.strip().lower()
    t = re.sub(r"[^a-z0-9\s\-]", "", t)
    t = re.sub(r"\s+", " ", t).strip()

    tokens = [w for w in t.split() if w and w not in INSIGHT_STOPWORDS and len(w) > 2]
    if not tokens:
        return "General"

    phrase = " ".join(tokens[:5])
    return phrase[:1].upper() + phrase[1:]


def has_llm_key() -> bool:
    return bool(os.getenv("OPENAI_API_KEY"))


def generate_insight_heuristic(theme_title: str) -> Dict[str, Any]:
    label = clean_theme_label(theme_title)
    return {
        "insight": f"Users are repeatedly reporting friction related to: {label}.",
        "recommendation": "Validate with users, define scope, estimate effort, and prioritize into the next sprint.",
        "priority": 3,
        "meta": {"generator": "heuristic_v2", "label": label},
    }


def generate_insight_llm(theme_title: str, evidence_quotes: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    evidence_quotes: [{ "source": "Zendesk", "text": "..." }, ...]
    """
    # make sure your venv has openai installed
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    label = clean_theme_label(theme_title)
    evidence_text = "\n".join(
        [f"- ({q.get('source','Unknown')}) {q.get('text','')}" for q in evidence_quotes[:6] if q.get("text")]
    )

    prompt = f"""
You are a product analyst. Write ONE concise insight and ONE actionable recommendation.

Theme label: {label}

Evidence:
{evidence_text}

Rules:
- Make the insight specific to the evidence.
- Avoid generic filler like "there are issues" unless evidence is specific.
- Recommendation should be concrete and next-step oriented.
- Return JSON ONLY with keys: insight, recommendation, priority
Priority: 1=highest, 5=lowest.
"""

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )

    # raw = resp.choices[0].message.content or "{}"
    # data = json.loads(raw)

    raw = (resp.choices[0].message.content or "").strip()

# strip ```json ... ``` if present
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1].strip()
    if raw.lower().startswith("json"):
        raw = raw[4:].strip()

    try:
        data = json.loads(raw)
    except Exception:
        data = {}


    # clamp priority safely to 1..5
    try:
        pr = int(data.get("priority", 3))
    except Exception:
        pr = 3
    pr = max(1, min(5, pr))

    return {
        "insight": (data.get("insight") or "").strip() or f"Users report recurring friction related to {label}.",
        "recommendation": (data.get("recommendation") or "").strip() or "Validate scope and prioritize a targeted fix.",
        "priority": pr,
        "meta": {"generator": "llm_v1", "label": label, "model": "gpt-4o-mini"},
    }


# ---------------------------
# 2) Updated POST endpoint for insights
# ---------------------------
@app.post("/runs/{run_id}/insights")
def run_insights(run_id: str):
    """
    Insights step:
      - loads run
      - loads preprocess artifact items
      - loads themes for this run
      - generates insights + recommendations (heuristic or LLM)
      - UPSERTS into run_insights (dedupe by run_id + theme_id)
      - updates run_steps('insights') status
    """

    # 1) Load run
    run_res = (
        supabase.table("analysis_runs")
        .select("id, workspace_id, input_snapshot")
        .eq("id", run_id)
        .single()
        .execute()
    )
    run = run_res.data
    if not run:
        raise HTTPException(status_code=404, detail="run_not_found")

    workspace_id = run["workspace_id"]

    # 2) Mark step running
    try:
        supabase.table("run_steps") \
            .update({"status": "running"}) \
            .eq("run_id", run_id) \
            .eq("step_name", "insights") \
            .execute()
    except Exception:
        pass

    try:
        # 3) Load preprocess items (required)
        preprocess_payload, items = load_preprocess_items(run_id)

        # feedback_id -> row
        by_id: Dict[str, Dict[str, Any]] = {}
        for it in items:
            if it.get("id"):
                by_id[str(it["id"])] = it

        # 3b) Load sources so we can show source names next to evidence quotes
        source_ids = sorted({str(it.get("source_id")) for it in items if it.get("source_id")})
        source_name_by_id: Dict[str, str] = {}

        if source_ids:
            src_res = (
                supabase.table("sources")
                .select("id, name")
                .in_("id", source_ids)
                .execute()
            )
            for s in (src_res.data or []):
                source_name_by_id[str(s["id"])] = s.get("name") or "Unknown"

        # 4) Load themes
        themes_res = (
            supabase.table("themes")
            .select("id, title, description, evidence_feedback_ids, created_at")
            .eq("run_id", run_id)
            .order("created_at", desc=True)
            .execute()
        )
        themes = themes_res.data or []
        if len(themes) == 0:
            raise HTTPException(status_code=400, detail="no_themes_found_run_themes_first")

        upserted = 0

        for t in themes:
            theme_id = t.get("id")
            title = t.get("title") or "General"

            evidence_ids = t.get("evidence_feedback_ids") or []
            if not isinstance(evidence_ids, list):
                evidence_ids = []

            evidence_rows = [by_id.get(str(fid)) for fid in evidence_ids if by_id.get(str(fid))]
            evidence_texts = [(r.get("raw_text") or "") for r in evidence_rows if r]

            # build evidence quotes with source names (for LLM prompt + UI meta)
            evidence_quotes: List[Dict[str, str]] = []
            for r in evidence_rows[:6]:
                sid = str(r.get("source_id")) if r and r.get("source_id") else ""
                evidence_quotes.append({
                    "source": source_name_by_id.get(sid, "Unknown"),
                    "text": (r.get("raw_text") or "").strip(),
                })

            # Base priority from evidence text
            priority = _priority_from_evidence_text(evidence_texts)
            try:
                priority = int(priority)
            except Exception:
                priority = 3
            priority = max(1, min(5, priority))

            # Generate insight text
            try:
                if has_llm_key():
                    gen = generate_insight_llm(title, evidence_quotes)
                else:
                    gen = generate_insight_heuristic(title)
            except Exception as e:
                gen = generate_insight_heuristic(title)
                gen["meta"] = {
                    **(gen.get("meta") or {}),
                    "llm_error": str(e),
                    "generator": "heuristic_fallback",
                }

            insight = gen["insight"]
            recommendation = gen["recommendation"]
            priority = gen.get("priority", priority)
            meta = gen.get("meta", {}) or {}

            # NEW: roadmap / sales scoring fields
            scores = score_insight_attributes(title, evidence_texts)

            # enrich meta with pipeline context
            meta.update({
                "preprocess_version": preprocess_payload.get("version", "v1"),
                "theme_title_raw": title,
                "theme_label_clean": clean_theme_label(title),
                "evidence_quotes": evidence_quotes,
            })

            row = {
                "run_id": run_id,
                "workspace_id": workspace_id,
                "theme_id": theme_id,
                "insight": insight,
                "recommendation": recommendation,
                "priority": priority,
                "impact_score": scores["impact_score"],
                "effort_estimate": scores["effort_estimate"],
                "customer_segment": scores["customer_segment"],
                "revenue_risk": scores["revenue_risk"],
                "evidence_feedback_ids": evidence_ids,
                "meta": meta,
            }

            # 5) UPSERT (dedupe): requires UNIQUE(run_id, theme_id)
            supabase.table("run_insights").upsert(
                row,
                on_conflict="run_id,theme_id"
            ).execute()

            upserted += 1

        # 6) Mark step succeeded
        try:
            supabase.table("run_steps") \
                .update({"status": "succeeded"}) \
                .eq("run_id", run_id) \
                .eq("step_name", "insights") \
                .execute()
        except Exception:
            pass

        return {"status": "ok", "insights_upserted": upserted}

    except Exception:
        try:
            supabase.table("run_steps") \
                .update({"status": "failed"}) \
                .eq("run_id", run_id) \
                .eq("step_name", "insights") \
                .execute()
        except Exception:
            pass
        raise

@app.get("/runs/{run_id}/insights")
def list_insights(run_id: str):
    """
    Fetch insights for a run (for Next.js UI).
    """
    res = (
        supabase.table("run_insights")
        .select("id, theme_id, insight, recommendation, priority, impact_score, effort_estimate, customer_segment, revenue_risk, evidence_feedback_ids, meta, created_at")
        .eq("run_id", run_id)
        .order("priority", desc=True)
        .order("created_at", desc=True)
        .execute()
    )
    return {"items": res.data or []}


# new start of the next end point of PREPROCESS 
@app.post("/runs/{run_id}/preprocess")
def run_preprocess(run_id: str):
    """
    Preprocess step:
      - loads run
      - pulls feedback based on input_snapshot.filters + limit
      - computes simple signals + basic duplicate grouping
      - stores results in run_artifacts(kind='preprocess', version='v1')
      - updates run_steps('preprocess') status
    """

    # --- 1) Load run
    run_res = (
        supabase.table("analysis_runs")
        .select("id, workspace_id, status, input_snapshot")
        .eq("id", run_id)
        .single()
        .execute()
    )
    run = run_res.data
    if not run:
        return {"error": "run_not_found", "run_id": run_id}

    workspace_id = run["workspace_id"]
    input_snapshot = run.get("input_snapshot") or {}
    limit = int(input_snapshot.get("limit") or 200)
    filters = input_snapshot.get("filters") or {}

    # --- 2) Mark step as running (best effort)
    try:
        supabase.table("run_steps") \
            .update({"status": "running"}) \
            .eq("run_id", run_id) \
            .eq("step_name", "preprocess") \
            .execute()
    except Exception:
        pass

    try:
        # --- 3) Build feedback query
        q = (
            supabase.table("feedback_items")
            .select("id, raw_text, intent, sentiment, source_id, occurred_at")
            .eq("workspace_id", workspace_id)
        )

        # Apply filters (intent/sentiment are direct columns)
        if filters.get("intent"):
            q = q.eq("intent", filters["intent"])
        if filters.get("sentiment"):
            q = q.eq("sentiment", filters["sentiment"])

        # Source filter: UI gives a "source" string (like "app_store" / "zendesk" / "discord")
        # Your feedback_items.source_id is UUID, so we must resolve the string -> sources.id
        if filters.get("source"):
            source_id = resolve_source_id(
                supabase,
                workspace_id,
                filters["source"],
            )
            if not source_id:
                raise Exception(f"Source '{filters['source']}' not found in sources table")
            q = q.eq("source_id", source_id)

        fb_res = q.order("occurred_at", desc=True).limit(limit).execute()
        rows = fb_res.data or []

        items = []
        for r in rows:
            items.append({
            "id": r.get("id"),
            "raw_text": r.get("raw_text"),
            "intent": r.get("intent"),
            "sentiment": r.get("sentiment"),
            "source_id": r.get("source_id"),
            "occurred_at": r.get("occurred_at"),
         })

        # --- 4) Compute signals
        intent_counts = Counter()
        sentiment_counts = Counter()
        source_counts = Counter()
        keyword_counts = Counter()

        dup_groups: Dict[str, List[str]] = defaultdict(list)

        for r in rows:
            intent_counts[r.get("intent") or "unknown"] += 1
            sentiment_counts[r.get("sentiment") or "unknown"] += 1
            source_counts[str(r.get("source_id") or "unknown")] += 1

            raw = r.get("raw_text") or ""
            norm = normalize_text(raw)
            if norm:
                dup_groups[sha1_hex(norm)].append(r["id"])

            words = norm.split()

            for i in range(len(words)):
                w = words[i]

                if len(w) >= 4 and w not in STOPWORDS:
                    keyword_counts[w] += 1

                # bigrams
                if i < len(words) - 1:
                    phrase = f"{words[i]} {words[i+1]}"
                    if all(len(x) >= 4 for x in phrase.split()):
                        keyword_counts[phrase] += 2
## Should be indented by 5 indents
        duplicate_groups = [
            {"hash": h, "count": len(ids), "feedback_ids": ids[:25]}
            for h, ids in dup_groups.items()
            if len(ids) >= 2
        ]
        duplicate_groups.sort(key=lambda x: x["count"], reverse=True)
        duplicate_groups = duplicate_groups[:20]

        payload = {
            "run_id": run_id,
            "workspace_id": workspace_id,
            "filters": filters,
            "limit": limit,
            "total_items": len(rows),
            "items": [
                    {
                    "id": r["id"],
                    "raw_text": r.get("raw_text"),
                    "intent": r.get("intent"),
                    "sentiment": r.get("sentiment"),
                    "source_id": r.get("source_id"),
                    "occurred_at": r.get("occurred_at"),
                    }
                for r in rows
                    ],
            "counts": {
                "intent": counter_top(intent_counts, 20),
                "sentiment": counter_top(sentiment_counts, 20),
                "source_id": counter_top(source_counts, 20),
            },
            "top_keywords": counter_top(keyword_counts, 25),
            "duplicate_groups": duplicate_groups,
        }

        # --- 5) Upsert into run_artifacts
        artifact_row = {
            "run_id": run_id,
            "workspace_id": workspace_id,
            "kind": "preprocess",
            "version": "v1",
            "payload": payload,
        }

        upsert_res = (
            supabase.table("run_artifacts")
            .upsert(artifact_row, on_conflict="run_id,kind,version")
            .execute()
        )

        # --- 6) Mark step succeeded
        try:
            supabase.table("run_steps") \
                .update({"status": "succeeded"}) \
                .eq("run_id", run_id) \
                .eq("step_name", "preprocess") \
                .execute()
        except Exception:
            pass

        return {
            "status": "ok",
            "artifact": (upsert_res.data[0] if upsert_res.data else artifact_row),
        }

    except Exception:
        try:
            supabase.table("run_steps") \
                .update({"status": "failed"}) \
                .eq("run_id", run_id) \
                .eq("step_name", "preprocess") \
                .execute()
        except Exception:
            pass
        raise

# Execute the Single Run Analysis Button on the UI

@app.post("/runs/{run_id}/execute")
def run_execute(run_id: str, background_tasks: BackgroundTasks):
    """
    One-click pipeline:
      preprocess -> themes -> insights
    Runs in the background so the request returns immediately.
    """

    # 1) Ensure run exists
    run_res = (
        supabase.table("analysis_runs")
        .select("id, workspace_id, status")
        .eq("id", run_id)
        .single()
        .execute()
    )
    run = run_res.data
    if not run:
        raise HTTPException(status_code=404, detail="run_not_found")

    # 2) Mark run as running (best effort)
    try:
        supabase.table("analysis_runs").update({"status": "running"}).eq("id", run_id).execute()
    except Exception:
        pass

    # 3) Ensure run_steps rows exist (best effort)
    try:
        steps = ["preprocess", "themes", "insights"]
        rows = [{"run_id": run_id, "step_name": s, "status": "queued"} for s in steps]
        # assumes you have a unique constraint on (run_id, step_name)
        supabase.table("run_steps").upsert(rows, on_conflict="run_id,step_name").execute()
    except Exception:
        pass

    # 4) Background pipeline task
    background_tasks.add_task(_execute_pipeline_background, run_id)

    return {"status": "queued", "run_id": run_id, "steps": ["preprocess", "themes", "insights"]}


def _execute_pipeline_background(run_id: str):
    """
    Runs the pipeline sequentially.
    If anything fails, mark run failed.
    """

    try:
        # preprocess
        try:
            run_preprocess(run_id)
        except Exception:
            # step function should mark failed, but just in case
            try:
                supabase.table("run_steps").update({"status": "failed"}).eq("run_id", run_id).eq("step_name", "preprocess").execute()
            except Exception:
                pass
            raise

        # themes (now should consume preprocess artifact)
        try:
            run_themes(run_id)
        except Exception:
            try:
                supabase.table("run_steps").update({"status": "failed"}).eq("run_id", run_id).eq("step_name", "themes").execute()
            except Exception:
                pass
            raise

        # insights
        try:
            run_insights(run_id)
        except Exception:
            try:
                supabase.table("run_steps").update({"status": "failed"}).eq("run_id", run_id).eq("step_name", "insights").execute()
            except Exception:
                pass
            raise

        # If all succeeded
        try:
            supabase.table("analysis_runs").update({"status": "succeeded"}).eq("id", run_id).execute()
        except Exception:
            pass

    except Exception:
        # Mark run failed
        try:
            supabase.table("analysis_runs").update({"status": "failed"}).eq("id", run_id).execute()
        except Exception:
            pass

        # Optional: store the traceback somewhere (console for now)
        traceback.print_exc()

# FASTAPI Status endpoint for Run Status Poller that autorefreshes - The Run Detail page polls the API every ~2 seconds only while the run is running/queued
# When it becomes succeeded/failed, polling stops and the page refreshes to show final data

@app.get("/runs/{run_id}/status")
def get_run_status(run_id: str):
    run_res = (
        supabase.table("analysis_runs")
        .select("id, status, created_at")
        .eq("id", run_id)
        .single()
        .execute()
    )
    run = run_res.data
    if not run:
        raise HTTPException(status_code=404, detail="run_not_found")

    # Also return step statuses so UI can show progress
    steps_res = (
        supabase.table("run_steps")
        .select("step_name, status, updated_at")
        .eq("run_id", run_id)
        .execute()
    )

    return {
        "run_id": run_id,
        "status": run.get("status"),
        "steps": steps_res.data or [],
    }

@app.get("/runs/{run_id}/artifacts")
def list_run_artifacts(
    run_id: str,
    kind: Optional[str] = Query(default=None),
    version: Optional[str] = Query(default=None),
):
    q = (
        supabase.table("run_artifacts")
        .select("id, run_id, workspace_id, kind, version, payload, created_at, updated_at")
        .eq("run_id", run_id)
        .order("created_at", desc=True)
    )

    if kind:
        q = q.eq("kind", kind)

    if version:
        q = q.eq("version", version)

    res = q.execute()

    # PostgREST returns errors here
    if getattr(res, "error", None):
        raise HTTPException(status_code=500, detail=res.error.message)

    return {"items": res.data or []}
