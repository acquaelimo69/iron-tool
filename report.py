"""PDF report generation for Real Estate Investment Analyzer (WeasyPrint).

Layout e identità grafica basati sul mockup v2 (palette navy/gold/cream,
font Inter + IBM Plex Mono). WeasyPrint 66+ supporta CSS Grid, Flexbox,
custom properties (var()) e @font-face con file TTF locali.
"""
import base64
import io
import os

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from engine import crossover_leva_etf, rata_mensile

# ---------------------------------------------------------------------------
# Brand palette
# ---------------------------------------------------------------------------

BRAND = {
    "navy_950": "#0B1220",
    "navy_900": "#0F172A",
    "navy_800": "#1E293B",
    "navy_700": "#334155",
    "gold": "#C59B27",
    "gold_dark": "#8A6A15",
    "gold_soft": "#F5EBD0",
    "cream": "#F7F5F0",
    "line": "#E7E4DC",
    "ink": "#1F2A37",
    "muted": "#8A93A0",
    "green": "#1B7A4D",
    "green_soft": "#EAF6EE",
    "red": "#B4342E",
    "red_soft": "#FBEBEA",
    "orange": "#B5651D",
    "orange_soft": "#FBEEE0",
    "blue": "#2A4B8D",
    "blue_soft": "#EAF0FB",
}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def _fmt(val, decimali=0):
    if decimali == 0:
        s = f"{round(val):,}"
    else:
        s = f"{val:,.{decimali}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def _pct(val, decimali=2):
    if val is None:
        return "N/D"
    return f"{_fmt(val * 100, decimali)} %"


def _fig_to_base64(fig: go.Figure, width=860, height=320, scale=2) -> str:
    img_bytes = fig.to_image(format="png", width=width, height=height, scale=scale)
    b64 = base64.b64encode(img_bytes).decode("utf-8")
    return f"data:image/png;base64,{b64}"


def _get_row(df: pd.DataFrame, anno: int):
    if df is None or df.empty:
        return None
    match = df[df["Anno"] == anno]
    return match.iloc[0] if not match.empty else None


# ---------------------------------------------------------------------------
# Chart builders (brand palette, trasparente per la card bianca)
# ---------------------------------------------------------------------------


def _apply_brand_layout(fig: go.Figure, height: int, ytitle="Euro", y2=None):
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=height, width=860,
        font=dict(family="Inter, Helvetica, Arial, sans-serif", size=11, color=BRAND["navy_700"]),
        xaxis=dict(title="Anni", gridcolor="#EFEBE2"),
        yaxis=dict(title=ytitle, gridcolor="#EFEBE2", tickformat=",.0f"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, font=dict(size=10)),
        margin=dict(l=20, r=30, t=30, b=40),
        hovermode="x unified",
    )
    if y2:
        fig.update_layout(
            yaxis2=dict(title=y2, overlaying="y", side="right", tickformat=",.0f",
                        gridcolor="rgba(0,0,0,0)")
        )
    fig.update_traces(hovertemplate="%{y:,.0f} €")


def _build_projection_chart(df_proj) -> str:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_proj["Anno"], y=df_proj["Guadagno_Netto_Immobile"],
        name="Guadagno Netto", mode="lines+markers",
        line=dict(color=BRAND["navy_900"], width=3), marker=dict(size=6),
    ))
    fig.add_trace(go.Scatter(
        x=df_proj["Anno"], y=df_proj["CF_Cumulato"],
        name="CF Cumulato", mode="lines",
        line=dict(color=BRAND["gold"], width=2, dash="dash"),
    ))
    fig.add_hline(y=0, line_dash="dot", line_color=BRAND["muted"], opacity=0.4)
    _apply_brand_layout(fig, 300, "Guadagno Netto (€)")
    return _fig_to_base64(fig, height=300)


def _build_amort_chart(df_mutuo) -> str:
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df_mutuo["Anno"], y=df_mutuo["Quota_Capitale_Annua"],
        name="Quota Capitale", marker_color=BRAND["navy_900"],
    ))
    fig.add_trace(go.Bar(
        x=df_mutuo["Anno"], y=df_mutuo["Quota_Interessi_Annua"],
        name="Quota Interessi", marker_color=BRAND["gold"],
    ))
    fig.add_trace(go.Scatter(
        x=df_mutuo["Anno"], y=df_mutuo["Capitale_Residuo"],
        name="Capitale Residuo", yaxis="y2",
        mode="lines+markers", line=dict(color=BRAND["green"], width=2, dash="dot"),
        marker=dict(size=5),
    ))
    fig.update_layout(barmode="stack")
    _apply_brand_layout(fig, 300, "Importo Annuo (€)", y2="Capitale Residuo (€)")
    return _fig_to_base64(fig, height=300)


def _build_benchmark_leva_chart(df_proj, etf_puro, equity_val) -> str:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_proj["Anno"], y=df_proj["Guadagno_Netto_Immobile"],
        name=f"Immobile con Mutuo — {_fmt(equity_val)} €",
        mode="lines+markers", line=dict(color=BRAND["navy_900"], width=3), marker=dict(size=6),
    ))
    fig.add_trace(go.Scatter(
        x=list(range(1, len(etf_puro) + 1)), y=etf_puro.tolist(),
        name=f"ETF Azionario — {_fmt(equity_val)} €",
        mode="lines", line=dict(color=BRAND["gold"], width=2, dash="dash"),
    ))
    fig.add_hline(y=0, line_dash="dot", line_color=BRAND["muted"], opacity=0.4)
    _apply_brand_layout(fig, 280, "Guadagno Netto (€)")
    return _fig_to_base64(fig, height=280)


def _build_delta_chart(anni, diff, pos_color, neg_color=BRAND["red"]) -> str:
    colori = [pos_color if d >= 0 else neg_color for d in diff]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=anni, y=diff, name="Delta (Immobile − ETF)", marker_color=colori,
    ))
    fig.add_hline(y=0, line_dash="dot", line_color=BRAND["muted"], opacity=0.4)
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        height=190, width=860,
        font=dict(family="Inter, Helvetica, Arial, sans-serif", size=10, color=BRAND["navy_700"]),
        xaxis=dict(title="Anno", gridcolor="#EFEBE2"),
        yaxis=dict(title="Differenza (€)", gridcolor="#EFEBE2", tickformat=",.0f"),
        showlegend=False,
        margin=dict(l=20, r=20, t=10, b=40),
    )
    fig.update_traces(hovertemplate="%{y:,.0f} €")
    return _fig_to_base64(fig, height=190)


