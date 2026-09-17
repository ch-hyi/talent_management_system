from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()

# ====================================================
# Base Directory
# ====================================================

BACKEND_DIR = Path(__file__).resolve().parent

PROJECT_DIR = BACKEND_DIR.parent

DATA_DIR = BACKEND_DIR / "data"

# ====================================================
# Database
# ====================================================

TALENT_DB_PATH = DATA_DIR / "104_talent.db"

USER_DB_PATH = DATA_DIR / "user.db"

LOG_DB_PATH = DATA_DIR / "log.db"

# ====================================================
# Excel / ODS Files
# ====================================================

LAB_FILE = DATA_DIR / "公司經緯度.xlsx"

POSTCODE_FILE = DATA_DIR / "1050429_行政區經緯度.ods"

ZIPCODE_FILE = DATA_DIR / "taiwan_zipcode_clean.xlsx"

DISCIPLINE_FILE = DATA_DIR / "學門.xlsx"

SUB_DISCIPLINE_FILE = DATA_DIR / "學類.xlsx"

# ====================================================
# Redis
# ====================================================

REDIS_URL = os.getenv(
    "REDIS_URL",
    "redis://localhost:6379/0"
)

# ====================================================
# Ollama
# ====================================================

os.environ["OLLAMA_HOST"] = "http://host.docker.internal:11434"
OLLAMA_HOST = os.getenv(
    "OLLAMA_HOST",
    "http://localhost:11434"
)
OLLAMA_MODEL = os.getenv(
    "OLLAMA_MODEL",
    "qwen3.5_9b"
)

# ====================================================
# API
# ====================================================

API_URL = os.getenv(
    "API_URL",
    "http://localhost:8000"
)

API_HOST = os.getenv(
    "API_HOST",
    "0.0.0.0"
)

API_PORT = int(
    os.getenv(
        "API_PORT",
        "8000"
    )
)

# ====================================================
# Streamlit
# ====================================================

STREAMLIT_URL = os.getenv(
    "STREAMLIT_URL",
    "http://localhost:8501"
)

# ====================================================
# Frontend Static
# ====================================================

STATIC_DIR = PROJECT_DIR / "frontend" / "static"

ATTACHMENT_DIR = STATIC_DIR / "attachment"

TEMP_DIR = STATIC_DIR / "temp"

MSG_BACKUP_DIR = STATIC_DIR / "msg_backup"