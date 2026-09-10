import numpy as np
import pandas as pd
import streamlit as st

from engine import (
    InvestmentParams,
    piano_ammortamento,
    proiezione,
    calcola_irr,
    calcola_npv,
    flussi_per_irr,
    scenario_cash,
    calcola_rendimenti_per_anno,
)
from ui_sidebar import render_sidebar
from ui_tabs import render_tab_kpi, render_tab_mutuo, render_tab_benchmark, render_tab_dettaglio


# ─── Page Config ───────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Iron Tool",
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

st.title("🏢 Iron Tool")
st.caption("Simulazione avanzata rendimenti immobiliari, leva finanziaria, cash flow e confronto ETF")

# ═════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═════════════════════════════════════════════════════════════════════════════

sb = render_sidebar()

params = InvestmentParams(
    prezzo=sb.prezzo, imposte=sb.imposte, notaio=sb.notaio,
    agenzia_acquisto=sb.agenzia_acq, lavori=sb.lavori,
    compenso_tecnico=sb.compenso_tecnico, oneri_urbanistici=sb.oneri_urbanistici, arredo=sb.arredo,
    usa_mutuo=sb.usa_mutuo, equity=sb.equity_val, importo_mutuo=sb.mutuo_val,
    tasso_interesse=sb.tasso, anni_mutuo=sb.anni_mut,
    affitto_lordo_annuo=sb.affitto_lordo,
    cedolare=sb.cedolare, imu=sb.imu, condominio=sb.condominio,
    altro_costi=sb.altro_costi,
    flag_detrazioni=sb.flag_detrazioni, detrazione_annua=sb.detrazione_annua_val,
    anni_detrazione=sb.anni_detraz, sfitto_pct=sb.sfitto,
    capex_pct=sb.capex_pct, rivalutazione_annua=sb.rivalutazione,
    rendimento_etf=sb.rend_etf, anni_simulazione=sb.anni_sim,
    inflazione_annua=sb.inflazione / 100, agenzia_vendita_pct=sb.agenzia_vendita_val,
    agenzia_vendita_fissa=sb.agenzia_vendita_fissa,
    prezzo_vendita=sb.prezzo_vendita_val,
    eta_richiedente=sb.eta_rich, costo_assicurazione=sb.costo_assicurazione,
    costo_perizia=sb.costo_perizia, classe_ape=sb.classe_ape, taeg=sb.taeg_val / 100,
    reddito_mensile=sb.reddito_mensile,
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

df_proj = _cached_proiezione(params.__dict__)
df_cash = _cached_scenario_cash(params.__dict__)
etf_puro = params.equity * (1 + params.rendimento_etf) ** np.arange(1, params.anni_simulazione + 1) - params.equity
etf_cash = sb.totale_inv * (1 + params.rendimento_etf) ** np.arange(1, params.anni_simulazione + 1) - sb.totale_inv

if not df_proj.empty:
    flussi = flussi_per_irr(df_proj, params.equity)
    irr_val = calcola_irr(flussi)
    npv_val = calcola_npv(flussi, params.rendimento_etf)
else:
    irr_val = None
    npv_val = 0.0

df_rend, best_year, best_annual = calcola_rendimenti_per_anno(df_proj, sb.equity_val, sb.anni_sim)

# ═════════════════════════════════════════════════════════════════════════════
# TABS
# ═════════════════════════════════════════════════════════════════════════════

tab_kpi, tab_mutuo, tab_bench, tab_dettaglio = st.tabs([
    "📊 KPI & Sintesi",
    "🏦 Piano Ammortamento",
    "🥊 Benchmark ETF",
    "📋 Dettaglio Completo",
])

with tab_kpi:
    render_tab_kpi(sb, df_proj, df_rend, best_year, best_annual)

with tab_mutuo:
    render_tab_mutuo(sb, params, df_mutuo)

with tab_bench:
    render_tab_benchmark(sb, df_proj, df_cash, etf_puro, etf_cash)

with tab_dettaglio:
    render_tab_dettaglio(sb, params, df_proj, df_mutuo, df_cash, etf_puro, etf_cash,
                          df_rend, best_year, best_annual, irr_val)

# ─── Footer ────────────────────────────────────────────────────────────────
st.markdown("---")
st.caption("Built with Streamlit • Pandas • NumPy • Plotly")
