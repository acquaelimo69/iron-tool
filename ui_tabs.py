import io

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from engine import (
    WORK_ITEMS,
    FURN_ITEMS,
    rata_mensile,
    calcola_costo_extra_taeg,
    crossover_leva_etf,
)
from report import generate_pdf
from utils import fmt


def render_tab_kpi(sb, df_proj, df_rend, best_year, best_annual):
    st.subheader("Metriche Chiave")
    c1, c2, c3 = st.columns(3)
    c1.metric("Investimento Totale", f"{fmt(sb.totale_inv)} €")
    c2.metric("Equity (Capitale Proprio)", f"{fmt(sb.equity_val)} €")
    c3.metric("Importo Mutuo", f"{fmt(sb.mutuo_val)} €" if sb.usa_mutuo else "—")

    st.markdown("---")
    st.subheader("Rendimenti per Orizzonte Temporale")

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
            rend_ann_pct = ((guadagno_5 + sb.equity_val) / sb.equity_val) ** (1 / 5) - 1
            st.info(
                f"**Come si calcola (es. Anno 5):**\n\n"
                f"Guadagno Totale Netto = (Prezzo Vendita − Debito Residuo) + Cash Flow Cumulato − Equity\n\n"
                f"Cash Flow Cumulato = Σ(Affitto − Costi − Rata + **Detrazioni** − CapEx) per 5 anni = {fmt(cum_cf_5)} €\n\n"
                f"= ({fmt(prezzo_5)} − {fmt(residuo_5)}) + {fmt(cum_cf_5)} − {fmt(sb.equity_val)} = **{fmt(guadagno_5)} €**\n\n"
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


def render_tab_mutuo(sb, params, df_mutuo):
    if not df_mutuo.empty and sb.usa_mutuo and sb.mutuo_val > 0:
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
                f"| Totale restituito: **{fmt(tot_interessi + tot_capitale)} €** su **{fmt(sb.mutuo_val)} €**")

        # Callout informativo TAN vs TAEG (costo reale del finanziamento)
        if sb.taeg_val > 0 and sb.taeg_val / 100 > params.tasso_effettivo:
            r_tan = rata_mensile(sb.mutuo_val, params.tasso_effettivo, sb.anni_mut)
            r_taeg = rata_mensile(sb.mutuo_val, sb.taeg_val / 100, sb.anni_mut)
            costo_extra = calcola_costo_extra_taeg(sb.mutuo_val, params.tasso_effettivo,
                                                   sb.taeg_val / 100, sb.anni_mut)
            spese_cnt = sb.costo_perizia + sb.costo_assicurazione
            altri = max(costo_extra - spese_cnt, 0)
            st.info(
                f"**Costo reale del finanziamento (TAN vs TAEG)**\n\n"
                f"TAN {params.tasso_interesse * 100:.2f}% · TAEG {sb.taeg_val:.2f}% — rata "
                f"**{fmt(r_tan, 2)} €/mese** vs **{fmt(r_taeg, 2)} €/mese** equivalenti "
                f"→ costo extra stimato su {sb.anni_mut} anni: **≈ {fmt(costo_extra)} €**.\n\n"
                f"Di questi, **{fmt(spese_cnt)} €** (perizia + assicurazione) sono già inclusi "
                f"nell'investimento totale; i restanti **≈ {fmt(altri)} €** coprono le altre spese "
                f"del mutuo (istruttoria, imposta sostitutiva, incasso rata…).\n\n"
                f"Stima approssimata: il TAEG non è un tasso applicato alla rata, ma la misura "
                f"standardizzata del costo complessivo del finanziamento."
            )
    else:
        st.info("Nessun mutuo — nessun piano di ammortamento da mostrare.")


