import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


class Config:
    APP_VERSION = os.environ.get("APP_VERSION", "2.3.0")
    SECRET_KEY = os.environ.get("SECRET_KEY", "ai-test-platform-dev-key")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{BASE_DIR / 'data.db'}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    RUNS_DIR = BASE_DIR / "runs"
    UPLOADS_DIR = BASE_DIR / "uploads"
    MAX_CONTENT_LENGTH = 8 * 1024 * 1024
    # 开发/本地环境：模板与静态文件随磁盘即时更新，避免旧缓存
    TEMPLATES_AUTO_RELOAD = True
    SEND_FILE_MAX_AGE_DEFAULT = 0

    # ---- DeepSeek 大模型 API ----
    # 默认使用 DeepSeek 官方 OpenAI 兼容接口；如需本地部署（如 Ollama/vLLM），
    # 修改 DEEPSEEK_BASE_URL 与 DEEPSEEK_MODEL 即可。
    DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
    DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
    DEEPSEEK_TIMEOUT = int(os.environ.get("DEEPSEEK_TIMEOUT", "60"))
