"""
Financial engine for real estate investment analysis.
Ammortization schedules, cash flow projections, IRR/NPV, benchmark comparison.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd
from scipy.optimize import brentq


# ---------------------------------------------------------------------------
# Catalogo voci lavori e mobilio
# ---------------------------------------------------------------------------

WORK_ITEMS = [
    {"id": "w1",  "categoria": "DEMOLIZIONI", "voce": "Smontaggio e trasporto e smaltimento delle porte", "um": "cad", "prezzo": 27.50, "iva_pct": 0.10},
    {"id": "w2",  "categoria": "DEMOLIZIONI", "voce": "Smontaggio e trasporto e smaltimento delle finestre", "um": "cad", "prezzo": 27.08, "iva_pct": 0.10},
    {"id": "w3",  "categoria": "DEMOLIZIONI", "voce": "Smontaggio e trasporto e smaltimento di impianti e accessori bagno", "um": "cad", "prezzo": 190, "iva_pct": 0.10},
    {"id": "w4",  "categoria": "DEMOLIZIONI", "voce": "Realizzazione e chiusura tracce per impianti", "um": "cad", "prezzo": 5000, "iva_pct": 0.10},
    {"id": "w5",  "categoria": "DEMOLIZIONI", "voce": "Demolizione di tramezzi compreso trasporto e smaltimento", "um": "mq",  "prezzo": 25, "iva_pct": 0.10},
    {"id": "w6",  "categoria": "DEMOLIZIONI", "voce": "Analisi calcinacci", "um": "cad", "prezzo": 250, "iva_pct": 0.10},
    {"id": "w7",  "categoria": "DEMOLIZIONI", "voce": "Rimozione di battiscopa", "um": "ml",  "prezzo": 4, "iva_pct": 0.10},
    {"id": "w8",  "categoria": "DEMOLIZIONI", "voce": "Demolizione trasporto e smaltimento di pavimenti e rivestimenti", "um": "mq",  "prezzo": 25, "iva_pct": 0.10},
    {"id": "w9",  "categoria": "DEMOLIZIONI", "voce": "Demolizione trasporto e smaltimento del massetto", "um": "mq",  "prezzo": 25, "iva_pct": 0.10},
    {"id": "w10", "categoria": "DEMOLIZIONI", "voce": "Demolizione trasporto e smaltimento di intonaco", "um": "mq",  "prezzo": 15, "iva_pct": 0.10},
    {"id": "w11", "categoria": "COSTRUZIONI", "voce": "Posa di controsoffitto in cartongesso", "um": "mq",  "prezzo": 50, "iva_pct": 0.10},
    {"id": "w12", "categoria": "COSTRUZIONI", "voce": "Pareti divisorie in cartongesso spessore di 12.5", "um": "mq",  "prezzo": 60, "iva_pct": 0.10},
    {"id": "w13", "categoria": "COSTRUZIONI", "voce": "Sovraprezzo per isolamento con lana di vetro spessore 40mm", "um": "mq",  "prezzo": 5, "iva_pct": 0.22},
    {"id": "w14", "categoria": "COSTRUZIONI", "voce": "Sovraprezzo per utilizzo lastre cartongesso verdi", "um": "mq",  "prezzo": 5, "iva_pct": 0.22},
    {"id": "w15", "categoria": "COSTRUZIONI", "voce": "Rinforzo in legno per pareti in cartongesso", "um": "mq",  "prezzo": 30, "iva_pct": 0.22},
    {"id": "w16", "categoria": "COSTRUZIONI", "voce": "Posa controtelaio per portoncino blindato", "um": "cad", "prezzo": 250, "iva_pct": 0.10},
    {"id": "w17", "categoria": "COSTRUZIONI", "voce": "Parete acustica tra unità immobiliari", "um": "mq",  "prezzo": 108, "iva_pct": 0.10},
    {"id": "w18", "categoria": "COSTRUZIONI", "voce": "Vespaio areato", "um": "mq",  "prezzo": 68, "iva_pct": 0.10},
    {"id": "w19", "categoria": "COSTRUZIONI", "voce": "Magrone rck15", "um": "mq",  "prezzo": 218.10, "iva_pct": 0.10},
    {"id": "w20", "categoria": "COSTRUZIONI", "voce": "Nuovo massetto", "um": "mq",  "prezzo": 28, "iva_pct": 0.10},
    {"id": "w21", "categoria": "COSTRUZIONI", "voce": "Piatto doccia (posa)", "um": "cad", "prezzo": 100, "iva_pct": 0.10},
    {"id": "w22", "categoria": "COSTRUZIONI", "voce": "Intonaco deumidificante (fornitura e posa)", "um": "mq",  "prezzo": 55, "iva_pct": 0.10},
    {"id": "w23", "categoria": "COSTRUZIONI", "voce": "Intonaco finitura civile (fornitura e posa)", "um": "mq",  "prezzo": 32, "iva_pct": 0.10},
    {"id": "w24", "categoria": "COSTRUZIONI", "voce": "Rasatura pareti (pronte per tinteggiatura)", "um": "mq",  "prezzo": 20, "iva_pct": 0.10},
    {"id": "w25", "categoria": "COSTRUZIONI", "voce": "Tinteggiatura a tempera", "um": "mq",  "prezzo": 8, "iva_pct": 0.10},
    {"id": "w26", "categoria": "COSTRUZIONI", "voce": "Pavimento SPC o gres (fornitura e posa)", "um": "mq",  "prezzo": 60, "iva_pct": 0.22},
    {"id": "w27", "categoria": "COSTRUZIONI", "voce": "Rivestimenti ceramici (fornitura e posa)", "um": "mq",  "prezzo": 60, "iva_pct": 0.22},
    {"id": "w28", "categoria": "COSTRUZIONI", "voce": "Battiscopa in legno h 5 cm (fornitura e posa)", "um": "ml",  "prezzo": 15, "iva_pct": 0.22},
    {"id": "w29", "categoria": "BAGNO COMPLETO", "voce": "Demolizione e ricostruzione completa bagno (opere murarie+impianti+sanitari+rubinetteria+box doccia)", "um": "cad", "prezzo": 7000, "iva_pct": 0.10},
    {"id": "w30", "categoria": "IMPIANTI", "voce": "Impianto elettrico completo", "um": "cad", "prezzo": 6000, "iva_pct": 0.10},
    {"id": "w31", "categoria": "IMPIANTI", "voce": "Split (fornitura e posa)", "um": "cad", "prezzo": 600, "iva_pct": 0.22},
    {"id": "w32", "categoria": "IMPIANTI", "voce": "Impianto idrico sanitario (bagno completo + cucina)", "um": "cad", "prezzo": 2300, "iva_pct": 0.10},
    {"id": "w33", "categoria": "IMPIANTI", "voce": "Pompa di calore per impianto canalizzato a bocchette", "um": "cad", "prezzo": 4000, "iva_pct": 0.22},
    {"id": "w34", "categoria": "IMPIANTI", "voce": "Montaggio sanitari e mobile bagno (prezzo a bagno)", "um": "cad", "prezzo": 500, "iva_pct": 0.10},
    {"id": "w35", "categoria": "IMPIANTI", "voce": "Boiler acqua calda (fornitura e montaggio)", "um": "cad", "prezzo": 550, "iva_pct": 0.22},
    {"id": "w36", "categoria": "FORNITURE E MONTAGGIO", "voce": "Porte interne e maniglie (fornitura e montaggio)", "um": "cad", "prezzo": 330, "iva_pct": 0.22},
    {"id": "w37", "categoria": "FORNITURE E MONTAGGIO", "voce": "Infissi esterni (fornitura e montaggio stimato)", "um": "cad", "prezzo": 500, "iva_pct": 0.22},
    {"id": "w38", "categoria": "FORNITURE E MONTAGGIO", "voce": "Motore tapparelle elettriche (fornitura e montaggio)", "um": "cad", "prezzo": 80, "iva_pct": 0.22},
    {"id": "w39", "categoria": "FORNITURE E MONTAGGIO", "voce": "Portoncino blindato (fornitura e montaggio)", "um": "cad", "prezzo": 820, "iva_pct": 0.22},
]

FURN_ITEMS = [
    {"id": "f1",  "categoria": "CAMERE", "voce": "Letto matrimoniale 160 cm", "um": "cad", "prezzo": 159, "iva_inclusa": True},
    {"id": "f2",  "categoria": "CAMERE", "voce": "Letto piazza e mezzo 140 cm", "um": "cad", "prezzo": 189, "iva_inclusa": True},
    {"id": "f3",  "categoria": "CAMERE", "voce": "Letto singolo 90 cm", "um": "cad", "prezzo": 109, "iva_inclusa": True},
    {"id": "f4",  "categoria": "CAMERE", "voce": "Materasso matrimoniale 160 cm", "um": "cad", "prezzo": 499, "iva_inclusa": True},
    {"id": "f5",  "categoria": "CAMERE", "voce": "Materasso piazza e mezzo 140 cm", "um": "cad", "prezzo": 479, "iva_inclusa": True},
    {"id": "f6",  "categoria": "CAMERE", "voce": "Materasso singolo 90 cm", "um": "cad", "prezzo": 299, "iva_inclusa": True},
    {"id": "f7",  "categoria": "CAMERE", "voce": "Comodini 35x49", "um": "cad", "prezzo": 35, "iva_inclusa": True},
    {"id": "f8",  "categoria": "CAMERE", "voce": "Specchio 30x115", "um": "cad", "prezzo": 19.95, "iva_inclusa": True},
    {"id": "f9",  "categoria": "CAMERE", "voce": "Armadio camera doppia 235 cm (lung.)", "um": "cad", "prezzo": 460, "iva_inclusa": True},
    {"id": "f10", "categoria": "CAMERE", "voce": "Armadio camera singola 120 cm (lung.)", "um": "cad", "prezzo": 219, "iva_inclusa": True},
    {"id": "f11", "categoria": "CAMERE", "voce": "Scrivania 105x60", "um": "cad", "prezzo": 105, "iva_inclusa": True},
    {"id": "f12", "categoria": "CAMERE", "voce": "Sedia", "um": "cad", "prezzo": 60, "iva_inclusa": True},
    {"id": "f13", "categoria": "SOGGIORNO", "voce": "Divano 2 posti 190 cm", "um": "cad", "prezzo": 399, "iva_inclusa": True},
    {"id": "f14", "categoria": "SOGGIORNO", "voce": "Divano 3 posti 228 cm", "um": "cad", "prezzo": 499, "iva_inclusa": True},
    {"id": "f15", "categoria": "SOGGIORNO", "voce": "Mobile TV 146 cm", "um": "cad", "prezzo": 119, "iva_inclusa": True},
    {"id": "f16", "categoria": "SOGGIORNO", "voce": "TV 32 pollici", "um": "cad", "prezzo": 99, "iva_inclusa": True},
    {"id": "f17", "categoria": "SOGGIORNO", "voce": "Tavolo pranzo 140 cm allungabile", "um": "cad", "prezzo": 279, "iva_inclusa": True},
    {"id": "f18", "categoria": "SOGGIORNO", "voce": "Sedie", "um": "cad", "prezzo": 60, "iva_inclusa": True},
    {"id": "f19", "categoria": "ILLUMINAZIONE", "voce": "Luci per stanza", "um": "cad", "prezzo": 30, "iva_inclusa": True},
    {"id": "f20", "categoria": "CUCINA", "voce": "Cucina con elettrodomestici lung. 3.68 m", "um": "cad", "prezzo": 4071, "iva_inclusa": True},
    {"id": "f21", "categoria": "CUCINA", "voce": "Cucina con elettrodomestici lung. 3.09 m", "um": "cad", "prezzo": 3575.50, "iva_inclusa": True},
    {"id": "f22", "categoria": "MONTAGGIO E TRASPORTO", "voce": "Montaggio", "um": "cad", "prezzo": 3000, "iva_inclusa": True},
    {"id": "f23", "categoria": "MONTAGGIO E TRASPORTO", "voce": "Trasporto", "um": "cad", "prezzo": 500, "iva_inclusa": True},
]


def calcola_totale_lavori(qty_map: dict[str, float]) -> float:
    """Somma dei totali (prezzo * qty) per le voci lavori."""
    return sum(item["prezzo"] * qty_map.get(item["id"], 0.0) for item in WORK_ITEMS)


def calcola_totale_mobilio(qty_map: dict[str, float]) -> float:
    """Somma dei totali (prezzo * qty) per le voci mobilio (IVA già inclusa)."""
    return sum(item["prezzo"] * qty_map.get(item["id"], 0.0) for item in FURN_ITEMS)


def calcola_iva_lavori(qty_map: dict[str, float]) -> dict:
    """Calcola IVA sui lavori: 10% su manodopera, 22% su forniture.
    Restituisce {'lavori_imponibile': ..., 'iva_10': ..., 'iva_22': ..., 'iva_totale': ...}."""
    imponibile_10 = 0.0
    imponibile_22 = 0.0
    for item in WORK_ITEMS:
        qty = qty_map.get(item["id"], 0.0)
        if qty <= 0:
            continue
        totale = item["prezzo"] * qty
        if item["iva_pct"] == 0.10:
            imponibile_10 += totale
        else:
            imponibile_22 += totale
    iva_10 = imponibile_10 * 0.10
    iva_22 = imponibile_22 * 0.22
    return {
        "imponibile_10": imponibile_10,
        "imponibile_22": imponibile_22,
        "iva_10": iva_10,
        "iva_22": iva_22,
        "iva_totale": iva_10 + iva_22,
    }


# ---------------------------------------------------------------------------
# Calcolo automatico imposte di acquisto
# ---------------------------------------------------------------------------

def calcola_imposte_acquisto(
    prezzo: float,
    acquirente: str = "privato",       # "privato" | "azienda"
    tipo_immobile: str = "prima",       # "prima" | "seconda"
    venditore: str = "privato",         # "privato" | "azienda"
    regime: str = "iva",                # "iva" | "registro" (solo se venditore azienda)
    rendita_catastale: Optional[float] = None,
) -> dict:
    """Calcola automaticamente imposte di acquisto immobiliare.
    Restituisce dict con singole voci e totale."""
    valore_catastale = 0.0
    base_imponibile_registro = prezzo

    if acquirente == "privato" and venditore == "privato":
        if rendita_catastale is None or rendita_catastale <= 0:
            return {"errore": "Rendita catastale necessaria per calcolo privato-privato"}
        rendita_rivalutata = rendita_catastale * 1.05
        moltiplicatore = 110 if tipo_immobile == "prima" else 120
        valore_catastale = rendita_rivalutata * moltiplicatore
        base_imponibile_registro = valore_catastale

    registro = ipotecaria = catastale = iva = 0.0

    if acquirente == "azienda" and venditore == "privato":
        registro = max(prezzo * 0.09, 1000)
        ipotecaria = 50
        catastale = 50
    elif venditore == "privato":
        aliquota = 0.02 if tipo_immobile == "prima" else 0.09
        registro = max(base_imponibile_registro * aliquota, 1000)
        ipotecaria = 50
        catastale = 50
    elif venditore == "azienda":
        if regime == "iva":
            iva = prezzo * (0.04 if tipo_immobile == "prima" else 0.10)
            registro = 200
            ipotecaria = 200
            catastale = 200
        else:
            aliquota = 0.02 if tipo_immobile == "prima" else 0.09
            registro = max(prezzo * aliquota, 1000)
            ipotecaria = 50
            catastale = 50

    totale = registro + ipotecaria + catastale + iva
    return {
        "rendita_catastale": rendita_catastale or 0,
        "valore_catastale": valore_catastale,
        "registro": registro,
        "ipotecaria": ipotecaria,
        "catastale": catastale,
        "iva": iva,
        "totale": totale,
    }


@dataclass(unsafe_hash=True)
class InvestmentParams:
    # Acquisto & Lavori
    prezzo: float
    imposte: float
    notaio: float
    agenzia_acquisto: float
    lavori: float
    compenso_tecnico: float
    oneri_urbanistici: float
    arredo: float

    # Finanziamento
    usa_mutuo: bool
    equity: float
    importo_mutuo: float
    tasso_interesse: float  # decimale, es. 0.035
    anni_mutuo: int

    # Affitto & Costi Operativi
    affitto_lordo_annuo: float
    cedolare: float
    imu: float
    condominio: float
    altro_costi: float

    # Fiscali & Benchmark
    flag_detrazioni: bool
    detrazione_annua: float
    anni_detrazione: int
    sfitto_pct: float
    capex_pct: float
    rivalutazione_annua: float  # decimale, es. 0.015
    rendimento_etf: float  # decimale, es. 0.07
    anni_simulazione: int
    inflazione_annua: float = 0.0  # decimale, es. 0.02
    agenzia_vendita_pct: float = 3.0  # percentuale, es. 3.0 (usata solo se agenzia_vendita_fissa == 0)
    agenzia_vendita_fissa: float = 0.0  # importo fisso commissione agenzia (0 = usa percentuale)
    prezzo_vendita: float = 0.0  # 0 = usa rivalutazione_annua, >0 = prezzo fisso

    # Dettagli mutuo (dal preventivo reale)
    eta_richiedente: int = 30  # età anagrafica per verifica limite 80 anni
    costo_assicurazione: float = 0.0  # premio unico assicurazione incendio (€)
    costo_perizia: float = 0.0  # spese perizia tecnica (€)
    classe_ape: str = "altro"  # "A/B" → spread ridotto -0.40%, "altro" → nessuno sconto
    taeg: float = 0.0  # Tasso Annuo Effettivo Globale (0 = non disponibile, solo informativo)
    reddito_mensile: float = 0.0  # reddito netto mensile per verifica rapporto rata/reddito

    @property
    def tasso_effettivo(self) -> float:
        if self.classe_ape == "A/B" and self.tasso_interesse > 0.004:
            return self.tasso_interesse - 0.004
        return self.tasso_interesse

    @property
    def totale_investimento(self) -> float:
        return (self.prezzo + self.imposte + self.notaio + self.agenzia_acquisto
                + self.lavori + self.compenso_tecnico + self.oneri_urbanistici
                + self.arredo + self.costo_assicurazione + self.costo_perizia)

    @property
    def costi_fissi_annui(self) -> float:
        return self.cedolare + self.imu + self.condominio + self.altro_costi

    @property
    def rata_mensile(self) -> float:
        return rata_mensile(self.importo_mutuo, self.tasso_effettivo, self.anni_mutuo)

    @property
    def totale_pagato_mutuo(self) -> float:
        return self.rata_mensile * self.anni_mutuo * 12



# ---------------------------------------------------------------------------
# Ammortamento francese a rata costante
# ---------------------------------------------------------------------------

def rata_mensile(capitale: float, tasso_annuo: float, anni: int) -> float:
    if capitale <= 0 or tasso_annuo <= 0 or anni <= 0:
        return 0.0
    r = tasso_annuo / 12
    n = anni * 12
    return capitale * (r * (1 + r) ** n) / ((1 + r) ** n - 1)


def piano_ammortamento(capitale: float, tasso_annuo: float, anni: int) -> pd.DataFrame:
    if capitale <= 0 or tasso_annuo <= 0 or anni <= 0:
        return pd.DataFrame(columns=[
            "Anno", "Rata_Mensile", "Rata_Annua", "Quota_Capitale_Annua",
            "Quota_Interessi_Annua", "Capitale_Residuo"
        ])

    r = tasso_annuo / 12
    n = anni * 12
    rat = rata_mensile(capitale, tasso_annuo, anni)

    residuo = capitale
    righe = []
    for mese in range(1, n + 1):
        int_m = residuo * r
        cap_m = rat - int_m
        residuo -= cap_m
        righe.append({
            "Mese": mese,
            "Anno": (mese - 1) // 12 + 1,
            "Rata": rat,
            "Quota_Capitale": cap_m,
            "Quota_Interessi": int_m,
            "Capitale_Residuo": max(0.0, residuo),
        })

    df_mesi = pd.DataFrame(righe)

    df_anno = (
        df_mesi
        .groupby("Anno", as_index=False)
        .agg(
            Rata_Mensile=("Rata", "first"),
            Rata_Annua=("Rata", "sum"),
            Quota_Capitale_Annua=("Quota_Capitale", "sum"),
            Quota_Interessi_Annua=("Quota_Interessi", "sum"),
            Capitale_Residuo=("Capitale_Residuo", "last"),
        )
    )
    return df_anno


# ---------------------------------------------------------------------------
# Proiezione pluriannuale
# ---------------------------------------------------------------------------

def proiezione(p: InvestmentParams) -> pd.DataFrame:
    """Calcola le proiezioni anno per anno e restituisce un DataFrame."""

    df_mutuo = piano_ammortamento(p.importo_mutuo, p.tasso_effettivo, p.anni_mutuo)

    valore_imm = p.prezzo + p.lavori
    cap_etf = p.equity
    cum_cf = 0.0

    righe = []
    for t in range(1, p.anni_simulazione + 1):
        infl_factor = (1 + p.inflazione_annua) ** (t - 1)

        if not df_mutuo.empty and t <= p.anni_mutuo:
            riga = df_mutuo.loc[df_mutuo["Anno"] == t].iloc[0]
            rata_t = riga["Rata_Annua"]
            residuo = riga["Capitale_Residuo"]
        else:
            rata_t = 0.0
            residuo = 0.0

        affitto_eff = p.affitto_lordo_annuo * infl_factor * (1 - p.sfitto_pct / 100)
        costi_annui = p.costi_fissi_annui * infl_factor
        capex_acc = affitto_eff * (p.capex_pct / 100)
        detr = p.detrazione_annua if t <= p.anni_detrazione else 0.0

        cf_netto = affitto_eff - costi_annui - rata_t + detr - capex_acc
        cum_cf += cf_netto

        valore_imm *= (1 + p.rivalutazione_annua)
        cap_etf *= (1 + p.rendimento_etf)

        # valore_imm = valore di mercato "vero" (rivaluta il prezzo d'acquisto+lavori).
        # prezzo_vendita_eff = quanto incassi davvero: se l'utente fissa un prezzo di
        # vendita, questo resta l'ancora (rivalutata) anche se diverge da valore_imm.
        if p.prezzo_vendita > 0:
            prezzo_vendita_eff = p.prezzo_vendita * (1 + p.rivalutazione_annua) ** t
        else:
            prezzo_vendita_eff = valore_imm
        spese_agenzia = p.agenzia_vendita_fissa if p.agenzia_vendita_fissa > 0 else prezzo_vendita_eff * (p.agenzia_vendita_pct / 100)
        realizzo = prezzo_vendita_eff - residuo - spese_agenzia
        equity_imm = (prezzo_vendita_eff - residuo - spese_agenzia) + cum_cf - p.equity

        righe.append({
            "Anno": t,
            "Affitto_Effettivo": affitto_eff,
            "Costi_Fissi": costi_annui,
            "Rata_Mutuo": rata_t,
            "Detrazione": detr,
            "CapEx_Accantonato": capex_acc,
            "CF_Netto_Anno": cf_netto,
            "CF_Cumulato": cum_cf,
            "Capitale_Residuo_Mutuo": residuo,
            "Valore_Immobile": prezzo_vendita_eff,
            "Valore_Mercato_Immobile": valore_imm,
            "Realizzo_Netto": realizzo,
            "Guadagno_Netto_Immobile": equity_imm,
            "Guadagno_Netto_ETF": cap_etf - p.equity,
        })

    return pd.DataFrame(righe)


# ---------------------------------------------------------------------------
# IRR / NPV
# ---------------------------------------------------------------------------

def calcola_irr(flussi: list[float]) -> float | None:
    if len(flussi) < 2:
        return None
    try:
        return brentq(lambda r: sum(f / (1 + r) ** t for t, f in enumerate(flussi)), -0.5, 5.0)
    except (ValueError, RuntimeError):
        return None


def calcola_npv(flussi: list[float], tasso: float) -> float:
    return sum(f / (1 + tasso) ** t for t, f in enumerate(flussi))


def flussi_per_irr(df_proj: pd.DataFrame, equity: float) -> list[float]:
    flussi = [-equity]
    for _, riga in df_proj.iterrows():
        flussi.append(riga["CF_Netto_Anno"])
    last = df_proj.iloc[-1]
    flussi[-1] += last["Realizzo_Netto"]
    return flussi


def calcola_rendimenti_per_anno(df_proj: pd.DataFrame, equity_val: float, anni_sim: int) -> tuple[pd.DataFrame, int, float]:
    """Rendimento annualizzato (CAGR) e guadagno totale per ogni anno >= 5.

    Restituisce (df_rendimenti, miglior_anno, miglior_rendimento_annuale).
    """
    righe = []
    best_annual = -float("inf")
    best_year = 0
    for yr in range(5, anni_sim + 1):
        if df_proj.empty or yr not in df_proj["Anno"].values:
            continue
        r = df_proj[df_proj["Anno"] == yr].iloc[0]
        guadagno = r["Guadagno_Netto_Immobile"]
        totale = guadagno + equity_val
        rend_annuale = (totale / equity_val) ** (1 / yr) - 1 if equity_val > 0 and totale > 0 else 0.0
        righe.append({
            "Anno": yr,
            "Rendimento Annuale Netto": rend_annuale,
            "Guadagno Totale Netto": guadagno,
        })
        if rend_annuale > best_annual:
            best_annual = rend_annuale
            best_year = yr
    return pd.DataFrame(righe), best_year, best_annual


# ---------------------------------------------------------------------------
# Benchmark: scenario 100% cash (no mutuo)
# ---------------------------------------------------------------------------

def scenario_cash(p: InvestmentParams) -> pd.DataFrame:
    cash = InvestmentParams(
        prezzo=p.prezzo, imposte=p.imposte, notaio=p.notaio,
        agenzia_acquisto=p.agenzia_acquisto, lavori=p.lavori,
        compenso_tecnico=p.compenso_tecnico, oneri_urbanistici=p.oneri_urbanistici, arredo=p.arredo,
        usa_mutuo=False, equity=p.totale_investimento, importo_mutuo=0.0,
        tasso_interesse=0.0, anni_mutuo=1,
        affitto_lordo_annuo=p.affitto_lordo_annuo,
        cedolare=p.cedolare, imu=p.imu, condominio=p.condominio,
        altro_costi=p.altro_costi,
        flag_detrazioni=p.flag_detrazioni, detrazione_annua=p.detrazione_annua,
        anni_detrazione=p.anni_detrazione, sfitto_pct=p.sfitto_pct,
        capex_pct=p.capex_pct, rivalutazione_annua=p.rivalutazione_annua,
        rendimento_etf=p.rendimento_etf, anni_simulazione=p.anni_simulazione,
        inflazione_annua=p.inflazione_annua, agenzia_vendita_pct=p.agenzia_vendita_pct,
        agenzia_vendita_fissa=p.agenzia_vendita_fissa,
        prezzo_vendita=p.prezzo_vendita,
        eta_richiedente=p.eta_richiedente, costo_assicurazione=p.costo_assicurazione,
        costo_perizia=p.costo_perizia, classe_ape=p.classe_ape, taeg=p.taeg,
        reddito_mensile=p.reddito_mensile,
    )
    return proiezione(cash)


# ---------------------------------------------------------------------------
# Validazioni bancarie (dal preventivo reale)
# ---------------------------------------------------------------------------

def verifica_limite_eta(eta: int, durata_anni: int) -> tuple[bool, str]:
    """Verifica che eta + durata mutuo <= 80 (limite MPS e molti istituti)."""
    totale = eta + durata_anni
    ok = totale <= 80
    msg = (
        f"OK: età {eta} + durata {durata_anni} = {totale} ≤ 80"
        if ok else
        f"ERRORE: età {eta} + durata {durata_anni} = {totale} > 80 — superato il limite bancario"
    )
    return ok, msg


def calcola_ltv_massimo(importo_mutuo: float, valore_immobile: float) -> float:
    """Restituisce l'LTV ratio (0-100)."""
    if valore_immobile <= 0:
        return 0.0
    return importo_mutuo / valore_immobile * 100


