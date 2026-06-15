"""
Factory per istanze Chrome Selenium isolate per profilo.
Ogni profilo usa una cartella dati separata → cookie/sessione indipendenti.
"""

import logging
import shutil
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException

from src.config import PROFILES_DIR, PAGE_LOAD_TIMEOUT, IMPLICIT_WAIT, USER_AGENTS, HEADLESS

logger = logging.getLogger(__name__)

# Tempo massimo per l'avvio di Chrome (secondi)
_DRIVER_STARTUP_TIMEOUT = 30


def _check_chrome_available():
    """Verifica che chrome/chromium sia disponibile nel PATH."""
    for binary in ("google-chrome", "chromium-browser", "chromium", "chrome"):
        if shutil.which(binary):
            return binary
    return None


def get_driver(profile_name: str) -> webdriver.Chrome:
    """
    Restituisce un driver Chrome con profilo persistente isolato.
    I cookie vengono salvati in profiles/<profile_name>/ tra una sessione e l'altra.
    Solleva RuntimeError se Chrome non è disponibile o non parte.
    """
    chrome_binary = _check_chrome_available()
    if chrome_binary is None:
        raise RuntimeError(
            "Chrome/Chromium non trovato nel PATH. "
            "Installare con: sudo apt install chromium-browser"
        )

    profile_dir = PROFILES_DIR / profile_name
    profile_dir.mkdir(parents=True, exist_ok=True)

    options = Options()

    if HEADLESS:
        options.add_argument("--headless=new")

    # Profilo persistente
    options.add_argument(f"--user-data-dir={profile_dir}")

    # Isolamento e stabilità
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    # Riduce il numero di crash del renderer su sistemi con poca RAM
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-gpu")
    options.add_argument("--single-process")

    # User-agent specifico del profilo
    ua = USER_AGENTS.get(profile_name, USER_AGENTS["scienza"])
    options.add_argument(f"--user-agent={ua}")

    # Risoluzione realistica
    options.add_argument("--window-size=1920,1080")

    try:
        driver = webdriver.Chrome(options=options)
    except WebDriverException as e:
        msg = str(e)
        if "chrome not reachable" in msg.lower() or "failed to start" in msg.lower():
            raise RuntimeError(
                f"Chrome non riuscito ad avviarsi per profilo '{profile_name}'. "
                f"Dettaglio: {msg}"
            ) from e
        if "session not created" in msg.lower():
            raise RuntimeError(
                f"Versione ChromeDriver incompatibile con Chrome per profilo '{profile_name}'. "
                "Aggiornare chromedriver."
            ) from e
        raise

    driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
    driver.implicitly_wait(IMPLICIT_WAIT)

    # Rimuove il flag webdriver dal navigator JS
    try:
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"},
        )
    except Exception as e:
        logger.warning("CDP webdriver patch fallita (ignorabile): %s", e)

    logger.info("Driver creato per profilo '%s' → %s", profile_name, profile_dir)
    return driver


def safe_quit(driver):
    """Chiude il driver senza sollevare eccezioni (da usare nei blocchi finally)."""
    if driver is None:
        return
    try:
        driver.quit()
    except Exception as e:
        logger.debug("Errore chiusura driver (ignorabile): %s", e)
