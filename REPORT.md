# KhidmatAI — Architecture & Implementation Report

## Platform Upgrade Summary

KhidmatAI has been upgraded from a JSON-file-based MVP to a **production-ready, professional welfare navigation platform** with SQLite persistence, a LangGraph AI agent, multi-model fallback chain, user authentication, and a polished unified UI. The latest release integrates the dedicated landing page design as the canonical homepage and unifies every page (landing, login, register, dashboard, chat, admin) under one Manrope/green design language with a shared dark/light theme.

---

## 1. Backend & Database Migration (SQLite)

### Database Schema

All JSON file storage (`programs.json`, `admin_data.json`, etc.) has been replaced with a robust **SQLite database** (`khidmatai.db`), managed by `backend/database.py`.

| Table | Purpose |
|---|---|
| `programs` | Welfare programs with eligibility, documents, categories, locations, source URLs |
| `universities` | University scholarship records (same schema as programs) |
| `organizations` | NGO/Welfare body registrations with status: `pending` / `approved` / `rejected` |
| `settings` | Key-value store for contact info, ticker announcements, hero slides (JSON-serialised) |
| `users` | User accounts with bcrypt-hashed passwords, CNIC, city, application tracking |

### Auto-Seeding

On first startup, `init_db()` automatically:
1. Creates all tables if they don't exist
2. Seeds `programs` from `programs.json`, `assistance.json`, `welfare_programs.json`, `aid_and_support.json`, `hospitals.json`, `dynamic_welfare.json`
3. Seeds `universities` from `universities.json`
4. Seeds default `settings` (contact info, ticker text, hero slides)

JSON files in `data/` remain as the initial seed source but are no longer read at runtime.

### Key Files

| File | Responsibility |
|---|---|
| `backend/database.py` | SQLite connection, schema, CRUD operations, seeding, password hashing (direct `bcrypt` library) |
| `backend/agent.py` | LangGraph agentic workflow, model fallback chain, Tavily search |
| `backend/main.py` | FastAPI app, all public API endpoints, user auth, eligibility engine |
| `backend/admin.py` | Admin dashboard API routes (settings, slides, orgs, ticker) |

---

## 2. LangGraph AI Agent & Multi-Model Fallback Chain

### Agentic Workflow (`backend/agent.py`)

The chatbot uses a **LangGraph StateGraph** with three sequential nodes:

```
User Query
    │
    ▼
┌──────────────────┐
│  retrieve_db     │  Step 1: Query SQLite programs table
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  search_web      │  Step 2: Tavily web search (enrichment)
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  synthesize      │  Step 3: LLM synthesis with fallback chain
└──────────────────┘
```

### Model Fallback Chain

The `call_llm_with_fallback()` function tries models in strict order:

| Priority | Provider | Model | Purpose |
|---|---|---|---|
| 1 (Primary) | DashScope | `qwen3.7-plus` | Main reasoning model |
| 2 (Secondary) | DashScope | `qwen3.6-plus` | Fallback if primary fails |
| 3 (Tertiary) | DashScope | `qwen3.6-flash` | Fast fallback |
| 4 (Last Resort) | Groq | `llama-3.3-70b-versatile` | Emergency fallback |
| 5 (Safety Net) | — | Deterministic Mode | Template-based answer from DB records |

All DashScope calls use the OpenAI-compatible endpoint: `https://dashscope-intl.aliyuncs.com/compatible-mode/v1`

### Safety Rules

The system prompt enforces:
- **Never invent financial amounts, eligibility rules, or deadlines**
- Use ONLY verified records from the database
- Max 2-sentence summary, max 10-word match explanations
- Structured JSON output only

---

## 3. Frontend Architecture

### Unified Design System (`khidmat.css`)

Every page shares one stylesheet built on the landing-page design language:

