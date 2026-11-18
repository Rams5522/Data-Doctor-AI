from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # LLM configuration
    LLM_PROVIDER: str = "ollama"
    LLM_MODEL: str = "llama2"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OPENAI_API_KEY: str = ""
    GROQ_API_KEY: str = ""
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"

    # Database
    # Keep SQLite anchored to the backend directory regardless of the shell's current directory.
    DATABASE_URL: str = f"sqlite:///{(BACKEND_DIR / 'datadoctor_ai.db').as_posix()}"

    # ChromaDB
    CHROMA_PERSIST_DIRECTORY: str = "./storage/chroma"

    # Upload limits
    MAX_UPLOAD_MB: int = 25

    # Other settings
    PROJECT_NAME: str = "DataDoctor AI"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api"


settings = Settings()
