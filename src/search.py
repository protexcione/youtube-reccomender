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

logger = logging.getLogger("yt_recommender")

SEARCH_URL = "https://www.youtube.com/results?search_query={query}&sp=EgIQAQ%3D%3D"
# sp=EgIQAQ== filtra solo video (esclude playlist e canali)


def search_videos(driver, query: str, max_results: int = 5) -> list[dict]:
    """
    Cerca su YouTube e restituisce fino a max_results video.
    Ogni elemento: {'video_id': str, 'title': str, 'channel': str}
    """
    url = SEARCH_URL.format(query=query.replace(" ", "+"))
    logger.info("Ricerca: '%s'", query)
    driver.get(url)
    time.sleep(random.uniform(2, 4))

    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "ytd-video-renderer"))
        )
    except TimeoutException:
        logger.warning("Timeout risultati ricerca per '%s'", query)
        return []

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
                channel = renderer.find_element(
                    By.CSS_SELECTOR, "ytd-channel-name a"
                ).text
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
