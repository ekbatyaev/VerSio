from pathlib import Path
from pydantic import BaseModel, Field, field_validator
from src.settings import settings

class Chapter:
    chapter_path: str
    tag: str
    attrib: dict
    text: str
    tail: str
    children: dict

class EpubBook(BaseModel):
    file_type: str
    source_path: Path
    opf_path: str
    title: str | None = None
    creators: list[str] = Field(default_factory = list)
    language: str | None = None
    description: str | None = None
    chapters: list[Chapter] = Field(default_factory = list)

    @field_validator("file_type")
    @classmethod
    def check_supported(cls, value: str) -> str:
        value = value.lower()
        if value not in settings.supported_formats_set:
            raise ValueError(f"Неподдерживаемый формат: {value}")
        return value