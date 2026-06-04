#!/bin/bash
# Esegui una sola volta: crea venv e installa dipendenze
set -e

echo "==> Creazione virtual environment..."
python3 -m venv .venv

echo "==> Attivazione venv..."
source .venv/bin/activate

echo "==> Installazione dipendenze..."
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "✅ Ambiente pronto."
echo "   Per attivarlo: source .venv/bin/activate"
echo "   Per testare:   python test_selenium.py"