def _build_benchmark_cash_chart(df_cash, etf_cash, totale_inv) -> str:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_cash["Anno"], y=df_cash["Guadagno_Netto_Immobile"],
        name=f"Immobile Cash — {_fmt(totale_inv)} €",
        mode="lines+markers", line=dict(color=BRAND["green"], width=3), marker=dict(size=6),
    ))
    fig.add_trace(go.Scatter(
        x=list(range(1, len(etf_cash) + 1)), y=etf_cash.tolist(),
        name=f"ETF Azionario — {_fmt(totale_inv)} €",
        mode="lines", line=dict(color=BRAND["gold"], width=2, dash="dash"),
    ))
    fig.add_hline(y=0, line_dash="dot", line_color=BRAND["muted"], opacity=0.4)
    _apply_brand_layout(fig, 280, "Guadagno Netto (€)")
    return _fig_to_base64(fig, height=280)


def _max_delta(diff: np.ndarray):
    """Anno e valore della massima differenza immobile−ETF."""
    if diff is None or len(diff) == 0:
        return 0, 0.0
    idx = int(np.argmax(diff))
    return idx + 1, diff[idx]


def _crossover_ui(cross: dict, anni_sim: int):
    """Testo per la card 'quando la leva smette di pagare'."""
    esito = cross.get("esito")
    if esito == "sorpasso":
        ultimo = cross.get("ultimo_anno_vantaggio")
        anno = cross.get("anno_sorpasso")
        stat = f"Anno {ultimo}" if ultimo else "N/D"
        note = (f"La leva batte l'ETF per orizzonti di vendita fino all'anno {ultimo} "
                f"(sorpasso stimato ≈ anno {anno:.1f}). Se pensi di vendere oltre l'anno "
                f"{ultimo + 1}, l'ETF azionario sarebbe stato la scelta migliore: oltre "
                f"quel limite la leva perde il confronto.")
    elif esito == "leva_vince_sempre":
        stat = f"Anno {anni_sim}+"
        note = (f"La leva batte l'ETF su tutto l'orizzonte simulato ({anni_sim} anni): "
                f"il mutuo resta la scelta più conveniente fino all'ultimo anno considerato.")
    elif esito == "etf_vince_sempre":
        stat = "Mai"
        note = (f"L'ETF azionario batte la leva fin dal primo anno: con queste ipotesi "
                f"il mutuo non genera alcun vantaggio rispetto all'alternativa azionaria.")
    else:
        stat = "N/D"
        note = "Confronto non disponibile."
    return stat, note


# ---------------------------------------------------------------------------
# HTML section builders
# ---------------------------------------------------------------------------


def _build_header(params, has_mutuo) -> str:
    badge = f"Simulazione {params.anni_simulazione} anni"
    if has_mutuo:
        badge += f" · Mutuo {params.anni_mutuo} anni"
    return f"""
    <div class="header">
        <div class="brand">
            <div class="brand-mark">V</div>
            <div>
                <div class="brand-name">Valle delle Case</div>
                <div class="h-title">Analisi Investimento Immobiliare</div>
                <div class="h-sub">Report personalizzato — {('con mutuo' if has_mutuo else '100% cash')} · tasso {_pct(params.tasso_effettivo) if has_mutuo else 'n/a'}</div>
            </div>
        </div>
        <div class="badge">{badge}</div>
    </div>

    <div class="nav-pills">
        <a href="#sec1"><span>01</span>KPI &amp; Sintesi</a>
        <a href="#sec2"><span>02</span>Piano Ammortamento</a>
        <a href="#sec3"><span>03</span>Benchmark ETF</a>
        <a href="#sec4"><span>04</span>Dettaglio Completo</a>
    </div>
    """


def _build_kpi_section(params, totale_inv, equity_val, mutuo_val, best_year,
                       best_annual, df_proj, df_mutuo, has_mutuo) -> str:
    """Sezione 01 — Metriche chiave e rendimenti per orizzonte."""
    rend_pct = _pct(best_annual) if best_year > 0 else "N/D"
    mutuo_str = f"{_fmt(mutuo_val)} €" if has_mutuo else "Nessuno"

    # Tabella rendimenti per orizzonte (dal 5° anno, come in app)
    rend_rows = ""
    if not df_proj.empty:
        for yr in range(5, params.anni_simulazione + 1):
            r = _get_row(df_proj, yr)
            if r is None:
                continue
            guadagno = r["Guadagno_Netto_Immobile"]
            totale = guadagno + equity_val
            rend_annuale = (totale / equity_val) ** (1 / yr) - 1 if equity_val > 0 and totale > 0 else 0
            rend_rows += f"""
            <tr><td>{yr}</td><td class="num">{_pct(rend_annuale)}</td><td class="num pos">{_fmt(guadagno)} €</td></tr>
            """

    # Callout formula sull'anno 5 (se disponibile)
    callout = ""
    r5 = _get_row(df_proj, 5)
    if r5 is not None and equity_val > 0:
        prezzo = r5["Valore_Immobile"]
        residuo = r5["Capitale_Residuo_Mutuo"]
        cf_cum = r5["CF_Cumulato"]
        guad = r5["Guadagno_Netto_Immobile"]
        totale = guad + equity_val
        cagr = (totale / equity_val) ** 0.2 - 1 if totale > 0 else 0
        callout = f"""
        <div class="callout-blue">
            <div class="card-title">Come si calcola (es. Anno 5)</div>
            <div class="formula">
                Guadagno Totale Netto = (Prezzo Vendita − Debito Residuo) + Cash Flow Cumulato − Equity<br>
                Cash Flow Cumulato = Σ(Affitto − Costi − Rata + Detrazioni − CapEx) per 5 anni = <span class="num">{_fmt(cf_cum)} €</span><br>
                = ({_fmt(prezzo)} − {_fmt(residuo)}) + {_fmt(cf_cum)} − {_fmt(equity_val)} = <span class="num">{_fmt(guad)} €</span><br>
                Rendimento Annuale Netto (CAGR) = (({_fmt(guad)} + {_fmt(equity_val)}) / {_fmt(equity_val)}) ^ (1/5) − 1 = <span class="num">{_pct(cagr)}</span>
            </div>
        </div>
        """

    return f"""
    <div class="section-block" id="sec1">
        <div class="section-eyebrow">Sezione 01</div>
        <div class="section-title">Metriche Chiave</div>

        <div class="kpi-hero-grid">
            <div class="kpi-hero"><div class="lbl">Investimento Totale</div><div class="val num">{_fmt(totale_inv)} €</div></div>
            <div class="kpi-hero"><div class="lbl">Equity (Capitale Proprio)</div><div class="val num">{_fmt(equity_val)} €</div></div>
            <div class="kpi-hero"><div class="lbl">Importo Mutuo</div><div class="val num">{mutuo_str}</div></div>
        </div>

        <div class="subhead">Miglior Anno per Vendere</div>
        <div class="stat-pair-grid">
            <div class="stat-pair"><div class="lbl">Miglior anno per vendere</div><div class="val">{('Anno ' + str(best_year)) if best_year > 0 else 'N/D'}</div></div>
            <div class="stat-pair gold"><div class="lbl">Rendimento annuale netto</div><div class="val num">{rend_pct}</div></div>
        </div>

        <div class="subhead">Rendimenti per Orizzonte Temporale</div>
        <table class="data">
            <thead><tr><th>Anno</th><th>Rendimento Annuale Netto</th><th>Guadagno Totale Netto</th></tr></thead>
            <tbody>{rend_rows}</tbody>
        </table>

        {callout}

        <div class="info-box">
            <div class="card-title">Come leggere queste metriche</div>
            <div class="def"><b>Rendimento Annuale Netto</b> — quanto rende in media ogni anno il tuo investimento (CAGR). Include sia il cash flow che la rivalutazione dell'immobile.</div>
            <div class="def"><b>Guadagno Totale Netto</b> — il profitto reale in tasca se vendessi in quell'anno, dopo agenzia, spese e residuo mutuo.</div>
            <div class="def"><b>Miglior Anno per Vendere</b> — l'anno che massimizza il rendimento annuale. Non è sempre l'ultimo anno.</div>
            <div class="def"><b>Quando la leva smette di pagare</b> — il "Miglior anno" qui è basato sul rendimento annualizzato (CAGR); il punto in cui l'ETF supera l'immobile con leva è discusso nella <b>Sezione 03</b>. Sono due prospettive diverse: rendimento per anno vs vantaggio assoluto rispetto all'ETF.</div>
        </div>
    </div>
    """


