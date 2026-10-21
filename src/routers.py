import asyncio
from pathlib import Path
from src.settings import settings
from src.backend.decoder.functions import file_decoder
from src.backend.encoder.functions import file_encoder
from src.backend.ai.functions import ai_process


async def _get_translated_book(file_path: str | Path):
    path = Path(file_path)
    # Декодирование книги
    decoded_book = await file_decoder(path)
    # Отправка книги в модуль ИИ для первода
    language_to_translate = "English"
    result_book = await ai_process(decoded_book, language_to_translate)
    # Кодирование книги и отдача ее пользователю
    encode_book = await file_encoder(result_book)

    return "completed"

async def main():
    print(await _get_translated_book(settings.temp_files_path / "Molot_Vulkana.epub"))

if __name__ == "__main__":
    asyncio.run(main())



