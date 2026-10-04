import zipfile
from io import BytesIO
import posixpath
from urllib.parse import unquote
from lxml import etree

NS = {
    "container": "urn:oasis:names:tc:opendocument:xmlns:container",
    "opf": "http://www.idpf.org/2007/opf",
    "dc": "http://purl.org/dc/elements/1.1/",
}

XML_PARSER = etree.XMLParser(resolve_entities=False)

class EpubDecodeError(Exception):
    """Файл не удалось разобрать: битый архив, нет нужных файлов, невалидный XML."""

def read_xml(zf: zipfile.ZipFile, name: str) -> etree._ElementTree:
    """Читает XML-файл из архива как есть, ничего не пересобирая."""
    try:
        return etree.parse(BytesIO(zf.read(name)), XML_PARSER)
    except KeyError as e:
        raise EpubDecodeError(f"В архиве нет файла {name}") from e
    except etree.XMLSyntaxError as e:
        raise EpubDecodeError(f"Невалидный XML в {name}: {e}") from e


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


def read_chapters(opf: etree._ElementTree, opf_path: str) -> list[str]:
    """Порядок глав из spine -> пути к XHTML-файлам внутри архива."""
    opf_dir = posixpath.dirname(opf_path)
    manifest = {item.get("id"): item for item in opf.iterfind("opf:manifest/opf:item", NS)}

    chapters = []
    for itemref in opf.iterfind("opf:spine/opf:itemref", NS):
        item = manifest.get(itemref.get("idref"))
        if item is None or item.get("media-type") != "application/xhtml+xml":
            continue
        # href в OPF записан относительно папки OPF и может быть URL-кодирован (%20)
        href = unquote(item.get("href", ""))
        chapters.append(posixpath.normpath(posixpath.join(opf_dir, href)))

    if not chapters:
        raise EpubDecodeError("В spine нет ни одной главы")
    return chapters