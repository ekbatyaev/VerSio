import asyncio
import zipfile
from pathlib import Path
from typing import Callable
from src.models import Book, EpubBook
from src.settings import settings, logger
from src.parser.formats import epub

Decoder = Callable[[Path], Book]
DECODERS: dict[str, Decoder] = {}

class DecodeError(Exception):
    """Файл не удалось разобрать: битый архив, нет нужных файлов, невалидный XML."""


def register_decoder(*extensions: str):
    def decorator(func: Decoder) -> Decoder:
        for ext in extensions:
            ext = ext.lower()
            if ext in DECODERS:
                raise ValueError(f"Декодер для {ext} уже зарегистрирован")
            DECODERS[ext] = func
        return func
    return decorator

@register_decoder(".epub")
def _decode_epub(path: Path) -> Book:
    try:

        with zipfile.ZipFile(path) as zf:
            opf_path = epub.find_opf(zf)
            opf = epub.read_xml(zf, opf_path)
            return EpubBook(
                file_type=".epub",
                source_path=path,
                opf_path=opf_path,
                chapters=epub.read_chapters(zf, opf, opf_path),
                **epub.read_metadata(opf),
            )

    except FileNotFoundError as e:
        raise DecodeError(f"Файл не найден: {path}") from e
    except zipfile.BadZipFile as e:
        raise DecodeError(f"{path.name} не открывается как ZIP — это не EPUB") from e

async def file_decoder(file_path: str | Path) -> Book:
    path = Path(file_path)
    extension = path.suffix.lower()

    decoders_set = set(DECODERS.keys())

    if decoders_set != settings.supported_formats_set:
        logger.warning(f"Описанные в .env форматы не совпадают с набором форматов декораторов: {decoders_set ^ settings.supported_formats_set}")

    decoder = DECODERS.get(extension)

    if decoder is None:
        raise ValueError(f"Неподдерживаемый формат файла для обработки: "
                         f"{extension or 'без расширения'}")

    logger.info(f"Декодирую {path.name} как {extension}")

    return await asyncio.to_thread(decoder, path)

async def main():
    book = await file_decoder(settings.temp_files_path / "Molot_Vulkana.epub")
    print("Название:", book.title)
    print("Авторы:  ", book.creators)
    print("Язык:    ", book.language)
    print("Описание:", book.description)
    print("OPF:     ", book.opf_path)
    print("Главы в порядке чтения:")
    for chapter in book.chapters:
        print("  ", chapter)
        print(chapter.tree())

if __name__ == "__main__":
    asyncio.run(main())



