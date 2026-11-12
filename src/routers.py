import asyncio
from pathlib import Path
from src.settings import settings
from src.backend.decoder.functions import file_decoder
from src.backend.encoder.functions import file_encoder
from src.backend.ai.functions import ai_process


async def _get_translated_book(file_path: str | Path, language_from_translate: str,
                               language_to_translate: str,
                                temperature_of_translation: float = 0.4):
    path = Path(file_path)
    # Декодирование книги
    decoded_book = await file_decoder(path)
    # Отправка книги в модуль ИИ для первода
    result_book = await ai_process(decoded_book, language_from_translate,
                                   language_to_translate, temperature_of_translation)
    # Кодирование книги и отдача ее пользователю
    encode_book = await file_encoder(result_book)

    return "completed"


async def main():
    print(await _get_translated_book(settings.temp_files_path / "Molot_Vulkana.epub"))


if __name__ == "__main__":
    asyncio.run(main())
