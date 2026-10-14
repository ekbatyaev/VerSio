import asyncio
from pathlib import Path
from src.settings import settings, logger
from src.parser.decoders import file_decoder
from src.ai.functions import ai_process


async def _get_translated_book(file_path: str | Path):
    path = Path(file_path)
    # Декодирование книги
    decoded_book = await file_decoder(path)
    # Отправка книги в модуль ИИ для первода
    result_book = await ai_process(decoded_book)
    # Кодирование книги и отдача ее пользователю

    return "completed"

async def main():
    print(await _get_translated_book(settings.temp_files_path / "Molot_Vulkana.epub"))

if __name__ == "__main__":
    asyncio.run(main())



