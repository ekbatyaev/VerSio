from src.backend.ai.schemas import EpubBodyTagsHiding, TextSegment
from src.settings import logger, settings
import re

TAG_SPLIT_RE = re.compile(r"(<[^>]+>)")
EDGE_WS_RE = re.compile(r"(\s*)(.*?)(\s*)", re.DOTALL)
PLACEHOLDER_RE = re.compile(r"(?:TAG|TEXT)\[\d+\]")

SENTENCE_END_RE = re.compile(r"[.!?…;]+[\"'»”)\]]*(?=\s)")  # конец предложения + закрывающие кавычки/скобки
SENSE_END_RE = re.compile(r"[:,]|\s[-–—](?=\s)")
WORD_END_RE = re.compile(r"\s+")


class EpubTagsProcessingException(BaseException):
    """Ошибка обработки тегов EPUB"""


def restore_tags(hidden: EpubBodyTagsHiding) -> str:
    lookup = hidden.markup_tags | {s.tag_name: s.translated_text or s.original_text
                                   for s in hidden.text_segments}
    return PLACEHOLDER_RE.sub(lambda m: lookup[m.group()], hidden.hided_tags_body)


def _last_cut(pattern: re.Pattern, text: str, limit: int) -> int | None:
    cut = None
    for m in pattern.finditer(text, 0, limit):  # ищем только в первых limit символах
        cut = m.end()
    return cut or None


async def divider_of_text(text: str) -> list[str]:
    limit = settings.max_characters_text_tag
    pieces: list[str] = []
    while len(text) > limit:
        cut = (_last_cut(SENTENCE_END_RE, text, limit)
               or _last_cut(SENSE_END_RE, text, limit)
               or _last_cut(WORD_END_RE, text, limit)
               or limit)
        pieces.append(text[:cut])
        text = text[cut:]
    pieces.append(text)
    return pieces


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
                part = f"{lead}"
                divided_text_pieces = await divider_of_text(text)
                start_index = len(text_segments)
                for i, piece in enumerate(divided_text_pieces, start=1):
                    tag_name = f"TEXT[{start_index + i}]"
                    text_segments.append(TextSegment(
                        tag_name=tag_name,
                        original_text=piece,
                        translated_text=None
                    ))
                    part += f"{tag_name}"
                part += f"{trail}"
                parts.append(part)
            else:
                parts.append(part)

        return EpubBodyTagsHiding(markup_tags=markup_tags, text_segments=text_segments,
                                  hided_tags_body="".join(parts))
    except EpubTagsProcessingException as e:
        logger.exception(f"Ошибка составления тэгов для epub книги пользователя:\n{e}\nBody:\n{body}")
        raise EpubTagsProcessingException("Произошла ошибка обработки Epub файла, пожалуйста, проверьте битый ли файл.")
