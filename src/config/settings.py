from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
            env_file='.env',
            env_file_encoding="utf-8",
            case_sensitive=False,
            extra="ignore"
    )

    openai_api_key:str= Field(...)
    chat_model:str =  Field(default="gpt-4o-mini")

    # Database
    database_url:str = Field(..., description="postgresql database url")
    redis_url:str = Field(..., description="redis database url")

settings = Settings()