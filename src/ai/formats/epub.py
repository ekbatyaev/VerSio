from src.ai.models import EpubBodyTagsHiding
import re


TAG_RE = re.compile(r"<[^>]+>")


async def process_tags(body: str) -> EpubBodyTagsHiding:
    # Должен заменить все тэги на простые TAG[№] в формате str, и
    # занести это в dict
    tags = TAG_RE.findall(body)
    hided_body = [body := body.replace(tag,f"TAG[{i}]", 1) for i, tag in enumerate(tags)]
    print(hided_body)
    pass