def verifica_ltv(importo_mutuo: float, valore_immobile: float,
                 max_ltv: float = 80.0) -> tuple[bool, str]:
    """Verifica che LTV <= max_ltv (default 80%)."""
    ltv = calcola_ltv_massimo(importo_mutuo, valore_immobile)
    ok = ltv <= max_ltv
    msg = (
        f"OK: LTV {ltv:.1f}% ≤ {max_ltv:.0f}%"
        if ok else
        f"ERRORE: LTV {ltv:.1f}% > {max_ltv:.0f}% — il mutuo eccede il massimo concedibile"
    )
    return ok, msg


def calcola_rapporto_rata_reddito(rata_mensile: float, reddito_mensile: float) -> float:
    """Restituisce il rapporto rata/reddito (0-100)."""
    if reddito_mensile <= 0:
        return 0.0
    return rata_mensile / reddito_mensile * 100


def verifica_rata_reddito(rata_mensile: float, reddito_mensile: float,
                          max_ratio: float = 35.0) -> tuple[bool, str]:
    """Verifica che rata/reddito <= max_ratio (default 35%)."""
    ratio = calcola_rapporto_rata_reddito(rata_mensile, reddito_mensile)
    ok = ratio <= max_ratio
    msg = (
        f"OK: rapporto rata/reddito {ratio:.1f}% ≤ {max_ratio:.0f}%"
        if ok else
        f"ATTENZIONE: rapporto rata/reddito {ratio:.1f}% > {max_ratio:.0f}% — la banca potrebbe non erogare"
    )
    return ok, msg


