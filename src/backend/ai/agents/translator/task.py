import json
from typing import Final
from src.backend.ai.client import client
from src.settings import logger
from src.backend.ai.schemas import TextSegment
from src.backend.ai.agents.translator.functions import TranslationStatus


def build_guided_json(keys: list[str]) -> dict:
    return {
        "type": "object",
        "properties": {
            "translation": {
                "type": "object",
                "properties": {key: {"type": "string"} for key in keys},
                "required": keys,
                "additionalProperties": False,
            }
        },
        "required": ["translation"],
        "additionalProperties": False,
    }


SYSTEM_PROMPT: Final[str] = """\
Ты — профессиональный литературный переводчик художественной прозы.

ВХОДНЫЕ ДАННЫЕ
В сообщении пользователя: язык оригинала, целевой язык,
сведения о книге (могут отсутствовать) и JSON-объект с фрагментами текста.
Ключи объекта — идентификаторы TEXT[1], TEXT[2], …; значения — фрагменты одной главы в порядке чтения.
Фрагменты получены разрезанием по тегам разметки. Поэтому фрагмент может быть целым абзацем, частью предложения,
одним выделенным словом, заголовком, номером сноски или знаком препинания. Соседние фрагменты часто составляют
 одно предложение.

КАК ПЕРЕВОДИТЬ
1. Читай фрагменты подряд как связный текст, чтобы понимать контекст, но перевод TEXT[n] должен
 содержать перевод только TEXT[n].
2. Не переноси слова между фрагментами и не объединяй их. Если предложение разбито
 на несколько фрагментов, построй перевод так,
   чтобы переводы, склеенные по порядку, читались естественно, а выделенное слово осталось в своём фрагменте.
3. Передавай смысл, тон, стиль и ритм оригинала. Не упрощай, не пересказывай, не сокращай, не смягчай грубую лексику
   и ничего не добавляй от себя: никаких примечаний и пояснений переводчика.
4. Имена, названия и термины переводи единообразно во всех фрагментах.
 Если в сведениях о книге есть глоссарий, следуй ему.
5. Используй типографику целевого языка: кавычки, оформление прямой речи, тире.
6. ИНОЯЗЫЧНЫЕ ВСТАВКИ НЕ ПЕРЕВОДИ. Переводи только текст на языке оригинала.
 Всё, что написано на любом другом языке
   (цитаты, эпиграфы, латинские и французские выражения, английские фразы, названия, песни, надписи и т. п.),
   копируй в перевод дословно, символ в символ: не переводи,
    не транслитерируй, не исправляй, не меняй регистр и диакритику.
   Это касается и фрагмента целиком, и вставки внутри фрагмента: переведи окружающий текст, а вставку оставь как есть.
   Кавычки вокруг такой вставки оформи по правилам целевого языка, саму вставку не трогай.
7. Также оставляй без изменений: числа и номера сносок, отдельные символы (*, †, №).
8. HTML-сущности (&amp;, &#160;, &lt;, &gt; и т. п.) сохраняй как есть. Если в переводе нужен амперсанд, пиши &amp;.
   Никогда не пиши символы < и > и не добавляй HTML-теги.
9. Не добавляй пробелы в начале и в конце фрагмента.

ФОРМАТ ОТВЕТА
Верни только JSON-объект с теми же ключами, что во входном, в том же порядке; значение — строка с переводом фрагмента.
Не пропускай ключи и не добавляй новые. Без комментариев и без markdown.

Пример (язык оригинала — русский, целевой язык — английский):
Вход:  {"TEXT[1]": "Он надел", "TEXT[2]": "старую", "TEXT[3]": "куртку и вышел за&#160;дверь.",
 "TEXT[4]": "Над входом висела надпись «Carpe diem», а ниже — «Lasciate ogni speranza».",
  "TEXT[5]": "Errare humanum est."}
Ответ: {"translation": {"TEXT[1]": "He put on the", "TEXT[2]": "old",
 "TEXT[3]": "jacket and stepped out the door.",
  "TEXT[4]": "Above the entrance hung the inscription “Carpe diem,” and below it, “Lasciate ogni speranza.”",
   "TEXT[5]": "Errare humanum est."}}
"""


async def translate_segments(texts_to_translate: list[TextSegment], language_from_translate: str,
                             language_to_translate: str, temperature: float | None = None,
                             book_info: str = "", retries: int = 2) -> TranslationStatus:
    """
    Переводит один батч сегментов. Перевод записывается в text_segment.translated_text.
    """
    dictionary_of_translation = {text.tag_name: text.original_text for text in texts_to_translate}
    keys = list(dictionary_of_translation)

    user_content = [
        {
            "type": "text",
            "text": (
                f"Информация про книгу:\n\n{book_info or 'Ничего не найдено.'}\n\n"
                "---\n\n"
                f"Язык оригинала: {language_from_translate}. Целевой язык: {language_to_translate}.\n"
                "Вставки на других языках оставь без изменений.\n\n"
                f"{json.dumps(dictionary_of_translation, ensure_ascii=False)}"
            )
        }
    ]

    translated_text_segments: dict | None = None
    for attempt in range(1, retries + 2):
        try:
            request_result: dict = await client.send_request(
                system_prompt=SYSTEM_PROMPT,
                guided_json=build_guided_json(keys),
                user_content=user_content,
                temperature=temperature,
            )
            translated_text_segments = request_result["translation"]
            missing = set(keys) - set(translated_text_segments)
            if not missing:
                break
            logger.warning("Попытка {}: в ответе не хватает ключей {}", attempt, sorted(missing))
        except Exception as e:
            logger.exception("Попытка {}: ошибка при обработке запроса: {}", attempt, e)

    if translated_text_segments is None:
        return TranslationStatus(processed=0, error=len(texts_to_translate))

    processed = 0
    error = 0
    for text_segment in texts_to_translate:
        if text_segment.tag_name in translated_text_segments:
            text_segment.translated_text = translated_text_segments[text_segment.tag_name]
            processed += 1
        else:
            text_segment.translated_text = text_segment.original_text
            error += 1
            logger.error(f"Тега под названием {text_segment.tag_name} не найдено.")
    return TranslationStatus(processed=processed, error=error)
