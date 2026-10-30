from typing import Final
from src.backend.ai.client import client, LLMResponseParseError
from src.backend.ai.schemas import AddonChapterPartsInfo
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
    allowed_tags_name: list[str], texts_segments: str, max_cuts: int = 20
) -> list[AddonChapterPartsInfo]:
    """Возвращает разделенные по смыслу части главы."""
    user_content = [{
        "type": "text",
        "text": (
            f"Разрешённые метки для разреза: {', '.join(allowed_tags_name)}\n\n"
            f"Текстовые сегменты для смыслового разделения:\n\n{texts_segments}"
        ),
    }]

    try:
        result: dict = await client.send_request(
            system_prompt=SEGMENTER_PROMPT.format(max_cuts=max_cuts),
            guided_json=build_cut_schema(allowed_tags_name, max_cuts),
            user_content=user_content,
            temperature=0.0,
        )
    except Exception as e:
        logger.exception("Не удалось выбрать разрез")
        raise LLMResponseParseError("Ошибка запроса к модели") from e

    # дедуп и сортировка по порядку в тексте — модель может перепутать
    order = {tag: i for i, tag in enumerate(allowed_tags_name)}
    seen: set[str] = set()
    parts_info: list[AddonChapterPartsInfo] = []
    for item in sorted(result["divider"], key=lambda d: order[d["cut_after_tag"]]):
        if item["cut_after_tag"] in seen:
            continue
        seen.add(item["cut_after_tag"])
        logger.debug(item)
        parts_info.append(AddonChapterPartsInfo(**item))
    return parts_info
