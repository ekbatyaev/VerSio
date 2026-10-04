import asyncio
from pathlib import Path
from src.settings import settings, logger
from src.parser.functions import file_decoder
from src.coder.functions import create_epub


async def _get_translated_book(file_path: str | Path):
    path = Path(file_path)

    processed_book = await file_decoder(path)
    create_book = await create_epub(processed_book)

    return "completed"

async def main():
    print(await _get_translated_book(settings.temp_files_path / "Molot_Vulkana.epub"))

if __name__ == "__main__":
    asyncio.run(main())



