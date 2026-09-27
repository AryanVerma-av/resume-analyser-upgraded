import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from workspace root or backend folder
env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()

# API Keys
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
TYPESAFE_API_KEY = os.getenv("TYPESAFE_API_KEY", "").strip()

# Models
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b").strip()
TYPESAFE_MODEL = os.getenv("TYPESAFE_MODEL", "jev-latest").strip()

# Configurable Deterministic Screening Thresholds (Section 7 & 27)
ROLE_CONFIDENCE_THRESHOLD = float(os.getenv("ROLE_CONFIDENCE_THRESHOLD", "0.50"))
BASIC_FIT_THRESHOLD = float(os.getenv("BASIC_FIT_THRESHOLD", "0.50"))
EXPERIENCE_THRESHOLD = float(os.getenv("EXPERIENCE_THRESHOLD", "0.50"))

# Batch Processing Concurrency Limit (Section 18)
MAX_CONCURRENT_CALLS = int(os.getenv("MAX_CONCURRENT_CALLS", "5"))
