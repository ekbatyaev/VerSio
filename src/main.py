import asyncio
from src.ai.server import llm_server
from src.routers import _get_translated_book
from src.settings import settings


async def main():
    async with llm_server():
        print(await _get_translated_book(settings.temp_files_path / "Molot_Vulkana.epub"))


if __name__ == "__main__":
    asyncio.run(main())