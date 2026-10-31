import asyncio
from typing import Callable, Awaitable
from src.schemas import Book, EpubBook
from src.settings import logger, settings
from src.backend.ai.schemas import EpubBodyTagsHiding, AddonChapterPartsInfo
from src.backend.ai.formats.epub import process_tags, restore_tags
from src.backend.ai.agents.translator.functions import translate_text
from src.backend.ai.agents.segmentor.functions import cut_chapter_into_parts

Processor = Callable[[Book], Awaitable[Book]]
PROCESSORS: dict[str, Processor] = {}

class ProcessingError(Exception):
    """Файл не удалось обработать."""

def register_processor(*extensions: str):
    def decorator(func: Processor) -> Processor:
        for ext in extensions:
            ext = ext.lower()
            if ext in PROCESSORS:
                raise ValueError(f"Обработчик формата для {ext} уже зарегистрирован")
            PROCESSORS[ext] = func
        return func
    return decorator

@register_processor(".epub")
async def _process_epub(book: EpubBook, language_from_translate: str = "Russian",
                        language_to_translate: str = "English") -> EpubBook:
    for chapter in book.chapters:
        body: str = chapter.body()

        tags_result: EpubBodyTagsHiding = await process_tags(body)
        restored_body = restore_tags(tags_result)
        if restored_body != body:
            logger.warning(
                f"Разметка в файле была заменена.\nСобранная версия:\n{restored_body}Оригинальная версия:\n{body}")

        # Собираем метаданные о главе, делим ее на более мелкие кусочки для осмысленного перевода
        chapter_metadata_info: list[AddonChapterPartsInfo] = await cut_chapter_into_parts(tags_result.text_segments,
                                                             settings.llm_max_chapter_segmentor_tokens)
        for part_info in chapter_metadata_info:
            # Перевод файла с помощью ИИ

            await translate_text(text_segments=tags_result.text_segments,
                                 language_from_translate=language_from_translate,
                                 language_to_translate=language_to_translate,
                                 context=context, specific=specific)
        new_body = restore_tags(tags_result)
        # Окончание перевода файла с помощью ИИ
        # Складываем главы обратно
        chapter.set_body(new_body)

    return book

async def ai_process(book: Book, language_to_translate: str) -> Book:

    processor = PROCESSORS.get(book.file_type)

    if processor is None:
        raise ValueError(f"Неподдерживаемый формат файла для обработки: "
                         f"{book.file_type or 'без расширения'}")

    logger.info(f"Обрабатываю {book.source_path} как {book.file_type}")

    return await processor(book, language_to_translate)

async def main():
    pass

if __name__ == "__main__":
    asyncio.run(main())
