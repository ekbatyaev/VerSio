import asyncio
from src.settings import settings, logger
from src.backend.ai.schemas import TranslateBatch
from src.backend.ai.agents.translator.schemas import TranslationStatus
from src.backend.ai.agents.translator.task import translate_segments

translation_semaphore = asyncio.Semaphore(settings.max_translator_workers)


async def translate_text(batches: list[TranslateBatch],
                         language_from: str, language_to: str,
                         book_description: str | None, temperature: float | None) -> TranslationStatus:
    n = len(batches)
    done_segments = 0

    async def run_batch(batch_number: int, batch: TranslateBatch) -> TranslationStatus:
        nonlocal done_segments
        async with translation_semaphore:
            status = await translate_segments(
                texts=batch.text_segments,
                language_from=language_from,
                language_to=language_to,
                context=batch.context,
                specific=batch.specific,
                book_description=book_description,
                temperature=temperature
            )
        done_segments += len(batch.text_segments)
        logger.info(f"Батч {batch_number}/{len(batches)}: переведено {status.processed} из {len(batch.text_segments)}, "
                    f"ошибок {status.error}. Обработано всего: {done_segments} из {n}.")
        return status

    statuses = await asyncio.gather(*(run_batch(i, batch) for i, batch in enumerate(batches, start=1)))

    total = TranslationStatus(processed=sum(s.processed for s in statuses),
                              error=sum(s.error for s in statuses))
    logger.info(f"Перевод завершён: переведено {total.processed} из {n}, ошибок {total.error}.")
    return total