def render_tab_benchmark(sb, df_proj, df_cash, etf_puro, etf_cash):
    st.subheader("Confronto: Immobile vs ETF")

    # ── SEZIONE 1: Confronto con Leva (equity) ──────────────────────────────
    st.markdown(f"#### Confronto con Leva ({fmt(sb.equity_val)} € investiti)")

    fig_leva = go.Figure()

    fig_leva.add_trace(go.Scatter(
        x=df_proj["Anno"],
        y=df_proj["Guadagno_Netto_Immobile"],
        name=f"Immobile con Mutuo ({fmt(sb.equity_val)} € equity)",
        mode="lines+markers",
        line=dict(color="#636EFA", width=3),
    ))

    fig_leva.add_trace(go.Scatter(
        x=list(range(1, sb.anni_sim + 1)),
        y=etf_puro.tolist(),
        name=f"ETF Azionario ({fmt(sb.equity_val)} €)",
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
            st.metric(label="Anni simulati", value=f"{sb.anni_sim}")

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
        st.success(f"**La leva batte l'ETF su tutto l'orizzonte simulato ({sb.anni_sim} anni):** "
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
    st.markdown(f"#### Confronto Cash ({fmt(sb.totale_inv)} € investiti)")

    fig_cash = go.Figure()

    fig_cash.add_trace(go.Scatter(
        x=df_cash["Anno"],
        y=df_cash["Guadagno_Netto_Immobile"],
        name=f"Immobile Cash ({fmt(sb.totale_inv)} €)",
        mode="lines+markers",
        line=dict(color="#EF553B", width=3),
    ))

    fig_cash.add_trace(go.Scatter(
        x=list(range(1, sb.anni_sim + 1)),
        y=etf_cash.tolist(),
        name=f"ETF Azionario ({fmt(sb.totale_inv)} €)",
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
            st.metric(label="Anni simulati", value=f"{sb.anni_sim}")

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

    anni_confronto = [a for a in [5, 10, 15, 20, 25, 30] if a <= sb.anni_sim]
    righe_bench = []
    for yr in anni_confronto:
        imm_leva = df_proj.loc[df_proj["Anno"] == yr, "Guadagno_Netto_Immobile"]
        imm_cash = df_cash.loc[df_cash["Anno"] == yr, "Guadagno_Netto_Immobile"]
        etf_leva = sb.equity_val * (1 + sb.rend_etf) ** yr - sb.equity_val
        etf_cash_v = sb.totale_inv * (1 + sb.rend_etf) ** yr - sb.totale_inv
        righe_bench.append({
            "Anno": yr,
            "Immobile (Mutuo)": imm_leva.values[0] if len(imm_leva) else 0,
            f"ETF ({fmt(sb.equity_val)} €)": etf_leva,
            "Divario Leva": (imm_leva.values[0] - etf_leva) if len(imm_leva) else 0,
            "Immobile (Cash)": imm_cash.values[0] if len(imm_cash) else 0,
            f"ETF ({fmt(sb.totale_inv)} €)": etf_cash_v,
            "Divario Cash": (imm_cash.values[0] - etf_cash_v) if len(imm_cash) else 0,
        })
    df_bench = pd.DataFrame(righe_bench)

    def color_divario(val):
        color = "#00CC96" if val > 0 else "#EF553B" if val < 0 else ""
        return f"color: {color}; font-weight: bold" if color else ""

    styled = df_bench.style.format({
        "Immobile (Mutuo)": lambda v: f"{fmt(v)} €",
        f"ETF ({fmt(sb.equity_val)} €)": lambda v: f"{fmt(v)} €",
        "Divario Leva": lambda v: f"{'+' if v > 0 else ''}{fmt(v)} €",
        "Immobile (Cash)": lambda v: f"{fmt(v)} €",
        f"ETF ({fmt(sb.totale_inv)} €)": lambda v: f"{fmt(v)} €",
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


def render_tab_dettaglio(sb, params, df_proj, df_mutuo, df_cash, etf_puro, etf_cash,
                          df_rend, best_year, best_annual, irr_val):
    st.subheader("Dettaglio Completo Simulazione")

    st.markdown("#### Voci di Costo")
    voci = pd.DataFrame({
        "Voce": [
            "Prezzo Immobile", "Imposte Acquisto", "Spese Notaio",
            "Agenzia Acquisto", "Lavori / Impianti", "Compenso Tecnico", "Oneri Urbanistici",
            "Arredamento", "Spese Perizia Mutuo", "Assicurazione Incendio",
        ],
        "Importo (€)": [fmt(v) for v in [sb.prezzo, sb.imposte, sb.notaio, sb.agenzia_acq, sb.lavori,
                                          sb.compenso_tecnico, sb.oneri_urbanistici, sb.arredo,
                                          sb.costo_perizia, sb.costo_assicurazione]],
    })
    st.dataframe(voci, use_container_width=True, hide_index=True)
    st.markdown(f"**TOTALE INVESTIMENTO: {fmt(sb.totale_inv)} €**")

    # --- Dettaglio Lavori ---
    lavori_con_qty = [item for item in WORK_ITEMS if sb.work_qty.get(item["id"], 0) > 0]
    if lavori_con_qty:
        st.markdown("#### Dettaglio Lavori Realizzati")
        righe_lavori = []
        for item in lavori_con_qty:
            qty = sb.work_qty[item["id"]]
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
        st.markdown(f"**Totale Lavori: {fmt(sb.lavori)} €** | IVA 10%: {fmt(sb.iva_lavori['iva_10'])} € | IVA 22%: {fmt(sb.iva_lavori['iva_22'])} €")

    if sb.flag_detrazioni:
        st.info(
            f"**Detrazione annua: {fmt(sb.detrazione_annua_val)} €** per 10 anni ({sb.aliquota_detr*100:.0f}%) → Totale: **{fmt(sb.detrazione_annua_val * 10)} €**\n\n"
            f"Base di calcolo:\n"
            f"- Lavori (IVA incl.): {fmt(sb.lavori)} €\n"
            f"- Compenso Tecnico: {fmt(sb.compenso_tecnico)} €\n"
            f"- Oneri Urbanistici: {fmt(sb.oneri_urbanistici)} €\n"
            f"- **Totale base: {fmt(sb.base_detr)} €**"
        )

    # --- Dettaglio Arredamento ---
    mobilio_con_qty = [item for item in FURN_ITEMS if sb.furn_qty.get(item["id"], 0) > 0]
    if mobilio_con_qty:
        st.markdown("#### Dettaglio Arredamento / Mobilio")
        righe_mobilio = []
        for item in mobilio_con_qty:
            qty = sb.furn_qty[item["id"]]
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
        st.markdown(f"**Totale Arredo: {fmt(sb.arredo)} €** (IVA 22% già inclusa nei prezzi)")

    # --- Dettaglio Imposte (se calcolo automatico) ---
    if sb.imposte_mode == "Automatico" and "errore" not in sb.det_imposte:
        st.markdown("#### Dettaglio Imposte di Acquisto")
        st.json({k: fmt(v) if isinstance(v, (int, float)) else v for k, v in sb.det_imposte.items()})

    st.markdown("#### Costi Operativi Annui")
    op = pd.DataFrame({
        "Voce": ["Affitto Lordo", "Cedolare Secca", "IMU", "Condominio", "Altri Costi"],
        "Importo (€)": [fmt(v) for v in [sb.affitto_lordo, sb.cedolare, sb.imu, sb.condominio, sb.altro_costi]],
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
        st.dataframe(df_annuali.style.format(fmt_annuali), use_container_width=True, hide_index=True)

        st.markdown("#### Entrate Stimate — Una Tantum (Vendita)")
        colonne_vendita = ["Anno", "Valore_Immobile", "Capitale_Residuo_Mutuo", "Guadagno_Netto_Immobile"]
        df_vendita = df_proj[df_proj["Anno"] >= 5][colonne_vendita].copy()
        df_vendita = df_vendita.rename(columns={"Guadagno_Netto_Immobile": "Guadagno Totale se Vendi"})
        fmt_vendita = {
            "Valore_Immobile": lambda v: f"{fmt(v)} €",
            "Capitale_Residuo_Mutuo": lambda v: f"{fmt(v)} €",
            "Guadagno Totale se Vendi": lambda v: f"{fmt(v)} €",
        }
        st.dataframe(df_vendita.style.format(fmt_vendita), use_container_width=True, hide_index=True)

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
                    f"{fmt(sb.totale_inv)} €", f"{fmt(sb.equity_val)} €",
                    f"{fmt(sb.mutuo_val)} €" if sb.usa_mutuo else "Nessuno",
                    f"{fmt(sb.tasso * 100, 2)}%" if sb.usa_mutuo else "—",
                    f"{sb.anni_mut} anni" if sb.usa_mutuo else "—",
                    f"{fmt(sb.rata_m, 2)} €" if sb.usa_mutuo else "—",
                    f"{fmt(sb.affitto_lordo)} €",
                    f"{fmt(params.costi_fissi_annui)} €",
                    f"{fmt(sb.detrazione_annua_val)} €" if sb.flag_detrazioni else "Non applicata",
                    f"{sb.sfitto}%", f"{sb.capex_pct}%",
                    f"{fmt(sb.rivalutazione * 100, 2)}%" if sb.rivalutazione > 0 else "—",
                    f"{fmt(sb.prezzo_vendita_val)} €" if sb.prezzo_vendita_val > 0 else "—",
                    f"{fmt(sb.rend_etf * 100, 1)}%",
                    f"{fmt(sb.inflazione)}%",
                    f"Anno {best_year}" if best_year > 0 else "N/D",
                    f"{fmt(best_annual * 100, 2)}%" if best_year > 0 else "N/D",
                ],
            })
            riepilogo.to_excel(writer, sheet_name="Riepilogo", index=False)

            # ── Foglio Rendimenti ──
            rendimenti = pd.DataFrame({
                "Anno": df_rend["Anno"],
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
                params=params, totale_inv=sb.totale_inv, equity_val=sb.equity_val,
                mutuo_val=sb.mutuo_val, irr_val=irr_val,
                best_year=best_year, best_annual=best_annual,
                df_proj=df_proj, df_mutuo=df_mutuo, etf_puro=etf_puro,
                anni_sim=sb.anni_sim,
                rend_etf=sb.rend_etf, inflazione=sb.inflazione,
                rivalutazione=sb.rivalutazione, prezzo_vendita_val=sb.prezzo_vendita_val,
                sfitto=sb.sfitto, capex_pct=sb.capex_pct,
                flag_detrazioni=sb.flag_detrazioni, detrazione_annua_val=sb.detrazione_annua_val,
                aliquota_detr=sb.aliquota_detr, base_detr=sb.base_detr,
                work_items=WORK_ITEMS, work_qty=sb.work_qty,
                furn_items=FURN_ITEMS, furn_qty=sb.furn_qty,
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