def _build_taeg_callout(params) -> str:
    """Callout informativo TAN vs TAEG (costo reale del finanziamento)."""
    taeg = params.taeg
    tasso_eff = params.tasso_effettivo
    importo = params.importo_mutuo
    anni = params.anni_mutuo
    if taeg <= 0 or taeg <= tasso_eff or importo <= 0:
        return ""

    rata_tan = rata_mensile(importo, tasso_eff, anni)
    rata_taeg = rata_mensile(importo, taeg, anni)
    costo_extra = (rata_taeg - rata_tan) * anni * 12
    spese_contabilizzate = params.costo_perizia + params.costo_assicurazione
    altri_costi = max(costo_extra - spese_contabilizzate, 0.0)

    eff_txt = ""
    if abs(tasso_eff - params.tasso_interesse) > 1e-9:
        eff_txt = f'&nbsp;·&nbsp; Tasso effettivo (APE): <span class="num">{_pct(tasso_eff)}</span>'

    return f"""
    <div class="callout-blue">
        <div class="card-title">Costo reale del finanziamento — TAN vs TAEG</div>
        <div class="formula">
            Tasso nominale annuo (TAN): <span class="num">{_pct(params.tasso_interesse)}</span>{eff_txt}
            &nbsp;·&nbsp; TAEG: <span class="num">{_pct(taeg)}</span><br>
            Rata calcolata sul TAN: <span class="num">{_fmt(rata_tan, 2)} €/mese</span> ·
            rata equivalente al TAEG: <span class="num">{_fmt(rata_taeg, 2)} €/mese</span>
            → costo extra stimato su {anni} anni: <span class="num">≈ {_fmt(costo_extra)} €</span><br>
            Di questi, <span class="num">{_fmt(spese_contabilizzate)} €</span> (perizia + assicurazione) sono già inclusi
            nell'investimento totale; i restanti <span class="num">≈ {_fmt(altri_costi)} €</span> coprono le altre spese
            del mutuo (istruttoria, imposta sostitutiva, incasso rata…).<br>
            <b>Nota metodologica</b>: stima approssimata — il TAEG non è un tasso applicato alla rata,
            ma la misura standardizzata del costo complessivo del finanziamento.
        </div>
    </div>
    """


def _build_amort_section(params, df_mutuo, has_mutuo) -> str:
    """Sezione 02 — Piano di ammortamento francese."""
    if not has_mutuo or df_mutuo.empty:
        return """
        <div class="section-block page-break" id="sec2">
            <div class="section-eyebrow">Sezione 02</div>
            <div class="section-title">Piano di Ammortamento Francese <span class="tag">Dettaglio annuo</span></div>
            <div class="info-box"><div class="card-title">Nessun mutuo attivo</div>
            <div class="def">Questa simulazione è in 100% cash: non è presente alcun piano di ammortamento.</div></div>
        </div>
        """

    rows = ""
    for _, r in df_mutuo.iterrows():
        rows += f"""
        <tr>
            <td>{int(r['Anno'])}</td>
            <td class="num">{_fmt(r['Rata_Mensile'], 2)} €</td>
            <td class="num">{_fmt(r['Rata_Annua'], 2)} €</td>
            <td class="num">{_fmt(r['Quota_Capitale_Annua'], 2)} €</td>
            <td class="num">{_fmt(r['Quota_Interessi_Annua'], 2)} €</td>
            <td class="num">{_fmt(r['Capitale_Residuo'], 2)} €</td>
        </tr>
        """

    tot_int = df_mutuo["Quota_Interessi_Annua"].sum()
    tot_cap = df_mutuo["Quota_Capitale_Annua"].sum()
    tot_pagato = tot_int + tot_cap
    pct_int = tot_int / tot_pagato * 100 if tot_pagato > 0 else 0

    chart = _build_amort_chart(df_mutuo)

    return f"""
    <div class="section-block page-break" id="sec2">
        <div class="section-eyebrow">Sezione 02</div>
        <div class="section-title">Piano di Ammortamento Francese <span class="tag">Dettaglio annuo</span></div>

        <table class="data">
            <thead><tr><th>Anno</th><th>Rata Mensile</th><th>Rata Annua</th><th>Quota Capitale</th><th>Quota Interessi</th><th>Capitale Residuo</th></tr></thead>
            <tbody>{rows}</tbody>
        </table>

        <div class="summary-line">
            Totale interessi: <strong class="num">{_fmt(tot_int)} €</strong> ({_fmt(pct_int, 1)}% del totale)
            &nbsp;·&nbsp; Totale restituito: <strong class="num">{_fmt(tot_pagato)} €</strong>
            &nbsp;·&nbsp; Rata costante mensile: <strong class="num">{_fmt(df_mutuo['Rata_Mensile'].iloc[0], 2)} €</strong>
        </div>

        {_build_taeg_callout(params)}

        <div class="subhead">Composizione Rata nel Tempo</div>
        <div class="chart-card">
            <div class="chart-legend">
                <span><span class="dot" style="background:{BRAND['navy_900']}"></span>Quota Capitale</span>
                <span><span class="dot" style="background:{BRAND['gold']}"></span>Quota Interessi</span>
                <span><span class="dot" style="background:{BRAND['green']}"></span>Capitale Residuo</span>
            </div>
            <img class="chart" src="{chart}">
        </div>
    </div>
    """


