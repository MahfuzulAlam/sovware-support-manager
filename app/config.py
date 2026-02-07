"""Application configuration."""

from pydantic_settings import BaseSettings
from typing import Optional, Literal
from pydantic import model_validator


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Help Scout Configuration
    helpscout_app_id: str
    helpscout_app_secret: str
    helpscout_api_url: str = "https://api.helpscout.net/v2"

    # AI API Configuration
    ai_api_type: Literal["openai", "groq"] = "groq"
    
    # OpenAI Configuration
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"

    # Groq Configuration
    groq_api_key: Optional[str] = None
    groq_model: str = "llama-3.1-8b-instant"

    # Database Configuration (disabled for now)
    database_url: Optional[str] = None  # Not used when database is disabled

    # Application Configuration
    app_name: str = "SovWare Support Management"
    debug: bool = True

    @model_validator(mode="after")
    def validate_api_keys(self):
        """Validate that the required API key is provided based on ai_api_type."""
        if self.ai_api_type == "openai" and not self.openai_api_key:
            raise ValueError("openai_api_key is required when ai_api_type is 'openai'")
        if self.ai_api_type == "groq" and not self.groq_api_key:
            raise ValueError("groq_api_key is required when ai_api_type is 'groq'")
        return self

    class Config:
        """Pydantic config."""

        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()

