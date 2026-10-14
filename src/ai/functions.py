import asyncio
from typing import Callable, Awaitable
from src.models import Book, EpubBook
from src.settings import settings, logger
from src.ai.models import EpubBodyTagsHiding
from src.ai.formats.epub import process_tags

Processor = Callable[[Book], Awaitable[Book]]
PROCESSORS: dict[str, Processor] = {}

class ProcessingError(Exception):
    """Файл не удалось обработать."""

def register_processor(*extensions: str):
    def decorator(func: Processor) -> Processor :
        for ext in extensions:
            ext = ext.lower()
            if ext in PROCESSORS:
                raise ValueError(f"Обработчик формата для {ext} уже зарегистрирован")
            PROCESSORS[ext] = func
        return func
    return decorator

@register_processor(".epub")
async def _process_epub(book: EpubBook) -> EpubBook:
    for chapter in book.chapters:
        body: str = chapter.body()

        tags_result:  EpubBodyTagsHiding = await process_tags(body)

        new_body = body  # ← сюда твоя обработка (перевод через LLM)


        chapter.set_body(new_body)

    return book

async def ai_process(book: Book) -> Book:

    processor = PROCESSORS.get(book.file_type)

    if processor is None:
        raise ValueError(f"Неподдерживаемый формат файла для обработки: "
                         f"{book.file_type or 'без расширения'}")

    logger.info(f"Обрабатываю {book.source_path} как {book.file_type}")

    return await processor(book)

async def main():
    pass

if __name__ == "__main__":
    asyncio.run(main())



