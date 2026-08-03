import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import io
import json

from engine import (
    InvestmentParams,
    rata_mensile,
    piano_ammortamento,
    proiezione,
    calcola_irr,
    calcola_npv,
    calcola_ltv_massimo,
    calcola_costo_extra_taeg,
    flussi_per_irr,
    scenario_cash,
    verifica_limite_eta,
    verifica_ltv,
    verifica_rata_reddito,
    crossover_leva_etf,
    WORK_ITEMS,
    FURN_ITEMS,
    calcola_totale_lavori,
    calcola_totale_mobilio,
    calcola_iva_lavori,
    calcola_imposte_acquisto,
)
from report import generate_pdf


def fmt(val, decimali=0):
    """Formatta un numero in stile italiano: 1.234,56"""
    if decimali == 0:
        s = f"{round(val):,}"
    else:
        s = f"{val:,.{decimali}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


# ─── Scenario persistence (session-only) ────────────────────────────────────
# Massima privacy: nessun file su disco. Gli scenari vivono solo in session_state
# della sessione corrente e si perdono al refresh/chiusura (usare "Scarica JSON").


def _save_scenario_to_disk(name: str, data: dict):
    """Session-only: lo scenario resta in session_state, nessun file scritto."""
    pass


def _delete_scenario_from_disk(name: str):
    """Session-only: nessun file da eliminare."""
    pass


def _load_scenarios_from_disk() -> dict:
    """Session-only: si parte sempre vuoti."""
    return {}


# ─── Page Config ───────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Investment Analyzer",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ─── Password gate (Streamlit Community Cloud) ──────────────────────────────
# Su cloud imposta la password nelle Secrets di Streamlit (APP_PASSWORD).
# In locale, senza secrets.toml, l'app resta aperta senza login.
def _password_gate() -> None:
    expected = st.secrets.get("APP_PASSWORD", "")
    if not expected:
        return
    if st.session_state.get("auth_ok"):
        return

    st.markdown("### 🔒 Area riservata")
    st.markdown("Inserisci la password per accedere alla simulazione.")
    pwd = st.text_input("Password", type="password")
    if st.button("Accedi", type="primary"):
        if pwd == expected:
            st.session_state["auth_ok"] = True
            st.rerun()
        else:
            st.error("Password errata.")
    st.stop()


_password_gate()

