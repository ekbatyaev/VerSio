from pydantic import BaseModel

class EpubBodyTagsHiding(BaseModel):
    tags: dict[str, str]
    hided_tags_body: str