- **Typography**: Manrope (Google Fonts) across all pages
- **Palette**: brand green `#087b5a`, navy `#073b59`, gold accents, CSS custom properties
- **Theme**: single persisted dark/light toggle (`khidmat-theme` in localStorage) shared by landing, auth, dashboard, chat and admin-adjacent pages
- **Language**: UI is English-only; the language selector, i18n dictionary and RTL switching were removed. The chatbot still understands natural multilingual user input.

### Public Landing Page (`index.html` + `landing.js`)

The dedicated landing page design is now the canonical homepage served at `/`:

- Hero with community imagery, trust badges and dual CTAs
- Impact bar (Discover → Understand → Connect → Act)
- About, Services (Education/Healthcare/Financial Aid/Community), visual mosaic, How-it-works, Why-KhidmatAI, stories and final CTA sections
- **Login-aware CTAs**: signed-in visitors see *Dashboard* buttons; new visitors see *Find support / Get started*
- Sticky header with mobile hamburger navigation and theme toggle

### Authentication Pages (`login.html`, `register.html` + `auth.js`)

Real API-backed authentication — no frontend-only fake auth:

- **Login**: `POST /api/auth/login` with friendly error messages, password visibility toggle, redirect to dashboard on success, auto-redirect if already signed in
- **Register (Individual)**: `POST /api/auth/register` with validation, password strength meter, terms confirmation, redirect to login on success
- **Register (Organization)**: `POST /api/organizations/register` — organizations enter the admin-approval workflow
- Auth notice handoff between register → login via sessionStorage

### AI Assistant (`chat.html` + `chat.js`)

Auth-guarded ChatGPT-style chat page served at `/chat`:

- Redirects unauthenticated visitors to `/login`
- Clean conversational bubbles; technical internals (models, pipelines, JSON) are never exposed
- Responses rendered as bullet-point summaries, program cards, *Official Source* links and next steps
- Voice input via SpeechRecognition and voice replies via speechSynthesis (toggleable)
- Suggestion chips plus deep-link support (`/chat?q=...`) from the dashboard
- Rate-limit and network errors surfaced as friendly messages

### User Dashboard (`dashboard.html` + `dashboard.js`)

Rebuilt in the unified design, preserving all functionality:

- **Auth gate**: unauthenticated visits redirect to `/login`; logout clears the session and returns to the landing page
- **Overview**: personalized hero with *Ask KhidmatAI* CTA, quick-action cards, trust-strip stats (live program count from `/api/health`) and recommended programs
- **AI Assistant section**: prominent CTA card linking to `/chat` with suggestion deep-links
- **Eligibility checker**: simple form calling `/api/eligibility` with scored, colour-coded results
- **Programs directory**: search + category filters on `/api/programs`, program cards with **View details** modal (support, eligibility, documents, how to apply, official source), Save bookmark and direct **Apply**
- **Applications**: submissions tracked via `/api/user/apply` and `/api/user/applications` (X-User-Email header) with status pills
- **Saved programs**: persisted in localStorage, view/remove
- **Nearby help**: Leaflet map combining curated facilities and geo-verified (Overpass) facilities with colour-coded markers and geolocation
- **Emergency**: helpline cards from `/api/emergency` with tel: quick-call buttons
- **Profile**: account details and logout
- **Application wizard**: 4-step modal (Program → Personal → Documents → Review) preserved from the original build

### Admin Dashboard (`admin.html` + `admin.js` + `admin.css`)

Preserved unchanged, with the same brand identity:

- **Secure Login**: Token-based authentication with session persistence
- **Overview Panel**: Live stats (program count, org count, pending approvals, slide count)
- **Hero Slider Management**: Add/delete slides with preview
- **Ticker Management**: Add/remove ticker messages with live save
- **Contact Settings**: Update phone, email, helpline, address
- **Organization Approvals**: Filter by status, approve/reject/delete with live SQLite sync
- **Program Management (CRUD)**: Full add/edit/delete for welfare programs with search and category filtering, modal-based form with all program fields (title, category, type, description, eligibility, documents, locations, source URL, etc.)
- **Geo Facility Collection**: Trigger the Overpass scraper to auto-populate facility locations

