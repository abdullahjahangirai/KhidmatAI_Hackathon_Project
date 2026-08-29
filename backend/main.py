import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
import time
from dotenv import load_dotenv
from fastapi import FastAPI, Query, Depends, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .admin import router as admin_router

load_dotenv()

_rate_store: dict[str, list] = {}

def rate_limit(request: Request, max_calls: int = 30, window: int = 60):
    ip = request.client.host or '0.0.0.0'
    now = time.time()
    calls = _rate_store.get(ip, [])
    calls = [t for t in calls if now - t < window]
    if len(calls) >= max_calls:
        raise HTTPException(status_code=429, detail='Too many requests. Please wait a moment.')
    calls.append(now)
    _rate_store[ip] = calls

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND = BASE_DIR / "frontend"
DATA = BASE_DIR / "data"
DYNAMIC_FILE = DATA / "dynamic_welfare.json"

APP_NAME = os.getenv("APP_NAME", "KhidmatAI")

# AI API Keys and Models
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash").strip()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile").strip()

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "").strip()

DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "").strip()
DASHSCOPE_BASE_URL = os.getenv("DASHSCOPE_BASE_URL", "https://dashscope-intl.aliyuncs.com/compatible-mode/v1").strip()

OFFICIAL_DOMAINS = {
    "hec.gov.pk", "scholarship.hec.gov.pk", "alkhidmat.org", "pbm.gov.pk", "bisp.gov.pk",
    "seef.sindh.gov.pk", "sindh.gov.pk", "sef.org.pk", "uok.edu.pk", "neduet.edu.pk",
    "duhs.edu.pk", "duet.edu.pk", "fuuast.edu.pk", "bbsul.edu.pk", "iba.edu.pk",
    "khi.nu.edu.pk", "bahria.edu.pk", "aku.edu", "szabist.edu.pk", "iobm.edu.pk",
    "jsmu.edu.pk", "muet.edu.pk", "usindh.edu.pk", "quest.edu.pk", "lumhs.edu.pk",
    "saylaniwelfare.com", "jdcwelfare.org", "edhi.org", "akhuwat.org.pk", "pmyp.gov.pk",
    "navttc.gov.pk", "ehsaas.gov.pk", "pass.gov.pk", "punjab.gov.pk", "kp.gov.pk",
}

# Ensure dynamic_welfare.json exists
if not DYNAMIC_FILE.exists():
    DYNAMIC_FILE.write_text("[]", encoding="utf-8")


