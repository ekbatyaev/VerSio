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

    @property
    def supported_formats_set(self) -> set[str]:
        return {ext.strip().lower() for ext in self.supported_formats.split(",") if ext.strip()}

settings = Settings()

if __name__ == "__main__":
    print(settings.model_dump())
