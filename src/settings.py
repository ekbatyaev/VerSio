from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from loguru import logger

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_PATH,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    supported_formats: str

    temp_files_path: Path = BASE_DIR / "src" / "temp_files"
    models_path: Path = BASE_DIR / "models"

    # Модель: репозиторий, файл и закрепление версии
    gguf_repo: str = "bartowski/google_gemma-4-26B-A4B-it-GGUF"
    gguf_file: str = "google_gemma-4-26B-A4B-it-IQ4_XS.gguf"
    hf_token: str | None = None

    # llama-server
    llm_server_bin: str = "/app/llama-server"
    llm_port: int = 8080
    llm_context: int = 32768
    llm_parallel: int = 1
    llm_extra_args: str = "-ngl 99 -ctk q8_0 -ctv q8_0"

    # Клиент
    llm_base_url: str = "http://127.0.0.1"
    llm_api_key: str = "none"
    llm_model_name: str = "gemma-4-26b-a4b"
    llm_timeout: float = 600

    @property
    def supported_formats_set(self) -> set[str]:
        return {ext.strip().lower() for ext in self.supported_formats.split(",") if ext.strip()}

settings = Settings()

if __name__ == "__main__":
    print(settings.model_dump())
