import os
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / '.env')

POWERCONTEXT_SERVER_URL = os.getenv("POWERCONTEXT_SERVER_URL", "http://127.0.0.1:18080")
POWERCONTEXT_API_TOKEN = os.getenv("POWERCONTEXT_API_TOKEN", "")
POWERCONTEXT_SCOPE_ID = os.getenv("POWERCONTEXT_SCOPE_ID", "")
POWERCONTEXT_SEARCH_MODE = os.getenv("POWERCONTEXT_SEARCH_MODE", "fts")
POWERCONTEXT_SCOPE_KEY = os.getenv("POWERCONTEXT_SCOPE_KEY", "workflow-ai-personal-v1")

APP_HOST = os.getenv("APP_HOST", "127.0.0.1")
APP_PORT = int(os.getenv("APP_PORT", "8000"))
DATABASE_PATH = os.getenv("DATABASE_PATH", str(PROJECT_ROOT / "data" / "workflow.db"))
