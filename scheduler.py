"""
Scheduler automatico per la raccolta dati giornaliera.
Esegue lo scraping della homepage ogni 24h per SIMULATION_DAYS giorni.

Uso:
  python scheduler.py               # avvia lo scheduler (blocca il terminale)
  python scheduler.py --status      # mostra stato senza avviare
  python scheduler.py --interval 60 # usa 60 secondi invece di 24h (per test)
  python scheduler.py --now         # esegue subito il giorno corrente, poi schedula

Lo scheduler:
  - Riprende automaticamente dal giorno successivo all'ultimo nel DB
  - Si ferma da solo dopo SIMULATION_DAYS esecuzioni
  - Salva lo stato in data/scheduler_state.json
  - Logga ogni esecuzione in logs/scheduler.log
  - Sopravvive a riavvii: se era al giorno 3, riprende dal giorno 4
"""

import sys
import json
import time
import signal
import logging
import argparse
from datetime import datetime, timedelta
from pathlib import Path

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR

from src.logger import setup_logging
from src.config import PROFILES, SIMULATION_DAYS, HOMEPAGE_RECS_COUNT, ROOT_DIR
from src.database import init_db, get_days_collected, get_collection_summary

logger = setup_logging("yt_recommender")

STATE_FILE = ROOT_DIR / "data" / "scheduler_state.json"
DEFAULT_INTERVAL_HOURS = 24


# ── Stato persistente ────────────────────────────────────────────────────────

def load_state() -> dict:
    """Carica lo stato dello scheduler da file JSON."""
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {"runs_completed": 0, "last_run": None, "last_day": 0}


def save_state(state: dict):
    """Salva lo stato dello scheduler su file JSON."""
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        logger.error("Errore salvataggio stato scheduler: %s", e)


def next_day_to_run() -> int:
    """
    Calcola il prossimo giorno da raccogliere in base ai dati nel DB.
    Restituisce None se tutti i giorni sono già completi.
    """
    days_done = get_days_collected()
    # Cerca il primo giorno (1-7) non ancora completo
    for day in range(1, SIMULATION_DAYS + 1):
        if day not in days_done:
            return day
    return None  # tutti i giorni completati


def is_day_complete(day: int) -> bool:
    """Restituisce True se tutti i profili hanno almeno HOMEPAGE_RECS_COUNT record per quel giorno."""
    from src.database import get_profile_day_counts
    counts = get_profile_day_counts()
    day_counts = {r["profile"]: r["count"] for r in counts if r["day"] == day}
    return (
        len(day_counts) == len(PROFILES) and
        all(day_counts.get(p, 0) >= HOMEPAGE_RECS_COUNT for p in PROFILES)
    )


# ── Job principale ───────────────────────────────────────────────────────────

def scraping_job(state: dict, scheduler: BlockingScheduler):
    """
    Job eseguito dallo scheduler ogni intervallo.
    Raccoglie le raccomandazioni per il giorno corrente.
    """
    day = next_day_to_run()

    if day is None:
        logger.info("Tutti i %d giorni completati — arresto scheduler", SIMULATION_DAYS)
        _print_final_summary()
        scheduler.shutdown(wait=False)
        return

    logger.info("=" * 55)
    logger.info("SCHEDULER — Avvio raccolta giorno %d/%d", day, SIMULATION_DAYS)
    logger.info("=" * 55)

    # Importa qui per evitare dipendenze circolari e caricare tardi il browser
    from scrape_homepage import _run_profiles_with_retry

    start = datetime.now()
    results = _run_profiles_with_retry(list(PROFILES.keys()), day)
    elapsed = (datetime.now() - start).seconds

    ok_count = sum(1 for v in results.values() if v)
    logger.info(
        "Giorno %d completato in %ds — %d/%d profili OK",
        day, elapsed, ok_count, len(PROFILES)
    )

    # Aggiorna stato
    state["runs_completed"] += 1
    state["last_run"] = datetime.now().isoformat()
    state["last_day"] = day
    save_state(state)

    # Controlla se era l'ultimo giorno
    if day >= SIMULATION_DAYS:
        logger.info("Ultimo giorno raggiunto (%d) — arresto scheduler", SIMULATION_DAYS)
        _print_final_summary()
        scheduler.shutdown(wait=False)


