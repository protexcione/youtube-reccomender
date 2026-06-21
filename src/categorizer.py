"""
Classificatore di categoria per video YouTube basato su keyword nel titolo/canale.
Usato in sostituzione della categoria YouTube reale (non disponibile senza API).
"""

import re

# Keyword per categoria (case-insensitive, ordine = priorità)
_RULES = [
    ("Scienza & Tech", [
        "science", "physics", "chemistry", "biology", "space", "nasa", "quantum",
        "math", "mathematics", "engineering", "technology", "tech", "ai", "robot",
        "scienza", "fisica", "chimica", "spazio", "tecnologia", "veritasium",
        "kurzgesagt", "minutephysics", "vsauce", "numberphile",
        "linus", "nvidia", "cpu", "gpu", "processor", "computer",
    ]),
    ("Cucina & Food", [
        "recipe", "cook", "food", "kitchen", "bake", "chef", "eat", "meal",
        "restaurant", "pasta", "pizza", "bread", "dessert", "cake", "sauce",
        "ricetta", "cucina", "cuoco", "mangiare", "pranzo", "cena", "babish",
        "grannies", "squisita", "gordon", "ramsay",
    ]),
    ("Musica", [
        "music", "song", "album", "concert", "live", "official", "audio",
        "lyrics", "ft.", "feat.", "mv", "video clip", "rap", "hip hop",
        "jazz", "classical", "orchestra", "piano", "guitar", "drum",
        "npr music", "colors", "pitchfork", "tiny desk",
    ]),
    ("Sport", [
        "sport", "football", "soccer", "basketball", "nba", "nfl", "tennis",
        "golf", "baseball", "hockey", "boxing", "mma", "ufc", "formula 1", "f1",
        "calcio", "serie a", "champions", "premier", "highlights", "match",
        "game recap", "espn", "sky sport", "goal", "goals",
    ]),
    ("Gaming & Videogiochi", [
        "game", "gaming", "gameplay", "playthrough", "review", "ps5", "xbox",
        "nintendo", "switch", "steam", "pc gaming", "fps", "rpg", "mmo",
        "minecraft", "fortnite", "ign", "gamespot", "trailer", "dlc", "patch",
    ]),
    ("News & Attualità", [
        "news", "breaking", "update", "report", "interview", "election",
        "notizie", "attualità", "politica", "economia", "guerra",
    ]),
    ("Intrattenimento", [
        "funny", "comedy", "reaction", "vlog", "challenge", "prank",
        "short", "trending", "viral", "meme", "compilation",
    ]),
]

_COMPILED = [
    (cat, [re.compile(r"\b" + re.escape(kw) + r"\b", re.IGNORECASE) for kw in kws])
    for cat, kws in _RULES
]


def classify(title: str, channel: str = "") -> str:
    """
    Classifica un video in base a titolo e canale.
    Restituisce la categoria come stringa; 'Altro' se nessuna regola corrisponde.
    """
    text = f"{title or ''} {channel or ''}"
    for cat, patterns in _COMPILED:
        for pat in patterns:
            if pat.search(text):
                return cat
    return "Altro"
