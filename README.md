# KhidmatAI — Welfare Navigation Platform

A source-first welfare navigation platform built with FastAPI + SQLite + LangGraph (Qwen via Alibaba Cloud Model Studio) + optional Tavily web search, wrapped in a unified Manrope/green design system.

## 1. What's inside

- **Public landing page** (`/`) — hero, services, how-it-works, impact and CTA sections. Login-aware: signed-in visitors see *Dashboard* buttons, new visitors see *Sign in / Get started*.
- **Real authentication** — `/login` and `/register` pages wired to `POST /api/auth/login` and `POST /api/auth/register`. The register page also hosts **Organization registration** (admin-approval workflow via `POST /api/organizations/register`).
- **Protected user dashboard** (`/dashboard`) — overview with stats and recommendations, AI assistant CTA, eligibility checker, program directory with search/filters, applications tracker, saved programs, nearby-help Leaflet map and emergency contacts.
- **AI assistant chat** (`/chat`) — auth-guarded ChatGPT-style conversation UI on `POST /api/chat`. Clean, non-technical presentation: bullet summaries, program cards, *Official Source* links, next steps. Voice input (STT) and voice replies (TTS) included.
- **Admin panel** (`/admin`) — program/organization/ticker management with the same brand identity.

All pages share one design language (Manrope font, green `#087b5a` palette, persistent dark/light theme via `khidmat-theme` in localStorage). The UI is English-only; the chatbot still understands natural multilingual input.

## 2. Folder structure

```text
KhidmatAI/
├── backend/
│   ├── main.py            # FastAPI app: pages, auth, programs, chat, facilities
│   ├── agent.py           # LangGraph agent: retrieve → search → synthesize
│   ├── admin.py           # Admin router: settings, programs, organizations
│   ├── database.py        # SQLite (khidmatai.db) helpers + migrations
│   └── geo_scraper.py     # Overpass/OpenStreetMap facility collector
├── frontend/
│   ├── index.html         # Public landing page (canonical homepage)
│   ├── login.html         # Sign-in (real API auth)
│   ├── register.html      # Individual + Organization registration
│   ├── dashboard.html     # Auth-guarded user dashboard
│   ├── chat.html          # Auth-guarded AI assistant
│   ├── admin.html         # Admin panel
│   ├── khidmat.css        # Unified stylesheet (landing + app + dark mode)
│   ├── landing.js         # Landing behaviour + login-aware CTAs
│   ├── auth.js            # Login/register logic (real FastAPI calls)
│   ├── dashboard.js       # Dashboard sections, map, wizard, modals
│   ├── chat.js            # Chat UI, STT/TTS, response rendering
│   ├── admin.js / admin.css
│   └── assets/            # Landing imagery + logo
├── data/                  # Seed JSON (programs, universities, welfare)
├── .env.example
├── requirements.txt
├── README.md
└── REPORT.md
```

## 3. Create the environment

Windows:

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and add your API keys.

## 4. Run

```powershell
uvicorn backend.main:app --reload
```

Open:

- Landing page: http://127.0.0.1:8000/
- Login: http://127.0.0.1:8000/login
- Register: http://127.0.0.1:8000/register
- Dashboard: http://127.0.0.1:8000/dashboard
- AI Assistant: http://127.0.0.1:8000/chat
- Admin: http://127.0.0.1:8000/admin
- Swagger: http://127.0.0.1:8000/docs

Admin credentials: `admin` / `khidmatai2024` (admin key: `khidmatai-admin-2024`).

## 5. User journey

```
Landing page → Get started → Register → Login → Dashboard
Landing page → Sign in → Login → Dashboard
Dashboard → Ask KhidmatAI → Chat (source-first answers) → Apply
Register (Organization tab) → Admin approval → Organization login
```

Unauthenticated visits to `/dashboard` or `/chat` are redirected to `/login`.

## 6. API keys

- `DASHSCOPE_API_KEY` — required for Alibaba Cloud Model Studio (Qwen). Region must match `BASE_URL`.
- `TAVILY_API_KEY` — optional live web search. Without it, KhidmatAI still answers from the local verified knowledge base.

API keys live only in the backend `.env` — never in frontend code.

## 7. Model fallback

The agent tries, in order:

1. qwen3.7-plus
2. qwen3.6-plus
3. qwen3.6-flash
4. Groq (if configured)
5. Deterministic verified mode (bullet-point answers from SQLite matches)

Web search is forced when local matches are weak (fewer than 2 strong results), then results are grounded against official domains before answering.

## 8. Product flow

```
User request
→ need detection
→ SQLite knowledge retrieval (khidmatai.db)
→ forced fresh web search when local matches are weak (Tavily)
→ Qwen source-grounded synthesis (short, bulleted, official-source linked)
→ programs + documents + next steps + official sources
```

The AI is instructed not to invent eligibility, amounts, deadlines, addresses or phone numbers. Every answer carries an *Official Source* link when available.

## 9. Important before submission

The bundled seed data is a DEMO knowledge base. Replace it with a properly verified dataset from official sources before presenting factual program details.
