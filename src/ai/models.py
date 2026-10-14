from pydantic import BaseModel

class EpubBodyTagsHiding:
    tags: dict[str, str]
    hided_tags_body: str
