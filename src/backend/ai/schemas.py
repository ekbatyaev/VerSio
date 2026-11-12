from pydantic import BaseModel
from typing import Optional

class TextSegment(BaseModel):
    tag_name: str
    original_text: str
    translated_text: Optional[str] = None

class TranslateBatch(BaseModel):
    text_segments: list[TextSegment]

    context: Optional[str] = None
    specific: Optional[str] = None

class EpubBodyTagsHiding(BaseModel):
    markup_tags: dict[str, str]

    text_segments: list[TextSegment]

    hided_tags_body: str
