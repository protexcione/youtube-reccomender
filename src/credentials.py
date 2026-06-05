"""
Legge le credenziali dei profili dal file .env
"""

import os
from dotenv import load_dotenv
from src.config import ROOT_DIR

load_dotenv(ROOT_DIR / ".env")


def get_credentials(profile_name: str) -> tuple[str, str]:
    """
    Restituisce (email, password) per il profilo dato.
    Lancia ValueError se le credenziali non sono nel .env
    """
    key = profile_name.upper()
    email = os.getenv(f"PROFILE_{key}_EMAIL")
    password = os.getenv(f"PROFILE_{key}_PASSWORD")

    if not email or not password:
        raise ValueError(
            f"Credenziali mancanti per '{profile_name}'. "
            f"Aggiungi PROFILE_{key}_EMAIL e PROFILE_{key}_PASSWORD nel file .env"
        )
    return email, password


def get_all_credentials() -> dict[str, tuple[str, str]]:
    """Restituisce credenziali di tutti i profili configurati."""
    from src.config import PROFILES
    result = {}
    for profile in PROFILES:
        try:
            result[profile] = get_credentials(profile)
        except ValueError as e:
            print(f"  ⚠️  {e}")
    return result
