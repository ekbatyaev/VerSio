import asyncio
import zipfile
from pathlib import Path
from typing import Callable
from src.schemas import Book
from src.settings import settings, logger
from src.backend.encoder.formats import epub

Encoder = Callable[[Book, Path], Path]
ENCODERS: dict[str, Encoder] = {}


class EncodeError(Exception):
    """Книгу не удалось собрать: нет исходного файла, неверный тип книги."""


def register_encoder(*extensions: str):
    def decorator(func: Encoder) -> Encoder:
        for ext in extensions:
            ext = ext.lower()
            if ext in ENCODERS:
                raise ValueError(f"Кодировщик для {ext} уже зарегистрирован")
            ENCODERS[ext] = func
        return func
    return decorator


@register_encoder(".epub")
def _encode_epub(book: Book, target: Path) -> Path:

    replacements = {chapter.path: chapter.result for chapter in book.chapters if chapter.result is not None}

    logger.info(f"Изменено глав: {len(replacements)} из {len(book.chapters)}")

    try:
        epub.write_epub(book.source_path, target, replacements)
    except FileNotFoundError as e:
        raise EncodeError(f"Исходный файл не найден: {book.source_path}") from e
    except zipfile.BadZipFile as e:
        raise EncodeError(f"{book.source_path.name} не открывается как ZIP") from e
    return target


async def file_encoder(book: Book, target: Path | None = None) -> Path:
    source = book.source_path
    target = Path(target) if target else source.with_stem(f"{source.stem}_translated")
    if target.resolve() == source.resolve():
        raise ValueError("Нельзя писать поверх исходника: сборка читает из него")

    encoders_set = set(ENCODERS.keys())
    if encoders_set != settings.supported_formats_set:
        logger.warning(
            f"Описанные в .env форматы не совпадают с набором форматов кодировщиков: {encoders_set ^ settings.supported_formats_set}")

    encoder = ENCODERS.get(book.file_type)
    if encoder is None:
        raise ValueError(f"Неподдерживаемый формат файла для сборки: {book.file_type}")

    logger.info(f"Собираю {target.name} как {book.file_type}")
    return await asyncio.to_thread(encoder, book, target)


async def main():
    from src.backend.decoder.functions import file_decoder
    book = await file_decoder(settings.temp_files_path / "Molot_Vulkana.epub")

    for chapter in book.chapters:
        chapter.set_body(chapter.body())   # «пустая» правка: проверяем, что сборка ничего не трогает
    target = await file_encoder(book)

    with zipfile.ZipFile(book.source_path) as a, zipfile.ZipFile(target) as b:
        assert a.namelist() == b.namelist(), "порядок или состав файлов изменился"
        changed = [n for n in a.namelist() if a.read(n) != b.read(n)]
        assert not changed, f"изменились: {changed}"
    print("OK:", target)


if __name__ == "__main__":
    asyncio.run(main())
