# YouTube Recommender Compass — Stato del Progetto

## Contesto
Progetto di ricerca accademica: "Le raccomandazioni di YouTube convergono verso gli stessi contenuti partendo da profili diversi?"

- **Repository:** `protexcione/youtube-reccomender`
- **Branch di sviluppo:** `claude/lucid-rubin-v3oPb`
- **PC utente:** Windows, PowerShell, Python 3.14, venv in `.venv/`
- **Attivazione venv:** `.venv\Scripts\activate`

---

## Stack tecnologico
- Python + Selenium (browser automation, no API YouTube)
- SQLite (database locale `data/recommendations.db`)
- Pandas, NetworkX, Matplotlib, Seaborn, SciPy
- APScheduler (raccolta automatica giornaliera)
- Chrome headless (`HEADLESS = True` in `src/config.py`)

## Struttura cartelle
```
youtube-reccomender/
├── src/
│   ├── config.py       # configurazione centrale (profili, seed, parametri)
│   ├── driver.py       # factory Chrome isolato per profilo (cookie persistenti)
│   ├── database.py     # schema SQLite + CRUD
│   ├── logger.py       # logging console + file rotante (UTF-8 forzato)
│   ├── search.py       # scraping risultati ricerca YouTube (con retry)
│   └── watcher.py      # visione video simulata + salvataggio DB
├── profiles/           # cookie Chrome isolati per ogni profilo
│   ├── scienza/
│   ├── cucina/
│   ├── musica/
│   ├── sport/
│   └── gaming/
├── data/
│   ├── raw/
│   ├── processed/
│   └── recommendations.db
├── logs/
├── reports/
├── setup_profiles.py   # inizializza i 5 profili Chrome (accetta cookie)
├── seed_watch.py       # ogni profilo guarda 10 video seed
├── test_setup.py       # test Lunedi: struttura + DB + logger
├── test_selenium.py    # test Chrome su YouTube
├── test_login.py       # test isolamento profili
├── test_seed_watch.py  # test ricerca + visione per profilo singolo
├── verify_cookies.py   # test Giovedi: persistenza + isolamento cookie (con browser)
├── test_cookies.py     # test Giovedi: struttura + mock driver (senza browser)
└── e2e_test.py         # test Venerdi: pipeline completa da zero a seed watching
```

## 5 Profili virtuali
| Profilo | Canali seed |
|---------|-------------|
| scienza | Kurzgesagt, Veritasium, MinutePhysics |
| cucina  | Binging with Babish, Pasta Grannies, Italia Squisita |
| musica  | NPR Music, COLORS, Pitchfork |
| sport   | ESPN, NBA, Sky Sport |
| gaming  | GameSpot, IGN, Linus Tech Tips |

---

## SCHEDULE COMPLETA

### SETTIMANA 1 — Setup & Infrastruttura (35 ore)

| Giorno | Attività | Stato | Output |
|--------|----------|-------|--------|
| Lunedi | Setup ambiente, struttura cartelle, DB, logger | ✅ FATTO | `src/config.py`, `src/database.py`, `src/logger.py`, `src/driver.py` |
| Martedi | 5 profili Chrome isolati con cookie separati (no login Google) | ✅ FATTO | `setup_profiles.py`, profili in `profiles/` |
| Mercoledi | Script seed watching: ogni profilo guarda 10 video | ✅ FATTO | `src/search.py`, `src/watcher.py`, `seed_watch.py` — 50 video guardati |
| Giovedi | Cookie persistence + profili Chrome verificati | ✅ FATTO | `verify_cookies.py`, `test_cookies.py`, snapshot in `profiles/_snapshots/` |
| Venerdi | Test end-to-end: 1 profilo completo da zero a seed watching | ✅ FATTO | `e2e_test.py` — 7 step, report con metriche |
| Sabato | Debug + hardening (gestione crash, rate limiting) | ⏳ PROSSIMO | — |

### SETTIMANA 2 — Raccolta Dati 7 giorni (25 ore)

