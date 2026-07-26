import os
from typing import List
from dataclasses import dataclass, field

@dataclass
class Settings:
    APP_NAME: str = os.getenv("APP_NAME", "Smart Sembako Cloud Bot")
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    PORT: int = int(os.getenv("PORT", "8000"))
    
    # Supabase Configuration
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", os.getenv("SUPABASE_SERVICE_ROLE_KEY", ""))
    
    # Telegram Bot Configuration
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_SECRET_TOKEN: str = os.getenv("TELEGRAM_SECRET_TOKEN", "smart-sembako-secret-token")
    
    # RBAC Access Control (Comma separated Telegram User IDs)
    OWNER_TELEGRAM_IDS: str = os.getenv("OWNER_TELEGRAM_IDS", "")
    CASHIER_TELEGRAM_IDS: str = os.getenv("CASHIER_TELEGRAM_IDS", "")
    
    # LLM Provider API Keys
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    
    # Model Configurations
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.1-70b-versatile")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    def get_owner_ids(self) -> List[int]:
        if not self.OWNER_TELEGRAM_IDS:
            return []
        return [int(x.strip()) for x in self.OWNER_TELEGRAM_IDS.split(",") if x.strip().isdigit()]

    def get_cashier_ids(self) -> List[int]:
        if not self.CASHIER_TELEGRAM_IDS:
            return []
        return [int(x.strip()) for x in self.CASHIER_TELEGRAM_IDS.split(",") if x.strip().isdigit()]

settings = Settings()
