from typing import Final
from src.backend.ai.client import client, LLMResponseParseError
from src.backend.ai.schemas import TranslateBatch, TextSegment
from src.settings import logger

SEGMENTER_PROMPT: Final[str] = """\
Ты — литературный редактор. Текст главы будет переводиться по частям, поэтому его нужно
разделить на части, каждая из которых цельна по смыслу и понятна без соседних.

ВХОДНЫЕ ДАННЫЕ
1. Фрагмент главы. Каждый сегмент начинается с метки вида TAG[N]. Сегменты идут в порядке чтения.
   Фрагмент может обрываться на середине сцены.
2. Список разрешённых меток — резать можно ТОЛЬКО после них.

КАК ВЫБИРАТЬ МЕСТО РАЗРЕЗА (от лучшего к худшему)
1. Смена сцены: другое место, время, действующие лица, другая сюжетная линия.
2. Конец эпизода внутри сцены: завершился разговор, герой остался один, закончилось действие.
3. Конец законченной мысли или описания перед новым событием.

НЕЛЬЗЯ резать:
- посреди диалога, пока собеседники продолжают обмениваться репликами;
- между репликой и относящимися к ней словами автора;
- между событием и его непосредственным последствием;
- после последнего сегмента фрагмента.

СКОЛЬКО РАЗРЕЗОВ
Сделай от 1 до {max_cuts} разрезов. Не режи ради количества: если хорошее место одно — верни одно.
Части не должны сильно отличаться по длине.

ФОРМАТ ОТВЕТА
JSON-объект с массивом "divider". Разрезы — строго в порядке следования в тексте, без повторов.
Для каждого разреза:
- "context": 1–2 предложения: что заканчивается перед разрезом и что начинается после;
- "specific": что важно знать переводчику следующей части: имена и пол персонажей,
  кто говорит, термины, тон, незавершённые линии из предыдущей части;
- "cut_after_tag": метка из списка разрешённых, ПОСЛЕ которой делается разрез,
  ровно в том виде, как она записана в списке.
"""


def build_cut_schema(allowed: list[str], max_cuts: int) -> dict:
    return {
        "type": "object",
        "properties": {
            "divider": {
                "type": "array",
                "minItems": 1,
                "maxItems": max_cuts,
                "items": {
                    "type": "object",
                    "properties": {
                        "context": {"type": "string", "maxLength": 400},
                        "specific": {"type": "string", "maxLength": 400},
                        "cut_after_tag": {"type": "string", "enum": allowed},
                    },
                    "required": ["context", "specific", "cut_after_tag"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["divider"],
        "additionalProperties": False,
    }


async def cut_pieces(
    segments_text: str,
    text_segments: list[TextSegment],
    max_cuts: int = 20,
) -> list[TranslateBatch]:
    """Возвращает разделённые по смыслу части главы."""
    if not text_segments:
        return []

    if len(text_segments) == 1:
        return [TranslateBatch(text_segments=text_segments, context="", specific="")]

    # Резать можно после любого сегмента, кроме последнего
    allowed_tags_name = [segment.tag_name for segment in text_segments[:-1]]
    max_cuts = min(max_cuts, len(allowed_tags_name))

    user_content = [{
        "type": "text",
        "text": (
            f"Разрешённые метки для разреза: {', '.join(allowed_tags_name)}\n\n"
            f"Текстовые сегменты для смыслового разделения:\n\n{segments_text}"
        ),
    }]

    try:
        result: dict = await client.send_request(
            system_prompt=SEGMENTER_PROMPT.format(max_cuts=max_cuts),
            guided_json=build_cut_schema(allowed_tags_name, max_cuts),
            user_content=user_content,
            temperature=0.1,
        )
    except Exception as e:
        logger.exception("Не удалось выбрать разрез")
        raise LLMResponseParseError("Ошибка запроса к модели") from e

    tag_to_index = {segment.tag_name: i for i, segment in enumerate(text_segments)}
    last_index = len(text_segments) - 1

    cuts: dict[int, dict] = {}
    for item in result["divider"]:
        index = tag_to_index.get(item["cut_after_tag"])
        if index is None or index >= last_index:
            logger.warning("Отброшен невалидный разрез: %s", item)
            continue
        if index not in cuts:
            cuts[index] = item

    batches: list[TranslateBatch] = []
    start = 0
    context, specific = "", ""

    for cut_index in sorted(cuts):
        batches.append(TranslateBatch(
            text_segments=text_segments[start: cut_index + 1],
            context=context,
            specific=specific,
        ))
        start = cut_index + 1
        context = cuts[cut_index]["context"]
        specific = cuts[cut_index]["specific"]

    # Хвост: всё после последнего разреза. Если разрезов нет, это вся глава.
    batches.append(TranslateBatch(
        text_segments=text_segments[start:],
        context=context,
        specific=specific,
    ))

    # Проверка: нет пустых кусков, и вместе они покрывают все сегменты
    total = sum(len(batch.text_segments) for batch in batches)
    has_empty = any(not batch.text_segments for batch in batches)
    if has_empty or total != len(text_segments):
        logger.error(
            "Некорректное разбиение: кусков=%d, сегментов в кусках=%d, всего сегментов=%d, разрезы=%s",
            len(batches), total, len(text_segments), sorted(cuts),
        )
        raise LLMResponseParseError("Разбиение главы потеряло или продублировало сегменты")

    return batches
