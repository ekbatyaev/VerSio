from src.backend.ai.schemas import EpubBodyTagsHiding, TextSegment
from src.settings import logger
import re

TAG_SPLIT_RE = re.compile(r"(<[^>]+>)")
EDGE_WS_RE = re.compile(r"(\s*)(.*?)(\s*)", re.DOTALL)
PLACEHOLDER_RE = re.compile(r"(?:TAG|TEXT)\[\d+\]")

class EpubTagsProcessingException(BaseException):
    """Ошибка обработки тегов EPUB"""

def restore_tags(hidden: EpubBodyTagsHiding) -> str:
    lookup = hidden.markup_tags | {s.tag_name: s.translated_text or s.original_text
                                   for s in hidden.text_segments}
    return PLACEHOLDER_RE.sub(lambda m: lookup[m.group()], hidden.hided_tags_body)

async def process_tags(body: str) -> EpubBodyTagsHiding:
    # Заменяет все тэги на простые TAG[№] в формате str, и
    # занести это в dict

    markup_tags: dict[str, str] = {}
    text_segments: list[TextSegment] = []
    parts: list[str] = []

    try:
        splitted_body = TAG_SPLIT_RE.split(body)

        for i, part in enumerate(splitted_body):
            if i % 2:
                tag_name = f"TAG[{len(markup_tags) + 1}]"
                markup_tags[tag_name] = part
                parts.append(tag_name)
            elif part.strip():
                lead, text, trail = EDGE_WS_RE.fullmatch(part).groups()
                tag_name = f"TEXT[{len(text_segments) + 1}]"
                text_segments.append(TextSegment(tag_name=tag_name,
                                                 original_text=text,
                                                 translated_text=None))
                parts.append(f"{lead}{tag_name}{trail}")
            else:
                parts.append(part)

        return EpubBodyTagsHiding(markup_tags=markup_tags, text_segments=text_segments,
                                  hided_tags_body="".join(parts))
    except EpubTagsProcessingException as e:
        logger.exception(f"Ошибка составления тэгов для epub книги пользователя:\n{e}\nBody:\n{body}")
        raise EpubTagsProcessingException("Произошла ошибка обработки Epub файла, пожалуйста, проверьте битый ли файл.")
