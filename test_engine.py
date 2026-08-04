import math

import numpy as np
import pandas as pd
import pytest

from engine import (
    InvestmentParams,
    calcola_irr,
    calcola_npv,
    calcola_rapporto_rata_reddito,
    calcola_ltv_massimo,
    calcola_costo_extra_taeg,
    crossover_leva_etf,
    flussi_per_irr,
    piano_ammortamento,
    proiezione,
    rata_mensile,
    scenario_cash,
    verifica_limite_eta,
    verifica_ltv,
    verifica_rata_reddito,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _default_params(**overrides) -> InvestmentParams:
    defaults = dict(
        prezzo=70000, imposte=1140, notaio=3000, agenzia_acquisto=3660,
        lavori=41468, compenso_tecnico=5000, oneri_urbanistici=6393, arredo=11598,
        usa_mutuo=True, equity=50000, importo_mutuo=82201,
        tasso_interesse=0.035, anni_mutuo=20,
        affitto_lordo_annuo=8400, cedolare=840, imu=263,
        condominio=300, altro_costi=552,
        flag_detrazioni=True, detrazione_annua=2643, anni_detrazione=10,
        sfitto_pct=5, capex_pct=5, rivalutazione_annua=0.015,
        rendimento_etf=0.07, anni_simulazione=20, inflazione_annua=0.02,
        agenzia_vendita_pct=3.0, prezzo_vendita=0.0,
        agenzia_vendita_fissa=0.0,
        eta_richiedente=30, costo_assicurazione=0.0, costo_perizia=0.0,
        classe_ape="altro", taeg=0.0, reddito_mensile=0.0,
    )
    defaults.update(overrides)
    return InvestmentParams(**defaults)


@pytest.fixture
def params():
    return _default_params()


# ---------------------------------------------------------------------------
# InvestmentParams
# ---------------------------------------------------------------------------

class TestInvestmentParams:
    def test_totale_investimento(self, params):
        assert params.totale_investimento == 70000 + 1140 + 3000 + 3660 + 41468 + 5000 + 6393 + 11598

    def test_costi_fissi_annui(self, params):
        assert params.costi_fissi_annui == 840 + 263 + 300 + 552


# ---------------------------------------------------------------------------
# rata_mensile
# ---------------------------------------------------------------------------

class TestRataMensile:
    def test_basic(self):
        rata = rata_mensile(100000, 0.03, 20)
        assert 500 < rata < 600

    def test_zero_capitale(self):
        assert rata_mensile(0, 0.03, 20) == 0.0

    def test_zero_tasso(self):
        assert rata_mensile(100000, 0, 20) == 0.0

    def test_zero_anni(self):
        assert rata_mensile(100000, 0.03, 0) == 0.0

    def test_negative_values(self):
        assert rata_mensile(-100000, 0.03, 20) == 0.0

    def test_known_value(self):
        # 100k, 5%, 10 years → 1060.66/month
        rata = rata_mensile(100000, 0.05, 10)
        assert abs(rata - 1060.66) < 0.01


# ---------------------------------------------------------------------------
# piano_ammortamento
# ---------------------------------------------------------------------------

class TestPianoAmmortamento:
    def test_empty_when_no_loan(self):
        df = piano_ammortamento(0, 0.03, 20)
        assert df.empty

    def test_columns(self, params):
        df = piano_ammortamento(params.importo_mutuo, params.tasso_interesse, params.anni_mutuo)
        expected = {"Anno", "Rata_Mensile", "Rata_Annua", "Quota_Capitale_Annua", "Quota_Interessi_Annua", "Capitale_Residuo"}
        assert set(df.columns) == expected

    def test_rows_count(self, params):
        df = piano_ammortamento(params.importo_mutuo, params.tasso_interesse, params.anni_mutuo)
        assert len(df) == params.anni_mutuo

    def test_final_balance_zero(self, params):
        df = piano_ammortamento(params.importo_mutuo, params.tasso_interesse, params.anni_mutuo)
        assert df.iloc[-1]["Capitale_Residuo"] < 1.0

    def test_principal_sums_to_loan(self, params):
        df = piano_ammortamento(params.importo_mutuo, params.tasso_interesse, params.anni_mutuo)
        assert abs(df["Quota_Capitale_Annua"].sum() - params.importo_mutuo) < 1.0

    def test_annual_payment_constant(self, params):
        df = piano_ammortamento(params.importo_mutuo, params.tasso_interesse, params.anni_mutuo)
        assert df["Rata_Annua"].nunique() == 1


# ---------------------------------------------------------------------------
# calcola_irr
# ---------------------------------------------------------------------------

class TestCalcolaIRR:
    def test_known_positive_irr(self):
        # Invest 100, get 110 after 1 year → IRR = 10%
        irr = calcola_irr([-100, 110])
        assert abs(irr - 0.10) < 1e-6

    def test_zero_cashflows(self):
        assert calcola_irr([]) is None

    def test_single_cashflow(self):
        assert calcola_irr([-100]) is None

    def test_all_negative(self):
        irr = calcola_irr([-100, -50, -30])
        assert irr is None

    def test_negative_irr(self):
        # Invest 100, get 90 → IRR = -10%
        irr = calcola_irr([-100, 90])
        assert abs(irr - (-0.10)) < 1e-4


# ---------------------------------------------------------------------------
# calcola_npv
# ---------------------------------------------------------------------------

class TestCalcolaNPV:
    def test_known_npv(self):
        # Invest 100, get 110 in 1 year, discount 10% → NPV = 0
        npv = calcola_npv([-100, 110], 0.10)
        assert abs(npv) < 1e-6

    def test_positive_npv(self):
        npv = calcola_npv([-100, 120], 0.10)
        assert npv > 0

    def test_negative_npv(self):
        npv = calcola_npv([-100, 105], 0.10)
        assert npv < 0


# ---------------------------------------------------------------------------
# flussi_per_irr
# ---------------------------------------------------------------------------

class TestFlussiPerIRR:
    def test_length(self, params):
        df = proiezione(params)
        flussi = flussi_per_irr(df, params.equity)
        assert len(flussi) == len(df) + 1

    def test_first_is_negative_equity(self, params):
        df = proiezione(params)
        flussi = flussi_per_irr(df, params.equity)
        assert flussi[0] == -params.equity

    def test_last_includes_realizzo(self, params):
        df = proiezione(params)
        flussi = flussi_per_irr(df, params.equity)
        last_cf = df.iloc[-1]["CF_Netto_Anno"] + df.iloc[-1]["Realizzo_Netto"]
        assert abs(flussi[-1] - last_cf) < 1e-6


# ---------------------------------------------------------------------------
# proiezione
# ---------------------------------------------------------------------------

class TestProiezione:
    def test_rows_count(self, params):
        df = proiezione(params)
        assert len(df) == params.anni_simulazione

    def test_columns(self, params):
        df = proiezione(params)
        expected = {
            "Anno", "Affitto_Effettivo", "Costi_Fissi", "Rata_Mutuo",
            "Detrazione", "CapEx_Accantonato", "CF_Netto_Anno", "CF_Cumulato",
            "Capitale_Residuo_Mutuo", "Valore_Immobile", "Realizzo_Netto",
            "Guadagno_Netto_Immobile", "Guadagno_Netto_ETF",
        }
        assert set(df.columns) == expected

    def test_property_value_grows(self, params):
        df = proiezione(params)
        assert df.iloc[-1]["Valore_Immobile"] > df.iloc[0]["Valore_Immobile"]

    def test_cumulative_cf_increases(self, params):
        df = proiezione(params)
        assert df.iloc[-1]["CF_Cumulato"] > df.iloc[0]["CF_Cumulato"]

    def test_inflation_effect(self):
        p_no_infl = _default_params(inflazione_annua=0.0)
        p_infl = _default_params(inflazione_annua=0.03)
        df_no = proiezione(p_no_infl)
        df_yes = proiezione(p_infl)
        # With inflation, later-year costs should be higher
        assert df_yes.iloc[-1]["Costi_Fissi"] > df_no.iloc[-1]["Costi_Fissi"]

    def test_detrazioni_stop(self, params):
        df = proiezione(params)
        # Year 11+ should have zero deduction
        assert df[df["Anno"] == 11].iloc[0]["Detrazione"] == 0.0
        assert df[df["Anno"] == 1].iloc[0]["Detrazione"] > 0.0

    def test_prezzo_vendita_rivalutato(self):
        prezzo_vendita = 100000.0
        rivalutazione = 0.03
        p = _default_params(
            prezzo_vendita=prezzo_vendita,
            rivalutazione_annua=rivalutazione,
            agenzia_vendita_pct=0.0,
            agenzia_vendita_fissa=0.0,
        )
        df = proiezione(p)
        for _, row in df.iterrows():
            t = int(row["Anno"])
            expected = prezzo_vendita * (1 + rivalutazione) ** t
            assert abs(row["Valore_Immobile"] - expected) < 0.01, (
                f"Anno {t}: atteso {expected:.2f}, trovato {row['Valore_Immobile']:.2f}"
            )


# ---------------------------------------------------------------------------
# scenario_cash
# ---------------------------------------------------------------------------

class TestScenarioCash:
    def test_no_mortgage_payments(self, params):
        df = scenario_cash(params)
        assert (df["Rata_Mutuo"] == 0).all()

    def test_same_length(self, params):
        df = scenario_cash(params)
        assert len(df) == params.anni_simulazione


# ---------------------------------------------------------------------------
# Verifiche bancarie e nuovi campi
# ---------------------------------------------------------------------------

class TestValidazioneBancaria:
    def test_limite_eta_ok(self):
        ok, msg = verifica_limite_eta(27, 20)
        assert ok
        assert "OK" in msg

    def test_limite_eta_ko(self):
        ok, msg = verifica_limite_eta(70, 20)
        assert not ok
        assert "ERRORE" in msg

    def test_limite_eta_boundary(self):
        ok, msg = verifica_limite_eta(60, 20)
        assert ok

    def test_ltv_ok(self):
        ok, msg = verifica_ltv(120000, 150000)
        assert ok
        assert abs(calcola_ltv_massimo(120000, 150000) - 80.0) < 0.01

    def test_ltv_ko(self):
        ok, msg = verifica_ltv(140000, 150000)
        assert not ok

    def test_ltv_exact_boundary(self):
        ok, msg = verifica_ltv(120000, 150000, max_ltv=80.0)
        assert ok

    def test_rapporto_rata_reddito_ok(self):
        ok, msg = verifica_rata_reddito(687, 2000)
        assert ok

    def test_rapporto_rata_reddito_ko(self):
        ok, msg = verifica_rata_reddito(900, 2000)
        assert not ok

    def test_rapporto_rata_reddito_zero_reddito(self):
        assert calcola_rapporto_rata_reddito(500, 0) == 0.0

    def test_costo_extra_taeg(self):
        extra = calcola_costo_extra_taeg(120000, 0.0335, 0.0356, 20)
        assert extra > 2000  # should be ~3100€

    def test_costo_extra_taeg_zero(self):
        assert calcola_costo_extra_taeg(100000, 0.03, 0.0, 20) == 0.0


class TestTassoEffettivo:
    def test_ape_discount(self):
        p = _default_params(tasso_interesse=0.035, classe_ape="A/B")
        expected = 0.035 - 0.004  # 3.10%
        assert abs(p.tasso_effettivo - expected) < 1e-10

    def test_ape_no_discount(self):
        p = _default_params(tasso_interesse=0.035, classe_ape="altro")
        assert abs(p.tasso_effettivo - 0.035) < 1e-10

    def test_ape_discount_floor(self):
        p = _default_params(tasso_interesse=0.003, classe_ape="A/B")
        assert abs(p.tasso_effettivo - 0.003) < 1e-10  # non scende sotto 0

    def test_rata_con_ape(self):
        """Con APE A/B il tasso effettivo è più basso → rata minore."""
        p_no_ape = _default_params(importo_mutuo=120000, tasso_interesse=0.0335, classe_ape="altro", anni_mutuo=20)
        p_ape = _default_params(importo_mutuo=120000, tasso_interesse=0.0335, classe_ape="A/B", anni_mutuo=20)
        assert p_no_ape.rata_mensile > p_ape.rata_mensile


class TestNuoviCampi:
    def test_totale_investimento_con_assicurazione(self):
        p = _default_params(costo_assicurazione=500, costo_perizia=180)
        base = 70000 + 1140 + 3000 + 3660 + 41468 + 5000 + 6393 + 11598
        assert p.totale_investimento == base + 500 + 180


# ---------------------------------------------------------------------------
# crossover_leva_etf
# ---------------------------------------------------------------------------

class TestCrossoverLevaETF:
    def _df(self, guadagni, anni=None):
        anni = anni or list(range(1, len(guadagni) + 1))
        return pd.DataFrame({"Anno": anni, "Guadagno_Netto_Immobile": guadagni})

    def test_sorpasso_dentro_orizzonte(self):
        # La leva vince fino all'anno 3, poi l'ETF prende il sopravvento
        df = self._df([10000, 12000, 15000, 14000, 13000])
        etf = np.array([9000, 11000, 14000, 16000, 19000])
        r = crossover_leva_etf(df, etf)
        assert r["esito"] == "sorpasso"
        assert r["ultimo_anno_vantaggio"] == 3
        assert 3.0 < r["anno_sorpasso"] < 4.0

    def test_leva_vince_sempre(self):
        df = self._df([10000, 12000, 15000, 18000, 22000])
        etf = np.array([9000, 11000, 14000, 17000, 21000])
        r = crossover_leva_etf(df, etf)
        assert r["esito"] == "leva_vince_sempre"
        assert r["ultimo_anno_vantaggio"] == 5
        assert r["anno_sorpasso"] is None

    def test_etf_vince_sempre(self):
        df = self._df([10000, 12000, 15000, 14000, 13000])
        etf = np.array([11000, 13000, 16000, 18000, 20000])
        r = crossover_leva_etf(df, etf)
        assert r["esito"] == "etf_vince_sempre"
        assert r["ultimo_anno_vantaggio"] is None
        assert r["anno_sorpasso"] == 1.0

    def test_etf_supera_senza_pareggio_mai(self):
        # diff sempre < 0 ma mai pari: esito comunque etf_vince_sempre
        df = self._df([5000, 6000])
        etf = np.array([6000, 6500])
        r = crossover_leva_etf(df, etf)
        assert r["esito"] == "etf_vince_sempre"

    def test_input_vuoti(self):
        r = crossover_leva_etf(None, np.array([1.0]))
        assert r["esito"] == "n/d"
        r = crossover_leva_etf(self._df([1000]), None)
        assert r["esito"] == "n/d"

    def test_sorpasso_esatto_anno_intero(self):
        # Ultimo vantaggio all'anno 3, anno 4 l'ETF prende il sopravvento
        df = self._df([10000, 12000, 14000, 14000])
        etf = np.array([9000, 11000, 13999, 16000])
        r = crossover_leva_etf(df, etf)
        assert r["esito"] == "sorpasso"
        assert r["ultimo_anno_vantaggio"] == 3
