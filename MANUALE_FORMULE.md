# Manuale del Controllore — Calcolo Investimenti Immobiliari

Questo documento descrive tutte le formule matematiche utilizzate dallo strumento, pensato per chi vuole capire esattamente come vengono calcolati i numeri che appaiono a schermo.

---

## Indice

1. [Investimento Totale](#1-investimento-totale)
2. [Costi di Acquisto — Imposte Automatiche](#2-costi-di-acquisto--imposte-automatiche)
3. [Lavori e IVA](#3-lavori-e-iva)
4. [Detrazione Fiscale (Bonus Ristrutturazione)](#4-detrazione-fiscale-bonus-ristrutturazione)
5. [Piano di Ammortamento Francese (Mutuo)](#5-piano-di-ammortamento-francese-mutuo)
6. [Tasso Effettivo e Sconto APE](#6-tasso-effettivo-e-sconto-ape)
7. [Proiezione Annuale — Cash Flow Operativo](#7-proiezione-annuale--cash-flow-operativo)
8. [Guadagno Netto alla Vendita](#8-guadagno-netto-alla-vendita)
9. [Rendimento Annualizzato (CAGR)](#9-rendimento-annualizzato-cagr)
10. [Miglior Anno per Vendere](#10-miglior-anno-per-vendere)
11. [IRR — Tasso Interno di Rendimento](#11-irr--tasso-interno-di-rendimento)
12. [NPV — Valore Attuale Netto](#12-npv--valore-attuale-netto)
13. [Confronto con ETF](#13-confronto-con-etf)
14. [Scenario Cash (100% senza mutuo)](#14-scenario-cash-100-senza-mutuo)
15. [Verifiche Bancarie (dal preventivo reale)](#15-verifiche-bancarie-dal-preventivo-reale)

---

## 1. Investimento Totale

È la somma di tutte le voci di spesa per acquistare e rendere operativo l'immobile:

```
Investimento Totale = Prezzo Immobile
                    + Imposte Acquisto
                    + Spese Notaio
                    + Agenzia Acquisto
                    + Lavori (imponibile)
                    + Compenso Tecnico
                    + Oneri Urbanistici
                    + Arredamento
                    + Spese Perizia Mutuo    ← obbligatoria per la banca
                    + Assicurazione Incendio  ← premio unico (MPS: AXA MPS)
```

Ciascuna voce è inserita manualmente dall'utente (o calcolata automaticamente per le imposte). Le ultime due voci (`costo_perizia`, `costo_assicurazione`) sono costi accessori del mutuo, spesso non inclusi nei preventivi di base ma obbligatori per l'erogazione.

---

## 2. Costi di Acquisto — Imposte Automatiche

Lo strumento può calcolare automaticamente le imposte di acquisto in base alla combinazione di acquirente, venditore, tipo immobile e regime fiscale.

### Caso A — Privato compra da Privato

```
Rendita Rivalutata = Rendita Catastale × 1,05

Valore Catastale = Rendita Rivalutata × 110   (se prima casa)
                 = Rendita Rivalutata × 120   (se seconda casa)

Imposta di Registro = max(Valore Catastale × 2%, 1.000 €)     (prima casa)
                   = max(Valore Catastale × 9%, 1.000 €)     (seconda casa)

Imposta Ipotecaria = 50 €
Imposta Catastale  = 50 €
```

### Caso B — Privato compra da Azienda (IVA)

```
IVA = Prezzo × 4%   (prima casa)
    = Prezzo × 10%  (seconda casa)

Imposta di Registro = 200 €
Imposta Ipotecaria  = 200 €
Imposta Catastale   = 200 €
```

### Caso C — Privato compra da Azienda (Registro)

```
Imposta di Registro = max(Prezzo × 2%, 1.000 €)   (prima casa)
                   = max(Prezzo × 9%, 1.000 €)   (seconda casa)

Imposta Ipotecaria = 50 €
Imposta Catastale  = 50 €
```

### Caso D — Azienda compra da Privato

```
Imposta di Registro = max(Prezzo × 9%, 1.000 €)
Imposta Ipotecaria  = 50 €
Imposta Catastale   = 50 €
```

### Totale Imposte

```
Totale = Registro + Ipotecaria + Catastale + IVA
```

---

## 3. Lavori e IVA

Per ogni voce di lavoro nell'apposito computo metrico:

```
Importo Voce = Prezzo Unitario × Quantità
```

I prezzi unitari nel computo metrico sono **imponibili** (IVA esclusa). L'IVA viene calcolata separatamente:

- **Aliquota 10%**: opere di manodopera, ristrutturazione edilizia
- **Aliquota 22%**: forniture di beni (infissi, pavimenti, sanitari, ecc.)

```
IVA 10% = somma(importo voci con iva_pct=10%) × 0,10
IVA 22% = somma(importo voci con iva_pct=22%) × 0,22

Costo Totale Lavori = somma imponibile + IVA 10% + IVA 22%
```

Il valore `Lavori` usato nelle formule successive è il **solo imponibile** (base per la detrazione fiscale).

---

## 4. Detrazione Fiscale (Bonus Ristrutturazione)

```
Base di Calcolo = Lavori (imponibile) + Compenso Tecnico + Oneri Urbanistici

Aliquota = 50%  (se si sposta la residenza entro 12 mesi)
         = 36%  (altrimenti)

Detrazione Annua = Base di Calcolo × Aliquota / 10 anni
```

La detrazione viene applicata per i primi 10 anni di simulazione.

---

## 5. Piano di Ammortamento Francese (Mutuo)

Il mutuo a rata costante (francese) si calcola così:

### Rata Mensile

```
tasso_mensile = Tasso Annuo / 12
mesi_totali  = Anni Mutuo × 12

Rata Mensile = Capitale × (tasso_mensile × (1 + tasso_mensile)^mesi_totali)
                           -------------------------------------------------
                           ((1 + tasso_mensile)^mesi_totali - 1)
```

### Mese per Mese

```
Interessi Mese = Capitale Residuo × tasso_mensile
Quota Capitale = Rata Mensile - Interessi Mese
Capitale Residuo (nuovo) = Capitale Residuo (vecchio) - Quota Capitale
```

### Riepilogo Annuale

```
Rata Annua        = Rata Mensile × 12
Capitale pagato   = somma delle quote capitale nell'anno
Interessi pagati  = somma degli interessi nell'anno
Residuo finale    = ultimo capitale residuo dell'anno
```

---

## 6. Tasso Effettivo e Sconto APE

Il tool può applicare uno **sconto sul tasso di interesse** in base alla classe energetica dell'immobile, come previsto da molti istituti (MPS: −0,40% per APE A o B).

```
Se Classe APE = "A/B":
    Tasso Effettivo = TASSO_INTERESSE − 0,004    (−0,40 punti percentuali)
Altrimenti:
    Tasso Effettivo = TASSO_INTERESSE
```

Il **tasso effettivo** (`tasso_effettivo`) è usato in tutte le formule successive (rata mensile, piano ammortamento, proiezione) al posto del TAN base. Questo significa che la rata diminuisce automaticamente se l'immobile ha una classe energetica alta.

### TAEG — Tasso Annuo Effettivo Globale

Il TAEG è un campo **informativo** opzionale. Rappresenta il costo totale del mutuo in percentuale annua, inclusi tutti gli oneri accessori (istruttoria, perizia, assicurazione). Quando inserito, il tool calcola:

```
Costo Extra TAEG = (Rata a TAEG − Rata a TAN) × mesi_totali

dove:
    Rata a TAEG = rata_mensile(capitale, taeg, durata)
    Rata a TAN  = rata_mensile(capitale, tasso_effettivo, durata)
```

La differenza mostra quanto costa in più il mutuo "vero" rispetto alla sola componente interessi.

---

## 7. Proiezione Annuale — Cash Flow Operativo

Anno per anno, per tutta la durata della simulazione:

### Fattore di Inflazione

```
Inflazione Anno t = (1 + Tasso Inflazione)^(t-1)
```

Anno 1 = 1 (nessuna inflazione). Da anno 2 in poi l'inflazione si applica cumulativamente.

### Affitto Effettivo

```
Affitto Effettivo = Affitto Lordo × Inflazione Anno t × (1 - Sfitto % / 100)
```

Lo sfitto riduce l'affitto lordo di una percentuale fissa (es. 5% = 5% di vacancy).

### Costi Fissi Annui

```
Costi Fissi = (Cedolare + IMU + Condominio + Altri Costi) × Inflazione Anno t
```

### CapEx (Accantonamento per manutenzione straordinaria)

```
CapEx = Affitto Effettivo × (CapEx % / 100)
```

### Detrazione Fiscale

```
Detrazione = Detrazione Annua   (se t ≤ 10)
           = 0                  (se t > 10)
```

### Cash Flow Netto dell'Anno

```
CF Netto Anno = Affitto Effettivo - Costi Fissi - Rata Mutuo + Detrazione - CapEx
```

### Cash Flow Cumulato

```
CF Cumulato t = CF Cumulato(t-1) + CF Netto Anno t
```

---

## 8. Guadagno Netto alla Vendita

### Valore dell'Immobile nel Tempo

Il valore iniziale di mercato è stimato come:

```
Valore Iniziale = Prezzo Acquisto + Lavori (imponibile)
```

Ogni anno si rivaluta:

```
Valore Anno t = Valore Iniziale × (1 + Rivalutazione Annua)^t
```

Se l'utente inserisce un **Prezzo di Vendita** fisso > 0, questo viene rivalutato annualmente con la stessa formula:

```
Prezzo Vendita Effettivo = Prezzo di Vendita × (1 + Rivalutazione Annua)^t
```

In questo modo la rivalutazione si applica sia al valore di mercato stimato sia al prezzo di vendita fisso inserito dall'utente.

### Spese di Agenzia alla Vendita

```
Se Commissione Fissa > 0:
    Spese Agenzia = Commissione Fissa (importo in €)

Altrimenti:
    Spese Agenzia = Prezzo di Vendita × (Commissione % / 100)
```

### Realizzo Netto (quanto incassi dalla vendita)

```
Realizzo Netto = Prezzo di Vendita - Residuo Mutuo - Spese Agenzia
```

### Guadagno Netto Complessivo (se vendi quell'anno)

```
Guadagno Netto = Realizzo Netto + CF Cumulato - Equity Iniziale
```

Dove:
- **Realizzo Netto** = ciò che ti rimane dalla vendita dopo aver pagato banca e agenzia
- **CF Cumulato** = tutto il cash flow accumulato negli anni (affitti - costi - rate + detrazioni)
- **Equity Iniziale** = il capitale che hai messo di tasca tua all'inizio

---

## 9. Rendimento Annualizzato (CAGR)

Il rendimento annualizzato medio (Compound Annual Growth Rate) si calcola come:

```
CAGR = (Valore Finale / Equity Iniziale)^(1 / Anni) - 1
```

Dove:

```
Valore Finale = Guadagno Netto + Equity Iniziale
```

In formula estesa:

```
CAGR = ((Realizzo Netto + CF Cumulato) / Equity Iniziale)^(1 / Anni) - 1
```

Il CAGR rappresenta il rendimento fisso annuo che, composto per `Anni` periodi, produrrebbe lo stesso risultato finale. È la metrica standard per confrontare investimenti con durate diverse.

---

## 10. Miglior Anno per Vendere

Lo strumento calcola il **CAGR** per ogni anno della simulazione (dal 5° in poi). L'anno con il CAGR più alto è segnalato come "Miglior anno per vendere".

```
Per ogni anno t da 5 a N:
    CAGR(t) = (Valore Finale(t) / Equity)^(1/t) - 1

Miglior Anno = t che massimizza CAGR(t)
```

Questo è utile perché il rendimento annualizzato può calare se si tiene l'immobile troppo a lungo (i costi di acquisto vengono ammortizzati su più anni, ma la rivalutazione potrebbe non compensare).

---

## 11. IRR — Tasso Interno di Rendimento

L'IRR è il tasso di sconto che rende il Valore Attuale Netto pari a zero.

```
0 = CF₀ + CF₁/(1+IRR) + CF₂/(1+IRR)² + ... + CFₙ/(1+IRR)ⁿ
```

Dove i flussi di cassa sono:

```
CF₀ = -Equity Iniziale
CF₁ ... CFₙ₋₁ = CF Netto Anno (affitto - costi - rata + detrazione - capex) di ogni anno
CFₙ = CF Netto Anno finale + Realizzo Netto
```

L'ultimo flusso include il realizzo della vendita (prezzo - residuo mutuo - agenzia).

L'IRR viene risolto numericamente con il metodo di Brent (bisezione + interpolazione quadratica).

---

## 12. NPV — Valore Attuale Netto

Il NPV attualizza tutti i flussi di cassa al tasso di rendimento dell'ETF (costo-opportunità):

```
NPV = CF₀ + CF₁/(1+r) + CF₂/(1+r)² + ... + CFₙ/(1+r)ⁿ

dove r = Rendimento ETF (tasso di sconto)
```

- **NPV > 0**: l'investimento immobiliare rende più dell'ETF
- **NPV < 0**: l'ETF rende più dell'immobile

---

## 13. Confronto con ETF

### Con Leva (stessa equity)

```
ETF (stessa equity) = Equity Iniziale × (1 + Rendimento ETF)^t - Equity Iniziale
Immobile con Mutuo   = Guadagno Netto Immobile (vedi sezione 7)
Divario              = Guadagno Immobile - Guadagno ETF
```

### Cash (stesso capitale totale)

```
ETF (stesso totale) = Investimento Totale × (1 + Rendimento ETF)^t - Investimento Totale
Immobile Cash        = Guadagno Netto scenario senza mutuo (vedi sezione 13)
Divario              = Guadagno Immobile Cash - Guadagno ETF Cash
```

---

## 14. Scenario Cash (100% senza mutuo)

Simula l'acquisto senza finanziamento. L'equity coincide con l'investimento totale.

```
Equity = Investimento Totale
Mutuo  = 0
Rata   = 0
```

Tutte le altre formule (affitto, costi, detrazioni, rivalutazione, guadagno) sono identiche, ma senza la componente mutuo.

Il confronto "scenario cash" risponde alla domanda: *"Ho tutti i soldi, conviene comprare l'immobile senza mutuo o investire tutto in ETF?"*

---

## 15. Verifiche Bancarie (dal preventivo reale)

Il tool include 4 verifiche automatiche basate sui criteri di erogazione di MPS e altri istituti:

### 15.1 Limite Età

La maggior parte delle banche richiede che l'età del richiedente più la durata del mutuo non superi 80 anni:

```
Età Finale = Età Richiedente + Durata Mutuo
Ammissibile  ⇔  Età Finale ≤ 80
```

### 15.2 Loan-to-Value (LTV)

Il mutuo non può superare una percentuale del valore dell'immobile (tipicamente 80%):

```
LTV % = Importo Mutuo / Valore Immobile × 100
Ammissibile  ⇔  LTV % ≤ 80%
```

Il valore dell'immobile considerato è il minore tra prezzo di acquisto e perizia.

### 15.3 Rapporto Rata / Reddito

Le banche verificano che la rata non assorba più del 33-35% del reddito netto mensile:

```
Rapporto % = Rata Mensile / Reddito Netto Mensile × 100
Soglia di attenzione  ⇔  Rapporto % > 35%
```

### 15.4 Costo Extra TAEG

Il TAEG (Tasso Annuo Effettivo Globale) include tutti i costi accessori. Se disponibile, il tool calcola il costo extra rispetto al solo TAN:

```
Extra TAEG = (Rata a TAEG − Rata a TAN) × Mesi Totali
```

---

## Riepilogo Variabili

| Variabile | Descrizione | Fonte |
|---|---|---|
| `prezzo` | Prezzo di acquisto immobile | Input utente |
| `imposte` | Imposte di acquisto | Input / calcolo automatico |
| `notaio` | Spese notarili | Input utente |
| `agenzia_acquisto` | Commissione agenzia all'acquisto | Input utente |
| `lavori` | Costo lavori (imponibile) | Computo metrico |
| `compenso_tecnico` | Architetto/geometra | Input utente |
| `oneri_urbanistici` | Oneri di urbanizzazione | Input utente |
| `arredo` | Arredamento (IVA inclusa) | Computo metrico |
| `equity` | Capitale proprio investito | Calcolato o input |
| `importo_mutuo` | Capitale mutuato | Calcolato o input |
| `tasso_interesse` | Tasso annuo mutuo (decimale, 3,5% = 0,035) | Input utente |
| `anni_mutuo` | Durata mutuo in anni | Input utente |
| `affitto_lordo_annuo` | Canone annuo lordo | Input utente |
| `cedolare` | Cedolare secca annua | Input utente |
| `imu` | IMU annua | Input utente |
| `condominio` | Spese condominio annue | Input utente |
| `altro_costi` | Altri costi fissi annui | Input utente |
| `sfitto_pct` | Percentuale sfitto/vacancy | Input utente (slider 0-20%) |
| `capex_pct` | Percentuale accantonamento CapEx | Input utente (slider 0-15%) |
| `rivalutazione_annua` | Rivalutazione annua immobile (decimale) | Input utente |
| `inflazione_annua` | Tasso inflazione annuo (decimale) | Input utente (slider 0-8%) |
| `rendimento_etf` | Rendimento annuo ETF (decimale) | Input utente |
| `agenzia_vendita_pct` | Commissione agenzia alla vendita (%) | Input utente |
| `agenzia_vendita_fissa` | Commissione agenzia alla vendita (€, 0 = usa %) | Input utente |
| `prezzo_vendita` | Prezzo di vendita fisso (0 = usa rivalutazione) | Input utente |
| `anni_simulazione` | Orizzonte temporale della simulazione | Input utente |
| `detrazione_annua` | Detrazione fiscale annuale | Calcolato |
| `aliquota_detr` | Aliquota detrazione (50% o 36%) | Calcolato |
| `eta_richiedente` | Età anagrafica del richiedente | Input utente |
| `costo_assicurazione` | Premio unico assicurazione incendio/scoppio | Input utente |
| `costo_perizia` | Spese perizia tecnica obbligatoria | Input utente |
| `classe_ape` | Classe energetica ("altro" o "A/B") | Input utente |
| `taeg` | Tasso Annuo Effettivo Globale (informativo) | Input utente |
| `reddito_mensile` | Reddito netto mensile del richiedente | Input utente |
| `tasso_effettivo` | Tasso dopo eventuale sconto APE | Proprietà calcolata |
| `tasso_mensile` | `tasso_effettivo / 12` | Derivato |
| `mesi_totali` | `anni_mutuo × 12` | Derivato |