| Giorno | Attività | Stato | Output |
|--------|----------|-------|--------|
| Lunedi | Script scraping homepage: 20 raccomandazioni per profilo | ❌ DA FARE | `src/scraper.py` |
| Martedi | Database schema per raccomandazioni giornaliere | ❌ DA FARE | tabella `recommendations` già pronta |
| Mercoledi | Scheduler automatico APScheduler: ogni 24h per 7 giorni | ❌ DA FARE | `scheduler.py` |
| Gio–Dom | Raccolta automatica in background + monitoraggio logs | ❌ DA FARE | 700 record (5×20×7) |
| Sabato | Script `get_category()` via scraping pagina video | ❌ DA FARE | categoria per ogni video |

### SETTIMANA 3 — Analisi & Visualizzazioni (50 ore)

| Giorno | Attività | Stato | Output |
|--------|----------|-------|--------|
| Lunedi | Jaccard similarity tra profili per ogni giorno | ❌ DA FARE | matrice 5×5×7 |
| Martedi | Overlap % giornaliero + trend temporale | ❌ DA FARE | tabella + plot |
| Mercoledi | Entropia H per giorno per profilo (diversity decay) | ❌ DA FARE | grafo H(t) |
| Giovedi | Heatmap profilo × categoria × giorno | ❌ DA FARE | heatmap matplotlib |
| Venerdi | Grafo convergenza NetworkX (nodi=profili, archi=Jaccard) | ❌ DA FARE | grafo animato |
| Sabato | Dashboard riassuntiva: tutti i grafici in PDF/HTML | ❌ DA FARE | report visuale |

### SETTIMANA 4 — Analisi Accademica & Scrittura (40 ore)

| Giorno | Attività | Stato | Output |
|--------|----------|-------|--------|
| Lunedi | Review letteratura: filter bubble, echo chamber, YouTube algorithm | ❌ DA FARE | bibliografia annotata |
| Martedi | Interpretazione risultati: H1/H2/H3 confermate? | ❌ DA FARE | sezione Risultati |
| Mercoledi | Scrittura tesi: Introduzione + Metodologia (8pp) | ❌ DA FARE | bozza cap. 1–2 |
| Giovedi | Scrittura tesi: Risultati + Discussione (8pp) | ❌ DA FARE | bozza cap. 3–4 |
| Venerdi | Conclusioni + limiti + sviluppi futuri (4pp) | ❌ DA FARE | documento 20pp |
| Sabato | Presentazione (10 slide) + rehearsal | ❌ DA FARE | slide deck |

---

## Ipotesi da testare
- **H1:** Profili diversi convergono verso 30-40% di overlap dopo 7 giorni
- **H2:** Entropia H scende nel tempo (meno varietà = convergenza)
- **H3:** Alcune categorie "catturano" tutti i profili indipendentemente dal seed

---

## Problemi noti / Note tecniche
- Il nome canale nei risultati di ricerca mostra "Sconosciuto" (problema CSS selector YouTube) — cosmetic, non blocca la ricerca
- Errori GPU AMD in console (EGL, direct_composition) — normali su Windows, ignorabili
- Errori Google GCM (DEPRECATED_ENDPOINT, PHONE_REGISTRATION_ERROR) — normali, ignorabili
- UnicodeEncodeError emoji su Windows — parzialmente risolto con UTF-8 forzato in logger.py; titoli con emoji nei log console mostrano errore ma i dati vengono salvati correttamente nel DB
- Il crash del renderer Chrome su timeout è gestito con retry automatico (3 tentativi, backoff 5s/10s/15s)

## Stato database attuale
- Tabella `seed_watches`: 50 record (10 video × 5 profili) + 5 record di test da Lunedi
- Tabella `recommendations`: vuota (si popola dalla Settimana 2)

---

## Comandi utili
```powershell
# Attiva ambiente
.venv\Scripts\activate

# Test tutto
python test_setup.py
python test_selenium.py
python test_login.py scienza
python test_seed_watch.py scienza

# Giovedi: verifica cookie
python test_cookies.py                  # test senza browser (struttura + mock)
python verify_cookies.py                # verifica completa con browser (tutti i profili)
python verify_cookies.py scienza        # solo un profilo

# Venerdi: test end-to-end
python e2e_test.py                      # usa profilo 'scienza' di default
python e2e_test.py cucina               # profilo specifico
python e2e_test.py scienza --keep-data  # non azzera il DB prima

# Setup profili
python setup_profiles.py

# Seed watching (profilo singolo o tutti)
python seed_watch.py scienza
python seed_watch.py

# Aggiorna da remoto
git pull origin claude/relaxed-shannon-y30nij
```
