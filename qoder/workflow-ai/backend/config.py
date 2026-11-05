import os
from dotenv import load_dotenv

load_dotenv()

POWERCONTEXT_SERVER_URL = os.getenv("POWERCONTEXT_SERVER_URL", "http://localhost:18080")
POWERCONTEXT_API_TOKEN = os.getenv("POWERCONTEXT_API_TOKEN", "")
POWERCONTEXT_SCOPE_ID = os.getenv("POWERCONTEXT_SCOPE_ID", "workflow-ai-scope")

APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
APP_PORT = int(os.getenv("APP_PORT", "8000"))
DATABASE_PATH = os.getenv("DATABASE_PATH", "./data/workflow.db")