def calcola_costo_extra_taeg(importo_mutuo: float, tan: float,
                              taeg: float, anni: int) -> float:
    """Differenza totale in € tra rata a TAEG e rata a TAN."""
    if taeg <= 0 or taeg <= tan or importo_mutuo <= 0:
        return 0.0
    rata_tan = rata_mensile(importo_mutuo, tan, anni)
    rata_taeg = rata_mensile(importo_mutuo, taeg, anni)
    return (rata_taeg - rata_tan) * anni * 12


# ---------------------------------------------------------------------------
# Punto di incrocio leva/ETF (crossover)
# ---------------------------------------------------------------------------

def crossover_leva_etf(df_proj: pd.DataFrame, etf_gain: np.ndarray) -> dict:
    """Analizza quando l'ETF azionario supera l'immobile a leva.

    Confronta anno per anno il guadagno netto dell'immobile con mutuo
    (``Guadagno_Netto_Immobile``) contro il guadagno dello stesso capitale
    investito in un ETF (``etf_gain``, array lungo quanto la proiezione).

    Ritorna un dict con:
      - ``ultimo_anno_vantaggio``: ultimo anno in cui l'immobile (leva) supera
        o pareggia l'ETF (``None`` se non lo supera mai);
      - ``anno_sorpasso``: anno interpolato in cui le due curve si incrociano
        (``None`` se non c'è sorpasso nell'orizzonte);
      - ``esito``: ``"sorpasso"`` | ``"leva_vince_sempre"`` | ``"etf_vince_sempre"``.
    """
    if df_proj is None or df_proj.empty or etf_gain is None or len(etf_gain) == 0:
        return {"ultimo_anno_vantaggio": None, "anno_sorpasso": None, "esito": "n/d"}

    diff = df_proj["Guadagno_Netto_Immobile"].values - np.asarray(etf_gain, dtype=float)
    anni = df_proj["Anno"].values.astype(float)

    win = diff >= 0
    if not win.any():
        return {
            "ultimo_anno_vantaggio": None,
            "anno_sorpasso": float(anni[0]),
            "esito": "etf_vince_sempre",
        }

    last = int(np.where(win)[0][-1])
    ultimo_anno = int(anni[last])
    if last == len(diff) - 1:
        return {
            "ultimo_anno_vantaggio": ultimo_anno,
            "anno_sorpasso": None,
            "esito": "leva_vince_sempre",
        }

    d0, d1 = diff[last], diff[last + 1]
    if d0 >= 0 and d1 < 0:
        anno_sorpasso = float(anni[last]) + d0 / (d0 - d1)
    else:
        anno_sorpasso = float(anni[last + 1])

    return {
        "ultimo_anno_vantaggio": ultimo_anno,
        "anno_sorpasso": anno_sorpasso,
        "esito": "sorpasso",
    }
