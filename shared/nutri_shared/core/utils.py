import re

from unidecode import unidecode


def slugify(text: str) -> str:
    text = unidecode(text)
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = text.strip("-")
    text = re.sub(r"-+", "-", text)
    return text
