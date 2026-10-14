import zipfile
from io import BytesIO
import posixpath
from urllib.parse import unquote
from lxml import etree
from src.models import EpubChapter, BODY_RE
from src.settings import logger

NS = {
    "container": "urn:oasis:names:tc:opendocument:xmlns:container",
    "opf": "http://www.idpf.org/2007/opf",
    "dc": "http://purl.org/dc/elements/1.1/",
    "xhtml": "http://www.w3.org/1999/xhtml",
}

XML_PARSER = etree.XMLParser(resolve_entities=False)

class EpubDecodeError(Exception):
    """Файл не удалось разобрать: битый архив, нет нужных файлов, невалидный XML."""

def read_bytes(zf: zipfile.ZipFile, name: str) -> bytes:
    """Файл из архива байт в байт."""
    try:
        return zf.read(name)
    except KeyError as e:
        raise EpubDecodeError(f"В архиве нет файла {name}") from e


def parse_xml(data: bytes, name: str) -> etree._ElementTree:
    """Разбирает уже прочитанные байты. data при этом не меняется."""
    try:
        return etree.parse(BytesIO(data), XML_PARSER)
    except etree.XMLSyntaxError as e:
        raise EpubDecodeError(f"Невалидный XML в {name}: {e}") from e


def read_xml(zf: zipfile.ZipFile, name: str) -> etree._ElementTree:
    """Читает XML-файл из архива как есть, ничего не пересобирая."""
    return parse_xml(read_bytes(zf, name), name)


def find_opf(zf: zipfile.ZipFile) -> str:
    """META-INF/container.xml указывает, где лежит OPF — описание книги."""
    container = read_xml(zf, "META-INF/container.xml")
    rootfile = container.find(".//container:rootfile", NS)
    if rootfile is None or not rootfile.get("full-path"):
        raise EpubDecodeError("В container.xml не указан путь к OPF")
    return rootfile.get("full-path")


def read_metadata(opf: etree._ElementTree) -> dict:
    """Поля dc:*. Любого из них может не быть — тогда None или пустой список."""
    metadata = opf.find("opf:metadata", NS)

    def values(name: str) -> list[str]:
        if metadata is None:
            return []
        return [" ".join(e.itertext()).strip() for e in metadata.iterfind(f"dc:{name}", NS)]

    def first(name: str) -> str | None:
        found = values(name)
        return found[0] if found else None

    return {
        "title": first("title"),
        "creators": values("creator"),
        "language": first("language"),
        "description": first("description"),
    }

def _chapter_title(tree: etree._ElementTree) -> str | None:
    """Первый заголовок h1–h3, иначе <title>. Для логов и контекста перевода."""
    for tag in ("h1", "h2", "h3", "title"):
        el = tree.find(f".//xhtml:{tag}", NS)
        if el is not None:
            text = " ".join("".join(el.itertext()).split())
            if text:
                return text
    return None

def read_chapters(zf: zipfile.ZipFile, opf: etree._ElementTree, opf_path: str) -> list[EpubChapter]:
    """Главы в порядке spine: путь, исходник и сведения о каждой."""
    opf_dir = posixpath.dirname(opf_path)
    manifest = {item.get("id"): item for item in opf.iterfind("opf:manifest/opf:item", NS)}

    chapters = []
    for itemref in opf.iterfind("opf:spine/opf:itemref", NS):
        item = manifest.get(itemref.get("idref"))
        if item is None or item.get("media-type") != "application/xhtml+xml":
            continue
        # href в OPF записан относительно папки OPF и может быть URL-кодирован (%20)
        href = unquote(item.get("href", ""))
        path = posixpath.normpath(posixpath.join(opf_dir, href))

        source = read_bytes(zf, path)
        tree = parse_xml(source, path)       # заодно проверяем, что XML валиден

        if not BODY_RE.search(source):
            raise EpubDecodeError(f"В {path} не найден <body>…</body>")

        chapter = EpubChapter(
            index=len(chapters),
            path=path,
            manifest_id=item.get("id"),
            linear=itemref.get("linear", "yes") != "no",
            title=_chapter_title(tree),
            source=source,
        )
        logger.debug(f"[{chapter.index}] {chapter.path}: {chapter.title!r}")
        chapters.append(chapter)

    if not chapters:
        raise EpubDecodeError("В spine нет ни одной главы")
    return chapters