def _build_benchmark_section(params, df_proj, etf_puro, df_cash, etf_cash,
                             totale_inv, equity_val, rend_etf, has_mutuo,
                             best_year=0) -> str:
    """Sezione 03 — Benchmark immobile vs ETF."""

    # Blocco a leva (solo se mutuo attivo)
    leva_block = ""
    if has_mutuo and etf_puro is not None and len(etf_puro) > 0:
        diff = df_proj["Guadagno_Netto_Immobile"].values - etf_puro
        yr_max, val_max = _max_delta(diff)
        cross = crossover_leva_etf(df_proj, etf_puro)
        cross_stat, cross_note = _crossover_ui(cross, params.anni_simulazione)
        best_txt = f"anno {best_year}" if best_year > 0 else "della Sezione 01"
        leva_block = f"""
        <div class="subhead">Confronto con Leva <span class="tag">{_fmt(equity_val)} € investiti</span></div>
        <div class="chart-card">
            <div class="chart-legend">
                <span><span class="dot" style="background:{BRAND['navy_900']}"></span>Immobile con Mutuo</span>
                <span><span class="dot" style="background:{BRAND['gold']}"></span>ETF Azionario</span>
            </div>
            <img class="chart" src="{_build_benchmark_leva_chart(df_proj, etf_puro, equity_val)}">
        </div>
        <div class="stat-pair-grid">
            <div class="stat-pair"><div class="lbl">Anno differenza massima</div><div class="val">Anno {yr_max}</div></div>
            <div class="stat-pair gold"><div class="lbl">Differenza max immobile − ETF</div><div class="val num">{('+' if val_max > 0 else '')}{_fmt(val_max)} €</div></div>
            <div class="stat-pair"><div class="lbl">La leva batte l'ETF fino a</div><div class="val">{cross_stat}</div></div>
        </div>
        <div class="callout-gold"><div class="card-title">Lettura rapida — quando la leva smette di pagare</div>
        <div class="def">{cross_note}</div>
        <div class="def"><b>Non confonderlo</b> con il "Miglior anno per vendere" ({best_txt}): quello massimizza il rendimento annualizzato (CAGR); questo indica il limite oltre il quale l'ETF avrebbe reso di più. Sono due prospettive diverse.</div>
        <div class="def"><b>Quanto è solido il sorpasso?</b> Dipende dalle ipotesi: i cash flow dell'immobile si accumulano senza reinvestimento, mentre l'ETF compone al {_pct(rend_etf)}. Con rivalutazione immobiliare ({_pct(params.rivalutazione_annua)} nel tuo caso) o reinvestendo i flussi, il punto di sorpasso si sposta più avanti.</div>
        </div>
        <div class="chart-card">
            <img class="chart" src="{_build_delta_chart(df_proj['Anno'].values, diff, BRAND['navy_900'])}">
            <div class="note">Differenza annua immobile − ETF: blu navy = leva vincente, rosso = ETF vincente.</div>
        </div>
        """
    else:
        leva_block = f"""
        <div class="subhead">Confronto con Leva <span class="tag">{_fmt(equity_val)} € investiti</span></div>
        <div class="info-box"><div class="card-title">Leva non applicabile</div>
        <div class="def">Nessun mutuo attivo: il confronto a leva coincide con il confronto cash.</div></div>
        """

    # Blocco 100% cash
    cash_block = ""
    if df_cash is not None and not df_cash.empty and etf_cash is not None and len(etf_cash) > 0:
        diff_c = df_cash["Guadagno_Netto_Immobile"].values - etf_cash
        yr_max_c, val_max_c = _max_delta(diff_c)
        cash_block = f"""
        <div class="subhead">Confronto 100% Cash <span class="tag">{_fmt(totale_inv)} € investiti</span></div>
        <div class="chart-card">
            <div class="chart-legend">
                <span><span class="dot" style="background:{BRAND['green']}"></span>Immobile Cash</span>
                <span><span class="dot" style="background:{BRAND['gold']}"></span>ETF Azionario</span>
            </div>
            <img class="chart" src="{_build_benchmark_cash_chart(df_cash, etf_cash, totale_inv)}">
        </div>
        <div class="stat-pair-grid">
            <div class="stat-pair"><div class="lbl">Anno differenza massima</div><div class="val">Anno {yr_max_c}</div></div>
            <div class="stat-pair gold"><div class="lbl">Differenza max immobile − ETF</div><div class="val num">{('+' if val_max_c > 0 else '')}{_fmt(val_max_c)} €</div></div>
        </div>
        <div class="chart-card">
            <img class="chart" src="{_build_delta_chart(df_cash['Anno'].values, diff_c, BRAND['green'])}">
            <div class="note">Differenza annua immobile − ETF: verde = immobile vincente, rosso = ETF vincente.</div>
        </div>
        """

    # Riepilogo a confronto
    anni_confronto = [a for a in [5, 10, 15, 20, 25, 30] if a <= params.anni_simulazione]
    rows = ""
    for yr in anni_confronto:
        imm_leva = _get_row(df_proj, yr)
        imm_cash = _get_row(df_cash, yr)
        imm_l_val = imm_leva["Guadagno_Netto_Immobile"] if imm_leva is not None else 0
        imm_c_val = imm_cash["Guadagno_Netto_Immobile"] if imm_cash is not None else 0
        etf_leva = equity_val * (1 + rend_etf) ** yr - equity_val
        etf_cash_v = totale_inv * (1 + rend_etf) ** yr - totale_inv
        div_leva = imm_l_val - etf_leva
        div_cash = imm_c_val - etf_cash_v
        sign_leva = "+" if div_leva > 0 else ("−" if div_leva < 0 else "")
        sign_cash = "+" if div_cash > 0 else ("−" if div_cash < 0 else "")
        rows += f"""
        <tr>
            <td>{yr}</td>
            <td class="num">{_fmt(imm_l_val)} €</td>
            <td class="num">{_fmt(etf_leva)} €</td>
            <td class="num {'pos' if div_leva >= 0 else 'neg'}">{sign_leva}{_fmt(abs(div_leva))} €</td>
            <td class="num">{_fmt(imm_c_val)} €</td>
            <td class="num">{_fmt(etf_cash_v)} €</td>
            <td class="num {'pos' if div_cash >= 0 else 'neg'}">{sign_cash}{_fmt(abs(div_cash))} €</td>
        </tr>
        """

    return f"""
    <div class="section-block page-break" id="sec3">
        <div class="section-eyebrow">Sezione 03</div>
        <div class="section-title">Benchmark: Immobile vs ETF Azionario</div>
        {leva_block}
        {cash_block}

        <div class="subhead">Riepilogo a Confronto</div>
        <table class="data">
            <thead>
                <tr>
                    <th>Anno</th>
                    <th>Immobile (Mutuo)</th>
                    <th>ETF ({_fmt(equity_val)} €)</th>
                    <th>Divario Leva</th>
                    <th>Immobile (Cash)</th>
                    <th>ETF ({_fmt(totale_inv)} €)</th>
                    <th>Divario Cash</th>
                </tr>
            </thead>
            <tbody>{rows}</tbody>
        </table>
    </div>
    """


