from pydantic import BaseModel
from typing import Optional

class TextSegment(BaseModel):
    tag_name: str
    original_text: str
    translated_text: Optional[str] = None

class AddonChapterPartsInfo(BaseModel):
    context: str
    specific: str
    cut_after_tag: str

class EpubBodyTagsHiding(BaseModel):
    markup_tags: dict[str, str]

    text_segments: list[TextSegment]

    hided_tags_body: str
