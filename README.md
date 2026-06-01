# YouTube Recommender Compass: Dove Ti Porta l'Algoritmo?

## Obiettivo
Simulare 5 "utenti virtuali" con interessi diversi e misurare se le raccomandazioni di YouTube convergono verso gli stessi contenuti dopo 7 giorni.

## Domanda di ricerca
**Partendo da video diversi, le raccomandazioni di YouTube convergono sempre verso gli stessi contenuti?**

## Deliverable minimi
1. Script automatizzato (Selenium) che crea 5 profili YouTube, guarda 10 video seed diversi per profilo, registra le prime 20 raccomandazioni homepage ogni giorno per 7 giorni
2. Metriche di convergenza: Overlap %, generi dominanti, diversity decay (entropia)
3. Visualizzazione: grafo di convergenza (nodi=profili, archi=similarità raccomandazioni)

## Stack Tecnologico
- **Python 3.8+**
- **Selenium**: automazione browser
- **Pandas**: gestione dati
- **NetworkX**: grafo di convergenza
- **Matplotlib**: visualizzazioni

## Pipeline (4 settimane = 150 ore)
1. **Settimana 1** (Giorni 1-7): Setup Selenium + creazione 5 profili + seed watching
2. **Settimana 2** (Giorni 8-14): Raccolta automatica raccomandazioni (7 giorni in background)
3. **Settimana 3** (Giorni 15-21): Calcolo metriche (overlap, entropia) + visualizzazione
4. **Settimana 4** (Giorni 22-28): Analisi e report finale (20 pagine) + presentazione

## Setup Ambiente

### Prerequisiti
- Python 3.8+
- Git
- Chrome/Chromium browser

### Installazione
```bash
# Clona il repo
git clone https://github.com/protexcione/youtube-reccomender.git
cd youtube-reccomender

# Crea ambiente virtuale
python -m venv venv

# Attiva ambiente virtuale
# Su Mac/Linux:
source venv/bin/activate
# Su Windows:
# venv\Scripts\activate

# Installa dipendenze
pip install -r requirements.txt
```

### Test Selenium
```bash
python test_selenium.py
```

## Struttura del Progetto
```
youtube-reccomender/
├── README.md                          # Questo file
├── requirements.txt                   # Dipendenze Python
├── test_selenium.py                   # Test Selenium
├── .gitignore                         # File da ignorare in Git
│
├── scripts/                           # Script principali
│   ├── __init__.py
│   ├── browser_setup.py               # Setup browser e driver
│   ├── profile_creator.py             # Creazione email e profili YouTube
│   ├── seed_watcher.py                # Automazione seed watching
│   ├── recommendation_collector.py    # Raccolta raccomandazioni
│   ├── metrics_calculator.py          # Calcolo metriche (overlap, entropia)
│   └── visualization.py               # Grafici e visualizzazione
│
├── data/                              # Dati
│   ├── raw/                           # Dati grezzi raccolti
│   │   └── .gitkeep
│   └── processed/                     # Dati puliti e processati
│       └── .gitkeep
│
├── docs/                              # Documentazione
│   ├── project_plan.md                # Piano dettagliato 28 giorni
│   ├── methodology.md                 # Metodologia esperimento
│   └── results_report.md              # Report risultati finali
│
└── notebooks/                         # Jupyter notebooks per analisi
    └── .gitkeep
```

## Avanzamento Progetto

### Settimana 1: Setup + Automazione
- [ ] **Giorno 1**: Setup ambiente e test Selenium
- [ ] **Giorno 2**: Email temporanee e registrazione profili
- [ ] **Giorno 3**: Seed watching automatizzato
- [ ] **Giorno 4**: Test end-to-end
- [ ] **Giorno 5**: Raccolta e parsing raccomandazioni
- [ ] **Giorno 6**: Debug e robustezza script
- [ ] **Giorno 7**: Tuning e preparazione automazione notturna

### Settimana 2: Raccolta Dati (7 giorni consecutivi)
- [ ] **Giorni 8-14**: Raccolta automatica homepage raccomandazioni

### Settimana 3: Analisi e Metriche
- [ ] **Giorno 15**: Jaccard similarity tra profili
- [ ] **Giorno 16**: Categorie dominanti
- [ ] **Giorno 17**: Entropia e diversity decay
- [ ] **Giorno 18**: Debug pipeline analitica
- [ ] **Giorno 19**: Grafo di convergenza
- [ ] **Giorno 20**: Refinement visualizzazioni
- [ ] **Giorno 21**: Output presentabili

### Settimana 4: Report e Presentazione
- [ ] **Giorno 22**: Outline documento (20 pagine)
- [ ] **Giorno 23**: Capitolo Metodologia
- [ ] **Giorno 24**: Capitolo Risultati
- [ ] **Giorno 25**: Capitolo Discussione
- [ ] **Giorno 26**: Revisione bozza
- [ ] **Giorno 27**: Slide presentazione
- [ ] **Giorno 28**: Validazione finale e backup

## Seed Video (Esempio)
```python
seeds = {
    'Scienza': ['Kurzgesagt', 'Veritasium', 'MinutePhysics'],
    'Cucina': ['Binging with Babish', 'Pasta Grannies'],
    'Musica': ['NPR Tiny Desk', 'COLORS'],
    'Sport': ['ESPN', 'NBA highlights'],
    'Gaming': ['GameSpot', 'IGN reviews']
}
# Per ogni profilo: guarda 10 video dal suo seed
# Poi solo registra, NON interagisce più
```

## Metriche da Calcolare

### 1. Overlap % (Jaccard Similarity)
```python
def jaccard_similarity(videos_A, videos_B):
    return len(set(videos_A) & set(videos_B)) / len(set(videos_A) | set(videos_B))
```

### 2. Categoria Dominante
Identifichiamo le 3 categorie più comuni tra le raccomandazioni

### 3. Entropia (Diversity Decay)
Se H scende nel tempo → convergenza verso pochi generi

## Risultati Attesi
- **H1**: Profili diversi convergono verso 30-40 video comuni
- **H2**: Esistono "attrattori" (generi/canali) che catturano tutti i profili
- **H3**: L'entropia delle raccomandazioni scende nel tempo

## Autore
protexcione

## License
MIT