def _build_detail_section(params, totale_inv, df_proj, df_mutuo, has_mutuo,
                          flag_detrazioni, detrazione_annua_val, aliquota_detr,
                          base_detr, work_items, work_qty, furn_items, furn_qty) -> str:
    """Sezione 04 — Dettaglio completo della simulazione."""

    # Voci di costo
    costi_rows = [
        ("Prezzo Immobile", params.prezzo),
        ("Imposte Acquisto", params.imposte),
        ("Spese Notaio", params.notaio),
        ("Agenzia Acquisto", params.agenzia_acquisto),
        ("Lavori / Impianti (imponibile)", params.lavori),
        ("Compenso Tecnico", params.compenso_tecnico),
        ("Oneri Urbanistici", params.oneri_urbanistici),
        ("Arredamento (IVA incl.)", params.arredo),
        ("Spese Perizia Mutuo", params.costo_perizia),
        ("Assicurazione Incendio", params.costo_assicurazione),
    ]
    costi_rows_html = "".join(
        f'<tr><td>{label}</td><td class="num">{_fmt(val)} €</td></tr>' for label, val in costi_rows
    )

    # Lavori
    lavori_con_qty = [it for it in work_items if work_qty.get(it["id"], 0) > 0]
    if lavori_con_qty:
        from engine import calcola_iva_lavori
        iva = calcola_iva_lavori(work_qty)
        lavori_rows = ""
        for it in lavori_con_qty:
            qty = work_qty[it["id"]]
            line_total = it["prezzo"] * qty
            iva_txt = f"{it['iva_pct']*100:.0f}%"
            lavori_rows += f"""
            <tr>
                <td><span class="cat-pill">{it['categoria']}</span></td>
                <td>{it['voce']}</td>
                <td>{it['um']}</td>
                <td class="num">{_fmt(it['prezzo'], 2)} €</td>
                <td class="num">{iva_txt}</td>
                <td class="num">{_fmt(qty, 1)}</td>
                <td class="num">{_fmt(line_total, 2)} €</td>
            </tr>
            """
        lavori_note = (
            f'<div class="total-line">Totale Lavori (imponibile): {_fmt(params.lavori)} €'
            f' &nbsp;|&nbsp; IVA 10%: {_fmt(iva["iva_10"])} €'
            f' &nbsp;|&nbsp; IVA 22%: {_fmt(iva["iva_22"])} €'
            f' &nbsp;|&nbsp; Totale IVA: {_fmt(iva["iva_totale"])} €</div>'
        )
    else:
        lavori_rows = '<tr><td colspan="7">Nessun lavoro selezionato.</td></tr>'
        lavori_note = ""

    # Detrazione
    if flag_detrazioni and aliquota_detr > 0:
        detrazione_box = f"""
        <div class="callout-green">
            <div class="card-title">Detrazione Fiscale Ristrutturazione</div>
            <div class="formula">
                Detrazione annua: <span class="num">{_fmt(detrazione_annua_val)} €</span> per {params.anni_detrazione} anni ({_pct(aliquota_detr, 0)}) → Totale: <span class="num">{_fmt(detrazione_annua_val * params.anni_detrazione)} €</span><br><br>
                Base di calcolo:<br>
                · Lavori (imponibile): {_fmt(params.lavori)} €<br>
                · Compenso Tecnico: {_fmt(params.compenso_tecnico)} €<br>
                · Oneri Urbanistici: {_fmt(params.oneri_urbanistici)} €<br>
                · <b>Totale base: {_fmt(base_detr)} €</b>
            </div>
        </div>
        """
    else:
        detrazione_box = ""

    # Arredo
    furn_con_qty = [it for it in furn_items if furn_qty.get(it["id"], 0) > 0]
    if furn_con_qty:
        furn_rows = ""
        for it in furn_con_qty:
            qty = furn_qty[it["id"]]
            line_total = it["prezzo"] * qty
            furn_rows += f"""
            <tr>
                <td><span class="cat-pill">{it['categoria']}</span></td>
                <td>{it['voce']}</td>
                <td>{it['um']}</td>
                <td class="num">{_fmt(it['prezzo'], 2)} €</td>
                <td class="num">22% incl.</td>
                <td class="num">{_fmt(qty, 0)}</td>
                <td class="num">{_fmt(line_total, 2)} €</td>
            </tr>
            """
        furn_note = f'<div class="total-line">Totale Arredo: {_fmt(params.arredo)} € (IVA 22% già inclusa)</div>'
    else:
        furn_rows = '<tr><td colspan="7">Nessun arredo selezionato.</td></tr>'
        furn_note = ""

    # Costi operativi
    op_rows = [
        ("Affitto Lordo", params.affitto_lordo_annuo),
        ("Cedolare Secca", params.cedolare),
        ("IMU", params.imu),
        ("Condominio", params.condominio),
        ("Altri Costi", params.altro_costi),
    ]
    op_rows_html = "".join(
        f'<tr><td>{label}</td><td class="num">{_fmt(val)} €</td></tr>' for label, val in op_rows
    )

    # Entrate annuali
    entrate_rows = ""
    if not df_proj.empty:
        for _, r in df_proj.iterrows():
            entrate_rows += f"""
            <tr>
                <td>{int(r['Anno'])}</td>
                <td class="num">{_fmt(r['Affitto_Effettivo'])} €</td>
                <td class="num">{_fmt(r['Detrazione'])} €</td>
                <td class="num">{_fmt(r['CF_Netto_Anno'])} €</td>
            </tr>
            """

    # Entrate una tantum (vendita)
    vendita_rows = ""
    if not df_proj.empty:
        for _, r in df_proj.iterrows():
            vendita_rows += f"""
            <tr>
                <td>{int(r['Anno'])}</td>
                <td class="num">{_fmt(r['Valore_Immobile'])} €</td>
                <td class="num">{_fmt(r['Capitale_Residuo_Mutuo'])} €</td>
                <td class="num pos">{_fmt(r['Guadagno_Netto_Immobile'])} €</td>
            </tr>
            """

    return f"""
    <div class="section-block page-break" id="sec4">
        <div class="section-eyebrow">Sezione 04</div>
        <div class="section-title">Dettaglio Completo Simulazione</div>

        <div class="subhead">Voci di Costo</div>
        <table class="data">
            <thead><tr><th>Voce</th><th>Importo</th></tr></thead>
            <tbody>{costi_rows_html}
                <tr class="total-row"><td><strong>TOTALE INVESTIMENTO</strong></td><td class="num"><strong>{_fmt(totale_inv)} €</strong></td></tr>
            </tbody>
        </table>

        <div class="subhead">Dettaglio Lavori Realizzati</div>
        <table class="data">
            <thead><tr><th>Categoria</th><th>Voce</th><th>UM</th><th>Prezzo Unit.</th><th>IVA</th><th>Qtà</th><th>Totale</th></tr></thead>
            <tbody>{lavori_rows}</tbody>
        </table>
        {lavori_note}

        {detrazione_box}

        <div class="subhead">Dettaglio Arredamento / Mobilio</div>
        <table class="data">
            <thead><tr><th>Categoria</th><th>Voce</th><th>UM</th><th>Prezzo Unit.</th><th>IVA</th><th>Qtà</th><th>Totale</th></tr></thead>
            <tbody>{furn_rows}</tbody>
        </table>
        {furn_note}

        <div class="subhead">Costi Operativi Annui</div>
        <table class="data">
            <thead><tr><th>Voce</th><th>Importo</th></tr></thead>
            <tbody>{op_rows_html}
                <tr class="total-row"><td><strong>TOTALE COSTI FISSI</strong></td><td class="num"><strong>{_fmt(params.costi_fissi_annui)} €</strong></td></tr>
            </tbody>
        </table>

        <div class="subhead">Entrate Stimate — Annuale</div>
        <table class="data">
            <thead><tr><th>Anno</th><th>Affitto Effettivo</th><th>Detrazione</th><th>CF Netto Anno</th></tr></thead>
            <tbody>{entrate_rows}</tbody>
        </table>

        <div class="subhead">Entrate Stimate — Una Tantum (Vendita)</div>
        <table class="data">
            <thead><tr><th>Anno</th><th>Valore Immobile</th><th>Capitale Residuo Mutuo</th><th>Guadagno Totale se Vendi</th></tr></thead>
            <tbody>{vendita_rows}</tbody>
        </table>
    </div>
    """


