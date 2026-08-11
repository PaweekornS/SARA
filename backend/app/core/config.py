from pydantic_settings import BaseSettings, SettingsConfigDict


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

    # ASR
    ASR_URL: str = "https://tokenmind.pathumma.in.th"
    ASR_MODEL: str = "ptm-asr-1"

    # MCP action layer
    MCP_SERVER_URL: str = "http://localhost:8001/mcp"

    # ไฟล์อัปโหลด — ของจริงควรเป็น object storage (FR-M10-06) ไม่ใช่ดิสก์ของ container
    UPLOAD_DIR: str = "/tmp/sara-uploads"
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


settings = Settings()
