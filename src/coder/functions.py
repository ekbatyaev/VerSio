from ebooklib import epub
from src.models import Book
import uuid
import html

async def create_epub(epub_book: Book) -> str:
    book = epub.EpubBook()
    book.set_identifier(epub_book.title + uuid.uuid4().hex)
    book.set_title(epub_book.title)
    book.set_language(epub_book.language)
    book.add_author(epub_book.creator)

    chapters = []
    for i, charter in enumerate(epub_book.charters, 1):
        ch = epub.EpubHtml(title=f"Глава {1}", file_name=f"ch{i}.xhtml", lang="ru")
        ch.content = f"<h1>{html.escape(f"Глава {i}")}</h1><p>{html.escape(charter)}</p>"
        book.add_item(ch)
        chapters.append(ch)

    book.toc = chapters                      # оглавление
    book.spine = ["nav", *chapters]          # порядок чтения
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    epub.write_epub(epub_book.title + ".epub", book)
    return "lol"