# Documentazione Tecnica — Real Estate Investment Analyzer

## Indice

1. [Panoramica del Progetto](#1-panoramica-del-progetto)
2. [Struttura](#2-struttura)
3. [Architettura](#3-architettura)
4. [engine.py — Modello Finanziario](#4-enginepy--modello-finanziario)
5. [Interfaccia Streamlit](#5-interfaccia-streamlit-apppy-ui_sidebarpy-ui_tabspy)
6. [Algoritmi Chiave](#6-algoritmi-chiave)
7. [Setup e Avvio](#7-setup-e-avvio)
8. [Testing](#8-testing)
9. [Proposte Future](#9-proposte-future)
10. [Deploy su Streamlit Community Cloud](#10-deploy-su-streamlit-community-cloud)

---

## 1. Panoramica del Progetto

Applicazione Streamlit per la simulazione finanziaria di investimenti immobiliari con leva finanziaria (mutuo), confronto ETF, analisi IRR/NPV e esportazione report Excel.

**Stack tecnologico:**

| Componente | Libreria | Versione minima |
|---|---|---|
| UI / Dashboard | Streamlit | ≥ 1.32 |
| Calcoli numerici | NumPy | ≥ 1.24 |
| Tabelle dati | Pandas | ≥ 2.0 |
| Grafici interattivi | Plotly | 6.9.0 (pinnata) |
| Export immagini grafici (per il PDF) | kaleido | 1.4.0 (pinnata) |
| Ottimizzazione numerica | SciPy (`brentq`) | ≥ 1.11 |
| Export Excel | openpyxl | ≥ 3.1 |
| Report PDF | weasyprint | ≥ 66.0 |
| Testing | pytest | ≥ 7.0 |

> Plotly e kaleido sono pinnati a versione esatta (non `>=`) perché un bump di kaleido ha già rotto la generazione PDF su Streamlit Cloud in passato — vedi commit `518a5f7`.

---

## 2. Struttura

```
iron-tool/
├── app.py                 # Entrypoint Streamlit: orchestratore (page config, sidebar → engine → tabs)
├── ui_sidebar.py           # Widget sidebar (input, validazioni, salvataggio/import scenari)
├── ui_tabs.py               # Le 4 tab (KPI, Ammortamento, Benchmark, Dettaglio) + export Excel/PDF
├── utils.py                # Utility condivise (fmt: formattazione numeri in stile italiano)
├── engine.py              # Modello finanziario (calcoli, dataclass, formule)
├── report.py              # Generazione report PDF
├── test_engine.py         # Suite di test unitari
├── MANUALE_FORMULE.md     # Documentazione formule matematiche
├── MANUALE_FORMULE.docx   # Versione Word del manuale
├── README.md              # Questo file
├── requirements.txt       # Dipendenze Python
├── avvia.sh               # Script di avvio per macOS/Linux
├── avvia.bat              # Script di avvio per Windows
├── scenarios/             # Residuo di una vecchia feature di salvataggio su disco; oggi gli scenari sono solo in-session (vedi §5.3)
└── .streamlit/
    └── config.toml        # Configurazione Streamlit
```

---

## 3. Architettura

Il progetto segue una separazione netta tra **logica di calcolo** e **presentazione**:

```
┌───────────────────────────────────────────────────┐
│  app.py — orchestratore (page config, password,   │
│  costruisce InvestmentParams, chiama l'engine)     │
└───────────────┬─────────────────────┬─────────────┘
                │                     │
                ▼                     ▼
┌───────────────────────┐   ┌─────────────────────────┐
│  ui_sidebar.py         │   │  ui_tabs.py               │
│  render_sidebar()      │   │  render_tab_kpi()         │
│  → SimpleNamespace     │   │  render_tab_mutuo()       │
│  con tutti gli input   │   │  render_tab_benchmark()   │
│  raccolti + scenari    │   │  render_tab_dettaglio()   │
└───────────┬────────────┘   │  (include export Excel/PDF)│
            │                └─────────────┬─────────────┘
            ▼                              ▼
        ┌───────────────────────────────────────┐
        │           engine.py (Calcoli)          │
        │  InvestmentParams (dataclass)          │
        │  rata_mensile() / piano_ammortamento() │
        │  proiezione() / scenario_cash()        │
        │  calcola_irr() / calcola_npv()         │
        │  calcola_rendimenti_per_anno()         │
        └─────────────────────────────────────────┘
```

`engine.py` è un modulo **indipendente** (nessuna dipendenza da Streamlit: tutta la logica è testabile standalone con pytest). `ui_sidebar.py` e `ui_tabs.py` gestiscono rispettivamente input/layout della sidebar e rendering delle tab; `utils.py` contiene la sola funzione di formattazione (`fmt`) condivisa da entrambi. `app.py` fa da collante: raccoglie gli input dalla sidebar, costruisce `InvestmentParams`, chiama l'engine e passa i risultati alle tab.

---

## 4. engine.py — Modello Finanziario

### 4.1 InvestmentParams (dataclass)

Struttura dati centrale. Contiene tutti i parametri dell'investimento:

| Gruppo | Campi |
|---|---|---|
| **Acquisto & Lavori** | `prezzo`, `imposte`, `notaio`, `agenzia_acquisto`, `lavori`, `compenso_tecnico`, `oneri_urbanistici`, `arredo` |
| **Finanziamento** | `usa_mutuo`, `equity`, `importo_mutuo`, `tasso_interesse`, `anni_mutuo` |
| **Affitto & Costi** | `affitto_lordo_annuo`, `cedolare`, `imu`, `condominio`, `altro_costi` |
| **Fiscali & Benchmark** | `flag_detrazioni`, `detrazione_annua`, `anni_detrazione`, `sfitto_pct`, `capex_pct`, `rivalutazione_annua`, `rendimento_etf`, `anni_simulazione` |
| **Opzionali** | `inflazione_annua`, `agenzia_vendita_pct`, `agenzia_vendita_fissa`, `prezzo_vendita` |
| **Dettagli Mutuo Reali** | `eta_richiedente`, `costo_assicurazione`, `costo_perizia`, `classe_ape`, `taeg`, `reddito_mensile` |

**Proprietà calcolate:**

- `totale_investimento` — somma di tutte le voci di costo iniziali (incluse assicurazione e perizia)
- `costi_fissi_annui` — cedolare + IMU + condominio + altri
- `rata_mensile` — rata del mutuo (amortamento francese, basata su `tasso_effettivo`)
- `tasso_effettivo` — TAN con eventuale sconto APE A/B (−0.40%)
- `totale_pagato_mutuo` — rata × mesi totali

### 4.2 Funzioni

#### `rata_mensile(capitale, tasso_annuo, anni) -> float`

Calcola la rata mensile con schema di ammortamento ** francese** (rata costante):

```
rata = C × [r(1+r)^n] / [(1+r)^n − 1]
```

dove `r = tasso_annuo / 12` e `n = anni × 12`.

#### `piano_ammortamento(capitale, tasso_annuo, anni) -> DataFrame`

Genera il piano di ammortamento mese per mese, poi aggrega annualmente. Output colonne:

| Colonna | Descrizione |
|---|---|
| `Anno` | Numero dell'anno |
| `Rata_Mensile` | Rata costante (primo mese dell'anno) |
| `Rata_Annua` | Somma delle 12 rate mensili |
| `Quota_Capitale_Annua` | Ammontare del capitale restituito nell'anno |
| `Quota_Interessi_Annua` | Ammontare degli interessi pagati nell'anno |
| `Capitale_Residuo` | Debito residuo a fine anno |

#### `proiezione(p: InvestmentParams) -> DataFrame`

Simula anno per anno per `anni_simulazione` anni. Per ogni anno:

1. Applica inflazione a affitto e costi fissi
2. Calcola rata mutuo (se dentro il periodo di ammortamento)
3. Calcola CF netto: `affitto_eff − costi − rata + detrazione − capex`
4. Aggiorna valore immobile con rivalutazione annua
5. Calcola realizzo netto dalla vendita (prezzo − debito residuo − agenzia)
6. Calcola guadagno totale: `(valore_vendita − debito) + CF_cumulato − equity`

**Output colonne:** `Anno`, `Affitto_Effettivo`, `Costi_Fissi`, `Rata_Mutuo`, `Detrazione`, `CapEx_Accantonato`, `CF_Netto_Anno`, `CF_Cumulato`, `Capitale_Residuo_Mutuo`, `Valore_Immobile`, `Realizzo_Netto`, `Guadagno_Netto_Immobile`, `Guadagno_Netto_ETF`.

#### `calcola_irr(flussi) -> float | None`

Calcola l'Internal Rate of Return con il metodo **Brent** (`scipy.optimize.brentq`):

```
0 = Σ(flussi[t] / (1 + IRR)^t)
```

Cerca la radice nell'intervallo [-50%, +500%]. Restituisce `None` se non converge.

#### `calcola_npv(flussi, tasso) -> float`

Net Present Value a tasso di sconto dato:

```
NPV = Σ(flussi[t] / (1 + tasso)^t)
```

#### `flussi_per_irr(df_proj, equity) -> list[float]`

Costruisce la serie di flussi di cassa per il calcolo IRR:
- t=0: `−equity` (investimento iniziale)
- t=1..N-1: `CF_Netto_Anno`
- t=N: `CF_Netto_Anno + Realizzo_Netto` (vendita)

#### `scenario_cash(p) -> DataFrame`

Genera una proiezione alternativa con **mutuo = 0** (acquisto al 100% cash). Usata per il confronto benchmark immobile cash vs ETF.

#### `verifica_limite_eta(eta, durata) -> (bool, str)`

Verifica che `età richiedente + durata mutuo ≤ 80` (limite MPS).

#### `verifica_ltv(importo_mutuo, valore_immobile, max_ltv=80%) -> (bool, str)`

Verifica che il Loan-to-Value non superi la soglia massima.

#### `calcola_ltv_massimo(importo_mutuo, valore_immobile) -> float`

Restituisce LTV% (utile per warning UI).

#### `verifica_rata_reddito(rata_mensile, reddito_mensile, max_ratio=35%) -> (bool, str)`

Verifica che la rata non superi il 35% del reddito netto.

#### `calcola_rapporto_rata_reddito(rata, reddito) -> float`

Restituisce il rapporto rata/reddito percentuale.

#### `calcola_costo_extra_taeg(importo, tan, taeg, anni) -> float`

Calcola la differenza in € tra rata a TAEG e rata a TAN sull'intera durata.

---

## 5. Interfaccia Streamlit (app.py, ui_sidebar.py, ui_tabs.py)

### 5.1 Layout

- **Sidebar** (`ui_sidebar.render_sidebar()`) — 5 sezioni, restituisce un `SimpleNamespace` con tutti gli input raccolti (consumato da `app.py` per costruire `InvestmentParams` e passato a `ui_tabs`):
  1. **Costi Acquisto** — prezzo, imposte (auto/manuale), notaio, agenzia, **perizia**, **assicurazione incendio**, computo metrico lavori, arredamento
  2. **Finanziamento** — mutuo, tasso, durata, **età richiedente**, **classe APE**, **TAEG**, **reddito mensile** + warning automatici (limite età, LTV, rata/reddito)
  3. **Affitto & Costi Operativi** — canone, cedolare, IMU, condominio, altri
  4. **Fiscali & Benchmark** — detrazione, sfitto, CapEx, vendita, benchmark ETF
  5. **Scenari** — salva/carica/elimina, solo per la sessione corrente (vedi §5.3)
- **4 Tabs** (`ui_tabs.py`, una funzione `render_tab_*` per tab):
  - **KPI & Sintesi** (`render_tab_kpi`) — metriche chiave, tabella rendimenti per orizzonte, miglior anno per vendere
  - **Piano Ammortamento** (`render_tab_mutuo`) — tabella dettagliata + grafico composizione rata
  - **Benchmark ETF** (`render_tab_benchmark`) — confronto immobile vs ETF con leva e cash, grafici a barre del delta
  - **Dettaglio Completo** (`render_tab_dettaglio`) — tabelle voci di costo, flussi annuali, vendita, export Excel e PDF

### 5.2 Formattazione numeri

La funzione `fmt()` (in `utils.py`) formatta i numeri in stile italiano (punto per le migliaia, virgola per i decimali): `1.234,56`.

### 5.3 Scenari salvati

Gli scenari vivono **solo in `st.session_state["scenarios"]`** per la sessione corrente (sia in locale che su cloud): non c'è persistenza su disco, per privacy dei dati. Per conservarli tra sessioni si usa "Scarica JSON" e poi "Importa scenario da file".

### 5.4 Export Excel

Genera un file `.xlsx` con 4 fogli (Riepilogo, Rendimenti, Ammortamento, Proiezioni) formattati con header colorati, bordi e zebra striping.

---

## 6. Algoritmi Chiave

### 6.1 Amortamento Francese

Schema a **rata costante**: la quota interessi diminuisce nel tempo mentre la quota capitale aumenta. La rata rimane fissa per tutta la durata del mutuo.

```
Interessi_mese = Residuo × (tasso_annuo / 12)
Capitale_mese = Rata − Interessi_mese
Residuo = Residuo − Capitale_mese
```

### 6.2 Cash Flow Netto

```
CF = (Affitto × (1 − sfitto%) × (1 + inflazione)^t)
   − Costi_Fissi × (1 + inflazione)^t
   − Rata_Mutuo_Annuo
   + Detrazione_Fiscale (max 10 anni)
   − CapEx_Reserve (= Affitto_Effettivo × capex%)
```

### 6.3 Guadagno Netto (se vendi all'anno T)

```
Guadagno = (Valore_Immobile_T − Debito_Residuo_T) + CF_Cumulato_T − Equity
```

Include: rivalutazione immobiliare, costi di vendita (agenzia), cash flow accumulato e detrazioni fiscali.

### 6.4 IRR (Internal Rate of Return)

Tasso di rendimento interno che rende NPV = 0. Calcolato con il metodo di Brent (bisezione + regola falsa). L'investimento iniziale è l'equity (non l'intero importo), quindi misura il rendimento sul capitale proprio.

---

## 7. Setup e Avvio

### macOS

```bash
chmod +x avvia.sh
./avvia.sh
```

Lo script crea automaticamente un ambiente virtuale, installa le dipendenze e avvia Streamlit su `http://localhost:8501`.

**Requisito di sistema per il report PDF (WeasyPrint):** installa una volta sola `brew install pango`. Su Apple Silicon (`/opt/homebrew`) `avvia.sh` esporta automaticamente `DYLD_FALLBACK_LIBRARY_PATH`. Se avvii Streamlit manualmente, lancia:

```bash
export DYLD_FALLBACK_LIBRARY_PATH="/opt/homebrew/lib:$DYLD_FALLBACK_LIBRARY_PATH"
streamlit run app.py
```

### Windows

```bat
avvia.bat
```

Il report PDF richiede l'installer GTK (vedi [weasyprint docs](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#installation)); l'app funziona comunque, il download PDF mostrerà un avviso.

### Manuale

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

### Prerequisiti

- Python 3.10+ (consigliato 3.11+)
- Nessuna dipendenza di sistema richiesta (solo pip)

---

## 8. Testing

```bash
# Con pytest
.venv/bin/pytest test_engine.py -v

# Oppure direttamente
python -m pytest test_engine.py -v
```

La suite testa:

| Classe test | Copertura |
|---|---|---|
| `TestInvestmentParams` | Proprietà calcolate della dataclass |
| `TestRataMensile` | Calcolo rata, casi limite (zero, negativo, valore noto) |
| `TestPianoAmmortamento` | Struttura DataFrame, somma capitale = prestito, rata costante |
| `TestCalcolaIRR` | IRR noti, convergence, casi limite |
| `TestCalcolaNPV` | NPV positivo/negativo/zero |
| `TestFlussiPerIRR` | Lunghezza, primo flusso = −equity, ultimo include realizzo |
| `TestProiezione` | Numero righe, crescita valore, effetto inflazione, scadenza detrazioni, rivalutazione del prezzo di vendita fisso |
| `TestScenarioCash` | Nessuna rata mutuo, lunghezza corretta |
| `TestValidazioneBancaria` | Limite età, LTV, rapporto rata/reddito, costo extra TAEG |
| `TestTassoEffettivo` | Sconto APE A/B, rata con/senza sconto, floor |
| `TestNuoviCampi` | Totale investimento con assicurazione e perizia |
| `TestCrossoverLevaETF` | Anno di sorpasso leva vs ETF, casi "leva vince sempre" / "ETF vince sempre" |

---

## 9. Proposte Future

### 9.1 Riorganizzazione Sidebar (UX)

Raggruppare le 5 sezioni principali in `st.expander`, collassate di default:

- La sezione "Finanziamento" si espande automaticamente se il mutuo è attivo
- Riduce lo scroll iniziale, l'utente apre solo la sezione che gli serve
- Migliora l'esperienza su schermi piccoli

### 9.2 Confronto multi-scenario

Aggiungere una vista comparativa che affianca 2-3 scenari side-by-side (con/senza mutuo, diversa durata, diverso tasso) sullo stesso grafico e nella stessa tabella KPI.

### 9.3 Calcolo automatico assicurazione incendio

Ricavare il premio unico dalla formula MPS/AXA: `coefficiente × valore assicurato/1000 × anni durata`. Aggiungere un campo "valore assicurato" e calcolare automaticamente il costo.

---

## 10. Deploy su Streamlit Community Cloud

L'app è pronta per girare su [Streamlit Community Cloud](https://share.streamlit.io) (piano gratuito). Configurazione già presente nel repo:

- `requirements.txt` → dipendenze Python
- `packages.txt` → pacchetti di sistema apt (pango, richiesti da WeasyPrint per il PDF)
- `.gitignore` → esclude `.venv/`, `__pycache__/`, `.pytest_cache/`, `scenarios/` (dati utente) e `.streamlit/secrets.toml`

### Passi

1. Carica il progetto su un repository GitHub (senza scenari, `.venv` e `__pycache__`).
2. Su share.streamlit.io: **Create app** → seleziona repo/branch, il file resta `app.py`.
3. Nelle **Settings → Secrets** dell'app aggiungi:

```toml
APP_PASSWORD = "scegli_una_password_robusta"
```

4. Apri l'app: chiederà la password prima di mostrare qualsiasi contenuto.

### Comportamento su cloud

- **Scenari**: non vengono mai salvati su disco, né su cloud né in locale (per privacy dei dati — vedi §5.3). Si popolano tramite i pulsanti "Salva" (solo in sessione) o upload JSON (`Importa scenario da file`) e restano **nella singola sessione** del collaboratore. Alla chiusura o al riavvio dell'app spariscono: per conservarli va usato "Scarica JSON".
- **PDF**: generato sul server (pango installato da `packages.txt`) e scaricato via download.
- **Password**: gestita da `st.secrets["APP_PASSWORD"]`. Se non impostata, l'app resta aperta senza login (comodo per lo sviluppo locale).

> Nota sicurezza: la URL dell'app Community Cloud è pubblica; il contenuto è protetto dal gate di login a livello applicazione. Per dati molto riservati valuta auth di rete (es. Cloudflare Access) o un hosting privato.
