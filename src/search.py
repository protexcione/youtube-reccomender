"""
Cerca video su YouTube per canale/query e restituisce una lista di
{'video_id', 'title', 'channel'}.
Usa scraping della pagina di ricerca — niente API.
"""

import time
import random
import logging
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from src.rate_limiter import check_rate_limited, register_success, register_block, backoff_wait

logger = logging.getLogger("yt_recommender")

SEARCH_URL = "https://www.youtube.com/results?search_query={query}&sp=EgIQAQ%3D%3D"
# sp=EgIQAQ== filtra solo video (esclude playlist e canali)


def search_videos(driver, query: str, max_results: int = 5, retries: int = 3) -> list[dict]:
    """
    Cerca su YouTube e restituisce fino a max_results video.
    Ogni elemento: {'video_id': str, 'title': str, 'channel': str}
    Riprova automaticamente in caso di timeout o rate limiting.
    """
    url = SEARCH_URL.format(query=query.replace(" ", "+"))

    for attempt in range(1, retries + 1):
        try:
            logger.info("Ricerca: '%s' (tentativo %d/%d)", query, attempt, retries)
            driver.get(url)
            time.sleep(random.uniform(2, 4))

            # Controlla se YouTube ha rilevato scraping automatizzato
            if check_rate_limited(driver):
                register_block()
                if attempt < retries:
                    backoff_wait()
                    continue
                else:
                    logger.error("Rate limiting persistente per '%s' — skip", query)
                    return []

            break  # caricamento riuscito

        except TimeoutException:
            logger.warning("Timeout caricamento pagina per '%s' — tentativo %d/%d", query, attempt, retries)
            if attempt == retries:
                logger.error("Ricerca '%s' fallita dopo %d tentativi", query, retries)
                return []
            time.sleep(5 * attempt)  # backoff: 5s, 10s, 15s
        except Exception as e:
            logger.error("Errore inatteso durante driver.get() per '%s': %s", query, e)
            if attempt == retries:
                return []
            time.sleep(5 * attempt)

    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "ytd-video-renderer"))
        )
    except TimeoutException:
        # Potrebbe essere rate limiting senza redirect (pagina vuota)
        if check_rate_limited(driver):
            register_block()
            logger.warning("Rate limiting rilevato dopo attesa risultati per '%s'", query)
        else:
            logger.warning("Timeout risultati ricerca per '%s'", query)
        return []

    register_success()

    results = []
    renderers = driver.find_elements(By.CSS_SELECTOR, "ytd-video-renderer")

    for renderer in renderers[:max_results * 2]:  # ne leggiamo di più per avere margine
        try:
            link = renderer.find_element(By.CSS_SELECTOR, "a#video-title")
            href = link.get_attribute("href") or ""
            title = link.get_attribute("title") or link.text or ""

            if "watch?v=" not in href:
                continue

            video_id = href.split("watch?v=")[1].split("&")[0]

            try:
                # YouTube usa selettori diversi a seconda della versione
                for selector in [
                    "ytd-channel-name a",
                    "#channel-name a",
                    "#channel-name yt-formatted-string",
                    "yt-formatted-string#text.ytd-channel-name",
                ]:
                    els = renderer.find_elements(By.CSS_SELECTOR, selector)
                    if els and els[0].text.strip():
                        channel = els[0].text.strip()
                        break
                else:
                    channel = "Sconosciuto"
            except Exception:
                channel = "Sconosciuto"

            if video_id and title:
                results.append({
                    "video_id": video_id,
                    "title": title.strip(),
                    "channel": channel.strip(),
                })

            if len(results) >= max_results:
                break

        except Exception as e:
            logger.debug("Errore parsing renderer: %s", e)
            continue

    logger.info("Trovati %d video per '%s'", len(results), query)
    return results
