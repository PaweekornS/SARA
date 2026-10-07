"""
Application Configuration Settings
"""

from __future__ import annotations

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

INSECURE_SECRET = "change-me-in-production"


# ── Configuration Class ──────────────────────────────────────────────────────

class Settings(BaseSettings):
    PROJECT_NAME: str = "SARA · ผู้ช่วยสรุปการประชุม"
    # reverse proxy ของ server ตัด /api ออกก่อนส่งเข้ามา route จึงอยู่ที่ root
    # ROOT_PATH=/api บอก FastAPI ให้ /docs และ openapi.json สร้างลิงก์ถูก (ดู docs/RULES.md ข้อ 7)
    ROOT_PATH: str = ""

    # dev | prod — prod ปิดทางลัดสำหรับนักพัฒนาทั้งหมด (demo login, mock token)
    ENV: str = "dev"

    DATABASE_URL: str
    REDIS_URL: str = "redis://localhost:6379/0"

    # AI4Thai Pathumma / ThaiLLM
    APP_AI4THAI_API_KEY: str = ""
    PATHUMMA_BASE_URL: str = "https://tokenmind.pathumma.in.th/v1"
    PATHUMMA_MODEL_NAME: str = "thaillm-8b"
    LLM_TIMEOUT_SECONDS: int = 180
    #  thaillm-8b ปฏิเสธคำขอที่เกิน context นี้ทั้งคำขอ (ตัวเลขจาก error ของ gateway เอง)
    #  บันทึกยาวจึงต้องถูกแบ่งส่งเป็นช่วง ๆ — ดู services/extraction.py
    LLM_CONTEXT_TOKENS: int = 40960
    LLM_RESPONSE_RESERVE_TOKENS: int = 4096

    # Qdrant + embedding สำหรับถาม-ตอบ (รันบน CPU)
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_COLLECTION: str = "sara_chunks"
    EMBEDDING_MODEL: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    EMBEDDING_CACHE_DIR: str = ""
    VECTOR_MIN_SCORE: float = 0.3

    # ASR
    ASR_URL: str = "https://tokenmind.pathumma.in.th"
    ASR_MODEL: str = "ptm-asr-1"

    # ชั่วคราว (branch demo/openrouter): ตั้ง key นี้แล้ว LLM, ASR และ embedding จะวิ่งผ่าน OpenRouter แทน AI4Thai
    APP_OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_LLM_MODEL: str = "qwen/qwen3.5-9b"
    OPENROUTER_ASR_MODEL: str = "openai/whisper-large-v3-turbo"
    OPENROUTER_EMBEDDING_MODEL: str = "baai/bge-m3"

    @property
    def use_openrouter(self) -> bool:
        return bool(self.APP_OPENROUTER_API_KEY)

    # ตัวแปรที่ขึ้นต้นด้วย APP_ คือความลับ — บน GitLab ผูกกับ CI variable

    # Auth — Google Sign-In เป็นช่องทางเดียวที่ใช้ได้บน prod
    GOOGLE_CLIENT_ID: str = ""
    APP_SECRET_KEY: str = INSECURE_SECRET
    SESSION_EXPIRE_HOURS: int = 72
    SESSION_COOKIE_SECURE: bool = False
    ALLOW_DEMO_LOGIN: bool = False

    # SMTP
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    APP_SMTP_USER: str = ""
    APP_SMTP_PASSWORD: str = ""

    # โควตากันใช้ผิดวัตถุประสงค์ (นับใน Redis)
    PUBLIC_SUMMARIZE_PER_HOUR: int = 10
    EMAIL_RECIPIENTS_PER_DAY: int = 50
    MAX_EMAIL_RECIPIENTS: int = 10

    # ไฟล์อัปโหลด — ใช้ shared volume ระหว่าง API และ Celery Workers
    UPLOAD_DIR: str = "/data/uploads"
    MAX_UPLOAD_MB: int = 500

    # worker — งานเกินเวลานี้ถูกตัดทิ้ง และงานที่ค้างเกิน limit + 15 นาทีจะถูกตั้งเป็น failed
    MEETING_TIME_LIMIT_MINUTES: int = 60
    MAX_PROCESSING_ATTEMPTS: int = 2

    TIMEZONE: str = "Asia/Bangkok"

    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @model_validator(mode="after")
    def _refuse_insecure_prod(self) -> "Settings":
        if self.is_prod:
            if self.APP_SECRET_KEY == INSECURE_SECRET or len(self.APP_SECRET_KEY) < 32:
                raise ValueError("ENV=prod ต้องตั้ง APP_SECRET_KEY แบบสุ่มยาวอย่างน้อย 32 ตัวอักษร")
            if not self.GOOGLE_CLIENT_ID:
                raise ValueError("ENV=prod ต้องตั้ง GOOGLE_CLIENT_ID")
        return self

    @property
    def is_prod(self) -> bool:
        return self.ENV.lower() == "prod"

    @property
    def demo_login_enabled(self) -> bool:
        return not self.is_prod or self.ALLOW_DEMO_LOGIN

    @property
    def smtp_configured(self) -> bool:
        return bool(self.APP_SMTP_USER and self.APP_SMTP_PASSWORD)

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


# ── Global Settings Instance ─────────────────────────────────────────────────

settings = Settings()