def _build_glossary() -> str:
    items = [
        ("ROI", "Return on Investment: guadagno rispetto al capitale totale investito (equity + mutuo)."),
        ("ROE", "Return on Equity: guadagno rispetto al solo capitale proprio, misura l'effetto leva."),
        ("IRR", "Internal Rate of Return: tasso che rende nullo il valore attuale netto dei flussi di cassa."),
        ("CAGR", "Compound Annual Growth Rate: tasso di crescita annuo composto."),
        ("CapEx", "Capital Expenditure: accantonamento per manutenzioni straordinarie future."),
        ("TAN", "Tasso Annuo Nominale: il tasso di interesse puro applicato dal mutuo."),
        ("TAEG", "Tasso Annuo Effettivo Globale: costo reale del mutuo, spese accessorie incluse."),
        ("APE", "Attestato di Prestazione Energetica: classe energetica dell'immobile."),
        ("Cedolare Secca", "regime fiscale opzionale sugli affitti, tassazione fissa sostitutiva dell'IRPEF."),
        ("IMU", "Imposta Municipale Unica, tassa comunale sugli immobili."),
        ("Sfitto", "quota di tempo l'anno in cui si ipotizza l'immobile vuoto tra un inquilino e l'altro."),
        ("LTV", "Loan to Value: rapporto tra importo del mutuo e valore dell'immobile."),
    ]
    grid = ""
    for term, defn in items:
        grid += f'<div class="gloss-item"><span class="gloss-term">{term}</span> <span class="gloss-def">— {defn}</span></div>\n'
    return f"""
    <div class="section-block page-break" id="glossario">
        <div class="section-eyebrow">Appendice</div>
        <div class="section-title">Glossario — Significato delle Abbreviazioni</div>
        <div class="card">
            <div class="glossary-grid">{grid}</div>
        </div>
    </div>
    """


def _build_disclaimer() -> str:
    return """
    <div class="disclaimer" id="disclaimer">
        <div class="disclaimer-title">Avvertenza — Esclusione di responsabilità</div>
        <p>Il presente documento è uno strumento di <strong>simulazione puramente informativa</strong>, generato automaticamente a scopo illustrativo e didattico. Tutti i valori e i risultati riportati (rendimenti, IRR, ROE, cash flow, detrazioni, costi del mutuo, ecc.) sono <strong>stime</strong> basate esclusivamente sulle ipotesi inserite dall'utente.</p>
        <p>Nessun contenuto di questo report <strong>costituisce consulenza finanziaria, fiscale, legale o immobiliare</strong>, né una raccomandazione o un invito all'investimento, all'acquisto o alla vendita di immobili o strumenti finanziari. Simulazioni o risultati passati non garantiscono risultati futuri; i dati reali possono differire sensibilmente in funzione di mercato, tassi, fiscalità e costi effettivi.</p>
        <p>Prima di assumere qualsiasi decisione patrimoniale, si raccomanda di rivolgersi a un consulente finanziario abilitato e/o a un professionista fiscale abilitato. Il documento è generato senza verifica di dati reali e non implica alcuna responsabilità per errori, omissioni o per decisioni prese sulla base di questa simulazione.</p>
    </div>
    """


# ---------------------------------------------------------------------------
# CSS — identità del mockup v2
# ---------------------------------------------------------------------------

