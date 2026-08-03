#!/bin/bash
# Avvia l'applicazione Investment Analyzer
# Doppio click su questo file per avviare

cd "$(dirname "$0")"

echo "================================================"
echo "  Real Estate Investment Analyzer"
echo "================================================"
echo ""

errore() {
    echo ""
    echo "ERRORE: $1"
    echo ""
    read -p "Premi Invio per uscire..."
    exit 1
}

if ! command -v python3 &> /dev/null; then
    errore "Python3 non trovato. Installalo da: https://www.python.org/downloads/"
fi

echo "Python trovato: $(python3 --version)"
echo ""

# macOS/Homebrew: serve WeasyPrint (librerie pango/glib). Export necessario PRIMA dell'avvio.
if [ "$(uname)" = "Darwin" ]; then
    if [ -d "/opt/homebrew/lib" ]; then
        export DYLD_FALLBACK_LIBRARY_PATH="/opt/homebrew/lib${DYLD_FALLBACK_LIBRARY_PATH:+:$DYLD_FALLBACK_LIBRARY_PATH}"
    fi
    # Verifica dipendenza di sistema di WeasyPrint (solo se installato)
    if [ -x ".venv/bin/python" ] && .venv/bin/python -c "import weasyprint" 2>/dev/null; then
        if ! .venv/bin/python -c "from weasyprint import HTML" 2>/dev/null; then
            echo "⚠️  WeasyPrint richiede le librerie pango. Esegui:"
            echo "    brew install pango"
            echo ""
        fi
    fi
fi

if [ ! -d ".venv" ]; then
    echo "Primo avvio: installazione dipendenze (ci vogliono 1-2 minuti)..."
    python3 -m venv .venv || errore "Impossibile creare l'ambiente virtuale. Verifica di avere python3-venv installato."
    .venv/bin/pip install -q --upgrade pip || errore "Impossibile aggiornare pip."
    .venv/bin/pip install -q -r requirements.txt || errore "Impossibile installare le dipendenze. Verifica requirements.txt."
    echo "Installazione completata!"
    echo ""
fi

echo "Avvio dell'applicazione..."
echo "Una volta aperta, vai nel browser all'indirizzo: http://localhost:8501"
echo "Per CHIUDERE: premi Ctrl+C in questa finestra"
echo ""

.venv/bin/streamlit run app.py || errore "Streamlit non si e' avviato correttamente."

read -p "Premi Invio per uscire..."
