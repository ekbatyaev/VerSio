import copy
import os
from pathlib import Path
from lxml import etree
import zipfile

XML_PARSER = etree.XMLParser(resolve_entities=False)

class EpubEncodeError(Exception):
    """Книгу не удалось собрать: глава не найдена в архиве или её XHTML невалиден."""


def write_epub(source: Path, target: Path, replacements: dict[str, bytes]) -> None:
    """Копирует архив source в target запись за записью, подменяя только файлы из replacements."""
    for name, data in replacements.items():
        try:
            etree.fromstring(data, XML_PARSER)
        except etree.XMLSyntaxError as e:
            raise EpubEncodeError(f"Невалидный XHTML в {name}: {e}") from e

    tmp = target.with_name(target.name + ".tmp")
    try:
        with zipfile.ZipFile(source) as zin, zipfile.ZipFile(tmp, "w") as zout:
            if unknown := replacements.keys() - set(zin.namelist()):
                raise EpubEncodeError(f"В архиве нет файлов: {', '.join(sorted(unknown))}")

            # mimetype обязан идти первым; sorted устойчив, остальной порядок не меняется
            for info in sorted(zin.infolist(), key=lambda i: i.filename != "mimetype"):
                data = replacements[info.filename] if info.filename in replacements else zin.read(info)
                info = copy.copy(info)               # не портим ZipInfo исходного архива
                if info.filename == "mimetype":
                    info.compress_type = zipfile.ZIP_STORED
                    info.extra = b""
                zout.writestr(info, data)
        os.replace(tmp, target)                      # атомарно: битый файл не появится под именем target
    finally:
        tmp.unlink(missing_ok=True)