CSS = """
:root{
    --navy-950:#0B1220; --navy-900:#0F172A; --navy-800:#1E293B; --navy-700:#334155;
    --gold:#C59B27; --gold-dark:#8A6A15; --gold-soft:#F5EBD0;
    --cream:#F7F5F0; --card:#FFFFFF; --line:#E7E4DC;
    --ink:#1F2A37; --muted:#8A93A0;
    --green:#1B7A4D; --green-soft:#EAF6EE;
    --red:#B4342E; --red-soft:#FBEBEA;
    --orange:#B5651D; --orange-soft:#FBEEE0;
    --blue:#2A4B8D; --blue-soft:#EAF0FB;
    --radius:14px;
}

@font-face { font-family:'Inter'; font-weight:400; src:url('assets/fonts/Inter-Regular.ttf'); }
@font-face { font-family:'Inter'; font-weight:500; src:url('assets/fonts/Inter-Medium.ttf'); }
@font-face { font-family:'Inter'; font-weight:600; src:url('assets/fonts/Inter-SemiBold.ttf'); }
@font-face { font-family:'Inter'; font-weight:700; src:url('assets/fonts/Inter-Bold.ttf'); }
@font-face { font-family:'Inter'; font-weight:800; src:url('assets/fonts/Inter-ExtraBold.ttf'); }
@font-face { font-family:'PlexMono'; font-weight:500; src:url('assets/fonts/IBMPlexMono-Medium.ttf'); }
@font-face { font-family:'PlexMono'; font-weight:600; src:url('assets/fonts/IBMPlexMono-SemiBold.ttf'); }

@page{
    size:A4;
    margin:11mm 11mm 15mm 11mm;
    @bottom-center{
        content:"Pagina " counter(page) " di " counter(pages);
        font-family:'PlexMono'; font-size:7.5pt; color:var(--muted);
    }
    @bottom-right{
        content:"Valle delle Case · Analisi Investimento";
        font-family:'Inter'; font-size:7pt; color:#B8BEC9;
    }
}

html, body{
    background:var(--cream);
    margin:0; padding:0;
    font-family:'Inter', 'Helvetica Neue', Arial, sans-serif;
    font-size:10pt; color:var(--ink);
    -weasy-hyphens:auto;
}

.num{ font-family:'PlexMono', ui-monospace, monospace; font-variant-numeric:tabular-nums; }

/* HEADER */
.header{
    background:linear-gradient(135deg, var(--navy-950), var(--navy-800));
    border-radius:var(--radius); padding:16pt 20pt; color:#fff;
    display:flex; align-items:center; justify-content:space-between; margin-bottom:10pt;
}
.brand{ display:flex; align-items:center; gap:10pt; }
.brand-mark{
    width:24pt; height:24pt; border-radius:8pt;
    background:rgba(197,155,39,.16); border:1px solid rgba(197,155,39,.5);
    color:var(--gold); font-weight:800; font-size:14pt; line-height:24pt; text-align:center;
}
.brand-name{ font-size:7pt; letter-spacing:.14em; color:var(--gold); font-weight:700; text-transform:uppercase; }
.h-title{ font-size:14pt; font-weight:800; margin:1pt 0 2pt; hyphens:none; }
.h-sub{ font-size:8pt; color:#A9B4C6; }
.badge{
    background:rgba(197,155,39,.16); border:1px solid rgba(197,155,39,.5); color:var(--gold);
    font-size:7.5pt; font-weight:700; padding:4pt 9pt; border-radius:999px; white-space:nowrap;
}

/* NAV PILLS (indice) */
.nav-pills{ display:flex; gap:5pt; margin-bottom:18pt; flex-wrap:wrap; }
.nav-pills a{
    text-decoration:none; font-size:7.5pt; font-weight:700; color:var(--navy-700);
    background:#fff; border:1px solid var(--line); padding:5pt 9pt; border-radius:999px;
}
.nav-pills a span{ color:var(--gold); margin-right:4pt; }

.section-block{ margin-bottom:26pt; }
.section-eyebrow{ font-size:6.5pt; font-weight:700; letter-spacing:.12em; text-transform:uppercase; color:var(--gold); margin-bottom:2pt; }
.section-title{ font-size:12pt; font-weight:800; color:var(--navy-900); margin:0 0 11pt; padding-left:8pt; border-left:3px solid var(--gold); }
.section-title .tag{ font-size:7pt; font-weight:700; color:var(--muted); text-transform:uppercase; letter-spacing:.05em; margin-left:6pt; }
.subhead{ font-size:9pt; font-weight:700; color:var(--navy-800); margin:13pt 0 7pt; }

/* KPI hero */
.kpi-hero-grid{ display:flex; gap:8pt; margin-bottom:12pt; }
.kpi-hero{
    flex:1; background:linear-gradient(135deg,#F4F1FB,#EDEBFB);
    border:1px solid #E1DDF5; border-radius:10pt; padding:11pt 13pt;
}
.kpi-hero .lbl{ font-size:7pt; font-weight:600; color:var(--navy-700); margin-bottom:4pt; }
.kpi-hero .val{ font-size:17pt; font-weight:800; color:var(--navy-900); }

.stat-pair-grid{ display:flex; gap:8pt; margin-bottom:13pt; }
.stat-pair{
    flex:1; background:linear-gradient(135deg,#F4F1FB,#EDEBFB);
    border:1px solid #E1DDF5; border-radius:10pt; padding:11pt 13pt;
}
.stat-pair .lbl{ font-size:7.5pt; font-weight:600; color:var(--navy-700); margin-bottom:4pt; }
.stat-pair .val{ font-size:16pt; font-weight:800; color:var(--navy-900); }
.stat-pair.gold .val{ color:var(--gold-dark); }

/* Cards */
.card{
    background:var(--card); border:1px solid var(--line); border-radius:var(--radius);
    padding:12pt 14pt; box-shadow:0 1px 2px rgba(15,23,42,.06); break-inside:avoid;
}
.card-title{ font-size:8pt; font-weight:700; letter-spacing:.03em; color:var(--navy-800); margin-bottom:8pt; }

/* Callout & info */
.callout-blue{ background:var(--blue-soft); border:1px solid #D6E2F7; border-radius:var(--radius); padding:12pt 14pt; margin:12pt 0; break-inside:avoid; }
.callout-blue .card-title{ color:var(--blue); }
.callout-green{ background:var(--green-soft); border:1px solid #CFEBD9; border-radius:var(--radius); padding:12pt 14pt; margin:12pt 0; break-inside:avoid; }
.callout-green .card-title{ color:var(--green); }
.callout-blue .formula, .callout-green .formula{ font-size:8pt; color:var(--navy-800); line-height:1.9; }
.callout-blue .formula .num{ font-weight:600; color:var(--blue); }
.callout-green .formula .num{ font-weight:600; color:var(--green); }
.callout-gold{ background:var(--gold-soft); border:1px solid #E6D5A6; border-radius:var(--radius); padding:12pt 14pt; margin:12pt 0; break-inside:avoid; }
.callout-gold .card-title{ color:var(--gold-dark); }
.callout-gold .def b{ color:var(--gold-dark); }

.info-box{ background:#F8F7F4; border:1px solid var(--line); border-radius:var(--radius); padding:12pt 14pt; margin:12pt 0; }
.def{ font-size:8pt; color:var(--navy-700); margin-bottom:6pt; line-height:1.6; }
.def:last-child{ margin-bottom:0; }
.def b{ color:var(--navy-900); }

/* Chart */
.chart-card{
    background:var(--card); border:1px solid var(--line); border-radius:var(--radius);
    padding:11pt 13pt 6pt; box-shadow:0 1px 2px rgba(15,23,42,.06); margin-bottom:10pt;
}
.chart-legend{ display:flex; gap:12pt; font-size:7.5pt; color:var(--navy-700); margin-bottom:4pt; }
.dot{ display:inline-block; width:6pt; height:6pt; border-radius:2pt; margin-right:4pt; }
img.chart{ width:100%; max-height:160pt; object-fit:contain; margin:0; }

/* Tables */
table.data{ width:100%; border-collapse:collapse; font-size:7.6pt; }
table.data thead th{
    background:var(--navy-900); color:#fff; text-align:left; padding:5pt 7pt;
    font-size:6.6pt; font-weight:700; text-transform:uppercase; letter-spacing:.03em;
}
table.data tbody td{ padding:4pt 7pt; border-bottom:1px solid var(--line); color:var(--navy-700); }
table.data tbody tr:nth-child(even) td{ background:#FBFAF7; }
table.data tbody td:last-child{ text-align:right; font-weight:600; color:var(--ink); }
table.data td.num{ text-align:right; font-weight:500; }
table.data tr.total-row td{ background:#FBFAF7; border-top:1.5px solid var(--gold); border-bottom:none; font-weight:800; color:var(--navy-900); }
.cat-pill{
    display:inline-block; font-size:6.2pt; font-weight:700; letter-spacing:.03em;
    color:var(--navy-800); background:var(--gold-soft); padding:1.5pt 5pt; border-radius:4pt;
}
.pos{ color:var(--green) !important; }
.neg{ color:var(--red) !important; }

.summary-line{
    font-size:8pt; font-weight:700; color:var(--navy-900);
    background:var(--gold-soft); border:1px solid #EDDFB8; border-radius:8pt;
    padding:6pt 10pt; margin:8pt 0 0;
}
.total-line{ font-size:8pt; font-weight:700; color:var(--navy-900); margin:4pt 0 12pt; }
.note{ font-size:6.8pt; color:var(--muted); margin:4pt 0 0; }

/* Glossario */
.glossary-grid{ display:flex; flex-wrap:wrap; }
.gloss-item{
    width:48%; font-size:8pt; line-height:1.5; padding:5pt 0;
    border-bottom:1px dashed rgba(0,0,0,.08); margin-right:2%;
}
.gloss-term{ font-weight:800; color:var(--navy-900); }
.gloss-def{ color:var(--navy-700); }

/* Disclaimer */
.disclaimer{
    margin-top:14pt; padding:12pt 14pt;
    border:1px solid var(--line); border-left:4pt solid var(--gold);
    border-radius:var(--radius); background:#FBFAF5;
    color:var(--muted); font-size:8pt; line-height:1.55;
}
.disclaimer-title{ color:var(--ink); font-weight:800; font-size:9.5pt; margin-bottom:4pt; }
.disclaimer p{ margin:5pt 0; }
.disclaimer strong{ color:var(--navy-700); }

.page-break{ break-before:page; }
"""


