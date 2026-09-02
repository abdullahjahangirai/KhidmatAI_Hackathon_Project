"""LangGraph-based agentic workflow for KhidmatAI chatbot.

Flow:
  1. Local-first: Query SQLite programs table for matching welfare schemes.
  2. Web enrichment: Optionally call Tavily search for fresh evidence.
  3. Model fallback chain:
       Primary  → Google Gemini (GEMINI_API_KEY / GEMINI_MODEL)
       Secondary → DashScope Qwen (qwen3.7-plus → qwen3.6-plus → qwen3.6-flash)
       Tertiary → Groq (last resort)
  4. Deterministic mode (if every AI provider fails).

The user NEVER receives an empty or error response.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, TypedDict

import requests
from dotenv import load_dotenv
from langgraph.graph import END, StateGraph

load_dotenv()

# ---------------------------------------------------------------------------
# API configuration
# ---------------------------------------------------------------------------
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash").strip()

DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "").strip()
DASHSCOPE_BASE_URL = os.getenv(
    "DASHSCOPE_BASE_URL",
    "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
).strip()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b").strip()

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "").strip()

# Model fallback chain – DashScope / Qwen
MODEL_PRIMARY = "qwen3.7-plus"
MODEL_SECONDARY = "qwen3.6-plus"
MODEL_TERTIARY = "qwen3.6-flash"

# Circuit breakers: skip a provider after an auth failure (avoids retry storms)
_gemini_auth_failed = False
_dashscope_auth_failed = False


# ---------------------------------------------------------------------------
# Low-level API callers
# ---------------------------------------------------------------------------

def _call_gemini(system_prompt: str, user_prompt: str) -> str | None:
    """Call the primary Google Gemini model via the REST API."""
    global _gemini_auth_failed
    if _gemini_auth_failed:
        return None
    if not GEMINI_API_KEY or GEMINI_API_KEY.startswith(("your_", "yahan_")):
        return None
    try:
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{GEMINI_MODEL}:generateContent"
        )
        payload = {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 3072,
                "responseMimeType": "application/json",
            },
        }
        res = requests.post(
            url, params={"key": GEMINI_API_KEY}, json=payload, timeout=30
        )
        if res.status_code in (401, 403, 404):
            # dead key or retired model — skip straight to the next provider
            return None
        res.raise_for_status()
        data = res.json()
        candidates = data.get("candidates") or []
        if not candidates:
            return None
        parts = (candidates[0].get("content") or {}).get("parts") or []
        text = "".join(p.get("text", "") for p in parts).strip()
        return text or None
    except Exception:
        return None

def _call_dashscope_model(model: str, system_prompt: str, user_prompt: str) -> str | None:
    """Call a single DashScope / Qwen model via the OpenAI-compatible REST API."""
    global _dashscope_auth_failed
    if _dashscope_auth_failed:
        return None
    if not DASHSCOPE_API_KEY or DASHSCOPE_API_KEY.startswith(("your_", "yahan_")):
        return None
    try:
        url = f"{DASHSCOPE_BASE_URL}/chat/completions"
        headers = {
            "Authorization": f"Bearer {DASHSCOPE_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.1,
            "max_tokens": 2000,
            "response_format": {"type": "json_object"},
        }
        # Qwen reasoning models can take 25s+ on large prompts — keep the
        # timeout generous or every real call silently times out.
        res = requests.post(url, json=payload, headers=headers, timeout=45)
        # Fast-fail on auth errors — skip remaining DashScope models
        if res.status_code in (401, 403):
            _dashscope_auth_failed = True
            return None
        res.raise_for_status()
        data = res.json()
        content = data["choices"][0]["message"]["content"]
        # Strip reasoning blocks some Qwen models emit around the JSON
        # (tag built from parts so tooling cannot mangle the literal).
        _end_think = "</" + "think" + ">"
        if _end_think in content:
            content = content.split(_end_think)[-1].strip()
        return content
    except Exception:
        return None


def _call_groq(system_prompt: str, user_prompt: str) -> str | None:
    """Call Groq API (OpenAI-compatible) as final LLM fallback."""
    if not GROQ_API_KEY or GROQ_API_KEY.startswith(("your_", "yahan_")):
        return None
    try:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": GROQ_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.1,
            "max_tokens": 2000,
            "response_format": {"type": "json_object"},
        }
        res = requests.post(url, json=payload, headers=headers, timeout=30)
        res.raise_for_status()
        data = res.json()
        return data["choices"][0]["message"]["content"]
    except Exception:
        return None


def call_llm_with_fallback(
    system_prompt: str, user_prompt: str
) -> tuple[str | None, str]:
    """Multi-model fallback chain.

    Order:
      1. Google Gemini  (primary)
      2. DashScope qwen3.7-plus
      3. DashScope qwen3.6-plus
      4. DashScope qwen3.6-flash
      5. Groq (last resort)
    """
    # 1 — Gemini (primary)
    result = _call_gemini(system_prompt, user_prompt)
    if result:
        return result, f"Gemini ({GEMINI_MODEL}) [Primary]"

    # 2 — DashScope primary
    result = _call_dashscope_model(MODEL_PRIMARY, system_prompt, user_prompt)
    if result:
        return result, f"DashScope ({MODEL_PRIMARY}) [Secondary]"

    # 3 — DashScope secondary
    result = _call_dashscope_model(MODEL_SECONDARY, system_prompt, user_prompt)
    if result:
        return result, f"DashScope ({MODEL_SECONDARY}) [Tertiary]"

    # 4 — DashScope tertiary
    result = _call_dashscope_model(MODEL_TERTIARY, system_prompt, user_prompt)
    if result:
        return result, f"DashScope ({MODEL_TERTIARY}) [Quaternary]"

    # 5 — Groq fallback
    result = _call_groq(system_prompt, user_prompt)
    if result:
        return result, f"Groq ({GROQ_MODEL}) [Fallback]"

    return None, "Deterministic Verified Mode"


# ---------------------------------------------------------------------------
# Tavily Web Search (dynamic key loading)
# ---------------------------------------------------------------------------

def _get_tavily_key() -> str:
    """Dynamically fetch Tavily API key from environment (allows runtime updates)."""
    return os.getenv("TAVILY_API_KEY", "").strip()


def web_search(query: str) -> list[dict[str, str]]:
    """Run a Tavily advanced search and return structured results.
    
    Dynamically loads the API key from environment on each call.
    """
    api_key = _get_tavily_key()
    if not api_key or api_key.startswith(("your_", "yahan_", "paste_")):
        return []
    try:
        res = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": api_key,
                "query": f"{query} Pakistan official welfare scheme eligibility application",
                "search_depth": "advanced",
                "max_results": 5,
                "include_answer": True,
                "include_raw_content": False,
            },
            # Tavily advanced searches can take 20s+ (measured 20.2s live) —
            # keep the timeout generous or every search silently times out
            # and the web-evidence path returns nothing.
            timeout=40,
        )
        res.raise_for_status()
        data = res.json()
        results = []
        for item in data.get("results", []):
            results.append({
                "title": item.get("title", "Official source"),
                "url": item.get("url", ""),
                "content": (item.get("content") or "")[:2000],
            })
        return results
    except Exception:
        return []


# ---------------------------------------------------------------------------
# LangGraph state definition
# ---------------------------------------------------------------------------

class AgentState(TypedDict, total=False):
    query: str
    language: str
    profile: dict[str, Any]
    matches: list[dict[str, Any]]
    web_results: list[dict[str, str]]
    needs_web_search: bool
    raw_answer: str | None
    model_used: str
    final_answer: dict[str, Any]


# ---------------------------------------------------------------------------
# Graph nodes
# ---------------------------------------------------------------------------

def retrieve_from_db(state: AgentState) -> dict:
    """Step 1: Query the local SQLite database for matching welfare schemes.
    
    Sets needs_web_search=True when:
    - No strong matches found (score <= 5)
    - Low confidence results (fewer than 2 matches)
    """
    from . import database as db

    query = state.get("query", "")
    matches = db.get_programs_filtered(q=query)

    # Score and rank
    profile = state.get("profile", {})
    scored = sorted(
        ((_score_program(p, query, profile), p) for p in matches),
        key=lambda x: x[0],
        reverse=True,
    )
    # Only keep high-confidence matches (score > 5)
    ranked = [p for score, p in scored if score > 5][:8]

    # Flag web search if low confidence or empty
    needs_web = len(ranked) < 2  # Force web search if fewer than 2 strong matches
    
    # If no strong matches, include some generic programs but still flag web search
    if not ranked:
        all_progs = db.get_all_programs()
        ranked = all_progs[:3] if all_progs else []

    return {"matches": ranked, "needs_web_search": needs_web}


def search_web_node(state: AgentState) -> dict:
    """Step 2: Enrich with Tavily web search.
    
    ALWAYS executes when needs_web_search=True (low DB confidence).
    Uses the original query for better relevance.
    """
    needs_web = state.get("needs_web_search", False)
    query = state.get("query", "")
    
    # If DB had strong matches and we don't need web, skip search
    if not needs_web:
        return {"web_results": []}
    
    # Force web search execution for low-confidence queries
    web_query = f"{query} Pakistan welfare scheme eligibility application process"
    results = web_search(web_query)

    # Retry with broader query if first attempt returned nothing
    if not results:
        results = web_search(f"{query} Pakistan social support program BISP Ehsaas 2024 2025")
    
    # Final retry with simpler query
    if not results:
        results = web_search(query)

    return {"web_results": results}


def synthesize_answer(state: AgentState) -> dict:
    """Step 3: Synthesise the final answer using the model fallback chain.

    If local DB had no strong matches, prioritises web search results
    and clearly marks responses as web-sourced rather than hallucinating
    from irrelevant database records."""
    from . import main as main_mod  # access shared helpers

    query = state.get("query", "")
    language = state.get("language", "english")
    profile = state.get("profile", {})
    matches = state.get("matches", [])
    web_results = state.get("web_results", [])
    needs_web = state.get("needs_web_search", False)

    # Build record summaries for the LLM
    records = []
    for p in matches:
        records.append({
            "title": p.get("title"),
            "category": p.get("category"),
            "type": p.get("type"),
            "description": p.get("description"),
            "support": p.get("support"),
            "eligibility": p.get("eligibility"),
            "documents": p.get("documents"),
            "application": p.get("application"),
            "source_name": p.get("source_name"),
            "source_url": p.get("source_url"),
        })

    # Build system prompt that adapts based on data availability
    # All prompts emphasize SHORT, PROFESSIONAL, BULLET-POINT responses
    if needs_web and web_results:
        # DB had no matches — prioritise web evidence
        system_prompt = (
            "You are KhidmatAI, Pakistan's welfare assistant. Respond SHORT and PROFESSIONAL.\n"
            "IMPORTANT: Local database had no strong matches. Use WEB SEARCH EVIDENCE as primary source.\n"
            "Rules:\n"
            "1) summary = MAX 3 bullet points (• prefixed), no paragraphs, no filler\n"
            "2) Each bullet: one key fact only (eligibility, amount, or deadline)\n"
            "3) official_source = the BEST URL from web evidence\n"
            "4) NEVER invent data — only use web evidence provided\n"
            "5) If insufficient, say 'Check official website for details'\n"
            "Output strict JSON:\n"
            '{"summary": "• point1\\n• point2\\n• point3", '
            '"programs": [{"title": "", "match_level": "", "why_match": "", "official_source": ""}], '
            '"official_source": "best_url_here", '
            '"next_steps": ["step1", "step2"]}\n'
            f"Language: {language}"
        )
    elif not records and not web_results:
        # No data at all — direct to official sources
        system_prompt = (
            "You are KhidmatAI. Respond SHORT and PROFESSIONAL.\n"
            "No database or web results found. Direct user to official sources:\n"
            "• BISP portal: bisp.gov.pk\n"
            "• Helpline: 8171\n"
            "• Keep CNIC ready\n"
            "Output strict JSON:\n"
            '{"summary": "• No specific records found\\n• Visit bisp.gov.pk or call 8171\\n• Keep CNIC ready", '
            '"programs": [], "official_source": "https://bisp.gov.pk", '
            '"next_steps": ["Visit bisp.gov.pk", "Call 8171 helpline"]}\n'
            f"Language: {language}"
        )
    else:
        # Normal mode: DB has good matches
        system_prompt = (
            "You are KhidmatAI. Respond SHORT and PROFESSIONAL with bullet points.\n"
            "Rules:\n"
            "1) summary = MAX 3 bullet points (• prefixed), concise facts only\n"
            "2) why_match = MAX 8 words\n"
            "3) official_source = source_url from the record\n"
            "4) NEVER invent financial amounts, eligibility, or deadlines\n"
            "Output strict JSON:\n"
            '{"summary": "• point1\\n• point2\\n• point3", '
            '"programs": [{"title": "", "match_level": "", "why_match": "", "official_source": ""}], '
            '"official_source": "primary_url", '
            '"next_steps": ["step1", "step2"]}\n'
            f"Language: {language}"
        )

    user_prompt = (
        f"VERIFIED RECORDS:\n{json.dumps(records, ensure_ascii=False, indent=2)}\n\n"
    )
    if web_results:
        user_prompt += (
            f"WEB SEARCH EVIDENCE:\n"
            f"{json.dumps(web_results[:5], ensure_ascii=False, indent=2)}\n\n"
        )
    user_prompt += f"USER PROFILE: {json.dumps(profile, ensure_ascii=False)}\n"
    user_prompt += f"REQUESTED LANGUAGE: {language}\n"
    user_prompt += f"USER QUERY: {query}"

    raw, model_used = call_llm_with_fallback(system_prompt, user_prompt)
    parsed = main_mod.parse_json(raw)
    answer = main_mod.build_safe_answer(parsed, matches, language, profile)

    # If we relied on web search and have no program cards from DB,
    # build cards from web results instead of showing irrelevant DB records
    if needs_web and web_results and not answer.get("programs"):
        answer["programs"] = []
        for wr in web_results[:3]:
            answer["programs"].append({
                "title": wr.get("title", "Web Source"),
                "match_level": "Web verified",
                "why_match": (wr.get("content") or "")[:180],
                "support": [],
                "eligibility": [],
                "documents": [],
                "application": "Check official source for details.",
                "source_name": wr.get("title", "Web Source"),
                "source_url": wr.get("url", ""),
                "verified_at": "",
            })
        if not answer.get("summary"):
            answer["summary"] = f"Found {len(web_results)} web sources related to your query. Please verify details on official websites."

    return {
        "raw_answer": raw,
        "model_used": model_used,
        "final_answer": answer,
    }


# ---------------------------------------------------------------------------
# Program scoring (lightweight, DB-friendly)
# ---------------------------------------------------------------------------

def _score_program(p: dict[str, Any], query: str, profile: dict[str, Any]) -> int:
    import re as _re

    def _toks(v: str) -> set[str]:
        return set(_re.findall(r"[a-z0-9]+", str(v).lower()))

    q_toks = _toks(query)
    p_text = " ".join([
        str(p.get("title", "")), str(p.get("category", "")),
        str(p.get("description", "")),
        " ".join(str(x) for x in p.get("keywords", [])),
        " ".join(str(x) for x in p.get("eligibility", [])),
        " ".join(str(x) for x in p.get("locations", [])),
    ])
    p_toks = _toks(p_text)
    score = len(q_toks & p_toks) * 2

    # Category boost
    cats = {
        "Education": {"education", "scholarship", "student", "university", "fee"},
        "Healthcare": {"health", "medical", "hospital", "treatment", "doctor"},
        "Financial Aid": {"financial", "money", "cash", "zakat", "bisp", "kafalat"},
        "Food Support": {"food", "ration", "meal", "rashan"},
        "Employment": {"job", "employment", "skills", "training", "rozgar"},
    }
    p_cat = str(p.get("category", "")).lower()
    for _name, words in cats.items():
        if q_toks & words and any(w in p_cat for w in words):
            score += 15

    # Location boost
    cities = {str(c).lower() for c in profile.get("mentioned_cities", [])}
    locs = {str(x).lower() for x in p.get("locations", [])}
    if "all pakistan" in locs:
        score += 3
    if cities & locs:
        score += 10

    return score


# ---------------------------------------------------------------------------
# Deterministic answer builder
# ---------------------------------------------------------------------------

def _deterministic_answer(
    matches: list[dict[str, Any]], language: str
) -> dict[str, Any]:
    """Build a deterministic fallback answer with bullet-point summary."""
    count = len(matches)
    # Get the primary source URL from first match (if available)
    primary_source = matches[0].get("source_url", "") if matches else ""
    
    if language == "urdu":
        summary = f"• آپ کے لیے {count} تصدیق شدہ سرکاری فلاحی پروگرام دستیاب ہیں\n• تفصیلات کے لیے سرکاری ویب سائٹ دیکھیں\n• شناختی کارڈ اور ضروری دستاویزات تیار رکھیں"
        questions = [
            "آپ کے گھرانے کی ماہانہ آمدنی کتنی ہے؟",
            "آپ کس شہر میں مقیم ہیں؟",
            "کیا آپ کو تعلیم، علاج یا راشن کی مدد درکار ہے؟",
        ]
        next_steps = [
            "موجودہ درخواست کے لیے سرکاری ویب سائٹ سے رجوع کریں۔",
            "شناختی کارڈ اور ضروری دستاویزات تیار رکھیں۔",
        ]
    elif language == "roman":
        summary = f"• Aap ke liye {count} verified official options mile hain\n• Tafseelat ke liye official website check karein\n• CNIC aur zaroori documents tayar rakhein"
        questions = [
            "Ghar ki monthly income kitni hai?",
            "Aap kis shehar mein rehte hain?",
            "Aapko taleem, ilaj ya rashan mein se kis ki zaroorat hai?",
        ]
        next_steps = [
            "Official portal ya qareebi center check karein.",
            "CNIC aur zaroori documents tayar rakhein.",
        ]
    else:
        summary = f"• Found {count} verified official support options\n• Check official website for eligibility details\n• Keep CNIC and relevant documents ready"
        questions = [
            "What is your approximate monthly household income?",
            "Which city or district are you located in?",
            "Are you looking for education, health, or food support?",
        ]
        next_steps = [
            "Check the official website or nearest center for current intake.",
            "Keep CNIC, income slip, and academic documents ready.",
        ]

    programs = []
    for p in matches:
        programs.append({
            "title": p.get("title", ""),
            "match_level": "Potential match",
            "why_match": str(p.get("description", ""))[:80] + "..." if len(str(p.get("description", ""))) > 80 else str(p.get("description", "")),
            "support": p.get("support", []),
            "eligibility": p.get("eligibility", []),
            "documents": p.get("documents", []),
            "application": p.get("application", "Check the official source."),
            "source_name": p.get("source_name", "Official source"),
            "source_url": p.get("source_url", ""),
            "official_source": p.get("source_url", ""),  # New field
            "verified_at": p.get("verified_at", ""),
        })

    return {
        "summary": summary,
        "programs": programs,
        "official_source": primary_source,  # Top-level source
        "questions": questions,
        "next_steps": next_steps,
    }


# ---------------------------------------------------------------------------
# Graph construction & compilation (with conditional routing)
# ---------------------------------------------------------------------------

def _route_after_db(state: AgentState) -> str:
    """Conditional router: decides whether to call web search or skip to synthesis.
    
    Returns:
        'search_web' - if needs_web_search=True (low DB confidence)
        'synthesize' - if needs_web_search=False and we have strong matches
    """
    needs_web = state.get("needs_web_search", False)
    matches = state.get("matches", [])
    
    # Force web search if:
    # 1. needs_web_search flag is set (low DB confidence)
    # 2. No matches at all
    # 3. Fewer than 2 strong matches
    if needs_web or len(matches) < 2:
        return "search_web"
    
    # Skip web search if we have 2+ strong DB matches
    return "synthesize"


def _build_graph() -> StateGraph:
    graph = StateGraph(AgentState)
    graph.add_node("retrieve_db", retrieve_from_db)
    graph.add_node("search_web", search_web_node)
    graph.add_node("synthesize", synthesize_answer)

    graph.set_entry_point("retrieve_db")
    
    # Conditional routing: force web search when DB confidence is low
    graph.add_conditional_edges(
        "retrieve_db",
        _route_after_db,
        {
            "search_web": "search_web",
            "synthesize": "synthesize",
        },
    )
    
    graph.add_edge("search_web", "synthesize")
    graph.add_edge("synthesize", END)
    return graph


_compiled_app = _build_graph().compile()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_chat(query: str, language: str = "english", profile: dict | None = None) -> dict:
    """Execute the full agentic workflow and return structured result."""
    result = _compiled_app.invoke({
        "query": query,
        "language": language,
        "profile": profile or {},
        "matches": [],
        "web_results": [],
        "needs_web_search": False,
        "raw_answer": None,
        "model_used": "",
        "final_answer": {},
    })
    return {
        "answer": result.get("final_answer", {}),
        "model_used": result.get("model_used", "Unknown"),
        "matches": result.get("matches", []),
        "sources": result.get("web_results", []),
    }
