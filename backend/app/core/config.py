"""
Application Configuration Settings
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


# ── Configuration Class ──────────────────────────────────────────────────────

class Settings(BaseSettings):
    PROJECT_NAME: str = "SARA · ระบบสารบรรณการประชุมอัตโนมัติ"
    API_V1_STR: str = "/api"

    DATABASE_URL: str
    REDIS_URL: str = "redis://localhost:6379/0"

    # AI4Thai Pathumma / ThaiLLM
    APP_AI4THAI_API_KEY: str
    PATHUMMA_BASE_URL: str = "https://tokenmind.pathumma.in.th/v1"
    PATHUMMA_MODEL_NAME: str = "thaillm-8b"
    LLM_TIMEOUT_SECONDS: int = 180
    #  thaillm-8b ปฏิเสธคำขอที่เกิน context นี้ทั้งคำขอ (ตัวเลขจาก error ของ gateway เอง)
    #  บันทึกยาวจึงต้องถูกแบ่งส่งเป็นช่วง ๆ — ดู services/extraction.py
    LLM_CONTEXT_TOKENS: int = 40960
    LLM_RESPONSE_RESERVE_TOKENS: int = 4096

    # ASR
    ASR_URL: str = "https://tokenmind.pathumma.in.th"
    ASR_MODEL: str = "ptm-asr-1"

    # API Security
    API_KEY: str = ""

    # ไฟล์อัปโหลด — ใช้ shared volume ระหว่าง API และ Celery Workers
    UPLOAD_DIR: str = "/data/uploads"
    MAX_UPLOAD_MB: int = 500

    # เอกสารต้นแบบขององค์กร ถ้ามีไฟล์อยู่ ระบบจะสร้าง .docx จากไฟล์นี้แทนเอกสารเปล่า
    AGENDA_TEMPLATE_PATH: str = ""
    MINUTES_TEMPLATE_PATH: str = ""

    # การแจ้งเตือนมติ
    REMINDER_LEAD_DAYS: int = 7
    REMINDER_COOLDOWN_DAYS: int = 7
    TIMEZONE: str = "Asia/Bangkok"

    # magic link ให้ผู้รับผิดชอบแจ้งสถานะกลับโดยไม่ต้องล็อกอิน
    SECRET_KEY: str = "change-me-in-production"
    MAGIC_LINK_TTL_DAYS: int = 30
    PUBLIC_BASE_URL: str = "http://localhost:8000"

    # ยังไม่มีระบบล็อกอิน — ใช้ชื่อนี้เป็นผู้กระทำเมื่อไม่ได้ส่งหัวข้อ X-Actor มา
    DEFAULT_ACTOR: str = "ฝ่ายเลขานุการ"

    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


# ── Global Settings Instance ─────────────────────────────────────────────────

settings = Settings()