# ---------------------------------------------------------------------------
# Main generator
# ---------------------------------------------------------------------------

_HTML = None


def _get_html():
    """Lazy import di WeasyPrint con messaggio d'errore chiaro."""
    global _HTML
    if _HTML is not None:
        return _HTML
    try:
        from weasyprint import HTML
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "Impossibile importare WeasyPrint. Installa le dipendenze di sistema:\n"
            "  macOS:   brew install pango\n"
            "  Debian:  apt install libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libffi-dev\n"
            "Su macOS con Homebrew assicurati anche che DYLD_FALLBACK_LIBRARY_PATH "
            "includa /opt/homebrew/lib (vedi avvia.sh)."
        ) from exc
    _HTML = HTML
    return _HTML


def generate_pdf(
    params, totale_inv, equity_val, mutuo_val, irr_val,
    best_year, best_annual, df_proj, df_mutuo, etf_puro, anni_sim,
    rend_etf, inflazione, rivalutazione, prezzo_vendita_val,
    sfitto, capex_pct, flag_detrazioni, detrazione_annua_val,
    aliquota_detr, base_detr, work_items, work_qty,
    furn_items, furn_qty, df_cash, etf_cash,
) -> bytes:

    HTML = _get_html()

    has_mutuo = mutuo_val > 0 and df_mutuo is not None and not df_mutuo.empty

    header = _build_header(params, has_mutuo)
    sec1 = _build_kpi_section(params, totale_inv, equity_val, mutuo_val, best_year,
                              best_annual, df_proj, df_mutuo, has_mutuo)
    sec2 = _build_amort_section(params, df_mutuo, has_mutuo)
    sec3 = _build_benchmark_section(params, df_proj, etf_puro, df_cash, etf_cash,
                                    totale_inv, equity_val, rend_etf, has_mutuo,
                                    best_year=best_year)
    sec4 = _build_detail_section(
        params, totale_inv, df_proj, df_mutuo, has_mutuo,
        flag_detrazioni, detrazione_annua_val, aliquota_detr, base_detr,
        work_items, work_qty, furn_items, furn_qty,
    )
    glossary = _build_glossary()
    disclaimer = _build_disclaimer()

    html_content = f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="utf-8">
<title>Analisi Investimento Immobiliare — Valle delle Case</title>
<style>{CSS}</style>
</head>
<body>
{header}
{sec1}
{sec2}
{sec3}
{sec4}
{glossary}
{disclaimer}
</body>
</html>
"""

    pdf_bytes = io.BytesIO()
    HTML(string=html_content, base_url=BASE_DIR).write_pdf(target=pdf_bytes)
    return pdf_bytes.getvalue()