# ─── Custom CSS ────────────────────────────────────────────────────────────
st.markdown("""
<style>
    html, body, [class*="css"] {
        background-color: #FFFFFF;
        color: #1A1A1A;
    }
    .block-container { padding-top: 1.5rem; }
    div[data-testid="stMetric"] {
        background: linear-gradient(135deg, #f0f4ff, #f8f0ff);
        border: 1px solid #e0e0e0;
        border-radius: 10px;
        padding: 12px 16px;
    }
    div[data-testid="stMetric"] label { font-size: 0.82rem !important; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px 8px 0 0;
        padding: 10px 20px;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

st.title("🏢 Real Estate Investment Analyzer")
st.caption("Simulazione avanzata rendimenti immobiliari, leva finanziaria, cash flow e confronto ETF")

# ═════════════════════════════════════════════════════════════════════════════
# SESSION STATE & SCENARIO LOAD (must run before sidebar widgets)
# ═════════════════════════════════════════════════════════════════════════════

if "scenarios" not in st.session_state:
    st.session_state["scenarios"] = _load_scenarios_from_disk()
if "load_scenario" not in st.session_state:
    st.session_state["load_scenario"] = None
if "pending_delete" not in st.session_state:
    st.session_state["pending_delete"] = None

_CONVERSIONS = {
    "tasso_interesse": lambda v: v * 100,
    "rivalutazione_annua": lambda v: v * 100,
    "rendimento_etf": lambda v: v * 100,
    "inflazione_annua": lambda v: v * 100,
    "taeg": lambda v: v * 100,
}

if st.session_state["load_scenario"]:
    nome = st.session_state.pop("load_scenario")
    _loaded = st.session_state["scenarios"].get(nome)
    if _loaded:
        if "pratiche" in _loaded and "compenso_tecnico" not in _loaded:
            _p = _loaded.pop("pratiche")
            _loaded.setdefault("compenso_tecnico", _p * 0.4)
            _loaded.setdefault("oneri_urbanistici", _p * 0.6)
        for k, v in _loaded.items():
            if v is None:
                continue
            if k == "work_qty":
                for item_id, qty in v.items():
                    st.session_state[f"work_{item_id}"] = qty
            elif k == "furn_qty":
                for item_id, qty in v.items():
                    st.session_state[f"furn_{item_id}"] = qty
            elif k in _CONVERSIONS:
                st.session_state[k] = _CONVERSIONS[k](v)
            else:
                st.session_state[k] = v
        st.rerun()

# ═════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═════════════════════════════════════════════════════════════════════════════

# --- 1. Costi Acquisto & Lavori ---
st.sidebar.header("💰 1. Spese Acquisto & Lavori")
prezzo = st.sidebar.number_input("Prezzo Immobile (€)", value=0, step=1000, format="%d", key="prezzo")

# --- Calcolo automatico imposte ---
st.sidebar.subheader("Imposte di Acquisto")
imposte_mode = st.sidebar.radio("Modalità calcolo imposte", ["Manuale", "Automatico"], label_visibility="collapsed", key="imposte_mode")
acquirente = tipo_imm = venditore = None
regime = "iva"
rendita_cat = 0.0
if imposte_mode == "Automatico":
    acquirente = st.sidebar.selectbox("Acquirente", ["privato", "azienda"], key="acquirente")
    tipo_imm = st.sidebar.selectbox("Tipo Immobile", ["prima", "seconda"], key="tipo_imm")
    venditore = st.sidebar.selectbox("Venditore", ["privato", "azienda"], key="venditore")
    regime_opts = ["iva", "registro"] if venditore == "azienda" else ["iva"]
    regime = st.sidebar.selectbox("Regime", regime_opts, key="regime") if venditore == "azienda" else "iva"
    rendita_cat = st.sidebar.number_input("Rendita Catastale (€)", value=0.0, step=10.0, format="%.2f", key="rendita_cat",
                                          help="Necessaria per calcolo privato-privato")
    det_imposte = calcola_imposte_acquisto(
        prezzo=prezzo, acquirente=acquirente, tipo_immobile=tipo_imm,
        venditore=venditore, regime=regime, rendita_catastale=rendita_cat or None,
    )
    if "errore" in det_imposte:
        st.sidebar.warning(det_imposte["errore"])
        imposte = 0.0
    else:
        imposte = round(det_imposte["totale"])
        with st.sidebar.expander("Dettaglio imposte", expanded=False):
            st.caption(f"Registro: {fmt(det_imposte['registro'])}")
            st.caption(f"Ipotecaria: {fmt(det_imposte['ipotecaria'])}")
            st.caption(f"Catastale: {fmt(det_imposte['catastale'])}")
            if det_imposte["iva"] > 0:
                st.caption(f"IVA: {fmt(det_imposte['iva'])}")
            if det_imposte["valore_catastale"] > 0:
                st.caption(f"Valore catastale: {fmt(det_imposte['valore_catastale'])}")
else:
    imposte = st.sidebar.number_input("Imposte Acquisto (€)", value=0, step=100, format="%d", key="imposte",
                                       help="Registro + Ipotecaria + Catastale")

notaio = st.sidebar.number_input("Spese Notaio (€)", value=0, step=500, format="%d", key="notaio")
agenzia_acq = st.sidebar.number_input("Agenzia Immobiliare Acquisto (€)", value=0, step=100, format="%d", key="agenzia_acquisto")
costo_perizia = st.sidebar.number_input("Spese Perizia Mutuo (€)", value=0, step=50, format="%d", key="costo_perizia",
                                        help="Perizia tecnica obbligatoria per la banca (MPS: fino 180€ per importi ≤150k)")
costo_assicurazione = st.sidebar.number_input("Assicurazione Incendio (€)", value=0, step=50, format="%d", key="costo_assicurazione",
                                              help="Premio unico assicurazione incendio/scoppio obbligatoria (MPS: AXA MPS, premio unico anticipato)")

# --- Lavori dettagliati ---
st.sidebar.subheader("🔨 Computo Metrico Lavori")
work_qty: dict[str, float] = {}
WORK_DEFAULTS: dict[str, float] = {}

work_categories = list(dict.fromkeys(item["categoria"] for item in WORK_ITEMS))

for cat in work_categories:
    cat_items = [item for item in WORK_ITEMS if item["categoria"] == cat]
    with st.sidebar.expander(f"{cat} ({len(cat_items)} voci)", expanded=False):
        for item in cat_items:
            step_val = 1.0 if item["um"] == "cad" else 0.1
            default_val = float(WORK_DEFAULTS.get(item["id"], 0))
            qty = st.number_input(
                f"{item['voce']} ({item['um']}) — €{item['prezzo']:.2f}",
                value=default_val, min_value=0.0, step=step_val, format="%.1f",
                key=f"work_{item['id']}",
                help=f"Prezzo unitario: €{item['prezzo']:.2f}/{item['um']}",
            )
            work_qty[item["id"]] = qty

lavori = calcola_totale_lavori(work_qty)
iva_lavori = calcola_iva_lavori(work_qty)
st.sidebar.caption(f"Lavori imponibile 10%: {fmt(iva_lavori['imponibile_10'])} | IVA: {fmt(iva_lavori['iva_10'])}")
st.sidebar.caption(f"Forniture imponibile 22%: {fmt(iva_lavori['imponibile_22'])} | IVA: {fmt(iva_lavori['iva_22'])}")
st.sidebar.success(f"**Totale Lavori: {fmt(lavori + iva_lavori['iva_totale'])} €** (di cui IVA {fmt(iva_lavori['iva_totale'])} €)")

compenso_tecnico = st.sidebar.number_input("Compenso Tecnico (architetto, geometra, ecc.) (€)", value=0, step=500, format="%d", key="compenso_tecnico",
                                            help="Costi professionali per progettazione e direzione lavori — DETRAIBILI al 50%/36%")
oneri_urbanistici = st.sidebar.number_input("Oneri Urbanistici / Cessione (€)", value=0, step=500, format="%d", key="oneri_urbanistici",
                                            help="Oneri di urbanizzazione e cessione del fabbricato — DETRAIBILI al 50%/36%")

# --- Arredamento dettagliato ---
st.sidebar.subheader("🛋️ Arredamento / Mobilio")

FURN_DEFAULTS: dict[str, float] = {}

furn_qty: dict[str, float] = {}
furn_categories = list(dict.fromkeys(item["categoria"] for item in FURN_ITEMS))

for cat in furn_categories:
    cat_items = [item for item in FURN_ITEMS if item["categoria"] == cat]
    with st.sidebar.expander(f"{cat} ({len(cat_items)} voci)", expanded=False):
        for item in cat_items:
            default_val = float(FURN_DEFAULTS.get(item["id"], 0))
            qty = st.number_input(
                f"{item['voce']} — €{item['prezzo']:.2f} (IVA incl.)",
                value=default_val, min_value=0.0, step=1.0, format="%.0f",
                key=f"furn_{item['id']}",
                help=f"Prezzo unitario: €{item['prezzo']:.2f} (IVA 22% già inclusa)",
            )
            furn_qty[item["id"]] = qty

arredo = calcola_totale_mobilio(furn_qty)
st.sidebar.success(f"**Totale Arredo: {fmt(arredo)} €** (IVA 22% già inclusa)")

totale_inv = prezzo + imposte + notaio + agenzia_acq + lavori + compenso_tecnico + oneri_urbanistici + arredo + costo_assicurazione + costo_perizia
st.sidebar.success(f"**Investimento Totale: {fmt(totale_inv)} €**")

# --- 2. Finanziamento ---
st.sidebar.header("🏦 2. Finanziamento / Mutuo")
usa_mutuo = st.sidebar.checkbox("Includi Mutuo", value=True, key="usa_mutuo")

modalita = None
if usa_mutuo:
    modalita = st.sidebar.radio(
        "Modalità inserimento:",
        ["Capitale Proprio (Equity)", "Importo Mutuo diretto"],
        label_visibility="collapsed", key="modalita",
    )
    if modalita == "Capitale Proprio (Equity)":
        equity_val = st.sidebar.number_input("Capitale Proprio Disponibile (€)", value=0, step=5000, format="%d", key="equity")
        mutuo_val = max(0.0, totale_inv - equity_val)
        if equity_val > totale_inv:
            st.sidebar.warning("L'equity supera l'investimento totale — nessun mutuo necessario.")
            mutuo_val = 0.0
            equity_val = totale_inv
    else:
        mutuo_val = st.sidebar.number_input("Importo Mutuo (€)", value=0, step=5000, format="%d", key="importo_mutuo")
        equity_val = totale_inv - mutuo_val
        if mutuo_val > totale_inv:
            st.sidebar.warning("Il mutuo non può superare l'investimento totale.")
            mutuo_val = totale_inv
            equity_val = 0.0

    tasso = st.sidebar.number_input("Tasso d'interesse annuo (%)", value=0.0, step=0.10, format="%.2f", key="tasso_interesse") / 100
    anni_mut = st.sidebar.slider("Durata Mutuo (Anni)", 5, 30, 20, step=1, key="anni_mutuo")
    eta_rich = st.sidebar.number_input("Età Richiedente (anni)", value=0, step=1, key="eta_richiedente",
                                       help="Usata per verifica limite bancario: età + durata ≤ 80")
    classe_ape = st.sidebar.selectbox("Classe APE", ["altro", "A/B"], key="classe_ape",
                                      help="A/B: spread ridotto di 0,40 punti (MPS)")
    taeg_val = st.sidebar.number_input("TAEG (%)", value=0.0, step=0.10, format="%.2f", key="taeg",
                                       help="Tasso Annuo Effettivo Globale — se > 0, mostra il costo reale includendo assicurazione e spese")
    reddito_mensile = st.sidebar.number_input("Reddito Netto Mensile (€)", value=0, step=100, format="%d", key="reddito_mensile",
                                              help="Per verifica rapporto rata/reddito (limite bancario ~33-35%)")

    tasso_eff = tasso - 0.004 if classe_ape == "A/B" else tasso
    rata_m = rata_mensile(mutuo_val, tasso_eff, anni_mut)
    tot_pagato = rata_m * anni_mut * 12
    st.sidebar.info(f"Rata mensile: **{fmt(rata_m, 2)} €** — Totale pagato: **{fmt(tot_pagato)} €**"
                    + (f" (tasso eff. {fmt(tasso_eff*100, 2)}% con APE A/B)" if classe_ape == "A/B" else ""))

    # ── Warning bancari ──
    valore_imm_tot = prezzo + lavori
    if mutuo_val > 0 and valore_imm_tot > 0:
        ltv = calcola_ltv_massimo(mutuo_val, valore_imm_tot)
        if ltv > 80:
            st.sidebar.warning(f"LTV {ltv:.1f}% > 80% — il mutuo eccede il massimo concedibile (max {fmt(valore_imm_tot*0.8)} €)")
    if mutuo_val > 0:
        ok_eta, msg_eta = verifica_limite_eta(eta_rich, anni_mut)
        if not ok_eta:
            st.sidebar.error(msg_eta)
    if mutuo_val > 0 and reddito_mensile > 0:
        ok_rata, msg_rata = verifica_rata_reddito(rata_m, reddito_mensile)
        if not ok_rata:
            st.sidebar.warning(msg_rata)
else:
    mutuo_val = 0.0
    equity_val = totale_inv
    tasso = 0.0
    anni_mut = 1
    rata_m = 0.0

# --- 3. Affitto & Costi Operativi ---
st.sidebar.header("🏠 3. Affitto & Costi Operativi")
affitto_lordo = st.sidebar.number_input("Affitto Lordo Annuo (€)", value=0, step=600, format="%d", key="affitto_lordo_annuo",
                                         help="700 €/mese × 12")
cedolare = st.sidebar.number_input("Cedolare Secca (€)", value=0, step=100, format="%d", key="cedolare")
imu = st.sidebar.number_input("IMU Annua (€)", value=0, step=50, format="%d", key="imu")
condominio = st.sidebar.number_input("Spese Condominio (€)", value=0, step=50, format="%d", key="condominio")
altro_costi = st.sidebar.number_input("Altri Costi Fissi (€)", value=0, step=100, format="%d", key="altro_costi")

# --- 4. Fiscali, Vendita & Benchmark ---
st.sidebar.header("📊 4. Fiscali, Vendita & Benchmark")

st.sidebar.subheader("Detrazione Fiscale")
flag_detrazioni = st.sidebar.checkbox("Applica Detrazione Fiscale (Ristrutturazione)", value=True, key="flag_detrazioni")
if flag_detrazioni:
    porta_residenza = st.sidebar.checkbox("Porta Residenza entro12 mesi", value=True, key="porta_residenza",
                                          help="Sposta la residenza nel fabbricato entro12 mesi dal termine dei lavori → aliquota 50%. Altrimenti36%")
    aliquota_detr = 0.50 if porta_residenza else 0.36
    anni_detraz = 10
else:
    porta_residenza = False
    aliquota_detr = 0.0
    anni_detraz = 0

base_detr = lavori + compenso_tecnico + oneri_urbanistici
detrazione_annua_val = base_detr * aliquota_detr / anni_detraz if flag_detrazioni else 0.0

st.sidebar.subheader("Costi Operativi")
sfitto = st.sidebar.slider("Tasso di Sfitto / Vacancy (%)", 0, 20, 0, step=1, key="sfitto_pct",
                             help="Percentuale di affitto perso per mancati incassi")
capex_pct = st.sidebar.slider("CapEx Reserve (% affitto netto)", 0, 15, 0, step=1, key="capex_pct",
                              help="Risparmio accantonato per manutenzione straordinaria (tetti, impianti, infissi). Non è un costo immediato.")

st.sidebar.subheader("🏷️ Vendita Immobile")
prezzo_vendita_val = st.sidebar.number_input("Prezzo di Vendita Stimato (€)", value=0, step=5000, format="%d", key="prezzo_vendita",
                                              help="0 = usa il valore di mercato (rivalutazione). Se > 0, è il prezzo a cui vendi realmente.")
agenzia_vendita_mode = st.sidebar.radio(
    "Commissione Agenzia",
    ["Percentuale", "Importo Fisso"],
    label_visibility="collapsed", key="agenzia_vendita_mode",
)
if agenzia_vendita_mode == "Percentuale":
    agenzia_vendita_val = st.sidebar.number_input("Commissione Agenzia (%)", value=0.0, step=0.5, format="%.1f", key="agenzia_vendita_pct",
                                                   help="Percentuale del prezzo di vendita pagata all'agenzia")
    agenzia_vendita_fissa = 0.0
else:
    agenzia_vendita_fissa = st.sidebar.number_input("Commissione Agenzia (€)", value=0, step=500, format="%d", key="agenzia_vendita_fissa",
                                                     help="Importo fisso pagato all'agenzia alla vendita")
    agenzia_vendita_val = 0.0

st.sidebar.markdown("---")
st.sidebar.subheader("🔀 Benchmark")
inflazione = st.sidebar.slider("Inflazione Annua (%)", 0, 8, 0, step=1, key="inflazione_annua",
                               help="Crescita annua stimata di affitto e costi operativi")
rivalutazione = st.sidebar.number_input("Rivalutazione Annua Immobile (%)", value=0.0, step=0.25, format="%.2f", key="rivalutazione_annua") / 100
rend_etf = st.sidebar.number_input("Rendimento ETF Azionario Annuo (%)", value=0.0, step=0.5, format="%.1f", key="rendimento_etf") / 100
anni_sim = st.sidebar.slider("Orizzonte Simulazione (Anni)", 5, 30, 20, step=1, key="anni_simulazione")

# --- Validazioni input ---
if usa_mutuo and tasso == 0.0 and mutuo_val > 0:
    st.sidebar.warning("⚠️ Tasso 0% con mutuo attivo — la rata sarà 0, risultati non realistici.")
if usa_mutuo and anni_mut > anni_sim:
    st.sidebar.warning(f"⚠️ Durata mutuo ({anni_mut} anni) supera l'orizzonte simulazione ({anni_sim} anni).")
if affitto_lordo == 0 and usa_mutuo and mutuo_val > 0:
    st.sidebar.warning("⚠️ Affitto 0 con mutuo attivo — CF negativo strutturale.")
if rivalutazione > 0 and prezzo_vendita_val > 0:
    st.sidebar.warning("⚠️ Prezzo di vendita fisso e rivalutazione annua attivi insieme — la rivalutazione verrà ignorata.")

# --- 5. Scenari Salvati (persistenza su disco) ---
st.sidebar.markdown("---")
st.sidebar.header("💾 5. Scenari")

SCENARIO_DATA = {
    "prezzo": prezzo, "imposte": imposte, "notaio": notaio,
    "agenzia_acquisto": agenzia_acq, "lavori": lavori,
    "compenso_tecnico": compenso_tecnico, "oneri_urbanistici": oneri_urbanistici,
    "arredo": arredo,
    "usa_mutuo": usa_mutuo, "equity": equity_val,
    "importo_mutuo": mutuo_val, "tasso_interesse": tasso,
    "anni_mutuo": anni_mut,
    "affitto_lordo_annuo": affitto_lordo,
    "cedolare": cedolare, "imu": imu,
    "condominio": condominio, "altro_costi": altro_costi,
    "flag_detrazioni": flag_detrazioni,
    "porta_residenza": porta_residenza,
    "detrazione_annua": detrazione_annua_val,
    "anni_detrazione": anni_detraz,
    "sfitto_pct": sfitto, "capex_pct": capex_pct,
    "rivalutazione_annua": rivalutazione,
    "rendimento_etf": rend_etf,
    "anni_simulazione": anni_sim,
    "inflazione_annua": inflazione / 100,
    "agenzia_vendita_pct": agenzia_vendita_val,
    "agenzia_vendita_fissa": agenzia_vendita_fissa,
    "agenzia_vendita_mode": agenzia_vendita_mode,
    "prezzo_vendita": prezzo_vendita_val,
    "imposte_mode": imposte_mode,
    "acquirente": acquirente,
    "tipo_imm": tipo_imm,
    "venditore": venditore,
    "regime": regime,
    "rendita_cat": rendita_cat,
    "modalita": modalita if usa_mutuo else "Capitale Proprio (Equity)",
    "work_qty": work_qty,
    "furn_qty": furn_qty,
    "eta_richiedente": eta_rich,
    "costo_assicurazione": costo_assicurazione,
    "costo_perizia": costo_perizia,
    "classe_ape": classe_ape,
    "taeg": taeg_val / 100,
    "reddito_mensile": reddito_mensile,
}

with st.sidebar.expander("Salva scenario corrente", expanded=False):
    st.caption("Salvataggio SOLO in questa sessione: al refresh o alla chiusura si perde. Usa \"Scarica JSON\" per conservarlo.")
    scenario_name = st.text_input("Nome scenario", key="new_scenario_name")
    if st.button("Salva", use_container_width=True):
        if scenario_name.strip():
            key = scenario_name.strip()
            st.session_state["scenarios"][key] = SCENARIO_DATA
            _save_scenario_to_disk(key, SCENARIO_DATA)
            st.success(f"Scenario '{key}' salvato!")
            st.rerun()
        else:
            st.warning("Inserisci un nome.")
    _export_name = (scenario_name.strip() or "scenario").replace(" ", "_")
    _export_bytes = json.dumps({"name": _export_name, "params": SCENARIO_DATA},
                               ensure_ascii=False, indent=2).encode("utf-8")
    st.download_button(
        "Scarica JSON",
        data=_export_bytes,
        file_name=f"{_export_name}.json",
        mime="application/json",
        use_container_width=True,
        key="export_scenario",
        help="Esporta lo scenario corrente come file JSON, da ricaricare in qualsiasi sessione",
    )

with st.sidebar.expander("Importa scenario da file", expanded=False):
    uploaded = st.file_uploader("Carica un file .json", type=["json"], key="import_scenario")
    if uploaded is not None:
        try:
            raw = json.load(uploaded)
            imported_name = raw.get("name", uploaded.name.replace(".json", ""))
            imported_params = raw.get("params", raw)
            st.session_state["scenarios"][imported_name] = imported_params
            _save_scenario_to_disk(imported_name, imported_params)
            st.success(f"Scenario '{imported_name}' importato!")
            st.rerun()
        except (json.JSONDecodeError, KeyError):
            st.error("File non valido. Formato atteso: {\"name\": \"...\", \"params\": {...}}")

if st.session_state["scenarios"]:
    with st.sidebar.expander("Scenari salvati", expanded=True):
        for nome in list(st.session_state["scenarios"].keys()):
            c1, c2, c3 = st.columns([2, 1, 1])
            c1.caption(nome)
            if c2.button("⟳", key=f"load_{nome}", help="Carica questo scenario nei parametri"):
                st.session_state["load_scenario"] = nome
                st.rerun()
            if c3.button("✕", key=f"del_{nome}", help="Elimina scenario"):
                st.session_state["pending_delete"] = nome
                st.rerun()

        if st.session_state["pending_delete"]:
            nome_del = st.session_state["pending_delete"]
            st.warning(f"Eliminare **{nome_del}** definitivamente?")
            c_yes, c_no = st.columns(2)
            if c_yes.button("Sì, elimina", key="confirm_del", type="primary"):
                del st.session_state["scenarios"][nome_del]
                _delete_scenario_from_disk(nome_del)
                st.session_state["pending_delete"] = None
                st.rerun()
            if c_no.button("No, annulla", key="cancel_del"):
                st.session_state["pending_delete"] = None
                st.rerun()
else:
    st.sidebar.caption("Nessuno scenario. Importa un file .json per iniziare.")

# ═════════════════════════════════════════════════════════════════════════════
# ENGINE CALLS
# ═════════════════════════════════════════════════════════════════════════════

tasso_eff = tasso - 0.004 if classe_ape == "A/B" else tasso

params = InvestmentParams(
    prezzo=prezzo, imposte=imposte, notaio=notaio,
    agenzia_acquisto=agenzia_acq, lavori=lavori,
    compenso_tecnico=compenso_tecnico, oneri_urbanistici=oneri_urbanistici, arredo=arredo,
    usa_mutuo=usa_mutuo, equity=equity_val, importo_mutuo=mutuo_val,
    tasso_interesse=tasso, anni_mutuo=anni_mut,
    affitto_lordo_annuo=affitto_lordo,
    cedolare=cedolare, imu=imu, condominio=condominio,
    altro_costi=altro_costi,
    flag_detrazioni=flag_detrazioni, detrazione_annua=detrazione_annua_val,
    anni_detrazione=anni_detraz, sfitto_pct=sfitto,
    capex_pct=capex_pct, rivalutazione_annua=rivalutazione,
    rendimento_etf=rend_etf, anni_simulazione=anni_sim,
    inflazione_annua=inflazione / 100, agenzia_vendita_pct=agenzia_vendita_val,
    agenzia_vendita_fissa=agenzia_vendita_fissa,
    prezzo_vendita=prezzo_vendita_val,
    eta_richiedente=eta_rich, costo_assicurazione=costo_assicurazione,
    costo_perizia=costo_perizia, classe_ape=classe_ape, taeg=taeg_val / 100,
    reddito_mensile=reddito_mensile,
)

# ---------------------------------------------------------------------------
# Cached wrappers (decouple engine from Streamlit)
# ---------------------------------------------------------------------------

@st.cache_data
def _cached_proiezione(params_dict: dict) -> pd.DataFrame:
    return proiezione(InvestmentParams(**params_dict))

@st.cache_data
def _cached_scenario_cash(params_dict: dict) -> pd.DataFrame:
    return scenario_cash(InvestmentParams(**params_dict))

# ---------------------------------------------------------------------------
# ENGINE CALLS
# ---------------------------------------------------------------------------

df_mutuo = piano_ammortamento(params.importo_mutuo, params.tasso_interesse, params.anni_mutuo)
rata_annua = df_mutuo["Rata_Annua"].iloc[0] if not df_mutuo.empty else 0.0

df_proj = _cached_proiezione(params.__dict__)
df_cash = _cached_scenario_cash(params.__dict__)
etf_puro = params.equity * (1 + params.rendimento_etf) ** np.arange(1, params.anni_simulazione + 1) - params.equity
etf_cash = totale_inv * (1 + params.rendimento_etf) ** np.arange(1, params.anni_simulazione + 1) - totale_inv

if not df_proj.empty:
    flussi = flussi_per_irr(df_proj, params.equity)
    irr_val = calcola_irr(flussi)
    npv_val = calcola_npv(flussi, params.rendimento_etf)
else:
    irr_val = None
    npv_val = 0.0

# ═════════════════════════════════════════════════════════════════════════════
# TABS
# ═════════════════════════════════════════════════════════════════════════════

tab_kpi, tab_mutuo, tab_bench, tab_dettaglio = st.tabs([
    "📊 KPI & Sintesi",
    "🏦 Piano Ammortamento",
    "🥊 Benchmark ETF",
    "📋 Dettaglio Completo",
])

# ─── TAB 1: KPI & Sintesi ─────────────────────────────────────────────────
with tab_kpi:
    st.subheader("Metriche Chiave")
    c1, c2, c3 = st.columns(3)
    c1.metric("Investimento Totale", f"{fmt(totale_inv)} €")
    c2.metric("Equity (Capitale Proprio)", f"{fmt(equity_val)} €")
    c3.metric("Importo Mutuo", f"{fmt(mutuo_val)} €" if usa_mutuo else "—")

    st.markdown("---")
    st.subheader("Rendimenti per Orizzonte Temporale")

    anni_kpi = list(range(5, anni_sim + 1))

    righe_rend = []
    best_annual = -float("inf")
    best_year = 0
    for yr in anni_kpi:
        if not df_proj.empty and yr <= anni_sim:
            r = df_proj[df_proj["Anno"] == yr].iloc[0]
            guadagno = r["Guadagno_Netto_Immobile"]
            totale = guadagno + equity_val
            rend_totale = guadagno
            if equity_val > 0 and totale > 0 and yr > 0:
                rend_annuale = (totale / equity_val) ** (1 / yr) - 1
            else:
                rend_annuale = 0.0
            righe_rend.append({
                "Anno": yr,
                "Rendimento Annuale Netto": rend_annuale,
                "Guadagno Totale Netto": guadagno,
            })
            if rend_annuale > best_annual:
                best_annual = rend_annuale
                best_year = yr

    df_rend = pd.DataFrame(righe_rend)
    if not df_rend.empty:
        fmt_rend = {
            "Rendimento Annuale Netto": lambda v: f"{fmt(v * 100, 2)} %",
            "Guadagno Totale Netto": lambda v: f"{fmt(v)} €",
        }
        st.dataframe(df_rend.style.format(fmt_rend), use_container_width=True, hide_index=True)

        if 5 in df_proj["Anno"].values:
            r5 = df_proj[df_proj["Anno"] == 5].iloc[0]
            guadagno_5 = r5["Guadagno_Netto_Immobile"]
            prezzo_5 = r5["Valore_Immobile"]
            residuo_5 = r5["Capitale_Residuo_Mutuo"]
            cum_cf_5 = r5["CF_Cumulato"]
            detr_5 = r5["Detrazione"]
            rend_ann_pct = ((guadagno_5 + equity_val) / equity_val) ** (1 / 5) - 1
            st.info(
                f"**Come si calcola (es. Anno 5):**\n\n"
                f"Guadagno Totale Netto = (Prezzo Vendita − Debito Residuo) + Cash Flow Cumulato − Equity\n\n"
                f"Cash Flow Cumulato = Σ(Affitto − Costi − Rata + **Detrazioni** − CapEx) per 5 anni = {fmt(cum_cf_5)} €\n\n"
                f"= ({fmt(prezzo_5)} − {fmt(residuo_5)}) + {fmt(cum_cf_5)} − {fmt(equity_val)} = **{fmt(guadagno_5)} €**\n\n"
                f"Rendimento Annuale Netto = ((Guadagno + Equity) / Equity) ^ (1/5) − 1 = **{fmt(rend_ann_pct * 100, 2)} %**"
            )

    st.markdown("---")
    st.subheader("Miglior Anno per Vendere")
    if best_year > 0:
        c_best1, c_best2 = st.columns(2)
        c_best1.metric("Miglior anno per vendere", f"Anno {best_year}")
        c_best2.metric("Rendimento annuale netto", f"{fmt(best_annual * 100, 2)} %",
                       help="Il rendimento annualizzato più alto — l'anno in cui vendere massimizza il guadagno annualizzato")
    else:
        st.info("Dati insufficienti per calcolare il miglior anno.")

    with st.expander("Come leggere queste metriche?", expanded=False):
        st.markdown("""
**Rendimento Annuale Netto** — Quanto rende in media ogni anno il tuo investimento, calcolato come CAGR (Compound Annual Growth Rate). Se è 8%, significa che ogni anno il tuo capitale è cresciuto dell'8% in media. Include sia il cash flow che la rivalutazione dell'immobile.

**Guadagno Totale Netto** — Il guadagno assoluto in euro se vendessi quell'anno. È il profitto reale in tasca dopo aver pagato agenzia, spese e residuo mutuo.

**Miglior Anno per Vendere** — L'anno che massimizza il rendimento annuale. Non è sempre l'ultimo anno: a volte conviene vendere prima se il rendimento annuale cala col tempo.
        """)

    with st.expander("Glossario — Significato delle abbreviazioni", expanded=False):
        st.markdown("""
| Abbreviazione | Significato |
|---|---|
| **CF** | Cash Flow — flusso di cassa annuale (entrate − uscite) |
| **CF Mensile** | CF annuale diviso 12 |
| **CapEx** | Capital Expenditure — accantonamento per spese straordinarie (caldaia, tetto, impianti) |
| **ROI** | Return on Investment — rendimento totale in percentuale |
| **CAGR** | Compound Annual Growth Rate — rendimento annualizzato medio |
| **KPI** | Key Performance Indicator — indicatori chiave di performance |
| **ETF** | Exchange Traded Fund — fondo di investimento negoziato in borsa |
| **Equity** | Capitale proprio — quanto hai messo di tasca tua |
| **Mutuo / Leva** | Finanziamento bancario — usi poco capitale tuo per controllare un asset più grande |
| **Detrazione** | Agevolazione fiscale (es. Bonus 50%) che riduce le tasse che paghi |
| **Sfitto** | Periodo in cui l'appartamento è vuoto e non genera affitto |
| **Realizzo Netto** | Quanto incassi dalla vendita dopo aver pagato agenzia e residuo mutuo |
        """)


# ─── TAB 2: Piano Ammortamento ────────────────────────────────────────────
with tab_mutuo:
    if not df_mutuo.empty and usa_mutuo and mutuo_val > 0:
        st.subheader("Piano di Ammortamento Francese — Dettaglio Annuo")
        st.dataframe(
            df_mutuo.style.format({
                "Anno": lambda v: f"{int(v)}",
                "Rata_Mensile": lambda v: f"{fmt(v, 2)} €",
                "Rata_Annua": lambda v: f"{fmt(v, 2)} €",
                "Quota_Capitale_Annua": lambda v: f"{fmt(v, 2)} €",
                "Quota_Interessi_Annua": lambda v: f"{fmt(v, 2)} €",
                "Capitale_Residuo": lambda v: f"{fmt(v, 2)} €",
            }),
            use_container_width=True,
        )

        st.markdown("---")
        st.subheader("Composizione Rata nel Tempo")

        fig_amort = go.Figure()
        fig_amort.add_trace(go.Bar(
            x=df_mutuo["Anno"],
            y=df_mutuo["Quota_Interessi_Annua"],
            name="Quota Interessi",
            marker_color="#EF553B",
        ))
        fig_amort.add_trace(go.Bar(
            x=df_mutuo["Anno"],
            y=df_mutuo["Quota_Capitale_Annua"],
            name="Quota Capitale",
            marker_color="#636EFA",
        ))
        fig_amort.add_trace(go.Scatter(
            x=df_mutuo["Anno"],
            y=df_mutuo["Capitale_Residuo"],
            name="Capitale Residuo",
            yaxis="y2",
            mode="lines+markers",
            line=dict(color="#00CC96", width=2, dash="dot"),
        ))
        fig_amort.update_layout(
            barmode="stack",
            template="plotly_white",
            height=420,
            yaxis=dict(title="Importo Annuo (€)"),
            yaxis2=dict(title="Capitale Residuo (€)", overlaying="y", side="right"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
        )
        st.plotly_chart(fig_amort, use_container_width=True, key="fig_amort")

        tot_interessi = df_mutuo["Quota_Interessi_Annua"].sum()
        tot_capitale = df_mutuo["Quota_Capitale_Annua"].sum()
        pct_int = tot_interessi / (tot_interessi + tot_capitale) * 100
        st.info(f"Totale interessi pagati: **{fmt(tot_interessi)} €** ({fmt(pct_int, 1)}% del totale) "
                f"| Totale restituito: **{fmt(tot_interessi + tot_capitale)} €** su **{fmt(mutuo_val)} €**")

        # Callout informativo TAN vs TAEG (costo reale del finanziamento)
        if taeg_val > 0 and taeg_val / 100 > params.tasso_effettivo:
            r_tan = rata_mensile(mutuo_val, params.tasso_effettivo, params.anni_mutuo)
            r_taeg = rata_mensile(mutuo_val, taeg_val / 100, params.anni_mutuo)
            costo_extra = calcola_costo_extra_taeg(mutuo_val, params.tasso_effettivo,
                                                   taeg_val / 100, params.anni_mutuo)
            spese_cnt = costo_perizia + costo_assicurazione
            altri = max(costo_extra - spese_cnt, 0)
            st.info(
                f"**Costo reale del finanziamento (TAN vs TAEG)**\n\n"
                f"TAN {params.tasso_interesse * 100:.2f}% · TAEG {taeg_val:.2f}% — rata "
                f"**{fmt(r_tan, 2)} €/mese** vs **{fmt(r_taeg, 2)} €/mese** equivalenti "
                f"→ costo extra stimato su {params.anni_mutuo} anni: **≈ {fmt(costo_extra)} €**.\n\n"
                f"Di questi, **{fmt(spese_cnt)} €** (perizia + assicurazione) sono già inclusi "
                f"nell'investimento totale; i restanti **≈ {fmt(altri)} €** coprono le altre spese "
                f"del mutuo (istruttoria, imposta sostitutiva, incasso rata…).\n\n"
                f"Stima approssimata: il TAEG non è un tasso applicato alla rata, ma la misura "
                f"standardizzata del costo complessivo del finanziamento."
            )
    else:
        st.info("Nessun mutuo — nessun piano di ammortamento da mostrare.")


# ─── TAB 4: Benchmark ETF ─────────────────────────────────────────────────
with tab_bench:
    st.subheader("Confronto: Immobile vs ETF")

    # ── SEZIONE 1: Confronto con Leva (equity) ──────────────────────────────
    st.markdown(f"#### Confronto con Leva ({fmt(equity_val)} € investiti)")

    fig_leva = go.Figure()

    fig_leva.add_trace(go.Scatter(
        x=df_proj["Anno"],
        y=df_proj["Guadagno_Netto_Immobile"],
        name=f"Immobile con Mutuo ({fmt(equity_val)} € equity)",
        mode="lines+markers",
        line=dict(color="#636EFA", width=3),
    ))

    fig_leva.add_trace(go.Scatter(
        x=list(range(1, anni_sim + 1)),
        y=etf_puro.tolist(),
        name=f"ETF Azionario ({fmt(equity_val)} €)",
        mode="lines",
        line=dict(color="#00CC96", width=2, dash="dash"),
    ))

    fig_leva.add_hline(y=0, line_dash="dot", line_color="gray", opacity=0.5)
    fig_leva.update_layout(
        template="plotly_white",
        height=400,
        xaxis_title="Anni",
        yaxis_title="Guadagno Netto (€)",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    fig_leva.update_yaxes(hoverformat=",.2f")
    st.plotly_chart(fig_leva, use_container_width=True, key="fig_leva")

    diff_leva = df_proj["Guadagno_Netto_Immobile"].values - etf_puro
    idx_max_leva = int(np.argmax(diff_leva))
    max_gap_leva = diff_leva[idx_max_leva]
    anno_max_leva = int(df_proj["Anno"].iloc[idx_max_leva])

    col1, col2 = st.columns(2)
    with col1:
        if max_gap_leva > 0:
            st.metric(
                label="Anno in cui la differenza immobile - ETF è massima",
                value=f"Anno {anno_max_leva}",
            )
        else:
            st.metric(
                label="Confronto Immobile vs ETF",
                value="ETF batte sempre l'immobile",
            )
    with col2:
        if max_gap_leva > 0:
            st.metric(label="Differenza max immobile - ETF", value=f"{fmt(max_gap_leva)} €")
        else:
            st.metric(label="Anni simulati", value=f"{anni_sim}")

    colori_leva = ["#00CC96" if d > 0 else "#EF553B" for d in diff_leva]
    fig_delta_leva = go.Figure()
    fig_delta_leva.add_trace(go.Bar(
        x=df_proj["Anno"], y=diff_leva,
        name="Delta (Immobile - ETF)", marker_color=colori_leva,
    ))
    fig_delta_leva.add_hline(y=0, line_dash="dot", line_color="gray", opacity=0.5)
    fig_delta_leva.update_layout(
        template="plotly_white", height=280,
        xaxis_title="Anno", yaxis_title="Differenza (€)", showlegend=False,
    )
    fig_delta_leva.update_yaxes(hoverformat=",.2f")
    st.plotly_chart(fig_delta_leva, use_container_width=True, key="fig_delta_leva")

    cross = crossover_leva_etf(df_proj, etf_puro)
    if cross["esito"] == "sorpasso":
        ultimo = cross["ultimo_anno_vantaggio"]
        st.info(
            f"**La leva batte l'ETF per orizzonti di vendita fino all'anno {ultimo}** "
            f"(sorpasso stimato ≈ anno {cross['anno_sorpasso']:.1f}). Se pensi di vendere "
            f"oltre l'anno {ultimo + 1}, l'ETF azionario sarebbe stato la scelta migliore: "
            f"oltre quel limite la leva perde il confronto."
        )
    elif cross["esito"] == "leva_vince_sempre":
        st.success(f"**La leva batte l'ETF su tutto l'orizzonte simulato ({anni_sim} anni):** "
                   f"il mutuo resta la scelta più conveniente fino all'ultimo anno considerato.")
    elif cross["esito"] == "etf_vince_sempre":
        st.warning("**L'ETF batte la leva fin dal primo anno:** con queste ipotesi il mutuo "
                   "non genera alcun vantaggio rispetto all'alternativa azionaria.")

    with st.expander("Come leggere questi grafici?", expanded=False):
        st.markdown("""
I grafici confrontano **Immobile vs ETF** rispondendo a **due domande diverse**:

---

**Sezione 1 — "Con Leva"**: *Ho X €, conviene metterli in un immobile con mutuo o in un ETF?*

In questo grafico confronti il rendimento della tua **equity** (il capitale che metti di tasca tua) nell'immobile con leva, rispetto allo stesso importo investito in un ETF. La linea blu INCLUDE la leva finanziaria: usi poco capitale tuo ma controlli un asset più grande.

- **Blu sopra il verde** → la leva ti sta aiutando, l'immobile rende di più dell'ETF sullo stesso capitale
- **Verde sopra il blu** → l'ETF rende di più, le rate del mutuo mangiano i profitti

---

**Sezione 2 — "Cash"**: *Ho X € tutti insieme, conviene comprare cash l'immobile o investire in ETF?*

Qui non c'è mutuo: confronti il rendimento dell'immobile pagato interamente con quello di un ETF sullo stesso importo. È il confronto "pulito" — niente leva, niente rate.

- **Rosso sopra il verde** → l'immobile cash rende di più dell'ETF
- **Verde sopra il rosso** → l'ETF rende di più, è più semplice e liquido

---

**I grafici a barre** mostrano la **differenza anno per anno**: verdi quando l'immobile batte l'ETF, rosse quando vince l'ETF. Guarda come cambia nel tempo — all'inizio il mutuo pesa, poi la leva inverte la situazione.

---

**"Miglior anno per vendere" vs sorpasso** — Il "Miglior anno per vendere" (tab KPI) massimizza il rendimento annualizzato (CAGR), spesso l'anno 5. Il **sorpasso** qui indica invece il limite oltre il quale l'ETF avrebbe reso di più dell'immobile a leva. Sono due prospettive diverse: rendimento per anno vs vantaggio assoluto rispetto all'ETF.

**Attenzione alle ipotesi** — Il punto di sorpasso dipende dal modello: i cash flow dell'immobile si accumulano **senza reinvestimento**, mentre l'ETF compone ogni anno al tasso impostato. Con rivalutazione immobiliare o reinvestimento dei flussi, il sorpasso si sposta più in là.
        """)

    st.markdown("---")

    # ── SEZIONE 2: Confronto Cash (totale investimento) ─────────────────────
    st.markdown(f"#### Confronto Cash ({fmt(totale_inv)} € investiti)")

    fig_cash = go.Figure()

    fig_cash.add_trace(go.Scatter(
        x=df_cash["Anno"],
        y=df_cash["Guadagno_Netto_Immobile"],
        name=f"Immobile Cash ({fmt(totale_inv)} €)",
        mode="lines+markers",
        line=dict(color="#EF553B", width=3),
    ))

    fig_cash.add_trace(go.Scatter(
        x=list(range(1, anni_sim + 1)),
        y=etf_cash.tolist(),
        name=f"ETF Azionario ({fmt(totale_inv)} €)",
        mode="lines",
        line=dict(color="#00CC96", width=2, dash="dash"),
    ))

    fig_cash.add_hline(y=0, line_dash="dot", line_color="gray", opacity=0.5)
    fig_cash.update_layout(
        template="plotly_white",
        height=400,
        xaxis_title="Anni",
        yaxis_title="Guadagno Netto (€)",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    fig_cash.update_yaxes(hoverformat=",.2f")
    st.plotly_chart(fig_cash, use_container_width=True, key="fig_cash")

    diff_cash = df_cash["Guadagno_Netto_Immobile"].values - etf_cash
    idx_max_cash = int(np.argmax(diff_cash))
    max_gap_cash = diff_cash[idx_max_cash]
    anno_max_cash = int(df_cash["Anno"].iloc[idx_max_cash])

    col3, col4 = st.columns(2)
    with col3:
        if max_gap_cash > 0:
            st.metric(
                label="Anno in cui la differenza immobile - ETF è massima",
                value=f"Anno {anno_max_cash}",
            )
        else:
            st.metric(
                label="Confronto Immobile vs ETF",
                value="ETF batte sempre l'immobile",
            )
    with col4:
        if max_gap_cash > 0:
            st.metric(label="Differenza max immobile - ETF", value=f"{fmt(max_gap_cash)} €")
        else:
            st.metric(label="Anni simulati", value=f"{anni_sim}")

    colori_cash = ["#00CC96" if d > 0 else "#EF553B" for d in diff_cash]
    fig_delta_cash = go.Figure()
    fig_delta_cash.add_trace(go.Bar(
        x=df_cash["Anno"], y=diff_cash,
        name="Delta (Immobile - ETF)", marker_color=colori_cash,
    ))
    fig_delta_cash.add_hline(y=0, line_dash="dot", line_color="gray", opacity=0.5)
    fig_delta_cash.update_layout(
        template="plotly_white", height=280,
        xaxis_title="Anno", yaxis_title="Differenza (€)", showlegend=False,
    )
    fig_delta_cash.update_yaxes(hoverformat=",.2f")
    st.plotly_chart(fig_delta_cash, use_container_width=True, key="fig_delta_cash")

    st.markdown("---")
    st.subheader("Riepilogo a Confronto")

    anni_confronto = [a for a in [5, 10, 15, 20, 25, 30] if a <= anni_sim]
    righe_bench = []
    for yr in anni_confronto:
        imm_leva = df_proj.loc[df_proj["Anno"] == yr, "Guadagno_Netto_Immobile"]
        imm_cash = df_cash.loc[df_cash["Anno"] == yr, "Guadagno_Netto_Immobile"]
        etf_leva = equity_val * (1 + rend_etf) ** yr - equity_val
        etf_cash_v = totale_inv * (1 + rend_etf) ** yr - totale_inv
        righe_bench.append({
            "Anno": yr,
            "Immobile (Mutuo)": imm_leva.values[0] if len(imm_leva) else 0,
            f"ETF ({fmt(equity_val)} €)": etf_leva,
            "Divario Leva": (imm_leva.values[0] - etf_leva) if len(imm_leva) else 0,
            "Immobile (Cash)": imm_cash.values[0] if len(imm_cash) else 0,
            f"ETF ({fmt(totale_inv)} €)": etf_cash_v,
            "Divario Cash": (imm_cash.values[0] - etf_cash_v) if len(imm_cash) else 0,
        })
    df_bench = pd.DataFrame(righe_bench)
    df_bench.style.format({
        "Immobile (Mutuo)": lambda v: f"{fmt(v)} €",
        f"ETF ({fmt(equity_val)} €)": lambda v: f"{fmt(v)} €",
        "Divario Leva": lambda v: f"{'+' if v > 0 else ''}{fmt(v)} €",
        "Immobile (Cash)": lambda v: f"{fmt(v)} €",
        f"ETF ({fmt(totale_inv)} €)": lambda v: f"{fmt(v)} €",
        "Divario Cash": lambda v: f"{'+' if v > 0 else ''}{fmt(v)} €",
    })
    def color_divario(val):
        color = "#00CC96" if val > 0 else "#EF553B" if val < 0 else ""
        return f"color: {color}; font-weight: bold" if color else ""
    styled = df_bench.style.format({
        "Immobile (Mutuo)": lambda v: f"{fmt(v)} €",
        f"ETF ({fmt(equity_val)} €)": lambda v: f"{fmt(v)} €",
        "Divario Leva": lambda v: f"{'+' if v > 0 else ''}{fmt(v)} €",
        "Immobile (Cash)": lambda v: f"{fmt(v)} €",
        f"ETF ({fmt(totale_inv)} €)": lambda v: f"{fmt(v)} €",
        "Divario Cash": lambda v: f"{'+' if v > 0 else ''}{fmt(v)} €",
    }).map(color_divario, subset=["Divario Leva", "Divario Cash"])
    st.dataframe(styled, use_container_width=True, hide_index=True)

    with st.expander("Come leggere la tabella?", expanded=False):
        st.markdown("""
La tabella mostra il **guadagno netto cumulato** a diversi orizzonti temporali (5, 10, 15, 20, 25, 30 anni).

Le colonne sono **a coppie** per confronto diretto:

| Colonna | Cosa mostra |
|---|---|
| **Immobile (Mutuo)** | Guadagno netto usando il mutuo — include la leva finanziaria |
| **ETF (stessa equity)** | Quanto avresti guadagnato investendo la stessa equity in un ETF |
| **Immobile (Cash)** | Guadagno netto comprando senza mutuo — confronto pulito |
| **ETF (stesso totale)** | Quanto avresti guadagnato investendo l'intero importo in un ETF |

**Guadagno netto** = (Valore immobile - Debito residuo) + Cash Flow cumulato - Equity iniziale. Per l'ETF è semplicemente il rendimento composto meno il capitale iniziale.

**Come usarla**: confronta le colonne affiancate. Se l'immobile è sopra l'ETF nella stessa coppia, conviene l'immobile per quel capitale e quell'orizzonte temporale.
        """)


# ─── TAB 5: Dettaglio Completo ────────────────────────────────────────────
with tab_dettaglio:
    st.subheader("Dettaglio Completo Simulazione")

    st.markdown("#### Voci di Costo")
    voci = pd.DataFrame({
        "Voce": [
            "Prezzo Immobile", "Imposte Acquisto", "Spese Notaio",
            "Agenzia Acquisto", "Lavori / Impianti", "Compenso Tecnico", "Oneri Urbanistici",
            "Arredamento", "Spese Perizia Mutuo", "Assicurazione Incendio",
        ],
        "Importo (€)": [fmt(v) for v in [prezzo, imposte, notaio, agenzia_acq, lavori, compenso_tecnico, oneri_urbanistici, arredo, costo_perizia, costo_assicurazione]],
    })
    st.dataframe(voci, use_container_width=True, hide_index=True)
    st.markdown(f"**TOTALE INVESTIMENTO: {fmt(totale_inv)} €**")

    # --- Dettaglio Lavori ---
    lavori_con_qty = [item for item in WORK_ITEMS if work_qty.get(item["id"], 0) > 0]
    if lavori_con_qty:
        st.markdown("#### Dettaglio Lavori Realizzati")
        righe_lavori = []
        for item in lavori_con_qty:
            qty = work_qty[item["id"]]
            tot = item["prezzo"] * qty
            righe_lavori.append({
                "Categoria": item["categoria"],
                "Voce": item["voce"],
                "UM": item["um"],
                "Prezzo Unit. (€)": item["prezzo"],
                "IVA": f"{item['iva_pct']*100:.0f}%",
                "Qtà": qty,
                "Totale (€)": tot,
            })
        df_lavori_det = pd.DataFrame(righe_lavori)
        fmt_lavori = {
            "Prezzo Unit. (€)": lambda v: f"{fmt(v, 2)}",
            "Totale (€)": lambda v: f"{fmt(v, 2)}",
        }
        st.dataframe(df_lavori_det.style.format(fmt_lavori), use_container_width=True, hide_index=True)
        st.markdown(f"**Totale Lavori: {fmt(lavori)} €** | IVA 10%: {fmt(iva_lavori['iva_10'])} € | IVA 22%: {fmt(iva_lavori['iva_22'])} €")

    if flag_detrazioni:
        st.info(
            f"**Detrazione annua: {fmt(detrazione_annua_val)} €** per 10 anni ({aliquota_detr*100:.0f}%) → Totale: **{fmt(detrazione_annua_val * 10)} €**\n\n"
            f"Base di calcolo:\n"
            f"- Lavori (IVA incl.): {fmt(lavori)} €\n"
            f"- Compenso Tecnico: {fmt(compenso_tecnico)} €\n"
            f"- Oneri Urbanistici: {fmt(oneri_urbanistici)} €\n"
            f"- **Totale base: {fmt(base_detr)} €**"
        )

    # --- Dettaglio Arredamento ---
    mobilio_con_qty = [item for item in FURN_ITEMS if furn_qty.get(item["id"], 0) > 0]
    if mobilio_con_qty:
        st.markdown("#### Dettaglio Arredamento / Mobilio")
        righe_mobilio = []
        for item in mobilio_con_qty:
            qty = furn_qty[item["id"]]
            tot = item["prezzo"] * qty
            righe_mobilio.append({
                "Categoria": item["categoria"],
                "Voce": item["voce"],
                "UM": item["um"],
                "Prezzo Unit. (€)": item["prezzo"],
                "IVA": "22% incl.",
                "Qtà": qty,
                "Totale (€)": tot,
            })
        df_mobilio_det = pd.DataFrame(righe_mobilio)
        fmt_mobilio = {
            "Prezzo Unit. (€)": lambda v: f"{fmt(v, 2)}",
            "Totale (€)": lambda v: f"{fmt(v, 2)}",
        }
        st.dataframe(df_mobilio_det.style.format(fmt_mobilio), use_container_width=True, hide_index=True)
        st.markdown(f"**Totale Arredo: {fmt(arredo)} €** (IVA 22% già inclusa nei prezzi)")

    # --- Dettaglio Imposte (se calcolo automatico) ---
    if imposte_mode == "Automatico" and "errore" not in det_imposte:
        st.markdown("#### Dettaglio Imposte di Acquisto")
        st.json({k: fmt(v) if isinstance(v, (int, float)) else v for k, v in det_imposte.items()})

    st.markdown("#### Costi Operativi Annui")
    op = pd.DataFrame({
        "Voce": ["Affitto Lordo", "Cedolare Secca", "IMU", "Condominio", "Altri Costi"],
        "Importo (€)": [fmt(v) for v in [affitto_lordo, cedolare, imu, condominio, altro_costi]],
    })
    st.dataframe(op, use_container_width=True, hide_index=True)

    if not df_proj.empty:
        st.markdown("#### Entrate Stimate — Annuale")
        colonne_annuali = [
            "Anno", "Affitto_Effettivo", "Detrazione", "CF_Netto_Anno",
        ]
        fmt_annuali = {
            "Affitto_Effettivo": lambda v: f"{fmt(v)} €",
            "Detrazione": lambda v: f"{fmt(v)} €",
            "CF_Netto_Anno": lambda v: f"{fmt(v)} €",
        }
        df_annuali = df_proj[colonne_annuali].copy()
        st.dataframe(df_annuali.style.format(fmt_annuali), use_container_width=True)

        st.markdown("#### Entrate Stimate — Una Tantum (Vendita)")
        colonne_vendita = ["Anno", "Valore_Immobile", "Capitale_Residuo_Mutuo", "Guadagno_Netto_Immobile"]
        df_vendita = df_proj[df_proj["Anno"] >= 5][colonne_vendita].copy()
        df_vendita = df_vendita.rename(columns={"Guadagno_Netto_Immobile": "Guadagno Totale se Vendi"})
        fmt_vendita = {
            "Valore_Immobile": lambda v: f"{fmt(v)} €",
            "Capitale_Residuo_Mutuo": lambda v: f"{fmt(v)} €",
            "Guadagno Totale se Vendi": lambda v: f"{fmt(v)} €",
        }
        st.dataframe(df_vendita.style.format(fmt_vendita), use_container_width=True)

        with st.expander("Come leggere queste tabelle?", expanded=False):
            st.markdown("""
**Annuale** — Flussi ricorrenti anno per anno. L'affitto effettivo è già al netto di sfitto. I costi fissi includono cedolare, IMU, condominio e altri. La rata mutuo è l'importo annuo pagato alla banca. Il CF Netto è il risultato: positivo = l'immobile ti paga, negativo = ci devi mettere di tasca tua.

**Una Tantum (Vendita)** — Cosa succede se vendi quell'anno. Il Guadagno Totale include tutto: la differenza tra valore immobile e debito residuo, più tutti i cash flow accumulati, meno l'equity iniziale che hai investito.
            """)

    st.markdown("---")
    st.subheader("📥 Esporta Dati")

    if not df_proj.empty:
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            # ── Foglio Riepilogo ──
            riepilogo = pd.DataFrame({
                "Parametro": [
                    "Investimento Totale", "Equity (Capitale Proprio)", "Importo Mutuo",
                    "Tasso Mutuo Annuo", "Durata Mutuo", "Rata Mensile",
                    "Affitto Lordo Annuo", "Costi Fissi Annui", "Detrazione Annuale",
                    "Tasso Sfitto", "CapEx Reserve", "Rivalutazione Annuale",
                    "Prezzo Vendita Stimato", "Rendimento ETF", "Inflazione Annuale",
                    "Miglior Anno per Vendere", "Rendimento Annuale Migliore",
                ],
                "Valore": [
                    f"{fmt(totale_inv)} €", f"{fmt(equity_val)} €",
                    f"{fmt(mutuo_val)} €" if usa_mutuo else "Nessuno",
                    f"{fmt(tasso * 100, 2)}%" if usa_mutuo else "—",
                    f"{anni_mut} anni" if usa_mutuo else "—",
                    f"{fmt(rata_m, 2)} €" if usa_mutuo else "—",
                    f"{fmt(affitto_lordo)} €",
                    f"{fmt(params.costi_fissi_annui)} €",
                    f"{fmt(detrazione_annua_val)} €" if flag_detrazioni else "Non applicata",
                    f"{sfitto}%", f"{capex_pct}%",
                    f"{fmt(rivalutazione * 100, 2)}%" if prezzo_vendita_val == 0 else "—",
                    f"{fmt(prezzo_vendita_val)} €" if prezzo_vendita_val > 0 else "—",
                    f"{fmt(rend_etf * 100, 1)}%",
                    f"{fmt(inflazione)}%",
                    f"Anno {best_year}" if best_year > 0 else "N/D",
                    f"{fmt(best_annual * 100, 2)}%" if best_year > 0 else "N/D",
                ],
            })
            riepilogo.to_excel(writer, sheet_name="Riepilogo", index=False)

            # ── Foglio Rendimenti ──
            rendimenti = pd.DataFrame({
                "Anno": anni_kpi,
                "Rendimento Annuale Netto (%)": [
                    f"{fmt(r * 100, 2)}%" for r in df_rend["Rendimento Annuale Netto"]
                ],
                "Guadagno Totale Netto (€)": [
                    f"{fmt(v)} €" for v in df_rend["Guadagno Totale Netto"]
                ],
            })
            rendimenti.to_excel(writer, sheet_name="Rendimenti", index=False)

            # ── Foglio Ammortamento ──
            if not df_mutuo.empty:
                df_mutuo.to_excel(writer, sheet_name="Ammortamento", index=False)

            # ── Foglio Proiezioni ──
            df_proj.to_excel(writer, sheet_name="Proiezioni", index=False)

        # ── Formattazione Excel ──
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter

        wb = writer.book
        header_font = Font(bold=True, color="FFFFFF", size=11)
        header_fill = PatternFill(start_color="2F5496", end_color="2F5496", fill_type="solid")
        header_align = Alignment(horizontal="center", vertical="center")
        thin_border = Border(
            left=Side(style="thin", color="D0D0D0"),
            right=Side(style="thin", color="D0D0D0"),
            top=Side(style="thin", color="D0D0D0"),
            bottom=Side(style="thin", color="D0D0D0"),
        )
        zebra_light = PatternFill(start_color="F2F7FB", end_color="F2F7FB", fill_type="solid")

        for ws in wb.worksheets:
            for col_idx, cell in enumerate(ws[1], 1):
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = header_align
                cell.border = thin_border

            for row_idx, row in enumerate(ws.iter_rows(min_row=2, max_row=ws.max_row, max_col=ws.max_column), 2):
                for cell in row:
                    cell.border = thin_border
                    cell.alignment = Alignment(horizontal="center")
                    if row_idx % 2 == 0:
                        cell.fill = zebra_light

            for col_idx in range(1, ws.max_column + 1):
                max_len = max(
                    len(str(ws.cell(row=r, column=col_idx).value or ""))
                    for r in range(1, ws.max_row + 1)
                )
                ws.column_dimensions[get_column_letter(col_idx)].width = min(max_len + 4, 30)

            ws.sheet_properties.tabColor = "2F5496"

        st.download_button(
            "Scarica Report Completo (XLSX)",
            data=buffer.getvalue(),
            file_name="report_investimento.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

        try:
            pdf_bytes = generate_pdf(
                params=params, totale_inv=totale_inv, equity_val=equity_val,
                mutuo_val=mutuo_val, irr_val=irr_val,
                best_year=best_year, best_annual=best_annual,
                df_proj=df_proj, df_mutuo=df_mutuo, etf_puro=etf_puro,
                anni_sim=anni_sim,
                rend_etf=rend_etf, inflazione=inflazione,
                rivalutazione=rivalutazione, prezzo_vendita_val=prezzo_vendita_val,
                sfitto=sfitto, capex_pct=capex_pct,
                flag_detrazioni=flag_detrazioni, detrazione_annua_val=detrazione_annua_val,
                aliquota_detr=aliquota_detr, base_detr=base_detr,
                work_items=WORK_ITEMS, work_qty=work_qty,
                furn_items=FURN_ITEMS, furn_qty=furn_qty,
                df_cash=df_cash, etf_cash=etf_cash,
            )
            st.download_button(
                "Scarica Report PDF",
                data=pdf_bytes,
                file_name="report_investimento.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        except Exception as e:
            import traceback
            st.warning(f"Impossibile generare il PDF: {e}")
            st.error(traceback.format_exc())






# ─── Footer ────────────────────────────────────────────────────────────────
st.markdown("---")
st.caption("Built with Streamlit • Pandas • NumPy • Plotly — Dati precompilati dal report immobiliare Via Michelangelo Osimo")
