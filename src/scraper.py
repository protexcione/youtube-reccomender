"""
Scraping della homepage YouTube per raccogliere raccomandazioni.
Ogni profilo visita https://www.youtube.com/ e salva le prime
HOMEPAGE_RECS_COUNT raccomandazioni nel DB.

Usato dallo scheduler (Settimana 2) e da scrape_homepage.py.
"""

import time
import random
import logging
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

from src.config import HOMEPAGE_RECS_COUNT
from src.database import insert_recommendation
from src.rate_limiter import check_rate_limited, register_success, register_block, backoff_wait

logger = logging.getLogger("yt_recommender")

HOMEPAGE_URL = "https://www.youtube.com/"

# Selettori per le card video sulla homepage
# ytd-rich-item-renderer è il container principale del feed homepage
_FEED_ITEM_SELECTORS = [
    "ytd-rich-item-renderer",
    "ytd-video-renderer",
]

# Selettori multipli per il titolo video (YouTube cambia spesso)
_TITLE_SELECTORS = [
    "a#video-title-link",
    "a#video-title",
    "h3 a",
]

# Selettori multipli per il nome canale
_CHANNEL_SELECTORS = [
    "ytd-channel-name a",
    "#channel-name a",
    "#channel-name yt-formatted-string",
    "yt-formatted-string#text.ytd-channel-name",
    "ytd-video-owner-renderer a",
]


def scrape_homepage(driver, profile: str, day: int, max_results: int = None, retries: int = 3) -> list[dict]:
    """
    Carica la homepage YouTube per il profilo dato e raccoglie le raccomandazioni.
    Salva ogni raccomandazione nel DB e restituisce la lista dei record inseriti.

    Args:
        driver:      WebDriver già inizializzato con il profilo corretto
        profile:     nome del profilo (es. "scienza")
        day:         giorno della simulazione (1-7)
        max_results: quante raccomandazioni raccogliere (default: HOMEPAGE_RECS_COUNT)
        retries:     numero massimo di tentativi in caso di errore

    Returns:
        lista di dict con le raccomandazioni raccolte e salvate
    """
    if max_results is None:
        max_results = HOMEPAGE_RECS_COUNT

    logger.info("[%s] Scraping homepage — giorno %d (target: %d raccomandazioni)", profile, day, max_results)

    # Carica homepage con retry
    loaded = False
    for attempt in range(1, retries + 1):
        try:
            driver.get(HOMEPAGE_URL)
            time.sleep(random.uniform(3, 5))

            if check_rate_limited(driver):
                register_block()
                logger.warning("[%s] Rate limiting dopo caricamento homepage (tentativo %d/%d)", profile, attempt, retries)
                if attempt < retries:
                    backoff_wait()
                    continue
                logger.error("[%s] Rate limiting persistente — scraping homepage saltato", profile)
                return []

            loaded = True
            break

        except TimeoutException:
            logger.warning("[%s] Timeout homepage (tentativo %d/%d)", profile, attempt, retries)
            if attempt < retries:
                time.sleep(5 * attempt)
            continue
        except WebDriverException as e:
            logger.error("[%s] WebDriverException su homepage: %s", profile, e)
            if attempt < retries:
                time.sleep(5 * attempt)
            continue

    if not loaded:
        logger.error("[%s] Impossibile caricare la homepage dopo %d tentativi", profile, retries)
        return []

    # Aspetta che il feed si popoli
    feed_selector = _wait_for_feed(driver, profile)
    if feed_selector is None:
        return []

    register_success()

    # Scroll per caricare più risultati se necessario
    _scroll_to_load(driver, max_results, feed_selector)

    # Parsing delle card video
    results = _parse_feed(driver, profile, day, max_results, feed_selector)

    logger.info("[%s] Giorno %d: raccolte e salvate %d/%d raccomandazioni", profile, day, len(results), max_results)
    return results


def _wait_for_feed(driver, profile: str) -> str | None:
    """
    Attende che il feed homepage sia caricato.
    Prova i selettori in ordine e restituisce quello che funziona, o None.
    """
    for selector in _FEED_ITEM_SELECTORS:
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
            )
            logger.debug("[%s] Feed trovato con selettore: %s", profile, selector)
            return selector
        except TimeoutException:
            continue

    # Controlla se è rate limiting silenzioso (pagina caricata ma vuota)
    if check_rate_limited(driver):
        register_block()
        logger.warning("[%s] Rate limiting silenzioso rilevato (pagina vuota)", profile)
    else:
        logger.warning("[%s] Timeout: nessun elemento feed trovato sulla homepage", profile)

    return None


def _scroll_to_load(driver, target: int, selector: str):
    """
    Esegue scroll progressivo verso il basso per caricare più card nel feed.
    Si ferma quando ci sono abbastanza elementi o dopo max_scrolls iterazioni.
    """
    max_scrolls = 5
    for i in range(max_scrolls):
        current = len(driver.find_elements(By.CSS_SELECTOR, selector))
        if current >= target * 1.5:  # abbiamo il 50% di margine
            break
        try:
            driver.execute_script("window.scrollBy(0, 800)")
            time.sleep(random.uniform(1.0, 2.0))
        except Exception:
            break


def _parse_feed(driver, profile: str, day: int, max_results: int, selector: str) -> list[dict]:
    """
    Estrae video dal feed, li salva nel DB e restituisce i record inseriti.
    """
    items = driver.find_elements(By.CSS_SELECTOR, selector)
    results = []
    position = 0

    for item in items:
        if len(results) >= max_results:
            break
        try:
            video_id, title = _extract_video_id_and_title(item)
            if not video_id or not title:
                continue

            channel = _extract_channel(item)

            saved = insert_recommendation(
                profile=profile,
                day=day,
                position=position,
                video_id=video_id,
                title=title,
                channel=channel,
            )

            if saved:
                results.append({
                    "video_id": video_id,
                    "title": title,
                    "channel": channel,
                    "position": position,
                })
                logger.debug("[%s] Pos %2d: [%s] %s", profile, position, channel, title[:60])

            position += 1

        except Exception as e:
            logger.debug("[%s] Errore parsing item: %s", profile, e)
            continue

    return results


def _extract_video_id_and_title(item) -> tuple[str, str]:
    """Estrae video_id e title da una card del feed. Restituisce ('', '') se non trovato."""
    for selector in _TITLE_SELECTORS:
        try:
            link = item.find_element(By.CSS_SELECTOR, selector)
            href = link.get_attribute("href") or ""
            if "watch?v=" not in href:
                continue
            video_id = href.split("watch?v=")[1].split("&")[0]
            title = link.get_attribute("title") or link.text or ""
            if video_id and title.strip():
                return video_id, title.strip()
        except Exception:
            continue
    return "", ""


def _extract_channel(item) -> str:
    """Estrae il nome canale da una card del feed."""
    for selector in _CHANNEL_SELECTORS:
        try:
            els = item.find_elements(By.CSS_SELECTOR, selector)
            if els and els[0].text.strip():
                return els[0].text.strip()
        except Exception:
            continue
    return "Sconosciuto"


def get_day_recommendation_count(profile: str, day: int) -> int:
    """Restituisce quante raccomandazioni sono già salvate per profilo+giorno."""
    from src.database import get_recommendations
    return len(get_recommendations(profile=profile, day=day))
