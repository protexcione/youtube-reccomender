"""
Factory per istanze Chrome Selenium isolate per profilo.
Ogni profilo usa una cartella dati separata → cookie/sessione indipendenti.
"""

import logging
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

from src.config import PROFILES_DIR, PAGE_LOAD_TIMEOUT, IMPLICIT_WAIT, USER_AGENTS, HEADLESS

logger = logging.getLogger(__name__)


def get_driver(profile_name: str) -> webdriver.Chrome:
    """
    Restituisce un driver Chrome con profilo persistente isolato.
    I cookie vengono salvati in profiles/<profile_name>/ tra una sessione e l'altra.
    """
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

    # User-agent specifico del profilo
    ua = USER_AGENTS.get(profile_name, USER_AGENTS["scienza"])
    options.add_argument(f"--user-agent={ua}")

    # Risoluzione realistica
    options.add_argument("--window-size=1920,1080")

    driver = webdriver.Chrome(options=options)
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