def load_all_datasets() -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Load and aggregate programs, assistance, hospitals, and dynamic records."""
    all_programs: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_titles: set[str] = set()

    data_files = [
        "programs.json",
        "assistance.json",
        "welfare_programs.json",
        "aid_and_support.json",
        "hospitals.json",
        "dynamic_welfare.json",
    ]

    for fname in data_files:
        fpath = DATA / fname
        if fpath.exists():
            try:
                items = json.loads(fpath.read_text(encoding="utf-8"))
                if isinstance(items, list):
                    for item in items:
                        if not isinstance(item, dict):
                            continue
                        pid = str(item.get("id", "")).strip()
                        title = str(item.get("title", "")).strip().lower()
                        if pid and pid in seen_ids:
                            continue
                        if title and title in seen_titles:
                            continue
                        if pid:
                            seen_ids.add(pid)
                        if title:
                            seen_titles.add(title)
                        all_programs.append(item)
            except Exception:
                pass

    universities = []
    uni_path = DATA / "universities.json"
    if uni_path.exists():
        try:
            universities = json.loads(uni_path.read_text(encoding="utf-8"))
        except Exception:
            universities = []

    hospitals = []
    hosp_path = DATA / "hospitals.json"
    if hosp_path.exists():
        try:
            hospitals = json.loads(hosp_path.read_text(encoding="utf-8"))
        except Exception:
            hospitals = []

    return all_programs, universities, hospitals


ALL_PROGRAMS, UNIVERSITIES, HOSPITALS = load_all_datasets()

app = FastAPI(title=APP_NAME, version="5.0")
app.mount("/static", StaticFiles(directory=FRONTEND), name="static")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(admin_router)


# ---------------------------------------------------------------------------
# Models
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


# ---------------------------------------------------------------------------
# Text & Query Utilities
# ---------------------------------------------------------------------------
def tokens(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", str(value).lower()))


def detect_language(text: str, requested: str = "english") -> str:
    if requested in {"english", "roman", "urdu"}:
        return requested
    return "english"


# ---------------------------------------------------------------------------
# Rate Limiting (in-memory, per IP)
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
    cities = []
    for city in ["Karachi", "Larkana", "Hyderabad", "Sukkur", "Islamabad", "Rawalpindi", "Lahore", "Quetta", "Peshawar", "Multan", "Faisalabad"]:
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


def program_text(p: dict[str, Any]) -> str:
    return " ".join([
        str(p.get("title", "")),
        str(p.get("category", "")),
        str(p.get("type", "")),
        str(p.get("description", "")),
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
    global ALL_PROGRAMS
    profile = extract_profile(query)
    requested_categories = set(detect_categories(query))
    candidates = ALL_PROGRAMS
    if requested_categories:
        candidates = [p for p in ALL_PROGRAMS if any(c.lower() in str(p.get("category", "")).lower() for c in requested_categories)]
        if len(candidates) < 3:
            candidates = ALL_PROGRAMS

    if profile.get("education_level", "").startswith("Intermediate"):
        candidates = [p for p in candidates if p.get("id") not in {"bisp_taleemi", "bisp_nashonuma"}]

    ranked = sorted(((score_program(p, query, profile), p) for p in candidates), key=lambda x: x[0], reverse=True)
    results = [p for score, p in ranked if score > 0][:limit]
    if not results and ALL_PROGRAMS:
        results = ALL_PROGRAMS[:limit]
    return results


def is_official(url: str) -> bool:
    try:
        host = (urlparse(url).hostname or "").lower().removeprefix("www.")
        return host in OFFICIAL_DOMAINS or any(host.endswith("." + d) for d in OFFICIAL_DOMAINS)
    except Exception:
        return False


def clean_official_url(url: str) -> str:
    return url if is_official(url) else url or ""


# ---------------------------------------------------------------------------
# Tavily Search & Dynamic Auto-Saving
# ---------------------------------------------------------------------------
def web_search(query: str) -> list[dict[str, str]]:
    if not TAVILY_API_KEY or TAVILY_API_KEY.startswith("yahan_"):
        return []
    try:
        response = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": TAVILY_API_KEY,
                "query": f"{query} Pakistan official social welfare scheme eligibility",
                "search_depth": "advanced",
                "max_results": 5,
                "include_answer": True,
                "include_raw_content": False,
            },
            timeout=12,
        )
        response.raise_for_status()
        data = response.json()
        results = []
        for item in data.get("results", []):
            url = item.get("url", "")
            results.append({
                "title": item.get("title", "Official source"),
                "url": url,
                "content": (item.get("content") or "")[:2000],
            })
        return results
    except Exception:
        return []


def dynamic_save_program(item: dict[str, Any]) -> bool:
    """Save a newly discovered welfare program into dynamic_welfare.json and reload in-memory cache."""
    global ALL_PROGRAMS
    if not item.get("title"):
        return False
    try:
        records = []
        if DYNAMIC_FILE.exists():
            try:
                records = json.loads(DYNAMIC_FILE.read_text(encoding="utf-8"))
            except Exception:
                records = []

        # Check duplicate
        title_lower = str(item.get("title")).strip().lower()
        if any(str(r.get("title")).strip().lower() == title_lower for r in records):
            return False

        # Set default attributes
        slug = re.sub(r"[^a-z0-9]+", "_", title_lower)[:35].strip("_")
        entry = {
            "id": f"dynamic_{slug}_{int(datetime.now().timestamp())}",
            "title": str(item.get("title", "New Welfare Program")),
            "category": str(item.get("category", "General Welfare")),
            "type": str(item.get("type", "Government / NGO Initiative")),
            "description": str(item.get("description", "Discovered through live verified search.")),
            "support": item.get("support") if isinstance(item.get("support"), list) else [str(item.get("support", "Welfare Assistance"))],
            "eligibility": item.get("eligibility") if isinstance(item.get("eligibility"), list) else [str(item.get("eligibility", "Check official details."))],
            "documents": item.get("documents") if isinstance(item.get("documents"), list) else ["CNIC", "Proof of Residence / Income"],
            "application": str(item.get("application", "Visit the official portal or nearest facilitation desk.")),
            "locations": item.get("locations") if isinstance(item.get("locations"), list) else ["Pakistan"],
            "source_name": str(item.get("source_name", "Live Verified Web Search")),
            "source_url": str(item.get("source_url", "")),
            "verified_at": datetime.now().strftime("%Y-%m-%d"),
            "dynamic_saved": True,
        }

        records.append(entry)
        DYNAMIC_FILE.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
        ALL_PROGRAMS.insert(0, entry)
        return True
    except Exception:
        return False


def check_and_auto_save_from_search(query: str, search_results: list[dict[str, str]]) -> tuple[dict[str, Any] | None, bool]:
    """If search returns a new welfare scheme not currently in local DB, auto-save it."""
    if not search_results:
        return None, False

    welfare_keywords = {"scheme", "program", "programme", "wazifa", "scholarship", "rashan", "fund", "subsidy", "kafalat", "relief", "grant", "hospital", "clinic", "trust"}
    query_tokens = tokens(query)

    for item in search_results:
        title = item.get("title", "").strip()
        content = item.get("content", "").strip()
        item_tokens = tokens(title + " " + content)
        
        # Check if relevant welfare initiative
        if not (item_tokens & welfare_keywords):
            continue

        # Check if already present in ALL_PROGRAMS
        clean_title_toks = tokens(title)
        already_exists = False
        for p in ALL_PROGRAMS:
            p_toks = tokens(p.get("title", ""))
            if len(clean_title_toks & p_toks) >= max(2, len(clean_title_toks) * 0.7):
                already_exists = True
                break

        if not already_exists and len(title) > 5:
            # Extract structured record
            categories = detect_categories(title + " " + content)
            cat = categories[0] if categories else "Financial Aid"
            new_item = {
                "title": title[:100],
                "category": cat,
                "type": "Live Verified Scheme",
                "description": content[:220] if len(content) > 10 else f"Support program for {title}",
                "support": ["Financial / Material Assistance", "Verified official support pathway"],
                "eligibility": ["Pakistani citizens meeting designated criteria", "Valid CNIC or B-Form required"],
                "documents": ["CNIC / B-Form", "Application Form"],
                "application": f"Apply via {urlparse(item.get('url', '')).netloc or 'official portal'}.",
                "locations": ["All Pakistan"],
                "source_name": urlparse(item.get("url", "")).netloc or "Official Portal",
                "source_url": item.get("url", ""),
            }
            saved = dynamic_save_program(new_item)
            if saved:
                return new_item, True

    return None, False


# ---------------------------------------------------------------------------
# Dual AI Provider Fallback Handler (Gemini -> Groq -> DashScope -> Fallback)
# ---------------------------------------------------------------------------
def call_gemini(system_prompt: str, user_prompt: str) -> str | None:
    """Call Google Gemini API via REST with structured JSON format."""
    if not GEMINI_API_KEY or GEMINI_API_KEY.startswith("your_"):
        return None
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": f"SYSTEM INSTRUCTION:\n{system_prompt}\n\nUSER PROMPT:\n{user_prompt}"}
                    ],
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 800,
                "responseMimeType": "application/json",
            },
        }
        res = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=10)
        res.raise_for_status()
        data = res.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        return text
    except Exception:
        return None


def call_groq(system_prompt: str, user_prompt: str) -> str | None:
    """Call Groq API via REST (OpenAI-compatible) with fallback."""
    if not GROQ_API_KEY or GROQ_API_KEY.startswith("your_"):
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
            "max_tokens": 800,
            "response_format": {"type": "json_object"},
        }
        res = requests.post(url, json=payload, headers=headers, timeout=10)
        res.raise_for_status()
        data = res.json()
        return data["choices"][0]["message"]["content"]
    except Exception:
        return None


def call_dashscope(system_prompt: str, user_prompt: str) -> str | None:
    """Call DashScope / Qwen API if configured."""
    if not DASHSCOPE_API_KEY or DASHSCOPE_API_KEY.startswith("your_") or DASHSCOPE_API_KEY.startswith("yahan_"):
        return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=DASHSCOPE_API_KEY, base_url=DASHSCOPE_BASE_URL)
        res = client.chat.completions.create(
            model="qwen3.6-plus",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            max_tokens=600,
            response_format={"type": "json_object"},
        )
        return res.choices[0].message.content
    except Exception:
        return None


def call_llm_with_fallback(system_prompt: str, user_prompt: str) -> tuple[str | None, str]:
    """
    Robust Dual AI Provider Handler:
    1. Try Primary: Google Gemini API
    2. Fallback: Groq Cloud API
    3. Tertiary: DashScope Qwen
    4. Safety: Deterministic Mode
    """
    # 1. Primary AI: Google Gemini
    if GEMINI_API_KEY and not GEMINI_API_KEY.startswith("your_"):
        res = call_gemini(system_prompt, user_prompt)
        if res:
            return res, f"Google Gemini ({GEMINI_MODEL}) [Primary]"

    # 2. Secondary AI: Groq Cloud Failover
    if GROQ_API_KEY and not GROQ_API_KEY.startswith("your_"):
        res = call_groq(system_prompt, user_prompt)
        if res:
            return res, f"Groq Cloud ({GROQ_MODEL}) [Failover]"

    # 3. Tertiary: Dashscope
    if DASHSCOPE_API_KEY and not DASHSCOPE_API_KEY.startswith("your_"):
        res = call_dashscope(system_prompt, user_prompt)
        if res:
            return res, "DashScope Qwen [Legacy Provider]"

    return None, "Deterministic Verified Mode"


def localized(language: str, english: Any, roman: Any, urdu: Any) -> Any:
    return {"english": english, "roman": roman, "urdu": urdu}.get(language, english)


def deterministic_answer(matches: list[dict[str, Any]], language: str, profile: dict[str, Any]) -> dict[str, Any]:
    count = len(matches)
    summary = localized(
        language,
        f"Found {count} verified official support options for your query. Final approval is determined by the respective institution.",
        f"Aap ke liye {count} verified official options mile hain. Final eligibility related organization decide karegi.",
        f"آپ کے لیے {count} تصدیق شدہ سرکاری فلاحی پروگرام دستیاب ہیں۔ حتمی اہلیت متعلقہ ادارہ طے کرے گا۔",
    )
    programs = []
    for p in matches:
        programs.append({
            "title": p.get("title", ""),
            "match_level": "Potential match",
            "why_match": p.get("description", "")[:180],
            "support": p.get("support", []),
            "eligibility": p.get("eligibility", []),
            "documents": p.get("documents", []),
            "application": p.get("application", "Check the official source."),
            "source_name": p.get("source_name", "Official source"),
            "source_url": p.get("source_url", ""),
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
        "questions": questions,
        "next_steps": localized(
            language,
            ["Check the official website or nearest center for current intake.", "Keep CNIC, income slip, and academic documents ready."],
            ["Current application cycle ke liye official portal ya center check karein.", "CNIC aur zaroori documents tayar rakhein."],
            ["موجودہ درخواست کے لیے سرکاری ویب سائٹ یا قریبی مرکز سے رجوع کریں۔", "شناختی کارڈ اور ضروری دستاویزات تیار رکھیں۔"],
        ),
    }


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


def build_safe_answer(model_answer: dict[str, Any] | None, matches: list[dict[str, Any]], language: str, profile: dict[str, Any]) -> dict[str, Any]:
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

        programs.append({
            "title": p.get("title", ""),
            "match_level": match_level,
            "why_match": str(g.get("why_match") or p.get("description", ""))[:200],
            "support": p.get("support", []),
            "eligibility": p.get("eligibility", []),
            "documents": p.get("documents", []),
            "application": p.get("application", "Check the official source."),
            "source_name": p.get("source_name", "Official source"),
            "source_url": clean_official_url(p.get("source_url", "")),
            "verified_at": p.get("verified_at", ""),
        })

    questions = model_answer.get("questions")
    if not isinstance(questions, list) or not questions:
        questions = fallback["questions"]
    next_steps = model_answer.get("next_steps")
    if not isinstance(next_steps, list) or not next_steps:
        next_steps = fallback["next_steps"]

    summary_text = str(model_answer.get("summary") or fallback["summary"]).strip()
    return {
        "summary": summary_text,
        "programs": programs,
        "questions": [str(q) for q in questions[:4]],
        "next_steps": [str(x) for x in next_steps[:4]],
    }


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------
@app.get("/")
def root():
    return FileResponse(FRONTEND / "index.html")


@app.get("/admin")
def admin_panel():
    return FileResponse(FRONTEND / "admin.html")


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "primary_ai": "gemini" if GEMINI_API_KEY and not GEMINI_API_KEY.startswith("your_") else "not_configured",
        "fallback_ai": "groq" if GROQ_API_KEY and not GROQ_API_KEY.startswith("your_") else "not_configured",
        "search_configured": bool(TAVILY_API_KEY and not TAVILY_API_KEY.startswith("yahan_")),
        "programs_count": len(ALL_PROGRAMS),
        "universities_count": len(UNIVERSITIES),
        "hospitals_count": len(HOSPITALS),
    }


@app.get("/api/config")
def config():
    active_model = "Google Gemini" if GEMINI_API_KEY and not GEMINI_API_KEY.startswith("your_") else ("Groq Cloud" if GROQ_API_KEY and not GROQ_API_KEY.startswith("your_") else "Deterministic Mode")
    return {
        "app": APP_NAME,
        "languages": ["auto", "english", "roman", "urdu"],
        "active_model": active_model,
        "gemini_configured": bool(GEMINI_API_KEY and not GEMINI_API_KEY.startswith("your_")),
        "groq_configured": bool(GROQ_API_KEY and not GROQ_API_KEY.startswith("your_")),
        "search_configured": bool(TAVILY_API_KEY and not TAVILY_API_KEY.startswith("yahan_")),
    }


@app.get("/api/programs")
def programs(category: str = "all", q: str = "", province: str = "all"):
    data = ALL_PROGRAMS
    if category != "all" and category.strip():
        data = [p for p in data if category.lower() in str(p.get("category", "")).lower()]
    if province != "all" and province.strip():
        prov_low = province.lower().strip()
        data = [
            p for p in data
            if "all pakistan" in [str(x).lower() for x in p.get("locations", [])]
            or any(prov_low in str(x).lower() for x in p.get("locations", []))
            or prov_low in program_text(p).lower()
        ]
    if q.strip():
        qt = tokens(q)
        data = [p for p in data if qt & tokens(program_text(p))]
    return data


@app.get("/api/universities")
def universities(city: str = "Karachi", q: str = ""):
    c_low = city.strip().lower()
    data = []
    for u in UNIVERSITIES:
        u_city = str(u.get("city", "")).lower()
        u_locs = [str(x).lower() for x in u.get("locations", [])]
        u_addr = str(u.get("address", "")).lower()
        u_desc = str(u.get("description", "")).lower()
        if not c_low or c_low in u_city or any(c_low in loc for loc in u_locs) or c_low in u_addr or c_low in u_desc or "all pakistan" in u_locs or not u_city:
            data.append(u)

    if q.strip():
        qt = tokens(q)
        data = [u for u in data if qt & tokens(str(u.get("title", "") or u.get("name", "")) + " " + " ".join(u.get("keywords", [])))]
    return data


@app.post("/api/chat", dependencies=[Depends(rate_limit)])
def chat(req: ChatRequest):
    language = detect_language(req.message, req.language)
    profile = extract_profile(req.message)
    matches = retrieve_programs(req.message, 5)

    # Tavily Web Search
    search_query = f"{req.message} Pakistan social welfare scholarship scheme"
    web = web_search(search_query)

    # Dynamic JSON Auto-Saving if new program discovered
    new_saved_item, newly_saved = check_and_auto_save_from_search(req.message, web)

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

    system_prompt = """You are KhidmatAI, Pakistan's welfare navigator. Be EXTREMELY concise.