def _print_final_summary():
    """Stampa il riepilogo finale della raccolta."""
    s = get_collection_summary()
    print("\n" + "=" * 55)
    print("RACCOLTA COMPLETATA")
    print("=" * 55)
    print(f"  Record totali: {s.get('total_records', 0)} / {s.get('expected_total', 0)}")
    print(f"  Completezza:   {s.get('completeness_pct', 0)}%")
    print(f"  Giorni:        {s.get('days_collected', [])}")
    print("\nPuoi procedere con l'analisi dei dati raccolti.")


# ── Listener eventi ──────────────────────────────────────────────────────────

def _make_listener(state: dict, scheduler: BlockingScheduler):
    def listener(event):
        if event.exception:
            logger.error("Job scheduler fallito: %s", event.exception)
            # Non arresta lo scheduler — riproverà al prossimo intervallo
    return listener


# ── Status ───────────────────────────────────────────────────────────────────

def print_status():
    """Stampa lo stato corrente senza avviare lo scheduler."""
    init_db()
    state = load_state()
    s = get_collection_summary()
    day = next_day_to_run()

    print("\n" + "=" * 55)
    print("STATO SCHEDULER")
    print("=" * 55)
    print(f"  Runs completati:   {state['runs_completed']}")
    print(f"  Ultima esecuzione: {state['last_run'] or 'mai'}")
    print(f"  Ultimo giorno:     {state['last_day']}")
    print(f"  Prossimo giorno:   {day or 'COMPLETATO'}")
    print(f"  Record DB:         {s.get('total_records', 0)} / {s.get('expected_total', 0)}")
    print(f"  Completezza:       {s.get('completeness_pct', 0)}%")

    days = s.get("days_collected", [])
    bar = "".join("#" if d in days else "." for d in range(1, SIMULATION_DAYS + 1))
    print(f"  Progresso:         [{bar}] ({len(days)}/{SIMULATION_DAYS} giorni)")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Scheduler scraping YouTube Recommender")
    parser.add_argument("--status", action="store_true", help="Mostra stato e termina")
    parser.add_argument("--interval", type=float, default=DEFAULT_INTERVAL_HOURS,
                        help=f"Intervallo in ore tra le esecuzioni (default: {DEFAULT_INTERVAL_HOURS})")
    parser.add_argument("--now", action="store_true",
                        help="Esegui subito il giorno corrente, poi aspetta l'intervallo")
    args = parser.parse_args()

    init_db()

    if args.status:
        print_status()
        return

    state = load_state()
    day = next_day_to_run()

    if day is None:
        print("Tutti i giorni sono gia' stati raccolti. Niente da fare.")
        _print_final_summary()
        return

    interval_seconds = int(args.interval * 3600)
    scheduler = BlockingScheduler(timezone="Europe/Rome")

    # Aggiunge listener per errori
    scheduler.add_listener(
        _make_listener(state, scheduler),
        EVENT_JOB_EXECUTED | EVENT_JOB_ERROR
    )

    # Job ricorrente: ogni `interval` ore
    scheduler.add_job(
        scraping_job,
        trigger="interval",
        seconds=interval_seconds,
        args=[state, scheduler],
        id="scraping_job",
        next_run_time=datetime.now() if args.now else datetime.now() + timedelta(seconds=interval_seconds),
        max_instances=1,
        coalesce=True,
    )

    next_run = datetime.now() if args.now else datetime.now() + timedelta(seconds=interval_seconds)
    print("\n" + "=" * 55)
    print("SCHEDULER AVVIATO")
    print("=" * 55)
    print(f"  Prossimo giorno da raccogliere: {day}")
    print(f"  Prima esecuzione:               {'ORA' if args.now else next_run.strftime('%Y-%m-%d %H:%M')}")
    print(f"  Intervallo:                     {args.interval:.1f} ore")
    print(f"  Giorni rimanenti:               {SIMULATION_DAYS - (day - 1)}")
    print(f"  Fine prevista:                  {(next_run + timedelta(hours=args.interval * (SIMULATION_DAYS - day))).strftime('%Y-%m-%d %H:%M')}")
    print("\nPremi Ctrl+C per interrompere (i dati raccolti sono salvati)")
    print("=" * 55 + "\n")

    try:
        scheduler.start()
    except KeyboardInterrupt:
        logger.info("Scheduler interrotto dall'utente (Ctrl+C)")
        print("\nScheduler interrotto. I dati raccolti sono stati salvati nel DB.")
        print("Per riprendere: python scheduler.py --now")


if __name__ == "__main__":
    main()
