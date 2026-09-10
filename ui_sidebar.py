import hashlib
import json
from types import SimpleNamespace

import streamlit as st

from engine import (
    WORK_ITEMS,
    FURN_ITEMS,
    calcola_totale_lavori,
    calcola_totale_mobilio,
    calcola_iva_lavori,
    calcola_imposte_acquisto,
    rata_mensile,
    calcola_ltv_massimo,
    verifica_limite_eta,
    verifica_rata_reddito,
)
from utils import fmt


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


_CONVERSIONS = {
    "tasso_interesse": lambda v: v * 100,
    "rivalutazione_annua": lambda v: v * 100,
    "rendimento_etf": lambda v: v * 100,
    "inflazione_annua": lambda v: v * 100,
    "taeg": lambda v: v * 100,
}


def _init_scenario_state() -> None:
    """Inizializza session_state e applica uno scenario in attesa di caricamento.
    Deve girare PRIMA che i widget della sidebar vengano creati.
    """
    if "scenarios" not in st.session_state:
        st.session_state["scenarios"] = _load_scenarios_from_disk()
    if "load_scenario" not in st.session_state:
        st.session_state["load_scenario"] = None
    if "pending_delete" not in st.session_state:
        st.session_state["pending_delete"] = None

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


def render_sidebar() -> SimpleNamespace:
    """Disegna tutti i widget della sidebar e restituisce gli input raccolti."""

    _init_scenario_state()

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
        det_imposte = {}
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
        eta_rich = 0
        classe_ape = "altro"
        taeg_val = 0.0
        reddito_mensile = 0

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
                                                  help="0 = usa il valore di mercato (rivalutazione). Se > 0, è il prezzo di oggi: se la rivalutazione annua è attiva, verrà comunque rivalutato anno per anno fino alla vendita (non resta bloccato al valore inserito).")
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
        st.caption("Carica un JSON esportato: i dati vengono applicati subito ai parametri.")
        uploaded = st.file_uploader("Carica un file .json", type=["json"], key="import_scenario")
        if uploaded is not None:
            raw_bytes = uploaded.getvalue()
            fp = hashlib.md5(raw_bytes).hexdigest()
            if st.session_state.get("_last_import_fp") != fp:
                st.session_state["_last_import_fp"] = fp
                try:
                    raw = json.loads(raw_bytes.decode("utf-8"))
                    imported_name = raw.get("name", uploaded.name.replace(".json", ""))
                    imported_params = raw.get("params", raw)
                    st.session_state["scenarios"][imported_name] = imported_params
                    st.session_state["load_scenario"] = imported_name
                    st.success(f"Scenario '{imported_name}' importato e caricato nei parametri!")
                    st.rerun()
                except (json.JSONDecodeError, KeyError, UnicodeDecodeError):
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

    return SimpleNamespace(
        prezzo=prezzo, imposte=imposte, imposte_mode=imposte_mode, det_imposte=det_imposte,
        notaio=notaio, agenzia_acq=agenzia_acq, costo_perizia=costo_perizia,
        costo_assicurazione=costo_assicurazione, work_qty=work_qty, lavori=lavori,
        iva_lavori=iva_lavori, compenso_tecnico=compenso_tecnico, oneri_urbanistici=oneri_urbanistici,
        furn_qty=furn_qty, arredo=arredo, totale_inv=totale_inv,
        usa_mutuo=usa_mutuo, equity_val=equity_val, mutuo_val=mutuo_val, tasso=tasso,
        anni_mut=anni_mut, eta_rich=eta_rich, classe_ape=classe_ape, taeg_val=taeg_val,
        reddito_mensile=reddito_mensile, rata_m=rata_m,
        affitto_lordo=affitto_lordo, cedolare=cedolare, imu=imu, condominio=condominio,
        altro_costi=altro_costi, flag_detrazioni=flag_detrazioni, aliquota_detr=aliquota_detr,
        anni_detraz=anni_detraz, base_detr=base_detr, detrazione_annua_val=detrazione_annua_val,
        sfitto=sfitto, capex_pct=capex_pct, prezzo_vendita_val=prezzo_vendita_val,
        agenzia_vendita_val=agenzia_vendita_val, agenzia_vendita_fissa=agenzia_vendita_fissa,
        inflazione=inflazione, rivalutazione=rivalutazione, rend_etf=rend_etf, anni_sim=anni_sim,
    )
