# KhidmatAI Architecture

```text
Browser
  |
  v
HTML / CSS / JavaScript
  |
  v
FastAPI
  |
  +--> Local Welfare Knowledge Base
  |      programs.json
  |      keyword/category retrieval
  |
  +--> Tavily (optional fresh web evidence)
  |
  +--> Qwen model chain
         qwen3.7-plus
              |
         fallback on error
              v
         qwen3.6-plus
              |
         fallback on error
              v
         qwen3.6-flash
  |
  v
Source-grounded response
  - likely matches
  - possible eligibility
  - documents
  - next step
  - sources
```

Security:
- API keys stay in `.env` on the backend.
- Frontend never receives the Model Studio API key.
- AI is instructed to avoid unsupported factual claims.
- Welfare eligibility is presented as guidance, not guaranteed approval.
