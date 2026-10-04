from io import BytesIO
from pathlib import Path
from lxml import etree

from pydantic import BaseModel, Field, field_validator
from src.settings import settings


class Book(BaseModel):
    file_type: str
    source_path: Path
    title: str | None = None
    creators: list[str] = Field(default_factory = list)
    language: str | None = None
    description: str | None = None

    @field_validator("file_type")
    @classmethod
    def check_supported(cls, value: str) -> str:
        value = value.lower()
        if value not in settings.supported_formats_set:
            raise ValueError(f"Неподдерживаемый формат: {value}")
        return value

class EpubChapter(BaseModel):
    index: int
    path: str
    manifest_id: str
    linear: bool = True         # False — вспомогательная глава вне основного чтения (сноски и т.п.)
    title: str | None = None    # первый заголовок главы — для логов и контекста перевода
    source: bytes = Field(repr=False)   # исходный файл главы байт в байт

    def tree(self) -> etree._ElementTree:
        """Свежее дерево из исходника. Правки в нём не затрагивают source."""
        # те же настройки, что в epub.XML_PARSER: сущности вроде &nbsp; не раскрываются
        return etree.parse(BytesIO(self.source), etree.XMLParser(resolve_entities=False))

class EpubBook(Book):
    opf_path: str
    chapters: list[EpubChapter] = Field(default_factory = list)