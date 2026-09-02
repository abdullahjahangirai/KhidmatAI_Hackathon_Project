"""KhidmatAI — Professional Welfare Navigation Platform.

FastAPI application entry-point.  All JSON file storage has been replaced
with a robust SQLite database (backend.database).  The AI chatbot is
powered by a LangGraph agentic workflow (backend.agent).
"""

from __future__ import annotations

import json
import os
import re
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import database as db
from .admin import router as admin_router

load_dotenv()

# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND = BASE_DIR / "frontend"
APP_NAME = os.getenv("APP_NAME", "KhidmatAI")

OFFICIAL_DOMAINS = {
    "hec.gov.pk", "scholarship.hec.gov.pk", "alkhidmat.org", "pbm.gov.pk", "bisp.gov.pk",
    "seef.sindh.gov.pk", "sindh.gov.pk", "sef.org.pk", "uok.edu.pk", "neduet.edu.pk",
    "duhs.edu.pk", "duet.edu.pk", "fuuast.edu.pk", "bbsul.edu.pk", "iba.edu.pk",
    "khi.nu.edu.pk", "bahria.edu.pk", "aku.edu", "szabist.edu.pk", "iobm.edu.pk",
    "jsmu.edu.pk", "muet.edu.pk", "usindh.edu.pk", "quest.edu.pk", "lumhs.edu.pk",
    "saylaniwelfare.com", "jdcwelfare.org", "edhi.org", "akhuwat.org.pk", "pmyp.gov.pk",
    "navttc.gov.pk", "ehsaas.gov.pk", "pass.gov.pk", "punjab.gov.pk", "kp.gov.pk",
}

# In-memory caches populated at startup
ALL_PROGRAMS: list[dict[str, Any]] = []
UNIVERSITIES: list[dict[str, Any]] = []


# ---------------------------------------------------------------------------
# Lifespan — initialise database and load caches
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    global ALL_PROGRAMS, UNIVERSITIES
    db.init_db()
    ALL_PROGRAMS = db.get_all_programs()
    UNIVERSITIES = db.get_all_universities()
    yield


app = FastAPI(title=APP_NAME, version="6.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=FRONTEND), name="static")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(admin_router)


# ---------------------------------------------------------------------------
# Rate limiting (in-memory, per IP)
# ---------------------------------------------------------------------------
_rate_store: dict[str, list] = {}


def rate_limit(request: Request, max_calls: int = 30, window: int = 60) -> None:
    ip = (request.client.host if request.client else None) or "0.0.0.0"
    now = time.time()
    calls = _rate_store.get(ip, [])
    calls = [t for t in calls if now - t < window]
    if len(calls) >= max_calls:
        raise HTTPException(status_code=429, detail="Too many requests. Please wait a moment.")
    calls.append(now)
    _rate_store[ip] = calls


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------
class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=5000)
    language: str = "english"


class RecommendRequest(BaseModel):
    need: str = Field(min_length=1, max_length=3000)
    location: str = ""
    language: str = "auto"
    profile: dict[str, Any] = Field(default_factory=dict)


class EligibilityRequest(BaseModel):
    income: str = ""
    family_size: int = 4
    employment_status: str = "Unemployed"
    city: str = "Karachi"
    category: str = "all"
    education_level: str = ""
    special_criteria: list[str] = Field(default_factory=list)
    language: str = "auto"


class UserRegister(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=3, max_length=200)
    password: str = Field(min_length=4, max_length=200)
    phone: str = ""
    city: str = ""
    cnic: str = ""


class UserLogin(BaseModel):
    email: str
    password: str


class UserProfileUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    phone: str = Field(default="", max_length=30)
    city: str = Field(default="", max_length=100)
    cnic: str = Field(default="", max_length=20)


class WelfareApplication(BaseModel):
    program_id: str
    status: str = "pending"
    notes: str = ""


class OrgLogin(BaseModel):
    email: str
    password: str


class OrgProfileUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    org_type: str = Field(default="", max_length=100)
    contact: str = Field(default="", max_length=100)
    address: str = Field(default="", max_length=300)
    province: str = Field(default="", max_length=100)
    description: str = Field(default="", max_length=2000)
    website: str = Field(default="", max_length=300)
    city: str = Field(default="", max_length=100)
    services: str = Field(default="", max_length=1000)
    opening_hours: str = Field(default="", max_length=200)
    pricing: str = Field(default="", max_length=50)
    discount: str = Field(default="", max_length=50)


class OrgPostCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(default="", max_length=5000)
    category: str = Field(default="General", max_length=100)
    post_type: str = Field(default="Program", max_length=100)
    eligibility: list[str] = Field(default_factory=list)
    documents: list[str] = Field(default_factory=list)
    location: str = Field(default="", max_length=300)
    contact: str = Field(default="", max_length=100)
    website: str = Field(default="", max_length=300)
    pricing: str = Field(default="Free", max_length=50)
    image: str = Field(default="", max_length=500)


class OrgPostUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=300)
    description: str | None = Field(default=None, max_length=5000)
    category: str | None = Field(default=None, max_length=100)
    post_type: str | None = Field(default=None, max_length=100)
    eligibility: list[str] | None = None
    documents: list[str] | None = None
    location: str | None = Field(default=None, max_length=300)
    contact: str | None = Field(default=None, max_length=100)
    website: str | None = Field(default=None, max_length=300)
    pricing: str | None = Field(default=None, max_length=50)
    image: str | None = Field(default=None, max_length=500)


class AutoCollectRequest(BaseModel):
    city: str = "Karachi"
    categories: list[str] = []


