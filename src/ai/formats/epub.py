from src.ai.models import EpubBodyTagsHiding
import re


TAG_RE = re.compile(r"<[^>]+>")


async def process_tags(body: str) -> EpubBodyTagsHiding:
    # Заменяет все тэги на простые TAG[№] в формате str, и
    # занести это в dict

    tags = TAG_RE.findall(body)
    dictionary_of_tags = {'TAG[0]': "\xa0"}
    body = body.replace(r"\xa0", f"TAG[0]")

    for i, tag in enumerate(tags, start=1):
        dictionary_of_tags[f"TAG[{i}]"] = tag
        body = body.replace(tag, f"TAG[{i}]", 1)

    return EpubBodyTagsHiding(tags = dictionary_of_tags,
                              hided_tags_body = body)