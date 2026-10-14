from pathlib import Path
from pydantic import BaseModel, field_validator
from src.settings import settings
from dataclasses import field
import re

BODY_RE = re.compile(rb"<body\b.*?</body>", re.S)

class Book(BaseModel):
    file_type: str
    source_path: Path
    title: str | None = None
    creators: list[str] = field(default_factory = list)
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
    source: bytes = field(repr=False)   # исходный файл главы байт в байт
    result: bytes | None = field(default=None, repr=False)  # глава после твоей обработки

    def body(self) -> str:
        """<body …>…</body> как есть в файле, строкой."""
        return BODY_RE.search(self.source).group().decode("utf-8")

    def set_body(self, new_body: str) -> None:
        """Подставляет новый <body> на место старого. Всё вне body не трогается."""
        m = BODY_RE.search(self.source)
        self.result = self.source[:m.start()] + new_body.encode("utf-8") + self.source[m.end():]

class EpubBook(Book):
    opf_path: str
    chapters: list[EpubChapter] =field(default_factory = list)