# ---------------------------------------------------------------------------
# Text & query utilities
# ---------------------------------------------------------------------------
def tokens(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", str(value).lower()))


def detect_language(text: str, requested: str = "english") -> str:
    if requested in {"english", "roman", "urdu"}:
        return requested
    return "english"


def normalize_query(text: str) -> str:
    replacements = {
        "mene": "main", "kia": "kya", "he": "hai", "chate": "chahta", "lana": "lena",
        "mughe": "mujhe", "scholarships": "scholarship", "fees": "fee", "uni": "university",
        "karachi": "karachi", "larkana": "larkana", "sindh": "sindh", "inter": "intermediate",
        "rashan": "ration", "elaj": "treatment", "ilaj": "treatment", "pesa": "paisa",
    }
    value = (text or "").lower()
    for old, new in replacements.items():
        value = re.sub(rf"\b{re.escape(old)}\b", new, value)
    return value


def detect_categories(text: str) -> list[str]:
    t = tokens(normalize_query(text))
    groups = {
        "Education": {"education", "scholarship", "student", "university", "college", "fee", "admission", "study", "intermediate", "school", "taleem", "wazifa"},
        "Healthcare": {"health", "medical", "hospital", "medicine", "treatment", "doctor", "clinic", "ilaj", "dawa", "surgery", "dialysis"},
        "Financial Aid": {"financial", "money", "cash", "zakat", "income", "poverty", "aid", "assistance", "paisa", "paise", "bisp", "kafalat", "baitulmal"},
        "Food Support": {"food", "ration", "meal", "kitchen", "dastarkhwan", "rashan", "khana", "atta", "wheat"},
        "Employment": {"job", "employment", "skills", "training", "hunar", "rozgar", "kam", "karobar"},
        "Disability": {"disability", "disabled", "special", "mazoor", "wheelchair", "handicap"},
        "Disaster Relief": {"flood", "disaster", "relief", "emergency", "sailab", "aafat"},
    }
    return [name for name, words in groups.items() if t & words]


def extract_profile(text: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    q = normalize_query(text)
    profile: dict[str, Any] = {}
    cities: list[str] = []
    for city in ["Karachi", "Larkana", "Hyderabad", "Sukkur", "Islamabad",
                  "Rawalpindi", "Lahore", "Quetta", "Peshawar", "Multan", "Faisalabad"]:
        if city.lower() in q:
            cities.append(city)
    if cities:
        profile["mentioned_cities"] = cities
    if "intermediate" in q or "fsc" in q or re.search(r"\bfa\b", q) or "a level" in q:
        profile["education_level"] = "Intermediate completed / undergraduate applicant"
    elif "undergraduate" in q or "bachelor" in q or "university" in q:
        profile["education_level"] = "Undergraduate"
    if "public" in q:
        profile["institution_type"] = "Public"
    elif "private" in q:
        profile["institution_type"] = "Private"
    if "admission" in q or "admission lena" in q or "admission lo" in q:
        profile["status"] = "Seeking admission"
    if "widow" in q or "bewa" in q:
        profile["social_status"] = "Widow"
    if "disabled" in q or "mazoor" in q:
        profile["disability"] = True
    if extra:
        for k, v in extra.items():
            if v not in (None, "", []):
                profile[k] = v
    return profile


# ---------------------------------------------------------------------------
# Program scoring & retrieval (in-memory for speed)
# ---------------------------------------------------------------------------
def program_text(p: dict[str, Any]) -> str:
    return " ".join([
        str(p.get("title", "")), str(p.get("category", "")),
        str(p.get("type", "")), str(p.get("description", "")),
        " ".join(str(x) for x in p.get("keywords", [])),
        " ".join(str(x) for x in p.get("eligibility", [])),
        " ".join(str(x) for x in p.get("locations", [])),
        " ".join(str(x) for x in p.get("support", [])),
    ])


def score_program(p: dict[str, Any], query: str, profile: dict[str, Any]) -> int:
    q = tokens(normalize_query(query))
    h = tokens(program_text(p))
    score = len(q & h) * 2
    cats = detect_categories(query)
    p_cat = str(p.get("category", ""))
    if any(c.lower() in p_cat.lower() for c in cats):
        score += 15
    if "scholarship" in q and "scholarship" in p_cat.lower():
        score += 12
    if "hospital" in q and ("hospital" in h or p_cat == "Healthcare"):
        score += 12
    if "food" in q or "ration" in q or "rashan" in q:
        if "food" in p_cat.lower() or "ration" in h:
            score += 15
    cities = {str(x).lower() for x in profile.get("mentioned_cities", [])}
    locations = {str(x).lower() for x in p.get("locations", [])}
    if "all pakistan" in locations:
        score += 3
    if any(c in locations for c in cities):
        score += 10
    return score


def retrieve_programs(query: str, limit: int = 6) -> list[dict[str, Any]]:
    profile = extract_profile(query)
    requested_categories = set(detect_categories(query))
    candidates = ALL_PROGRAMS
    if requested_categories:
        candidates = [p for p in ALL_PROGRAMS
                      if any(c.lower() in str(p.get("category", "")).lower() for c in requested_categories)]
        if len(candidates) < 3:
            candidates = ALL_PROGRAMS
    if profile.get("education_level", "").startswith("Intermediate"):
        candidates = [p for p in candidates if p.get("id") not in {"bisp_taleemi", "bisp_nashonuma"}]
    ranked = sorted(((score_program(p, query, profile), p) for p in candidates), key=lambda x: x[0], reverse=True)
    results = [p for sc, p in ranked if sc > 0][:limit]
    if not results and ALL_PROGRAMS:
        results = ALL_PROGRAMS[:limit]
    return results


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------
def is_official(url: str) -> bool:
    try:
        host = (urlparse(url).hostname or "").lower().removeprefix("www.")
        return host in OFFICIAL_DOMAINS or any(host.endswith("." + d) for d in OFFICIAL_DOMAINS)
    except Exception:
        return False


def clean_official_url(url: str) -> str:
    return url if is_official(url) else url or ""


# ---------------------------------------------------------------------------
# Localization helper
# ---------------------------------------------------------------------------
def localized(language: str, english: Any, roman: Any, urdu: Any) -> Any:
    return {"english": english, "roman": roman, "urdu": urdu}.get(language, english)


# ---------------------------------------------------------------------------
# JSON parsing & safe-answer builder
# ---------------------------------------------------------------------------
def parse_json(raw: str | None) -> dict[str, Any] | None:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        match = re.search(r"\{.*\}", raw, re.S)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                pass
    return None


def deterministic_answer(matches: list[dict[str, Any]], language: str, profile: dict[str, Any]) -> dict[str, Any]:
    """Build a deterministic fallback answer with bullet-point summary."""
    count = len(matches)
    # Get the primary source URL from first match (if available)
    primary_source = matches[0].get("source_url", "") if matches else ""
    
    summary = localized(
        language,
        f"• Found {count} verified official support options\n• Check official website for eligibility details\n• Keep CNIC and relevant documents ready",
        f"• Aap ke liye {count} verified official options mile hain\n• Tafseelat ke liye official website check karein\n• CNIC aur zaroori documents tayar rakhein",
        f"• آپ کے لیے {count} تصدیق شدہ سرکاری فلاحی پروگرام دستیاب ہیں\n• تفصیلات کے لیے سرکاری ویب سائٹ دیکھیں\n• شناختی کارڈ اور ضروری دستاویزات تیار رکھیں",
    )
    programs = []
    for p in matches:
        programs.append({
            "title": p.get("title", ""),
            "match_level": "Potential match",
            "why_match": p.get("description", "")[:80] + "..." if len(str(p.get("description", ""))) > 80 else p.get("description", ""),
            "support": p.get("support", []),
            "eligibility": p.get("eligibility", []),
            "documents": p.get("documents", []),
            "application": p.get("application", "Check the official source."),
            "source_name": p.get("source_name", "Official source"),
            "source_url": p.get("source_url", ""),
            "official_source": p.get("source_url", ""),  # New field
            "verified_at": p.get("verified_at", ""),
        })
    questions = localized(
        language,
        ["What is your approximate monthly household income?", "Which city or district are you located in?", "Are you looking for education, health, or food support?"],
        ["Ghar ki taqreeban monthly income kitni hai?", "Aap kis shehar ya district mein rehte hain?", "Aapko taleem, ilaj ya rashan mein kis cheez ki zaroorat hai?"],
        ["آپ کے گھرانے کی ماہانہ آمدنی کتنی ہے؟", "آپ کس شہر یا ضلع میں مقیم ہیں؟", "کیا آپ کو تعلیم، علاج یا راشن کی مدد درکار ہے؟"],
    )
    return {
        "summary": summary,
        "programs": programs,
        "official_source": primary_source,  # Top-level source link
        "questions": questions,
        "next_steps": localized(
            language,
            ["Check the official website or nearest center for current intake.", "Keep CNIC, income slip, and academic documents ready."],
            ["Current application cycle ke liye official portal ya center check karein.", "CNIC aur zaroori documents tayar rakhein."],
            ["موجودہ درخواست کے لیے سرکاری ویب سائٹ یا قریبی مرکز سے رجوع کریں۔", "شناختی کارڈ اور ضروری دستاویزات تیار رکھیں۔"],
        ),
    }


def build_safe_answer(model_answer: dict[str, Any] | None, matches: list[dict[str, Any]], language: str, profile: dict[str, Any]) -> dict[str, Any]:
    """Build a safe answer, using fallback if model answer is missing."""
    fallback = deterministic_answer(matches, language, profile)
    if not model_answer:
        return fallback

    generated = {str(x.get("title")): x for x in model_answer.get("programs", []) if isinstance(x, dict)}
    programs = []
    for p in matches:
        g = generated.get(p.get("title", ""), {})
        match_level = g.get("match_level")
        if match_level not in {"High relevance", "Potential match", "Needs more information"}:
            match_level = "Potential match"
        # Use official_source from LLM or fallback to source_url
        official_src = g.get("official_source") or p.get("source_url", "")
        programs.append({
            "title": p.get("title", ""),
            "match_level": match_level,
            "why_match": str(g.get("why_match") or p.get("description", ""))[:80] + "..." if len(str(g.get("why_match") or p.get("description", ""))) > 80 else str(g.get("why_match") or p.get("description", "")),
            "support": p.get("support", []),
            "eligibility": p.get("eligibility", []),
            "documents": p.get("documents", []),
            "application": p.get("application", "Check the official source."),
            "source_name": p.get("source_name", "Official source"),
            "source_url": clean_official_url(p.get("source_url", "")),
            "official_source": clean_official_url(official_src),  # New field
            "verified_at": p.get("verified_at", ""),
        })

    questions = model_answer.get("questions")
    if not isinstance(questions, list) or not questions:
        questions = fallback["questions"]
    next_steps = model_answer.get("next_steps")
    if not isinstance(next_steps, list) or not next_steps:
        next_steps = fallback["next_steps"]
    summary_text = str(model_answer.get("summary") or fallback["summary"]).strip()
    
    # Get official_source from model answer or fallback
    official_source = model_answer.get("official_source") or fallback.get("official_source", "")
    
    return {
        "summary": summary_text,
        "programs": programs,
        "official_source": clean_official_url(official_source) if official_source else "",
        "questions": [str(q) for q in questions[:4]],
        "next_steps": [str(x) for x in next_steps[:4]],
    }


# ---------------------------------------------------------------------------
# Dynamic program saving (web-discovered programs → SQLite)
# ---------------------------------------------------------------------------
def dynamic_save_program(item: dict[str, Any]) -> bool:
    global ALL_PROGRAMS
    if not item.get("title"):
        return False
    title_lower = str(item.get("title")).strip().lower()
    if any(str(p.get("title", "")).strip().lower() == title_lower for p in ALL_PROGRAMS):
        return False

    slug = re.sub(r"[^a-z0-9]+", "_", title_lower)[:35].strip("_")
    entry: dict[str, Any] = {
        "id": f"dynamic_{slug}_{int(datetime.now().timestamp())}",
        "title": str(item.get("title", "New Welfare Program")),
        "category": str(item.get("category", "General Welfare")),
        "type": str(item.get("type", "Government / NGO Initiative")),
        "description": str(item.get("description", "Discovered through live verified search.")),
        "support": item.get("support") if isinstance(item.get("support"), list) else [str(item.get("support", "Welfare Assistance"))],
        "eligibility": item.get("eligibility") if isinstance(item.get("eligibility"), list) else [str(item.get("eligibility", "Check official details."))],
        "documents": item.get("documents") if isinstance(item.get("documents"), list) else ["CNIC", "Proof of Residence / Income"],
        "application": str(item.get("application", "Visit the official portal.")),
        "locations": item.get("locations") if isinstance(item.get("locations"), list) else ["Pakistan"],
        "source_name": str(item.get("source_name", "Live Verified Web Search")),
        "source_url": str(item.get("source_url", "")),
        "verified_at": datetime.now().strftime("%Y-%m-%d"),
        "dynamic_saved": True,
    }
    if db.insert_program(entry):
        ALL_PROGRAMS.insert(0, entry)
        return True
    return False


# ===================================================================
# API ENDPOINTS
# ===================================================================

# ---------------------------------------------------------------------------
# Page routes
# ---------------------------------------------------------------------------
@app.get("/")
def root():
    return FileResponse(FRONTEND / "index.html")


@app.get("/login")
def login_page():
    return FileResponse(FRONTEND / "login.html")


@app.get("/register")
def register_page():
    return FileResponse(FRONTEND / "register.html")


@app.get("/dashboard")
def user_dashboard():
    return FileResponse(FRONTEND / "dashboard.html")


@app.get("/chat")
def chat_page():
    return FileResponse(FRONTEND / "chat.html")


@app.get("/admin")
def admin_panel():
    return FileResponse(FRONTEND / "admin.html")


@app.get("/org")
def org_dashboard_page():
    return FileResponse(FRONTEND / "org.html")


# ---------------------------------------------------------------------------
# Health & Config
# ---------------------------------------------------------------------------
@app.get("/api/health")
def health():
    import os as _os
    return {
        "status": "ok",
        "database": "sqlite",
        "primary_ai": "DashScope/Qwen" if _os.getenv("DASHSCOPE_API_KEY", "").strip() else "not_configured",
        "fallback_ai": "groq" if _os.getenv("GROQ_API_KEY", "").strip() else "not_configured",
        "search_configured": bool(_os.getenv("TAVILY_API_KEY", "").strip() and not _os.getenv("TAVILY_API_KEY", "").startswith("yahan_")),
        "programs_count": len(ALL_PROGRAMS),
        "universities_count": len(UNIVERSITIES),
    }


@app.get("/api/config")
def config():
    import os as _os
    has_dash = bool(_os.getenv("DASHSCOPE_API_KEY", "").strip())
    has_groq = bool(_os.getenv("GROQ_API_KEY", "").strip())
    active_model = "DashScope Qwen" if has_dash else ("Groq Cloud" if has_groq else "Deterministic Mode")
    return {
        "app": APP_NAME,
        "languages": ["auto", "english", "roman", "urdu"],
        "active_model": active_model,
        "dashscope_configured": has_dash,
        "groq_configured": has_groq,
        "search_configured": bool(_os.getenv("TAVILY_API_KEY", "").strip()),
    }


# ---------------------------------------------------------------------------
# Programs & Universities
# ---------------------------------------------------------------------------
@app.get("/api/programs")
def api_programs(category: str = "all", q: str = "", province: str = "all"):
    if q or (category and category != "all") or (province and province != "all"):
        db.log_event("search", {"q": q[:200], "category": category, "province": province})
    return db.get_programs_filtered(category=category, q=q, province=province)


@app.get("/api/universities")
def api_universities(city: str = "Karachi", q: str = ""):
    return db.get_universities_filtered(city=city, q=q)


@app.get("/api/org-posts")
def api_org_posts(category: str = "all", q: str = ""):
    """Public feed of organization posts — only admin-verified (approved) posts
    from currently approved organizations (suspending an org hides its live posts instantly)."""
    posts = db.get_org_posts(status="approved", category=category, q=q, orgs_approved_only=True)
    return {"status": "success", "count": len(posts), "posts": posts}


# ---------------------------------------------------------------------------
# Chat — LangGraph agent
# ---------------------------------------------------------------------------
# Simple social greetings get a short, friendly reply without running the
# database/web-search pipeline, so "hello" never returns welfare results.
_GREETING_TOKENS = {
    "hello", "helo", "hi", "hii", "hiii", "hy", "hey", "yo", "salam", "salaam",
    "assalam", "asalam", "assalamu", "assalamualaikum", "asalamualaikum", "alaikum",
    "alaykum", "walaikum", "o", "u", "aoa", "adab", "greetings", "good", "morning",
    "afternoon", "evening", "night", "there", "everyone", "how", "are", "you", "today",
    "kaise", "ho", "hain", "aap", "kya", "haal", "hai", "whats", "up", "team", "bot",
    "khidmatai", "janab",
}

_GREETING_STRONG = {
    "hello", "helo", "hi", "hii", "hiii", "hy", "hey", "yo", "salam", "salaam",
    "assalam", "asalam", "assalamualaikum", "asalamualaikum", "aoa", "adab",
    "greetings", "good", "how", "kaise", "kya", "whats",
}

_GREETING_REPLIES = {
    "english": (
        "Hello! How can I help you today? I can help you find welfare programs, "
        "scholarships, healthcare support, financial assistance, or nearby services."
    ),
    "urdu": (
        "\u0627\u0633\u0644\u0627\u0645 \u0639\u0644\u06cc\u06a9\u0645! \u0645\u06cc\u06ba \u0622\u067e \u06a9\u06cc \u06a9\u06cc\u0627 \u0645\u062f\u062f \u06a9\u0631 \u0633\u06a9\u062a\u0627 \u06c1\u0648\u06ba\u061f "
        "\u0645\u06cc\u06ba \u0641\u0644\u0627\u062d\u06cc \u067e\u0631\u0648\u06af\u0631\u0627\u0645\u0632\u060c \u0633\u06a9\u0627\u0644\u0631\u0634\u067e\u0648\u06ba\u060c \u0635\u062d\u062a \u06a9\u06cc \u0645\u062f\u062f\u061b \u0645\u0627\u0644\u06cc \u0627\u0645\u062f\u0627\u062f \u06cc\u0627 \u0642\u0631\u06cc\u0628\u06cc \u062e\u062f\u0645\u0627\u062a \u0645\u06cc\u06ba \u0645\u062f\u062f \u06a9\u0631 \u0633\u06a9\u062a\u0627 \u06c1\u0648\u06ba\u06d4"
    ),
    "roman": (
        "Assalam o Alaikum! Main aap ki kya madad kar sakta hoon? Main welfare "
        "programs, scholarships, sehat ki madad, maali imdad ya qareebi khidmaat "
        "dhoondne mein madad kar sakta hoon."
    ),
}


def is_simple_greeting(message: str) -> bool:
    """True when the whole message is a short social greeting (hi, salam, ...)."""
    text = re.sub(r"[^\w\s]", " ", message.lower())
    text = re.sub(r"\s+", " ", text).strip()
    if not text or len(text.split()) > 5:
        return False
    words = text.split()
    return all(w in _GREETING_TOKENS for w in words) and any(w in _GREETING_STRONG for w in words)


# Questions about the assistant itself ("what can you help me with?").
# Answered directly without touching the search pipeline.
_CAPABILITY_PATTERNS = re.compile(
    r"("
    r"what (can|could|do|does) (you|u|i) (help|do|assist|support)"
    r"|how (can|could|do|does) (you|u) (help|assist)"
    r"|what (are|r) (your|ur) (services|features|capabilities)"
    r"|what do you (do|offer)"
    r"|who are (you|u)"
    r"|tell me about (yourself|you)"
    r"|aap kya (madad|help) kar sakte"
    r"|tum kya kar sakte"
    r"|aap kiya madad kar sakty"
    r"|"
    r"\u0622\u067e \u06a9\u06cc\u0627 \u0645\u062f\u062f \u06a9\u0631 \u0633\u06a9\u062a\u06d2"
    r")"
)

_CAPABILITY_REPLIES = {
    "english": (
        "I can help you find welfare programs, scholarships, healthcare support, "
        "financial assistance, jobs, and nearby support services."
    ),
    "urdu": (
        "\u0645\u06cc\u06ba \u0622\u067e \u06a9\u0648 \u0641\u0644\u0627\u062d\u06cc \u067e\u0631\u0648\u06af\u0631\u0627\u0645\u0632\u060c \u0633\u06a9\u0627\u0644\u0631\u0634\u067e\u0633\u060c \u0635\u062d\u062a \u06a9\u06cc \u0633\u06c1\u0648\u0644\u062a\u060c "
        "\u0645\u0627\u0644\u06cc \u0645\u062f\u062f\u060c \u0631\u0648\u0632\u06af\u0627\u0631 \u0627\u0648\u0631 \u0642\u0631\u06cc\u0628\u06cc \u062e\u062f\u0645\u0627\u062a \u062a\u0644\u0627\u0634 \u06a9\u0631\u0646\u06d2 \u0645\u06cc\u06ba \u0645\u062f\u062f \u06a9\u0631 \u0633\u06a9\u062a\u0627 \u06c1\u0648\u06ba\u06d4"
    ),
    "roman": (
        "Main aap ko welfare programs, scholarships, sehat ki madad, maali imdad, "
        "naukri aur qareebi khidmaat dhoondne mein madad kar sakta hoon."
    ),
}


def is_capability_question(message: str) -> bool:
    """True for 'what can you help me with?'-style questions."""
    return bool(_CAPABILITY_PATTERNS.search(message.lower()))


@app.post("/api/chat", dependencies=[Depends(rate_limit)])
def chat(req: ChatRequest):
    from .agent import run_chat

    language = detect_language(req.message, req.language)

    # Greetings: reply directly — no DB search, no web search, no LLM call.
    if is_simple_greeting(req.message):
        reply = _GREETING_REPLIES.get(language, _GREETING_REPLIES["english"])
        return {
            "answer": {
                "summary": reply,
                "programs": [],
                "official_source": "",
                "questions": [],
                "next_steps": [],
            },
            "model_used": "greeting",
            "language": language,
            "profile": {},
            "matches": [],
            "sources": [],
            "counts": {"matches": 0, "official_sources": 0},
        }

    # "What can you help me with?" — answer directly, no search pipeline.
    if is_capability_question(req.message):
        reply = _CAPABILITY_REPLIES.get(language, _CAPABILITY_REPLIES["english"])
        return {
            "answer": {
                "summary": reply,
                "programs": [],
                "official_source": "",
                "questions": [],
                "next_steps": [],
            },
            "model_used": "assistant-info",
            "language": language,
            "profile": {},
            "matches": [],
            "sources": [],
            "counts": {"matches": 0, "official_sources": 0},
        }

    db.log_event("ai_query", {"q": req.message[:200], "language": language})
    profile = extract_profile(req.message)
    result = run_chat(req.message, language=language, profile=profile)
    return {
        "answer": result["answer"],
        "model_used": result["model_used"],
        "language": language,
        "profile": profile,
        "matches": result["matches"],
        "sources": result["sources"],
        "counts": {"matches": len(result["matches"]), "official_sources": len(result["sources"])},
    }


# ---------------------------------------------------------------------------
# Recommend
# ---------------------------------------------------------------------------
@app.post("/api/recommend")
def recommend(req: RecommendRequest):
    combined = f"{req.need} {req.location} {json.dumps(req.profile, ensure_ascii=False)}"
    profile = extract_profile(combined, req.profile)
    matches = retrieve_programs(combined, 6)
    db.log_event("program_match", {"source": "recommend", "count": len(matches)})
    return {"matches": matches, "language": detect_language(req.need, req.language), "profile": profile}


# ---------------------------------------------------------------------------
# Eligibility engine
# ---------------------------------------------------------------------------
@app.post("/api/eligibility")
def check_eligibility_engine(req: EligibilityRequest):
    user_city = req.city.strip().lower()
    req_cat = req.category.strip().lower()
    emp_status = req.employment_status.strip().lower()

    income_num = 1_000_000
    if req.income:
        nums = re.findall(r"\d+", req.income.replace(",", ""))
        if nums:
            income_num = int(nums[0])
            if income_num < 1000:
                income_num *= 1000

    results = []
    for p in ALL_PROGRAMS:
        score = 0
        reasons: list[str] = []
        p_text = program_text(p).lower()
        p_cat = str(p.get("category", "")).lower()
        p_locs = [str(x).lower() for x in p.get("locations", [])]

        if "all pakistan" in p_locs or not user_city or any(user_city in loc for loc in p_locs):
            score += 25
            if user_city and any(user_city in loc for loc in p_locs):
                reasons.append(f"Available in your city / region ({req.city})")

        if req_cat == "all" or req_cat in p_cat:
            score += 25
            reasons.append(f"Matches category: {p.get('category', 'Support')}")

        if "income" in p_text or "poverty" in p_text or "25,000" in p_text or "50,000" in p_text or "low-income" in p_text:
            if income_num <= 30000:
                score += 30
                reasons.append("Income fits priority low-income threshold (<= Rs. 30,000)")
            elif income_num <= 60000:
                score += 20
                reasons.append("Income qualifies for general financial / scholarship aid")
        else:
            score += 15

        if "student" in emp_status or "intermediate" in req.education_level.lower() or "undergraduate" in req.education_level.lower():
            if "education" in p_cat or "scholarship" in p_text or "training" in p_text:
                score += 25
                reasons.append("Academic & student profile qualifies for scholarship/stipend")

        if "widow" in emp_status or "female" in emp_status:
            if "widow" in p_text or "women" in p_text or "kafalat" in p_text:
                score += 30
                reasons.append("Special priority allocated for female/widow-headed households")

        if "unemployed" in emp_status or "daily wage" in emp_status:
            if "financial" in p_cat or "food" in p_cat or "cash" in p_text or "ration" in p_text:
                score += 25
                reasons.append("Eligible for emergency cash grant & ration assistance")

        if "disab" in emp_status or "mazoor" in emp_status:
            if "disab" in p_text or "special" in p_text:
                score += 35
                reasons.append("Special disability quota and assistance applicable")

        if score >= 40:
            match_level = "Highly Eligible" if score >= 75 else ("Potential Match" if score >= 50 else "General Support")
            results.append({"score": min(score, 98), "match_level": match_level, "reasons": reasons, "program": p})

    results.sort(key=lambda x: x["score"], reverse=True)
    db.log_event("program_match", {"source": "eligibility", "city": req.city, "count": len(results)})
    return {"status": "success", "total_evaluated": len(ALL_PROGRAMS), "matches_count": len(results), "matches": results[:10]}


# ---------------------------------------------------------------------------
# Facilities (curated)
# ---------------------------------------------------------------------------
@app.get("/api/facilities")
def get_facilities(city: str = "Karachi", category: str = "all"):
    curated = [
        {"id": "civ_khi", "name": "Dr. Ruth Pfau Civil Hospital", "category": "hospital", "city": "Karachi", "zone": "Saddar / South", "lat": 24.8608, "lon": 67.0104, "address": "Mission Road, Ranchore Line, Karachi", "phone": "021-99215740", "type": "Public Tertiary Hospital (Free Care)"},
        {"id": "jpmc_khi", "name": "Jinnah Postgraduate Medical Centre (JPMC)", "category": "hospital", "city": "Karachi", "zone": "Cantt / Jamshed", "lat": 24.8532, "lon": 67.0456, "address": "Rafiqui Shaheed Road, Cantt, Karachi", "phone": "021-99201300", "type": "Public Teaching & CyberKnife Center"},
        {"id": "indus_khi", "name": "The Indus Hospital (Korangi)", "category": "hospital", "city": "Karachi", "zone": "Korangi", "lat": 24.8315, "lon": 67.1157, "address": "Plot C-76, Sector 31/5, Korangi Crossing, Karachi", "phone": "021-111-111-880", "type": "100% Free Quality Healthcare"},
        {"id": "siut_khi", "name": "Sindh Institute of Urology & Transplantation (SIUT)", "category": "hospital", "city": "Karachi", "zone": "Saddar", "lat": 24.8587, "lon": 67.0123, "address": "Civil Hospital Compound, Saddar, Karachi", "phone": "021-99215720", "type": "Free Dialysis, Urology & Transplants"},
        {"id": "nicvd_khi", "name": "National Institute of Cardiovascular Diseases (NICVD)", "category": "hospital", "city": "Karachi", "zone": "Cantt", "lat": 24.8517, "lon": 67.0423, "address": "Rafiqui Shaheed Road, Karachi", "phone": "021-99201271", "type": "Free Cardiac & Heart Surgeries"},
        {"id": "aku_khi", "name": "Aga Khan University Hospital (Patient Welfare)", "category": "hospital", "city": "Karachi", "zone": "Gulshan-e-Iqbal", "lat": 24.8918, "lon": 67.0747, "address": "Stadium Road, Gulshan-e-Iqbal, Karachi", "phone": "021-111-911-911", "type": "Need-Based Patient Welfare Fund"},
        {"id": "saylani_hds", "name": "Saylani Welfare International Head Office", "category": "welfare", "city": "Karachi", "zone": "Bahadurabad", "lat": 24.8825, "lon": 67.0694, "address": "A-25, Char Murti Chowrangi, Bahadurabad, Karachi", "phone": "021-111-729-526", "type": "Free Dastarkhwan, Ration & Mass IT"},
        {"id": "alkhidmat_khi", "name": "Alkhidmat Foundation Karachi Complex", "category": "welfare", "city": "Karachi", "zone": "Gulshan-e-Iqbal", "lat": 24.9175, "lon": 67.0921, "address": "501, Quaideen Colony, Gulshan-e-Iqbal, Karachi", "phone": "021-111-503-504", "type": "Disaster Relief, Orphan Care & Water"},
        {"id": "edhi_tower", "name": "Edhi Foundation Central Tower", "category": "welfare", "city": "Karachi", "zone": "Bolton Market", "lat": 24.8510, "lon": 66.9984, "address": "Sarafa Bazaar, Boulton Market, Karachi", "phone": "021-32413232", "type": "24/7 Ambulance, Shelter & Ration"},
        {"id": "bisp_khi", "name": "BISP Regional Facilitation Center Karachi", "category": "welfare", "city": "Karachi", "zone": "Saddar", "lat": 24.8621, "lon": 67.0210, "address": "State Life Building No. 11, Abdullah Haroon Rd", "phone": "0800-26477", "type": "Kafaalat Registration & 8171 Desk"},
        {"id": "uok_khi", "name": "University of Karachi (Financial Aid Office)", "category": "university", "city": "Karachi", "zone": "University Road", "lat": 24.9416, "lon": 67.1141, "address": "Main University Road, Karachi", "phone": "021-99261300", "type": "HEC Need-Based & Sindh SEEF Portal"},
        {"id": "ned_khi", "name": "NED University of Engineering & Technology", "category": "university", "city": "Karachi", "zone": "Gulshan", "lat": 24.9328, "lon": 67.1118, "address": "University Road, Karachi", "phone": "021-99261261", "type": "Engineering Scholarships & Endowment Fund"},
        {"id": "lahore_mayo", "name": "Mayo Hospital Lahore", "category": "hospital", "city": "Lahore", "zone": "Anarkali", "lat": 31.5762, "lon": 74.3129, "address": "Hospital Road, Anarkali Bazaar, Lahore", "phone": "042-99211100", "type": "Public Teaching Hospital"},
        {"id": "isb_pims", "name": "Pakistan Institute of Medical Sciences (PIMS)", "category": "hospital", "city": "Islamabad", "zone": "G-8/3", "lat": 33.7036, "lon": 73.0531, "address": "Sector G-8/3, Islamabad", "phone": "051-9261170", "type": "Federal Tertiary Care Hospital"},
        {"id": "isb_pbm", "name": "Pakistan Bait-ul-Mal Federal HQ", "category": "welfare", "city": "Islamabad", "zone": "H-8/4", "lat": 33.6844, "lon": 73.0479, "address": "Street No. 7, Sector H-8/4, Islamabad", "phone": "0800-66666", "type": "National Welfare Grants & Orphanages"},
        {"id": "peshawar_lrh", "name": "Lady Reading Hospital (LRH)", "category": "hospital", "city": "Peshawar", "zone": "City", "lat": 34.0125, "lon": 71.5785, "address": "PTCL Colony, Peshawar, KP", "phone": "091-9211430", "type": "Public Tertiary Hospital"},
        {"id": "quetta_cmh", "name": "Civil Hospital Quetta (Sandeman Provincial)", "category": "hospital", "city": "Quetta", "zone": "Jinnah Road", "lat": 30.1956, "lon": 67.0177, "address": "Jinnah Road, Quetta, Balochistan", "phone": "081-9202014", "type": "Provincial Teaching Hospital"},
    ]
    filtered = curated
    if city and city.lower() != "all":
        filtered = [f for f in filtered if f.get("city", "").lower() == city.lower()]
    if category and category.lower() != "all":
        filtered = [f for f in filtered if f.get("category", "").lower() == category.lower()]
    return {"status": "success", "city": city, "category": category, "count": len(filtered), "facilities": filtered}


# ---------------------------------------------------------------------------
# Nearby (OpenStreetMap Overpass with curated fallback)
# ---------------------------------------------------------------------------
@app.get("/api/nearby")
def nearby(location: str = Query(..., min_length=2, max_length=200), category: str = "all"):
    try:
        geo = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": f"{location}, Pakistan", "format": "json", "limit": 1},
            headers={"User-Agent": "KhidmatAI-Navigator/6.0"},
            timeout=8,
        ).json()
        lat, lon = (24.8607, 67.0011)
        if geo and len(geo) > 0:
            lat, lon = float(geo[0]["lat"]), float(geo[0]["lon"])
        filters = {
            "hospital": "[amenity=hospital]", "clinic": "[amenity=clinic]",
            "pharmacy": "[amenity=pharmacy]", "university": "[amenity=university]",
            "school": "[amenity=school]",
            "welfare": '[amenity~"social_facility|community_centre|food_sharing"]',
        }
        selector = filters.get(category, '[amenity~"hospital|clinic|pharmacy|social_facility|school|university"]')
        query = f"[out:json][timeout:15];nwr(around:8000,{lat},{lon}){selector};out center 35;"
        overpass_res = requests.post("https://overpass-api.de/api/interpreter", data=query, timeout=12)
        if overpass_res.ok:
            data = overpass_res.json()
            results = []
            for item in data.get("elements", []):
                tags = item.get("tags", {})
                center = item.get("center", item)
                if center.get("lat") is None or center.get("lon") is None:
                    continue
                results.append({
                    "name": tags.get("name", "Support Facility"),
                    "type": tags.get("amenity", category if category != "all" else "welfare"),
                    "address": ", ".join(x for x in [tags.get("addr:street"), tags.get("addr:suburb"), tags.get("addr:city")] if x) or f"Near {location}",
                    "lat": center["lat"], "lon": center["lon"],
                    "phone": tags.get("phone", tags.get("contact:phone", "")),
                    "map_url": f"https://www.google.com/maps/search/?api=1&query={center['lat']},{center['lon']}",
                })
            if results:
                return {"location": location, "coordinates": {"lat": lat, "lon": lon}, "results": results}
    except Exception:
        pass

    all_fac = get_facilities(city="all", category=category)["facilities"]
    return {
        "location": location,
        "coordinates": {"lat": 24.8607, "lon": 67.0011},
        "results": [
            {"name": f["name"], "type": f["type"], "address": f["address"],
             "lat": f["lat"], "lon": f["lon"], "phone": f["phone"],
             "map_url": f"https://www.google.com/maps/search/?api=1&query={f['lat']},{f['lon']}"}
            for f in all_fac
        ],
        "is_fallback": True,
    }


# ---------------------------------------------------------------------------
# Emergency contacts
# ---------------------------------------------------------------------------
@app.get("/api/emergency")
def emergency():
    return [
        {"name": "Rescue 1122", "number": "1122", "type": "Emergency Ambulance & Fire Service", "coverage": "Nationwide", "source": "https://www.rescue.gov.pk/"},
        {"name": "Police Emergency", "number": "15", "type": "Law Enforcement & Security", "coverage": "Nationwide", "source": "https://sindhpolice.gov.pk/"},
        {"name": "Edhi Ambulance", "number": "115", "type": "Emergency Medical Transport & Relief", "coverage": "Nationwide", "source": "https://edhi.org/"},
        {"name": "Chhipa Ambulance", "number": "1020", "type": "24/7 Free Ambulance Service", "coverage": "Karachi & Sindh", "source": "https://www.chhipa.org/"},
        {"name": "BISP 8171 Helpline", "number": "0800-26477", "type": "Financial Aid & Kafalat Verification", "coverage": "Nationwide", "source": "https://www.bisp.gov.pk/"},
        {"name": "Pakistan Bait-ul-Mal", "number": "0800-66666", "type": "Emergency Medical & Orphan Aid", "coverage": "Nationwide", "source": "https://www.pbm.gov.pk/"},
        {"name": "Aman Ambulance", "number": "1021", "type": "Advanced Cardiac Ambulance", "coverage": "Karachi", "source": "https://sindhrescue.gos.pk/"},
        {"name": "Child Protection Helpline", "number": "1121", "type": "Child Safety & Orphan Protection", "coverage": "Nationwide", "source": "https://cpwb.punjab.gov.pk/"},
    ]


# ===================================================================
# USER AUTHENTICATION
# ===================================================================

@app.post("/api/auth/register")
def register_user(req: UserRegister):
    user = db.create_user(
        name=req.name.strip(), email=req.email.strip().lower(),
        password=req.password, phone=req.phone.strip(),
        city=req.city.strip(), cnic=req.cnic.strip(),
    )
    if not user:
        raise HTTPException(status_code=409, detail="Email already registered.")
    return {"success": True, "user": user, "message": "Registration successful. Please log in."}


@app.post("/api/auth/login")
def login_user(req: UserLogin):
    user_row = db.get_user_by_email(req.email.strip().lower())
    if not user_row:
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    # Re-fetch raw to get password_hash
    from .database import get_connection, verify_password
    conn = get_connection()
    try:
        raw = conn.execute("SELECT password_hash FROM users WHERE email=?", (req.email.strip().lower(),)).fetchone()
    finally:
        conn.close()
    if not raw or not verify_password(req.password, raw["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    user_row.pop("password_hash", None)
    token = f"user_{uuid.uuid4().hex[:16]}"
    return {"success": True, "token": token, "user": user_row}


# ---------------------------------------------------------------------------
# User welfare application tracking
# ---------------------------------------------------------------------------
@app.post("/api/user/apply")
def submit_welfare_application(req: WelfareApplication, x_user_email: str = Header(default="")):
    if not x_user_email:
        raise HTTPException(status_code=401, detail="Missing user email header.")
    user = db.get_user_by_email(x_user_email.strip().lower())
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    app_id = f"app_{uuid.uuid4().hex[:10]}"
    application = {
        "id": app_id,
        "program_id": req.program_id,
        "status": req.status or "pending",
        "notes": req.notes,
        "submitted_at": datetime.now().isoformat(),
    }
    from .database import update_user_applications, get_connection
    conn = get_connection()
    try:
        raw = conn.execute("SELECT applications FROM users WHERE id=?", (user["id"],)).fetchone()
        existing = json.loads(raw["applications"]) if raw else []
    finally:
        conn.close()
    existing.append(application)
    update_user_applications(user["id"], existing)
    return {"success": True, "application": application}


@app.get("/api/user/applications")
def get_user_applications(x_user_email: str = Header(default="")):
    if not x_user_email:
        raise HTTPException(status_code=401, detail="Missing user email header.")
    user = db.get_user_by_email(x_user_email.strip().lower())
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    return {"applications": user.get("applications", [])}


@app.put("/api/user/profile")
def update_user_profile(req: UserProfileUpdate, x_user_email: str = Header(default="")):
    """Update the signed-in user's editable profile details (email is read-only)."""
    if not x_user_email:
        raise HTTPException(status_code=401, detail="Missing user email header.")
    user = db.get_user_by_email(x_user_email.strip().lower())
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    if not req.name.strip():
        raise HTTPException(status_code=400, detail="Name cannot be empty.")
    cnic = req.cnic.strip()
    if cnic and not re.fullmatch(r"\d{5}-\d{7}-\d", cnic):
        raise HTTPException(
            status_code=400,
            detail="CNIC must use the format 42101-1234567-1 (or be left empty).",
        )
    updated = db.update_user_profile(
        user["id"], name=req.name, phone=req.phone, city=req.city, cnic=cnic
    )
    if not updated:
        raise HTTPException(status_code=404, detail="User not found.")
    updated.pop("password_hash", None)
    return {"success": True, "user": updated, "message": "Profile updated successfully."}


# ===================================================================
# ORGANIZATION LOGIN
# ===================================================================

@app.post("/api/organizations/login")
def org_login(req: OrgLogin):
    org = db.get_org_by_email(req.email.strip().lower())
    if not org:
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    if org.get("status") == "suspended":
        raise HTTPException(status_code=403, detail="Organization account is suspended. Please contact the KhidmatAI admin.")
    if org.get("status") != "approved":
        raise HTTPException(status_code=403, detail=f"Organization is {org.get('status')}. Only approved organizations can log in.")
    pw_hash = org.get("password_hash", "")
    if not pw_hash or not db.verify_password(req.password, pw_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    org.pop("password_hash", None)
    token = f"org_{uuid.uuid4().hex[:16]}"
    return {"success": True, "token": token, "organization": org}


# ===================================================================
# ORGANIZATION DASHBOARD (profile + posts, auth via X-Org-Email)
# ===================================================================

def _require_org(x_org_email: str) -> dict[str, Any]:
    """Resolve the signed-in organization from the X-Org-Email header."""
    if not x_org_email:
        raise HTTPException(status_code=401, detail="Missing organization email header.")
    org = db.get_org_by_email(x_org_email.strip().lower())
    if not org:
        raise HTTPException(status_code=401, detail="Organization not found.")
    status = org.get("status")
    if status == "suspended":
        raise HTTPException(status_code=403, detail="Organization account is suspended. Contact the KhidmatAI admin.")
    if status != "approved":
        raise HTTPException(status_code=403, detail=f"Organization is {status}. Only approved organizations can use the dashboard.")
    return org


@app.get("/api/org/me")
def org_me(x_org_email: str = Header(default="")):
    org = _require_org(x_org_email)
    org.pop("password_hash", None)
    return {"success": True, "organization": org}


@app.put("/api/org/me")
def org_update_me(req: OrgProfileUpdate, x_org_email: str = Header(default="")):
    org = _require_org(x_org_email)
    updated = db.update_org_profile(org["id"], req.model_dump())
    if not updated:
        raise HTTPException(status_code=404, detail="Organization not found.")
    updated.pop("password_hash", None)
    return {"success": True, "organization": updated, "message": "Organization profile updated successfully."}


@app.get("/api/org/posts")
def org_my_posts(x_org_email: str = Header(default="")):
    org = _require_org(x_org_email)
    posts = db.get_org_posts(org_id=org["id"])
    return {"success": True, "count": len(posts), "posts": posts}


@app.post("/api/org/posts")
def org_create_post(req: OrgPostCreate, x_org_email: str = Header(default="")):
    org = _require_org(x_org_email)
    post = {
        "id": f"post_{uuid.uuid4().hex[:10]}",
        "org_id": org["id"],
        "org_name": org.get("name", ""),
        "title": req.title.strip(),
        "description": req.description.strip(),
        "category": req.category.strip() or "General",
        "post_type": req.post_type.strip() or "Program",
        "eligibility": [str(x).strip() for x in req.eligibility if str(x).strip()],
        "documents": [str(x).strip() for x in req.documents if str(x).strip()],
        "location": req.location.strip(),
        "contact": req.contact.strip(),
        "website": req.website.strip(),
        "pricing": req.pricing.strip() or "Free",
        "image": req.image.strip(),
        "status": "pending",  # every org post goes through admin verification
    }
    created = db.insert_org_post(post)
    return {"success": True, "post": created, "message": "Post submitted for admin verification."}


@app.put("/api/org/posts/{post_id}")
def org_update_post(post_id: str, req: OrgPostUpdate, x_org_email: str = Header(default="")):
    org = _require_org(x_org_email)
    post = db.get_org_post_by_id(post_id)
    if not post or post.get("org_id") != org["id"]:
        raise HTTPException(status_code=404, detail="Post not found.")
    data = {k: v for k, v in req.model_dump().items() if v is not None}
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update.")
    if "title" in data and not str(data["title"]).strip():
        raise HTTPException(status_code=400, detail="Title cannot be empty.")
    if not db.update_org_post(post_id, data):
        raise HTTPException(status_code=404, detail="Post not found.")
    # Edited content must be re-verified before it is shown publicly again.
    if post.get("status") == "approved":
        db.update_org_post_status(post_id, "pending")
    return {"success": True, "post": db.get_org_post_by_id(post_id), "message": "Post updated and sent for re-verification."}


@app.delete("/api/org/posts/{post_id}")
def org_delete_post(post_id: str, x_org_email: str = Header(default="")):
    org = _require_org(x_org_email)
    post = db.get_org_post_by_id(post_id)
    if not post or post.get("org_id") != org["id"]:
        raise HTTPException(status_code=404, detail="Post not found.")
    db.delete_org_post(post_id)
    return {"success": True}


# ===================================================================
# FACILITIES (geo-collected from Overpass + curated)
# ===================================================================

@app.get("/api/facilities/db")
def get_db_facilities(city: str = "all", category: str = "all"):
    """Return facilities collected from the Overpass geo-scraper."""
    facilities = db.get_facilities_filtered(city=city, category=category)
    return {"status": "success", "count": len(facilities), "facilities": facilities}


@app.post("/api/admin/facilities/auto-collect")
def auto_collect_facilities(
    req: AutoCollectRequest,
    x_admin_key: str | None = Header(default=None),
):
    """Trigger Overpass API scrape to auto-populate facility locations."""
    from .admin import verify_admin
    verify_admin(x_admin_key)
    from .geo_scraper import collect_and_store
    cats = req.categories if req.categories else None
    result = collect_and_store(city=req.city, categories=cats)
    return {"success": True, **result}
