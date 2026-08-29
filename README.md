# KhidmatAI — Hackathon MVP

A source-first welfare navigation assistant built with HTML/CSS/JS + FastAPI + Qwen via Alibaba Cloud Model Studio + optional Tavily web search.

## 1. Folder structure

```text
KhidmatAI/
├── backend/
│   ├── __init__.py
│   └── main.py
├── frontend/
│   ├── index.html
│   ├── styles.css
│   ├── app.js
│   └── khidmatai-logo.png
├── data/
│   └── programs.json
├── .env.example
├── requirements.txt
└── README.md
```

## 2. Create the environment

Windows:

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and add your API keys.

## 3. Run

```powershell
uvicorn backend.main:app --reload
```

Open:

http://127.0.0.1:8000

Swagger:

http://127.0.0.1:8000/docs

## 4. API keys

DASHSCOPE_API_KEY:
Create an Alibaba Cloud Model Studio API key for the region matching your BASE_URL.

TAVILY_API_KEY:
Optional. Without it, KhidmatAI still uses the local welfare knowledge base.

## 5. Model fallback

The app tries:

1. qwen3.7-plus
2. qwen3.6-plus
3. qwen3.6-flash

If a model call fails, the next model is attempted.

## 6. Important before hackathon submission

The included `programs.json` is a DEMO knowledge base. Replace it with a properly verified dataset from official sources before presenting factual program details.

Do not hard-code API keys in frontend JavaScript.

## 7. Product flow

User request
→ need detection
→ local knowledge retrieval
→ optional fresh web search
→ Qwen source-grounded response
→ programs + documents + next step + sources

The AI is instructed not to invent eligibility, amounts, deadlines, addresses or phone numbers.
