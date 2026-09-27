# Resume Analyzer (TypeSafe Stage 1 + Groq Stage 2)

A fast, cost-effective two-stage Resume Analyzer built with **TypeSafe System One (Jev)** for low-latency candidate screening and **Groq** for in-depth job-resume fit analysis.

---

## Architecture Overview

Processing 100+ resumes through heavy LLMs is slow, costly, and hits rate limits. This architecture introduces a strict two-stage gatekeeper:

```text
                  100+ RESUMES (PDF/DOCX)
                             │
                             ▼
                    Text Extraction (pypdf/docx)
                             │
                             ▼
                  ┌──────────────────────┐
                  │       STAGE 1        │
                  │     TYPESAFE JEV     │
                  │                      │
                  │  Choice: Role        │
                  │  Noul: Experience    │
                  │  Score: Skill Fit    │
                  └──────────┬───────────┘
                             │
                             ▼
                    Structured Results
                             │
                             ▼
                   Deterministic Python
                        Filtering
                       ┌─────┴─────┐
                       │           │
                       ▼           ▼
                    REJECT        PASS
                  (e.g. 68)     (e.g. 32)
                       │           │
                     STOP          ▼
                        ┌──────────────────────┐
                        │       STAGE 2        │
                        │       GROQ API       │
                        │                      │
                        │ parse_resume()       │
                        │ final_score()        │
                        └──────────┬───────────┘
                                   │
                                   ▼
                             MatchResult
                             (Detailed UI)
```

### Key Architectural Invariants
1. **TypeSafe Jev as Fast System One Classifier**: Evaluates atomic typed questions (`Choice`, `Noul`, `Score`) in parallel in a single API call per resume.
2. **Python Deterministic Gate**: AI makes classifications; deterministic Python makes filtering decisions. Non-matching roles or low-confidence classifications are stopped immediately.
3. **Groq Stage 2 Only for Passing Candidates**: Detailed LLM parsing and comparison runs strictly on candidates that clear Stage 1. 100 uploaded resumes != 100 Groq calls.
4. **Pydantic Type Safety**: Every data structure (`RoleType`, `JobD`, `Resume`, `ScreeningResult`, `MatchResult`) is validated through Pydantic contracts.

---

## Directory Structure

```text
resume-analyzer/
├── backend/
│   ├── config.py           # Configuration, thresholds, and environment variables
│   ├── models.py           # Pydantic models (RoleType, JobD, Resume, Results)
│   ├── parser.py           # Robust text extraction for PDF and DOCX
│   ├── typesafe_client.py  # TypeSafe System One client (Choice, Noul, Score)
│   ├── screening.py        # Deterministic Python filtering logic
│   ├── groq_client.py      # Groq Stage 2 client (parse_resume, final_score)
│   ├── matcher.py          # Orchestrates Stage 1 -> Filter -> Stage 2 pipeline
│   └── main.py             # FastAPI REST endpoints & static file serving
├── frontend/
│   ├── index.html          # Clean, minimalist UI
│   ├── style.css           # Clean styling (no emojis, professional typography)
│   └── script.js           # Batch upload handling, metrics & modal rendering
├── resumes/                # Sample test resumes (PDF format)
├── .env                    # Environment keys and threshold configurations
├── requirements.txt        # Python dependencies
├── test_pipeline.py        # Automated end-to-end batch verification test
└── README.md
```

---

## Configuration (`.env`)

```ini
GROQ_API_KEY=gsk_...
TYPESAFE_API_KEY=apikey_...
GROQ_MODEL=openai/gpt-oss-120b
TYPESAFE_MODEL=jev-latest

# Configurable Screening Thresholds
ROLE_CONFIDENCE_THRESHOLD=0.80
BASIC_FIT_THRESHOLD=0.60
EXPERIENCE_THRESHOLD=0.60
```

---

## Quickstart

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run End-to-End Automated Pipeline Test
```bash
python test_pipeline.py
```

### 3. Launch Web Application
```bash
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```
Open your browser at [http://127.0.0.1:8000](http://127.0.0.1:8000).
