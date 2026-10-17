from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    """App configuration, loaded from environment variables / .env (case-insensitive)."""

    model_config = SettingsConfigDict(
            env_file='.env',
            env_file_encoding="utf-8",
            case_sensitive=False,
            extra="ignore"
    )

    openai_api_key:str= Field(...)
    chat_model:str =  Field(default="gpt-6-luna")
    deepgram_api_key: str | None = Field(default=None, description="Deepgram API key for voice-mode speech-to-text; voice mode is disabled if unset")
    cartesia_api_key: str | None = Field(default=None, description="Cartesia API key for voice-mode text-to-speech; voice mode is disabled if unset")
    history_summarize_trigger: int = Field(default=10, description="Summarize + archive older messages once the session's message count exceeds this")
    history_keep_last_n: int = Field(default=6, description="Number of most recent messages to keep verbatim in the checkpointer when summarizing")
    memory_extraction_every_n_turns: int = Field(default=4, description="Run long-term memory extraction every N conversational turns, independent of summarization")
    session_idle_seconds: int = Field(default=600, description="Treat a session as idle (and flush pending memory) after this many seconds without a /chat call")
    frontend_origins: list[str] = Field(default=["http://localhost:3000"], description="Origins allowed to call the API via CORS (the Next.js dev server by default)")

    # Database
    database_url:str = Field(..., description="postgresql database url")
    redis_url:str = Field(..., description="redis database url")

settings = Settings()