Rules: 1) No conversational filler. 2) summary = max 2 sentences. 3) why_match = max 10 words. 4) Use ONLY the provided records.
Output strict JSON: {"summary": "...", "programs": [{"title": "", "match_level": "", "why_match": ""}], "questions": ["..."], "next_steps": ["..."]}
Language for all text: """ + language

    user_prompt = f"VERIFIED RECORDS:\n{json.dumps(records, ensure_ascii=False, indent=2)}\n\n"
    if web:
        user_prompt += f"WEB SEARCH EVIDENCE:\n{json.dumps(web[:3], ensure_ascii=False, indent=2)}\n\n"
    user_prompt += f"USER PROFILE: {json.dumps(profile, ensure_ascii=False)}\n"
    user_prompt += f"REQUESTED LANGUAGE: {language}\n"
    user_prompt += f"USER QUERY: {req.message}"

    raw, model_used = call_llm_with_fallback(system_prompt, user_prompt)
    answer = build_safe_answer(parse_json(raw), matches, language, profile)

    confirmation_note = ""
    if newly_saved and new_saved_item:
        confirmation_note = localized(
            language,
            f" I found new information online regarding '{new_saved_item.get('title')}' and automatically added it to our verified welfare records!",
            f" Maine online '{new_saved_item.get('title')}' ke baray mein nayi maloomat talaash kar ke hamare welfare records mein shamil kar di hai!",
            f" میں نے آن لائن '{new_saved_item.get('title')}' سے متعلق نئی معلومات تلاش کر کے ہمارے فلاحی ریکارڈ میں شامل کر دی ہے!",
        )
        answer["summary"] = f"{confirmation_note}\n\n{answer['summary']}"

    return {
        "answer": answer,
        "model_used": model_used,
        "language": language,
        "profile": profile,
        "matches": matches,
        "sources": web,
        "new_info_saved": newly_saved,
        "saved_item": new_saved_item,
        "counts": {"matches": len(matches), "official_sources": len(web)},
    }


@app.post("/api/recommend")
def recommend(req: RecommendRequest):
    combined = f"{req.need} {req.location} {json.dumps(req.profile, ensure_ascii=False)}"
    profile = extract_profile(combined, req.profile)
    matches = retrieve_programs(combined, 6)
    web = web_search(f"{combined} Pakistan official scholarship welfare")
    return {"matches": matches, "sources": web, "language": detect_language(req.need, req.language), "profile": profile}


@app.post("/api/eligibility")
def check_eligibility_engine(req: EligibilityRequest):
    """
    Intelligent Eligibility Engine: Evaluates user parameters (income, family size,
    employment, location, category) against all verified welfare records.
    """
    user_city = req.city.strip().lower()
    req_cat = req.category.strip().lower()
    emp_status = req.employment_status.strip().lower()

    # Parse income number
    income_num = 1000000
    if req.income:
        nums = re.findall(r"\d+", req.income.replace(",", ""))
        if nums:
            income_num = int(nums[0])
            if income_num < 1000:  # e.g. "25" meaning 25k
                income_num *= 1000

    results = []
    for p in ALL_PROGRAMS:
        score = 0
        reasons = []
        p_text = program_text(p).lower()
        p_cat = str(p.get("category", "")).lower()
        p_locs = [str(x).lower() for x in p.get("locations", [])]

        # 1. Location match
        if "all pakistan" in p_locs or not user_city or any(user_city in loc for loc in p_locs):
            score += 25
            if user_city and any(user_city in loc for loc in p_locs):
                reasons.append(f"Available in your city / region ({req.city})")

        # 2. Category match
        if req_cat == "all" or req_cat in p_cat:
            score += 25
            reasons.append(f"Matches category: {p.get('category', 'Support')}")

        # 3. Income evaluation
        if "income" in p_text or "poverty" in p_text or "25,000" in p_text or "50,000" in p_text or "low-income" in p_text:
            if income_num <= 30000:
                score += 30
                reasons.append("Income fits priority low-income threshold (<= Rs. 30,000)")
            elif income_num <= 60000:
                score += 20
                reasons.append("Income qualifies for general financial / scholarship aid")
        else:
            score += 15

        # 4. Employment & Special criteria
        if "student" in emp_status or "intermediate" in req.education_level.lower() or "undergraduate" in req.education_level.lower():
            if "education" in p_cat or "scholarship" in p_text or "training" in p_text:
                score += 25
                reasons.append("Academic & student profile qualifies for scholarship/stipend")

        if "widow" in emp_status or "female" in emp_status:
            if "widow" in p_text or "women" in p_text or "kafalat" in p_text:
                score += 30
                reasons.append("Special priority allocated for female/widow-headed households")

        if "unemployed" in emp_status or "daily wage" in emp_status:
            if "financial" in p_cat or "food" in p_cat or "cash" in p_text or "ration" in p_text or "pbm" in p.get("id", ""):
                score += 25
                reasons.append("Eligible for emergency cash grant & ration assistance")

        if "disab" in emp_status or "mazoor" in emp_status:
            if "disab" in p_text or "special" in p_text:
                score += 35
                reasons.append("Special disability quota and assistance applicable")

        if score >= 40:
            match_level = "Highly Eligible" if score >= 75 else ("Potential Match" if score >= 50 else "General Support")
            results.append({
                "score": min(score, 98),
                "match_level": match_level,
                "reasons": reasons,
                "program": p,
            })

    results.sort(key=lambda x: x["score"], reverse=True)
    return {
        "status": "success",
        "total_evaluated": len(ALL_PROGRAMS),
        "matches_count": len(results),
        "matches": results[:10],
    }


@app.get("/api/facilities")
def get_facilities(city: str = "Karachi", category: str = "all"):
    """Returns curated facilities with exact coordinates for the interactive map."""
    curated = [
        # Karachi Hospitals
        {"id": "civ_khi", "name": "Dr. Ruth Pfau Civil Hospital", "category": "hospital", "city": "Karachi", "zone": "Saddar / South", "lat": 24.8608, "lon": 67.0104, "address": "Mission Road, Ranchore Line, Karachi", "phone": "021-99215740", "type": "Public Tertiary Hospital (Free Care)"},
        {"id": "jpmc_khi", "name": "Jinnah Postgraduate Medical Centre (JPMC)", "category": "hospital", "city": "Karachi", "zone": "Cantt / Jamshed", "lat": 24.8532, "lon": 67.0456, "address": "Rafiqui Shaheed Road, Cantt, Karachi", "phone": "021-99201300", "type": "Public Teaching & CyberKnife Center"},
        {"id": "indus_khi", "name": "The Indus Hospital (Korangi)", "category": "hospital", "city": "Karachi", "zone": "Korangi", "lat": 24.8315, "lon": 67.1157, "address": "Plot C-76, Sector 31/5, Korangi Crossing, Karachi", "phone": "021-111-111-880", "type": "100% Free Quality Healthcare"},
        {"id": "siut_khi", "name": "Sindh Institute of Urology & Transplantation (SIUT)", "category": "hospital", "city": "Karachi", "zone": "Saddar", "lat": 24.8587, "lon": 67.0123, "address": "Civil Hospital Compound, Saddar, Karachi", "phone": "021-99215720", "type": "Free Dialysis, Urology & Transplants"},
        {"id": "nicvd_khi", "name": "National Institute of Cardiovascular Diseases (NICVD)", "category": "hospital", "city": "Karachi", "zone": "Cantt", "lat": 24.8517, "lon": 67.0423, "address": "Rafiqui Shaheed Road, Karachi", "phone": "021-99201271", "type": "Free Cardiac & Heart Surgeries"},
        {"id": "aku_khi", "name": "Aga Khan University Hospital (Patient Welfare)", "category": "hospital", "city": "Karachi", "zone": "Gulshan-e-Iqbal", "lat": 24.8918, "lon": 67.0747, "address": "Stadium Road, Gulshan-e-Iqbal, Karachi", "phone": "021-111-911-911", "type": "Need-Based Patient Welfare Fund"},
        {"id": "abbasi_khi", "name": "Abbasi Shaheed Hospital", "category": "hospital", "city": "Karachi", "zone": "Nazimabad / Central", "lat": 24.9192, "lon": 67.0325, "address": "Paposh Nagar, Nazimabad, Karachi", "phone": "021-99260400", "type": "Public General & Trauma Hospital"},
        {"id": "duhs_ojha", "name": "Dow University Hospital (Ojha Campus)", "category": "hospital", "city": "Karachi", "zone": "Gulzar-e-Hijri / Scheme 33", "lat": 24.9452, "lon": 67.1145, "address": "University Road, Gulzar-e-Hijri, Karachi", "phone": "021-99232660", "type": "Subsidized Multi-Specialty Hospital"},

        # Karachi Welfare & Food Points
        {"id": "saylani_hds", "name": "Saylani Welfare International Head Office", "category": "welfare", "city": "Karachi", "zone": "Bahadurabad / Gulshan", "lat": 24.8825, "lon": 67.0694, "address": "A-25, Char Murti Chowrangi, Bahadurabad, Karachi", "phone": "021-111-729-526", "type": "Free Dastarkhwan, Ration & Mass IT"},
        {"id": "alkhidmat_khi", "name": "Alkhidmat Foundation Karachi Complex", "category": "welfare", "city": "Karachi", "zone": "Gulshan-e-Iqbal", "lat": 24.9175, "lon": 67.0921, "address": "501, Quaideen Colony, Gulshan-e-Iqbal, Karachi", "phone": "021-111-503-504", "type": "Disaster Relief, Orphan Care & Water"},
        {"id": "jdc_khi", "name": "JDC Welfare Foundation Headquarters", "category": "welfare", "city": "Karachi", "zone": "Ancholi / F.B. Area", "lat": 24.9392, "lon": 67.0784, "address": "Block 20, Ancholi, Federal B Area, Karachi", "phone": "021-36341051", "type": "Free Dialysis, Emergency & Ration"},
        {"id": "edhi_tower", "name": "Edhi Foundation Central Tower", "category": "welfare", "city": "Karachi", "zone": "Bolton Market / Kharadar", "lat": 24.8510, "lon": 66.9984, "address": "Sarafa Bazaar, Boulton Market, Karachi", "phone": "021-32413232 / 115", "type": "24/7 Ambulance, Shelter & Ration"},
        {"id": "bisp_khi_central", "name": "BISP Regional Facilitation Center Karachi", "category": "welfare", "city": "Karachi", "zone": "Saddar", "lat": 24.8621, "lon": 67.0210, "address": "State Life Building No. 11, Abdullah Haroon Rd, Karachi", "phone": "0800-26477", "type": "Kafaalat Registration & 8171 Desk"},
        {"id": "pbm_khi_office", "name": "Pakistan Bait-ul-Mal District Office Karachi", "category": "welfare", "city": "Karachi", "zone": "Clifton", "lat": 24.8214, "lon": 67.0345, "address": "Block 5, Clifton, Karachi", "phone": "021-99251433", "type": "Individual Financial Assistance (IFA)"},

        # Universities in Karachi
        {"id": "uok_khi", "name": "University of Karachi (Financial Aid Office)", "category": "university", "city": "Karachi", "zone": "University Road", "lat": 24.9416, "lon": 67.1141, "address": "Main University Road, Karachi", "phone": "021-99261300", "type": "HEC Need-Based & Sindh SEEF Portal"},
        {"id": "ned_khi", "name": "NED University of Engineering & Technology", "category": "university", "city": "Karachi", "zone": "Gulshan / University Rd", "lat": 24.9328, "lon": 67.1118, "address": "University Road, Karachi", "phone": "021-99261261", "type": "Engineering Scholarships & Endowment Fund"},

        # Major Pakistan Cities
        {"id": "lahore_mayo", "name": "Mayo Hospital Lahore", "category": "hospital", "city": "Lahore", "zone": "Anarkali", "lat": 31.5762, "lon": 74.3129, "address": "Hospital Road, Anarkali Bazaar, Lahore", "phone": "042-99211100", "type": "Public Teaching Hospital"},
        {"id": "lahore_akhuwat", "name": "Akhuwat Foundation Head Office Lahore", "category": "welfare", "city": "Lahore", "zone": "Township", "lat": 31.4504, "lon": 74.3095, "address": "19-Civic Center, Township, Lahore", "phone": "042-111-448-464", "type": "Interest-Free Microfinance & Education"},
        {"id": "isb_pims", "name": "Pakistan Institute of Medical Sciences (PIMS)", "category": "hospital", "city": "Islamabad", "zone": "G-8/3", "lat": 33.7036, "lon": 73.0531, "address": "Sector G-8/3, Islamabad", "phone": "051-9261170", "type": "Federal Tertiary Care Hospital"},
        {"id": "isb_pbm", "name": "Pakistan Bait-ul-Mal Federal Headquarters", "category": "welfare", "city": "Islamabad", "zone": "H-8/4", "lat": 33.6844, "lon": 73.0479, "address": "Street No. 7, Sector H-8/4, Islamabad", "phone": "0800-66666", "type": "National Welfare Grants & Orphanages"},
        {"id": "peshawar_lrh", "name": "Lady Reading Hospital (LRH)", "category": "hospital", "city": "Peshawar", "zone": "Peshawar City", "lat": 34.0125, "lon": 71.5785, "address": "PTCL Colony, Peshawar, Khyber Pakhtunkhwa", "phone": "091-9211430", "type": "Public Tertiary Hospital"},
        {"id": "quetta_cmh", "name": "Civil Hospital Quetta (Sandeman Provincial)", "category": "hospital", "city": "Quetta", "zone": "Jinnah Road", "lat": 30.1956, "lon": 67.0177, "address": "Jinnah Road, Quetta, Balochistan", "phone": "081-9202014", "type": "Provincial Teaching Hospital"},
    ]

    filtered = curated
    if city and city.lower() != "all":
        filtered = [f for f in filtered if f.get("city", "").lower() == city.lower()]
    if category and category.lower() != "all":
        filtered = [f for f in filtered if f.get("category", "").lower() == category.lower()]

    return {"status": "success", "city": city, "category": category, "count": len(filtered), "facilities": filtered}


@app.get("/api/nearby")
def nearby(location: str = Query(..., min_length=2, max_length=200), category: str = "all"):
    """Searches nearby places via OpenStreetMap Overpass with fallback to curated facilities."""
    try:
        geo = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": f"{location}, Pakistan", "format": "json", "limit": 1},
            headers={"User-Agent": "KhidmatAI-Navigator/5.0"},
            timeout=8,
        ).json()

        lat, lon = (24.8607, 67.0011)  # Default Karachi
        if geo and len(geo) > 0:
            lat, lon = float(geo[0]["lat"]), float(geo[0]["lon"])

        filters = {
            "hospital": '[amenity=hospital]',
            "clinic": '[amenity=clinic]',
            "pharmacy": '[amenity=pharmacy]',
            "university": '[amenity=university]',
            "school": '[amenity=school]',
            "welfare": '[amenity~"social_facility|community_centre|food_sharing"]',
        }
        selector = filters.get(category, '[amenity~"hospital|clinic|pharmacy|social_facility|school|university"]')
        query = f'[out:json][timeout:15];nwr(around:8000,{lat},{lon}){selector};out center 35;'

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
                    "lat": center["lat"],
                    "lon": center["lon"],
                    "phone": tags.get("phone", tags.get("contact:phone", "")),
                    "map_url": f"https://www.google.com/maps/search/?api=1&query={center['lat']},{center['lon']}",
                })
            if results:
                return {"location": location, "coordinates": {"lat": lat, "lon": lon}, "results": results}
    except Exception:
        pass

    # Fallback to curated facilities
    all_fac = get_facilities(city="all", category=category)["facilities"]
    return {
        "location": location,
        "coordinates": {"lat": 24.8607, "lon": 67.0011},
        "results": [
            {
                "name": f["name"],
                "type": f["type"],
                "address": f["address"],
                "lat": f["lat"],
                "lon": f["lon"],
                "phone": f["phone"],
                "map_url": f"https://www.google.com/maps/search/?api=1&query={f['lat']},{f['lon']}",
            }
            for f in all_fac
        ],
        "is_fallback": True,
    }


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

