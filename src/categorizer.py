"""
Classificatore di categoria per video YouTube basato su keyword nel titolo/canale.
Usato in sostituzione della categoria YouTube reale (non disponibile senza API).
"""

import re

_RULES = [
    ("Scienza & Tech", [
        # Canali noti
        "kurzgesagt", "veritasium", "minutephysics", "vsauce", "numberphile",
        "linus tech tips", "linus", "techlinked", "marques", "mkbhd",
        # EN
        "science", "physics", "chemistry", "biology", "space", "nasa", "quantum",
        "mathematics", "math", "engineering", "technology", "tech", "artificial intelligence",
        "machine learning", "robot", "experiment", "theory", "explained",
        "how does", "how to", "diy", "innovation", "breakthrough",
        "planet", "universe", "galaxy", "atom", "evolution", "genetics",
        "nvidia", "cpu", "gpu", "processor", "benchmark", "review pc",
        # IT
        "scienza", "fisica", "chimica", "biologia", "spazio", "tecnologia",
        "intelligenza artificiale", "esperimento", "universo", "pianeta",
        "come funziona", "scoperta", "ricerca", "ingegneria",
    ]),
    ("Cucina & Food", [
        # Canali noti
        "babish", "pasta grannies", "italia squisita", "bon appétit", "bon appetit",
        "tasty", "binging", "gordon ramsay", "jamie oliver",
        # EN
        "recipe", "cook", "cooking", "food", "kitchen", "bake", "baking",
        "chef", "eat", "meal", "restaurant", "pasta", "pizza", "bread",
        "dessert", "cake", "sauce", "grill", "roast", "fry", "soup",
        "breakfast", "lunch", "dinner", "snack", "vegan", "vegetarian",
        "ingredient", "delicious", "taste", "flavor",
        # IT
        "ricetta", "cucina", "cuoco", "cucinare", "mangiare", "pranzo",
        "cena", "colazione", "pane", "dolce", "torta", "sugo", "ragù",
        "carbonara", "risotto", "tiramisù", "gelato", "antipasto",
        "ristorante", "trattoria", "chef", "piatto", "ingredienti",
        "fatto in casa", "homemade",
    ]),
    ("Musica", [
        # Canali noti
        "npr music", "colors", "pitchfork", "tiny desk", "vevo",
        # EN
        "music", "song", "album", "concert", "live performance", "official video",
        "official audio", "lyrics", "ft.", "feat.", "music video", "mv",
        "rap", "hip hop", "r&b", "jazz", "classical", "orchestra", "piano",
        "guitar", "drum", "bass", "pop", "rock", "metal", "indie", "folk",
        "tour", "single", "ep", "release", "cover", "remix", "acoustic",
        "vocalist", "artist", "band", "dj", "producer",
        # IT
        "musica", "canzone", "album", "concerto", "testo", "feat",
        "ufficiale", "video ufficiale", "remix", "cover", "acustico",
        "cantante", "artista", "gruppo", "chitarra", "pianoforte",
    ]),
    ("Sport", [
        # Canali noti
        "espn", "nba", "sky sport", "dazn", "eurosport",
        # EN
        "sport", "sports", "football", "soccer", "basketball", "tennis",
        "golf", "baseball", "hockey", "boxing", "mma", "ufc", "formula 1",
        "f1", "motogp", "cycling", "athletics", "swimming", "olympic",
        "highlights", "match", "game recap", "tournament", "championship",
        "league", "season", "player", "team", "coach", "transfer",
        "goal", "goals", "score", "win", "defeat", "final", "semifinal",
        "nfl", "mlb", "nhl", "premier league", "serie a", "la liga",
        # IT
        "calcio", "basket", "sport", "campionato", "partita", "gara",
        "gol", "vittoria", "sconfitta", "finale", "semifinale",
        "allenatore", "giocatore", "squadra", "calciatore", "atleta",
        "champions league", "europa league", "mondiale", "europeo",
        "motore", "circuito", "podio", "sorpasso",
    ]),
    ("Gaming & Videogiochi", [
        # Canali noti
        "gamespot", "ign", "gamingmerk",
        # EN
        "game", "gaming", "gameplay", "playthrough", "walkthrough",
        "ps5", "playstation", "xbox", "nintendo", "switch", "steam",
        "fps", "rpg", "mmo", "battle royale", "open world", "dlc",
        "minecraft", "fortnite", "gta", "cod", "call of duty",
        "elden ring", "zelda", "mario", "pokemon",
        "speedrun", "let's play", "lets play",
        "trailer", "game trailer", "reveal", "patch notes",
        "esport", "esports", "tournament gaming",
        # IT
        "videogioco", "videogiochi", "gioco", "giocare",
        "recensione gioco", "gameplay ita", "guida",
    ]),
    ("News & Attualità", [
        # EN
        "news", "breaking news", "update", "report", "interview",
        "election", "politics", "economy", "war", "conflict",
        "president", "government", "parliament", "vote",
        # IT
        "notizie", "attualità", "politica", "economia", "guerra",
        "elezioni", "governo", "presidente", "parlamento",
        "tg", "telegiornale", "cronaca", "inchiesta",
    ]),
    ("Intrattenimento", [
        # EN
        "funny", "comedy", "reaction", "vlog", "challenge", "prank",
        "short", "viral", "meme", "compilation", "best of",
        "fails", "moments", "try not to laugh",
        "movie", "film", "trailer", "series", "episode", "season",
        "netflix", "disney", "amazon prime",
        "talk show", "podcast", "interview show",
        # IT
        "divertente", "commedia", "reazione", "sfida", "scherzo",
        "film", "serie", "episodio", "stagione", "recensione film",
        "trailer italiano", "clip",
    ]),
]

_COMPILED = [
    (cat, [re.compile(r"\b" + re.escape(kw) + r"\b", re.IGNORECASE) for kw in kws])
    for cat, kws in _RULES
]


def classify(title: str, channel: str = "") -> str:
    """
    Classifica un video in base a titolo e canale.
    Restituisce la categoria; 'Altro' se nessuna regola corrisponde.
    """
    text = f"{title or ''} {channel or ''}"
    for cat, patterns in _COMPILED:
        for pat in patterns:
            if pat.search(text):
                return cat
    return "Altro"