---

## 4. API Routes

### Public Endpoints

| Method | Route | Description |
|---|---|---|
| `GET` | `/` | Serve public landing page (canonical homepage) |
| `GET` | `/login` | Serve login page |
| `GET` | `/register` | Serve registration page (individual + organization) |
| `GET` | `/dashboard` | Serve user dashboard (auth-gated client-side) |
| `GET` | `/chat` | Serve AI assistant page (auth-gated client-side) |
| `GET` | `/admin` | Serve admin dashboard |
| `GET` | `/api/health` | System health & stats |
| `GET` | `/api/config` | Active AI model configuration |
| `GET` | `/api/programs` | List/filter welfare programs |
| `GET` | `/api/universities` | List/filter university scholarships |
| `POST` | `/api/chat` | AI chatbot (LangGraph agent) |
| `POST` | `/api/recommend` | Program recommendations |
| `POST` | `/api/eligibility` | Eligibility evaluation engine |
| `GET` | `/api/facilities` | Curated facility locations |
| `GET` | `/api/nearby` | OpenStreetMap nearby search |
| `GET` | `/api/emergency` | Emergency contact numbers |
| `POST` | `/api/auth/register` | User registration |
| `POST` | `/api/auth/login` | User login |
| `POST` | `/api/user/apply` | Submit welfare application |
| `GET` | `/api/user/applications` | Get user's applications |

### Admin Endpoints (require `X-Admin-Key` header)

| Method | Route | Description |
|---|---|---|
| `POST` | `/api/admin/login` | Admin authentication |
| `GET` | `/api/admin/settings` | Get all admin settings |
| `POST` | `/api/admin/settings/contact` | Update contact info |
| `POST` | `/api/admin/settings/ticker` | Update ticker messages |
| `POST` | `/api/admin/hero-slides/add` | Add hero slide |
| `DELETE` | `/api/admin/hero-slides/{id}` | Delete hero slide |
| `POST` | `/api/admin/hero-slides/reorder` | Reorder hero slides |
| `GET` | `/api/admin/organizations` | List all organizations |
| `POST` | `/api/admin/organizations/{id}/approve` | Approve organization |
| `POST` | `/api/admin/organizations/{id}/reject` | Reject organization |
| `DELETE` | `/api/admin/organizations/{id}` | Delete organization |
| `GET` | `/api/admin/programs` | List programs (with search/filter) |
| `POST` | `/api/admin/programs/add` | Add new welfare program |
| `PUT` | `/api/admin/programs/{id}` | Update existing program |
| `DELETE` | `/api/admin/programs/{id}` | Delete program |

### Public (no auth) Settings

| Method | Route | Description |
|---|---|---|
| `GET` | `/api/public/settings` | Contact, ticker, hero slides |
| `GET` | `/api/public/approved-organizations` | Approved orgs only |
| `POST` | `/api/organizations/register` | Submit org registration |

---

## 5. Environment Variables

| Variable | Required | Description |
|---|---|---|
| `DASHSCOPE_API_KEY` | Yes | Alibaba Cloud Model Studio API key |
| `DASHSCOPE_BASE_URL` | No | Defaults to `https://dashscope-intl.aliyuncs.com/compatible-mode/v1` |
| `GROQ_API_KEY` | Recommended | Groq Cloud fallback API key |
| `GROQ_MODEL` | No | Defaults to `llama-3.3-70b-versatile` |
| `TAVILY_API_KEY` | Optional | Tavily web search API key |
| `APP_NAME` | No | Defaults to `KhidmatAI` |

**Security**: All API keys are stored in `.env` and never exposed to the frontend.

---

## 6. How to Run

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env with your API keys

# 3. Start the server
uvicorn backend.main:app --reload

