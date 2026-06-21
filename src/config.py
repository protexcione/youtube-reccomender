"""
Configurazione centrale del progetto.
Modifica SEED_CHANNELS e PROFILES per personalizzare i profili.
"""

import os
from pathlib import Path

# Radice del progetto
ROOT_DIR = Path(__file__).parent.parent

# Cartelle
PROFILES_DIR = ROOT_DIR / "profiles"
DATA_RAW_DIR = ROOT_DIR / "data" / "raw"
DATA_PROCESSED_DIR = ROOT_DIR / "data" / "processed"
LOGS_DIR = ROOT_DIR / "logs"
REPORTS_DIR = ROOT_DIR / "reports"

# Crea cartelle se non esistono
for d in [PROFILES_DIR, DATA_RAW_DIR, DATA_PROCESSED_DIR, LOGS_DIR, REPORTS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Database
DB_PATH = ROOT_DIR / "data" / "recommendations.db"

# Profili virtuali e canali seed
PROFILES = {
    "scienza":  ["Kurzgesagt – In a Nutshell", "Veritasium", "MinutePhysics"],
    "cucina":   ["Binging with Babish", "Pasta Grannies", "Italia Squisita"],
    "musica":   ["NPR Music", "COLORS", "Pitchfork"],
    "sport":    ["ESPN", "NBA", "Sky Sport"],
    "gaming":   ["GameSpot", "IGN", "Linus Tech Tips"],
}

# Quanti video seed guardare per profilo
SEED_VIDEOS_PER_PROFILE = 10

# Quante raccomandazioni homepage raccogliere per sessione
HOMEPAGE_RECS_COUNT = 20

# Durata simulazione (giorni)
SIMULATION_DAYS = 7

# Selenium settings
HEADLESS = True
PAGE_LOAD_TIMEOUT = 30        # secondi
IMPLICIT_WAIT = 10            # secondi
WATCH_DURATION_SECONDS = 30   # tempo simulato di visione per video seed

# User-agent per ogni profilo (evita fingerprinting uniforme)
USER_AGENTS = {
    "scienza": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "cucina":  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "musica":  "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "sport":   "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
    "gaming":  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
}
