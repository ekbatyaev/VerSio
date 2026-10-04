import asyncio
import zipfile
from pathlib import Path
from typing import Callable
from src.models import EpubBook
from src.settings import settings, logger
from src.parser.formats import epub

Encoder = Callable[[Path], Book]
ENCODERS: dict[str, Encoder] = {}

class DecodeError(Exception):
    """Файл не удалось разобрать: битый архив, нет нужных файлов, невалидный XML."""


def register_encoder(*extensions: str):
    def decorator(func: Encoder) -> Encoder:
        for ext in extensions:
            ext = ext.lower()
            if ext in ENCODERS:
                raise ValueError(f"Декодер для {ext} уже зарегистрирован")
            ENCODERS[ext] = func
        return func
    return decorator

@register_encoder(".epub")
def _decode_epub(path: Path) -> Book:
    try:

        with zipfile.ZipFile(path) as zf:
            opf_path = epub.find_opf(zf)
            opf = epub.read_xml(zf, opf_path)
            return Book(
                source_path=path,
                opf_path=opf_path,
                chapters=epub.read_chapters(opf, opf_path),
                **epub.read_metadata(opf),
            )
    except FileNotFoundError as e:
        raise DecodeError(f"Файл не найден: {path}") from e
    except zipfile.BadZipFile as e:
        raise DecodeError(f"{path.name} не открывается как ZIP — это не EPUB") from e

async def file_encoder(file_path: str | Path) -> Book:
    path = Path(file_path)
    extension = path.suffix.lower()

    encoders_set = set(ENCODERS.keys())

    if encoders_set != settings.supported_formats_set:
        logger.warning(f"Описанные в .env форматы не совпадают с набором форматов кодировщиков: {encoders_set ^ settings.supported_formats_set}")

    encoder = ENCODERS.get(extension)

    if encoder is None:
        raise ValueError(f"Неподдерживаемый формат файла для обработки: "
                         f"{extension or 'без расширения'}")

    logger.info(f"Декодирую {path.name} как {extension}")

    return await asyncio.to_thread(encoder, path)

async def main():
    from src.parser.decoders import file_decoder
    book = await file_decoder(settings.temp_files_path / "Molot_Vulkana.epub")
    print("Название:", book.title)
    print("Авторы:  ", book.creators)
    print("Язык:    ", book.language)
    print("Описание:", book.description)
    print("OPF:     ", book.opf_path)
    print("Главы в порядке чтения:")
    for chapter in book.chapters:
        print("  ", chapter)


if __name__ == "__main__":
    asyncio.run(main())