# 4. Open in browser
# Public site:    http://127.0.0.1:8000
# User dashboard: http://127.0.0.1:8000/dashboard
# Admin panel:    http://127.0.0.1:8000/admin
# API docs:       http://127.0.0.1:8000/docs
```

### Admin Credentials

- Username: `admin`
- Password: `khidmatai2024`

---

## 7. Architectural Changes Summary

| Component | Before | After |
|---|---|---|
| Data Storage | JSON files (`programs.json`, `admin_data.json`) | SQLite database (`khidmatai.db`) |
| AI Provider | Gemini → Groq → DashScope fallback | DashScope (qwen3.7-plus → qwen3.6-plus → qwen3.6-flash) → Groq |
| AI Workflow | Direct API calls | LangGraph StateGraph (retrieve → conditional search → synthesize) |
| User System | None | Registration, login, application tracking with bcrypt (direct, no passlib) |
| Frontend JS | Single `admin.js` with mixed logic | Separate `landing.js`, `auth.js`, `dashboard.js`, `chat.js` and `admin.js` |
| Theme | Basic dark mode | Unified dark/light with localStorage persistence across all pages |
| Languages | Partial i18n | English-only UI (chatbot still understands multilingual input) |
| Application Form | None | 4-step wizard modal |
| User Dashboard | None | Auth-gated portal with profile, applications, saved programs |
| Admin Program CRUD | None | Full add/edit/delete with search and category filter |
| Database Init | Manual JSON loading | Auto-create tables + seed from JSON on startup |
| Homepage | Old multi-page portal UI | Dedicated landing page design integrated as canonical homepage |
| Auth UX | Modal on old homepage | Dedicated `/login` and `/register` pages with real API auth |
| AI Chat | Embedded panel on old homepage | Dedicated `/chat` page, ChatGPT-style, auth-guarded |
| User endpoints | Broken header parsing (query param) | `X-User-Email` properly read via FastAPI `Header()` |

---

## 8. File Structure

```
KhidmatAI_Hackathon_Project-main/
├── backend/
│   ├── __init__.py
│   ├── database.py      ← SQLite module
│   ├── agent.py         ← LangGraph agent with forced web search routing
│   ├── geo_scraper.py   ← Overpass facility collector
│   ├── main.py          ← FastAPI app: pages, auth, programs, chat, facilities
│   └── admin.py         ← Admin API with SQLite + org approval workflow
├── frontend/
│   ├── index.html       ← REWRITTEN: landing page is now the canonical homepage
│   ├── login.html       ← NEW: real API login page
│   ├── register.html    ← NEW: individual + organization registration
│   ├── chat.html        ← NEW: auth-guarded ChatGPT-style AI assistant
│   ├── dashboard.html   ← REBUILT: unified design, all features preserved
│   ├── khidmat.css      ← NEW: unified stylesheet (landing + app UI + dark mode)
│   ├── landing.js       ← NEW: landing behaviour + login-aware CTAs
│   ├── auth.js          ← NEW: real login/register logic
│   ├── chat.js          ← NEW: chat UI with STT/TTS
│   ├── dashboard.js     ← REWRITTEN: unified dashboard logic
│   ├── admin.html       ← UPDATED: Admin dashboard + program CRUD
│   ├── admin.js         ← REWRITTEN: Admin-only logic + program mgmt
│   ├── admin.css        ← UPDATED: Program cards, modal, toolbar
│   ├── khidmatai-logo.png
│   └── assets/          ← NEW: landing imagery (logo, hero, services)
├── data/                ← Seed data (read once on first startup)
├── .env                 ← API keys (not committed)
├── .env.example         ← UPDATED: New variable structure
├── requirements.txt     ← UPDATED: Added langgraph, bcrypt, etc.
├── README.md            ← UPDATED: unified platform docs
├── REPORT.md            ← THIS FILE
└── khidmatai.db         ← AUTO-CREATED on first run (preserved)
```
