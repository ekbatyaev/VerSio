import asyncio
import ebooklib
import unicodedata
from ebooklib import epub
from bs4 import BeautifulSoup

from src.settings import settings, logger
from pathlib import Path
from typing import Callable
from src.models import Book

Decoder = Callable[[Path], str]
DECODERS: dict[str, Decoder] = {}

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
def _decode_epub(path):
    chapters = []
    try:
        book = epub.read_epub(str(path))
        print(book.metadata)
        print(book.spine)
        book_info = book.metadata.get("http://purl.org/dc/elements/1.1/")
        title, _ = book_info.get("title")[0]
        creator, _ = book_info.get("creator")[0]
        language, _= book_info.get("language")[0]
        description, _ = book_info.get("description")[0]

        for item_id, _ in book.spine:  # spine хранит порядок глав
            item = book.get_item_with_id(item_id)
            if item and item.get_type() == ebooklib.ITEM_DOCUMENT:
                soup = BeautifulSoup(item.get_content(), "html.parser")
                normalized_data = unicodedata.normalize("NFKD", soup.get_text("\n", strip=True))
                chapters.append(normalized_data)

        processed_book = Book(title = title, creator = creator,
                              language = language, description = description, charters=chapters)
        return processed_book

    except FileNotFoundError as e:
        logger.error(f"Ошибка обработки: {path}, ошибка {e}")
    except EncodingWarning as e:
        logger.error(f"Ошибка обработки: {path}, ошибка {e}")
    return "\n\n".join(chapters)

async def file_decoder(file_path: str | Path):
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

    processed_book = await asyncio.to_thread(decoder, path)

    return processed_book

async def main():
    print(await file_decoder(settings.temp_files_path / "Molot_Vulkana.epub"))

if __name__ == "__main__":
    asyncio.run(main())



