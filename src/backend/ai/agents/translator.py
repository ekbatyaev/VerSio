import asyncio
import json
from typing import Final

from src.backend.ai.client import client
from src.settings import logger
from src.backend.ai.schemas import TextSegment
from src.backend.ai.agents.schemas import TranslationStatus


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
В сообщении пользователя: язык оригинала, целевой язык, сведения о книге (могут отсутствовать) и JSON-объект с фрагментами текста.
Ключи объекта — идентификаторы TEXT[1], TEXT[2], …; значения — фрагменты одной главы в порядке чтения.
Фрагменты получены разрезанием по тегам разметки. Поэтому фрагмент может быть целым абзацем, частью предложения,
одним выделенным словом, заголовком, номером сноски или знаком препинания. Соседние фрагменты часто составляют одно предложение.

КАК ПЕРЕВОДИТЬ
1. Читай фрагменты подряд как связный текст, чтобы понимать контекст, но перевод TEXT[n] должен содержать перевод только TEXT[n].
2. Не переноси слова между фрагментами и не объединяй их. Если предложение разбито на несколько фрагментов, построй перевод так,
   чтобы переводы, склеенные по порядку, читались естественно, а выделенное слово осталось в своём фрагменте.
3. Передавай смысл, тон, стиль и ритм оригинала. Не упрощай, не пересказывай, не сокращай, не смягчай грубую лексику
   и ничего не добавляй от себя: никаких примечаний и пояснений переводчика.
4. Имена, названия и термины переводи единообразно во всех фрагментах. Если в сведениях о книге есть глоссарий, следуй ему.
5. Используй типографику целевого языка: кавычки, оформление прямой речи, тире.
6. ИНОЯЗЫЧНЫЕ ВСТАВКИ НЕ ПЕРЕВОДИ. Переводи только текст на языке оригинала. Всё, что написано на любом другом языке
   (цитаты, эпиграфы, латинские и французские выражения, английские фразы, названия, песни, надписи и т. п.),
   копируй в перевод дословно, символ в символ: не переводи, не транслитерируй, не исправляй, не меняй регистр и диакритику.
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
Вход:  {"TEXT[1]": "Он надел", "TEXT[2]": "старую", "TEXT[3]": "куртку и вышел за&#160;дверь.", "TEXT[4]": "Над входом висела надпись «Carpe diem», а ниже — «Lasciate ogni speranza».", "TEXT[5]": "Errare humanum est."}
Ответ: {"translation": {"TEXT[1]": "He put on the", "TEXT[2]": "old", "TEXT[3]": "jacket and stepped out the door.", "TEXT[4]": "Above the entrance hung the inscription “Carpe diem,” and below it, “Lasciate ogni speranza.”", "TEXT[5]": "Errare humanum est."}}
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


async def translate_text(text_segments: list[TextSegment], language_from_translate: str,
                         language_to_translate: str, temperature: float | None = None,
                         batch_size: int = 15, max_concurrency: int = 5, book_info: str = "") -> TranslationStatus:
    n = len(text_segments)
    batches = [text_segments[i:i + batch_size] for i in range(0, n, batch_size)]
    semaphore = asyncio.Semaphore(max_concurrency)
    done_segments = 0

    async def run_batch(batch_number: int, batch: list[TextSegment]) -> TranslationStatus:
        nonlocal done_segments
        async with semaphore:
            status = await translate_segments(
                texts_to_translate=batch,
                language_from_translate=language_from_translate,
                language_to_translate=language_to_translate,
                temperature=temperature,
                book_info=book_info,
            )
        done_segments += len(batch)
        logger.info(f"Батч {batch_number}/{len(batches)}: переведено {status.processed} из {len(batch)}, "
                    f"ошибок {status.error}. Обработано всего: {done_segments} из {n}.")
        return status

    statuses = await asyncio.gather(*(run_batch(i, batch) for i, batch in enumerate(batches, start=1)))

    total = TranslationStatus(processed=sum(s.processed for s in statuses),
                              error=sum(s.error for s in statuses))
    logger.info(f"Перевод завершён: переведено {total.processed} из {n}, ошибок {total.error}.")
    return total


if __name__ == "__main__":
    async def main():
        text_segments = [TextSegment(tag_name='TEXT[1]', original_text='1', translated_text=None),
                         TextSegment(tag_name='TEXT[2]',
                                     original_text='Артур Питт попал в толпу сразу же, как только покинул офис «Единства» и стал переходить улицу. Остановившись на углу возле своего автомобиля, он прикурил сигарету. Затем открыл дверцу машины, взял кейс-атташе и стал внимательно изучать толпу. Их было человек пятьдесят-шестьдесят — все это были местные жители: рабочие, механики, водители, фермеры, домохозяйки, бакалейщики. Самые обыкновенные представители среднего класса.',
                                     translated_text=None), TextSegment(tag_name='TEXT[3]',
                                                                        original_text='Питт скользнул на сидение и, взяв микрофон, встроенный в панель автомобиля, вызвал старшего по званию — начальника южно-американского региона. Люди уже заполнили улицу и направлялись прямо к нему. Вне всякого сомнения, они опознали его по одежде, соответствовавшей Т-классу — белой рубашке с галстуком, серому костюму, фетровой шляпе. Атташе-кейс. Сияющие черные туфли. Наконечник лучевого карандаша, торчащий из нагрудного кармана. Он вытащил золотистую трубку и держал ее наготове.',
                                                                        translated_text=None),
                         TextSegment(tag_name='TEXT[4]', original_text='—\xa0Критическое положение,\xa0— произнес он.',
                                     translated_text=None), TextSegment(tag_name='TEXT[5]',
                                                                        original_text='—\xa0Таубман слушает,\xa0— донеслось из микрофона.\xa0— Где вы находитесь?\xa0— Официальный голос доносился откуда-то сверху.',
                                                                        translated_text=None),
                         TextSegment(tag_name='TEXT[6]',
                                     original_text='—\xa0Все еще в Кедровой Роще, в Алабаме. Вокруг меня собирается толпа. Предполагаю, она блокировала дорогу. Похоже, что весь город собрался здесь.',
                                     translated_text=None),
                         TextSegment(tag_name='TEXT[7]', original_text='—\xa0Какие-то Исцелители?',
                                     translated_text=None),
                         TextSegment(tag_name='TEXT[8]',
                                     original_text='На краю тротуара молча стоял старик с крупной головой и короткой стрижкой. Он был одет в широкую, свободного покроя, одежду, сандалии и подпоясан узловатой веревкой.',
                                     translated_text=None),
                         TextSegment(tag_name='TEXT[9]', original_text='—\xa0Он один,\xa0— ответил Питт.',
                                     translated_text=None),
                         TextSegment(tag_name='TEXT[10]', original_text='—\xa0Попробуйте снять для «Вулкана-3».',
                                     translated_text=None),
                         TextSegment(tag_name='TEXT[11]', original_text='—\xa0Попытаюсь.', translated_text=None)]

        await translate_text(text_segments=text_segments, language_from_translate="Russian",
                             language_to_translate="English", max_concurrency=10)
        # print("Перевод закончен")
        # print(text_segments)

    asyncio.run(main())