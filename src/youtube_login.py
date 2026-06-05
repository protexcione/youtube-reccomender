"""
Login automatico su YouTube tramite account Google.
Salva la sessione nel profilo Chrome persistente → il login dura tra sessioni.
"""

import time
import logging
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException, NoSuchElementException

logger = logging.getLogger("yt_recommender")

GOOGLE_LOGIN_URL = "https://accounts.google.com/signin/v2/identifier?service=youtube"


def is_logged_in(driver) -> bool:
    """Controlla se il profilo è già loggato su YouTube."""
    driver.get("https://www.youtube.com")
    time.sleep(3)
    try:
        # Avatar account presente = loggato
        driver.find_element(By.CSS_SELECTOR, "button#avatar-btn")
        return True
    except NoSuchElementException:
        return False


def login(driver, email: str, password: str, profile_name: str) -> bool:
    """
    Esegue il login Google per il profilo dato.
    Restituisce True se il login è riuscito.
    """
    logger.info("[%s] Avvio login Google per %s", profile_name, email)
    driver.get(GOOGLE_LOGIN_URL)
    wait = WebDriverWait(driver, 20)

    try:
        # --- Step 1: inserisci email ---
        email_field = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='email']"))
        )
        _human_type(email_field, email)
        time.sleep(1)

        next_btn = driver.find_element(By.CSS_SELECTOR, "#identifierNext button, #identifierNext")
        next_btn.click()
        logger.info("[%s] Email inserita, attendo campo password...", profile_name)

        # --- Step 2: inserisci password ---
        password_field = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "input[type='password']"))
        )
        time.sleep(1)
        _human_type(password_field, password)
        time.sleep(1)

        pwd_next = driver.find_element(By.CSS_SELECTOR, "#passwordNext button, #passwordNext")
        pwd_next.click()
        logger.info("[%s] Password inserita, attendo conferma login...", profile_name)

        # --- Step 3: verifica login riuscito ---
        time.sleep(5)
        driver.get("https://www.youtube.com")
        time.sleep(3)

        driver.find_element(By.CSS_SELECTOR, "button#avatar-btn")
        logger.info("[%s] ✅ Login riuscito!", profile_name)
        return True

    except TimeoutException:
        logger.error("[%s] ❌ Timeout durante il login — verifica email/password", profile_name)
        return False
    except NoSuchElementException as e:
        logger.error("[%s] ❌ Elemento non trovato: %s", profile_name, e)
        logger.error("[%s] Potrebbe esserci un CAPTCHA o verifica in 2 step", profile_name)
        return False


def ensure_logged_in(driver, email: str, password: str, profile_name: str) -> bool:
    """
    Verifica se già loggato, altrimenti fa login.
    Grazie al profilo Chrome persistente, dopo la prima volta non serve rifare il login.
    """
    if is_logged_in(driver):
        logger.info("[%s] ✅ Già loggato — sessione ripristinata dal profilo Chrome", profile_name)
        return True

    logger.info("[%s] Non loggato — avvio procedura di login...", profile_name)
    return login(driver, email, password, profile_name)


def _human_type(element, text: str):
    """Digita il testo carattere per carattere con piccoli ritardi casuali."""
    import random
    element.click()
    for char in text:
        element.send_keys(char)
        time.sleep(random.uniform(0.05, 0.15))
