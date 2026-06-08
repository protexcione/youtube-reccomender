"""
Simula la visione di un video YouTube per un profilo.
Apre il video, aspetta WATCH_DURATION_SECONDS, poi passa al prossimo.
"""

import time
import random
import logging
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from src.config import WATCH_DURATION_SECONDS
from src.database import insert_seed_watch

logger = logging.getLogger("yt_recommender")

VIDEO_URL = "https://www.youtube.com/watch?v={video_id}"


def watch_video(driver, video: dict, profile_name: str) -> bool:
    """
    Apre il video e lo "guarda" per WATCH_DURATION_SECONDS.
    Restituisce True se andato a buon fine.
    """
    url = VIDEO_URL.format(video_id=video["video_id"])
    logger.info("[%s] Guardo: '%s' (%s)", profile_name, video["title"], video["channel"])

    try:
        driver.get(url)
        time.sleep(random.uniform(2, 4))

        # Prova ad avviare il video se in pausa
        _try_play(driver)

        # Attendi che il player sia presente
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "video.html5-main-video"))
        )

        # Simula visione: aspetta il tempo configurato con piccoli scroll casuali
        _simulate_watching(driver, WATCH_DURATION_SECONDS)

        # Salva nel database
        insert_seed_watch(
            profile=profile_name,
            video_id=video["video_id"],
            title=video["title"],
            channel=video["channel"],
        )
        logger.info("[%s] Salvato nel DB: %s", profile_name, video["video_id"])
        return True

    except TimeoutException:
        logger.warning("[%s] Timeout caricamento video %s", profile_name, video["video_id"])
        return False
    except Exception as e:
        logger.error("[%s] Errore durante visione %s: %s", profile_name, video["video_id"], e)
        return False


def watch_seed_videos(driver, profile_name: str, videos: list[dict]) -> int:
    """
    Guarda tutti i video seed per un profilo.
    Restituisce il numero di video guardati con successo.
    """
    watched = 0
    for i, video in enumerate(videos, 1):
        logger.info("[%s] Video %d/%d", profile_name, i, len(videos))
        ok = watch_video(driver, video, profile_name)
        if ok:
            watched += 1
        # Pausa tra video (comportamento umano)
        time.sleep(random.uniform(3, 7))

    logger.info("[%s] Seed watching completato: %d/%d video", profile_name, watched, len(videos))
    return watched


def _try_play(driver):
    """Clicca play se il video è in pausa."""
    try:
        btn = driver.find_element(By.CSS_SELECTOR, "button.ytp-play-button")
        label = btn.get_attribute("data-title-no-tooltip") or ""
        if "Play" in label or "Riproduci" in label:
            btn.click()
            time.sleep(1)
    except NoSuchElementException:
        pass


def _simulate_watching(driver, duration: int):
    """
    Aspetta 'duration' secondi simulando comportamento umano
    (piccoli scroll occasionali nella pagina).
    """
    elapsed = 0
    while elapsed < duration:
        chunk = min(random.uniform(5, 10), duration - elapsed)
        time.sleep(chunk)
        elapsed += chunk
        # Scroll casuale verso i commenti e ritorno
        if random.random() < 0.3:
            driver.execute_script("window.scrollBy(0, 300)")
            time.sleep(0.5)
            driver.execute_script("window.scrollBy(0, -300)")
