"""
SplitsenseAI Core Configuration
Loads environment variables via pydantic-settings.
"""

from pydantic_settings import BaseSettings
from pydantic import field_validator
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # --- App ---
    APP_NAME: str = "SplitsenseAI"
    APP_ENV: str = "development"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"
    API_BASE_URL: str = "http://localhost:8000"

    # --- CORS ---
    # Comma-separated list of allowed origins, or "*" for development.
    # Set to your Streamlit URL in production: https://your-app.onrender.com
    CORS_ORIGINS: str = "*"

    # --- Database ---
    # Render provides postgres:// — we auto-fix it to postgresql+asyncpg://
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/splitsenseai"

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def fix_database_url(cls, v: str) -> str:
        """Convert Render's postgres:// to the asyncpg driver format."""
        if v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql+asyncpg://", 1)
        return v

    # --- Auth (JWT) ---
    SECRET_KEY: str = "change-this-in-production-use-openssl-rand-hex-32"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours

    # --- Cloudinary ---
    CLOUDINARY_CLOUD_NAME: str = ""
    CLOUDINARY_API_KEY: str = ""
    CLOUDINARY_API_SECRET: str = ""

    # --- Groq Vision ---
    GROQ_API_KEY: str = ""

    # --- OCR ---
    OCR_CONFIDENCE_THRESHOLD: float = 0.4
    MAX_IMAGE_SIZE_MB: int = 10
    SUPPORTED_IMAGE_FORMATS: list[str] = ["jpg", "jpeg", "png", "webp", "bmp"]

    # --- ML ---
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    ZERO_SHOT_MODEL: str = "facebook/bart-large-mnli"
    SPACY_MODEL: str = "en_core_web_sm"

    # --- Categories ---
    EXPENSE_CATEGORIES: list[str] = [
        "Groceries", "Restaurant", "Fast Food", "Beverages",
        "Household", "Personal Care", "Healthcare", "Electronics",
        "Clothing", "Transport", "Entertainment", "Utilities",
        "Office Supplies", "Pet Supplies", "Miscellaneous"
    ]

    model_config = {"env_file": ".env", "case_sensitive": True, "extra": "ignore"}

    @property
    def cors_origins_list(self) -> list[str]:
        if self.CORS_ORIGINS.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache()
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
