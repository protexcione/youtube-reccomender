"""
Rilevamento rate limiting YouTube e backoff adattivo.

YouTube può bloccare lo scraping con:
  - Pagina CAPTCHA / verifica robot
  - Redirect a /sorry/index?
  - Pagina vuota senza ytd-video-renderer
  - HTTP 429 (raro con Selenium, ma possibile)

Questo modulo centralizza il rilevamento e gestisce il backoff.
"""

import time
import random
import logging

logger = logging.getLogger("yt_recommender")

# Segnali di rate limiting nella URL o nel titolo pagina
_RATE_LIMIT_URL_PATTERNS = [
    "/sorry/index",
    "accounts.google.com/ServiceLogin",
    "youtube.com/sorry",
]

_RATE_LIMIT_TITLE_PATTERNS = [
    "before you continue",
    "prima di continuare",
    "unusual traffic",
    "verify you're not a robot",
    "verifica",
    "captcha",
    "too many requests",
]

# Backoff state globale (condiviso tra profili nello stesso processo)
_consecutive_blocks = 0
_BASE_BACKOFF = 30       # secondi base
_MAX_BACKOFF = 300       # massimo 5 minuti
_JITTER_RATIO = 0.25     # ±25% di jitter


def check_rate_limited(driver) -> bool:
    """
    Controlla se la pagina corrente indica un blocco da rate limiting.
    Restituisce True se bloccato, False se tutto ok.
    """
    try:
        current_url = driver.current_url.lower()
        page_title = driver.title.lower()
    except Exception:
        return False  # driver in stato inconsistente — non siamo noi bloccati

    for pattern in _RATE_LIMIT_URL_PATTERNS:
        if pattern in current_url:
            logger.warning("Rate limiting rilevato: URL contiene '%s'", pattern)
            return True

    for pattern in _RATE_LIMIT_TITLE_PATTERNS:
        if pattern in page_title:
            logger.warning("Rate limiting rilevato: titolo pagina '%s'", driver.title)
            return True

    return False


def register_success():
    """Segnala una richiesta riuscita: resetta il contatore di blocchi."""
    global _consecutive_blocks
    if _consecutive_blocks > 0:
        logger.info("Rate limiting rientrato dopo %d blocchi consecutivi", _consecutive_blocks)
    _consecutive_blocks = 0


def register_block():
    """Segnala un blocco: incrementa il contatore e calcola il backoff."""
    global _consecutive_blocks
    _consecutive_blocks += 1
    logger.warning("Blocco #%d consecutivo da YouTube", _consecutive_blocks)


def backoff_wait(extra_seconds: float = 0):
    """
    Attende un tempo proporzionale ai blocchi consecutivi (backoff esponenziale + jitter).
    Chiamare dopo aver rilevato rate limiting.
    """
    global _consecutive_blocks

    base = min(_BASE_BACKOFF * (2 ** (_consecutive_blocks - 1)), _MAX_BACKOFF)
    jitter = base * _JITTER_RATIO * random.uniform(-1, 1)
    wait = max(base + jitter + extra_seconds, 5.0)

    logger.info(
        "Backoff adattivo: attendo %.0fs (blocco #%d, base=%ds)",
        wait, _consecutive_blocks, base
    )
    time.sleep(wait)


def human_delay(min_s: float = 2.0, max_s: float = 5.0):
    """Pausa breve casuale tra richieste per simulare comportamento umano."""
    time.sleep(random.uniform(min_s, max_s))


def wait_and_retry_if_blocked(driver, action_fn, max_retries: int = 3):
    """
    Esegue action_fn(driver) e, se la pagina risultante è bloccata,
    aspetta con backoff e riprova. Restituisce il risultato di action_fn
    o None se tutti i tentativi falliscono.

    action_fn deve chiamare driver.get() e restituire qualcosa.
    """
    for attempt in range(1, max_retries + 1):
        result = action_fn(driver)
        if not check_rate_limited(driver):
            register_success()
            return result
        register_block()
        if attempt < max_retries:
            backoff_wait()
        else:
            logger.error("Rate limiting persistente dopo %d tentativi — skip", max_retries)
            return None
    return None
