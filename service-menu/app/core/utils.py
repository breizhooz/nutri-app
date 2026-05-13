import re
from unidecode import unidecode

def slugify(text: str)-> str:
    """
    Convert the title to slub URL-friendly

    Exemples:
        "Pâtes à la carbonara" -> "pates-a-la-carbonara"
    """
    #convert  accent to ASCII
    text = unidecode(text)
    text = text.lower()
    #replace all non alphanum to -
    text = re.sub(r'[^a-z0-9]+', '-', text)
    #clean start
    text = text.strip('-')
    text = re.sub(r'-+', '-', text)
    return text