import asyncio
from src.settings import logger
from src.backend.ai.schemas import TextSegment
from src.backend.ai.agents.translator.schemas import TranslationStatus
from src.backend.ai.agents.translator.task import translate_segments

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

async def main():
    text_segments = [TextSegment(tag_name='TEXT[1]', original_text='1', translated_text=None),
                     TextSegment(tag_name='TEXT[2]',
                                 original_text='Артур Питт попал в толпу сразу же, как только покинул офис'
                                               ' «Единства»'
                                               ' и стал переходить улицу. Остановившись на углу возле своего'
                                               ' автомобиля,'
                                               ' он прикурил сигарету. Затем открыл дверцу машины,'
                                               ' взял кейс-атташе и стал внимательно изучать толпу.'
                                               ' Их было человек пятьдесят-шестьдесят — все это'
                                               ' были местные жители: рабочие, механики, водители,'
                                               ' фермеры, домохозяйки, бакалейщики.'
                                               ' Самые обыкновенные представители среднего класса.',
                                 translated_text=None),
                     TextSegment(tag_name='TEXT[3]',
                                original_text='Питт скользнул на сидение и, взяв микрофон, встроенный в панель'
                                              ' автомобиля, вызвал старшего по званию — начальника'
                                              ' южно-американского региона. Люди уже заполнили улицу и направлялись'
                                              ' прямо к нему. Вне всякого сомнения, они опознали его по одежде,'
                                              ' соответствовавшей Т-классу — белой рубашке с галстуком, серому'
                                              ' костюму, фетровой шляпе. Атташе-кейс. Сияющие черные туфли.'
                                              ' Наконечник лучевого карандаша, торчащий из нагрудного кармана.'
                                              ' Он вытащил золотистую трубку и держал ее наготове.',
                                                                    translated_text=None),
                     TextSegment(tag_name='TEXT[4]',
                                 original_text='—\xa0Критическое положение,\xa0— произнес он.',
                                 translated_text=None),
                     TextSegment(tag_name='TEXT[5]',
                                original_text='—\xa0Таубман слушает,\xa0— донеслось из микрофона.\xa0—'
                                              ' Где вы находитесь?\xa0— Официальный голос доносился'
                                              ' откуда-то сверху.',
                                                                    translated_text=None),
                     TextSegment(tag_name='TEXT[6]',
                                 original_text='—\xa0Все еще в Кедровой Роще, в Алабаме. Вокруг меня собирается'
                                               ' толпа. Предполагаю, она блокировала дорогу. Похоже,'
                                               ' что весь город собрался здесь.',
                                 translated_text=None),
                     TextSegment(tag_name='TEXT[7]', original_text='—\xa0Какие-то Исцелители?',
                                 translated_text=None),
                     TextSegment(tag_name='TEXT[8]',
                                 original_text='На краю тротуара молча стоял старик с крупной головой'
                                               ' и короткой стрижкой. Он был одет в широкую, свободного покроя,'
                                               ' одежду, сандалии и подпоясан узловатой веревкой.',
                                 translated_text=None),
                     TextSegment(tag_name='TEXT[9]', original_text='—\xa0Он один,\xa0— ответил Питт.',
                                 translated_text=None),
                     TextSegment(tag_name='TEXT[10]', original_text='—\xa0Попробуйте снять для «Вулкана-3».',
                                 translated_text=None),
                     TextSegment(tag_name='TEXT[11]', original_text='—\xa0Попытаюсь.', translated_text=None)]

    await translate_text(text_segments=text_segments, language_from_translate="Russian",
                         language_to_translate="English", max_concurrency=10)

if __name__ == "__main__":
    asyncio.run(main())
