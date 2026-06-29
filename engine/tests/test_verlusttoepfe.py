"""
pytest test_verlusttoepfe.py
Testet die drei Verlustverrechnungstöpfe nach § 20 Abs. 6 EStG.
"""
import sys, pytest
sys.path.insert(0, '/home/claude')
from verlusttoepfe import (
    KapitaleinkunfteInput, VerlustvortragState,
    berechne_verlusttoepfe, TERMIN_VERLUST_CAP
)

# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def axel_2025():
    """Axels reales 2025-Portfolio"""
    return KapitaleinkunfteInput(
        steuerjahr=2025,
        stillhalter_praemien=27_532.11, stillhalter_glatt=-22_994.13,
        dividenden=3_722.47, zinsen=59.56, syep=8.31,
        fx_gewinne=135.55,  fx_verluste=-927.58,
        km_sachausch=156.24, km_gl=-3.12,
        quellensteuer_anr=280.36,
    )

@pytest.fixture
def nur_topf1():
    return KapitaleinkunfteInput(
        steuerjahr=2025,
        stillhalter_praemien=10_000.0, stillhalter_glatt=-3_000.0,
        dividenden=2_000.0, zinsen=500.0,
    )

# ── Topf 1: Allgemein ────────────────────────────────────────────────────────

class TestTopf1Allgemein:

    def test_einfache_gewinne(self, nur_topf1):
        erg = berechne_verlusttoepfe(nur_topf1)
        assert erg.kap_z19 == pytest.approx(9_500.0, abs=0.01)

    def test_kap_z22_nur_negative_posten(self, nur_topf1):
        """Z22 enthält nur die Verluste, nicht die Gewinne"""
        erg = berechne_verlusttoepfe(nur_topf1)
        # Nur stillhalter_glatt = -3.000 ist negativ
        assert erg.kap_z22 == pytest.approx(3_000.0, abs=0.01)

    def test_axel_kap19(self, axel_2025):
        """Axels KAP-19 mit allen Modulen"""
        erg = berechne_verlusttoepfe(axel_2025)
        # 27532.11 - 22994.13 + 3722.47 + 67.87 + 135.55 - 927.58 + 156.24 - 3.12
        assert erg.kap_z19 == pytest.approx(7_689.41, abs=0.05)

    def test_axel_kap22(self, axel_2025):
        erg = berechne_verlusttoepfe(axel_2025)
        # |stillhalter_glatt| + |fx_verluste| + |km_gl|
        assert erg.kap_z22 == pytest.approx(23_924.83, abs=0.05)

    def test_axel_kap41(self, axel_2025):
        erg = berechne_verlusttoepfe(axel_2025)
        assert erg.kap_z41 == pytest.approx(280.36, abs=0.01)

    def test_verlust_topf1_wird_vorgetragen(self):
        """Nettoverlust Topf 1 → KAP-19=0 + Vortrag"""
        inp = KapitaleinkunfteInput(
            steuerjahr=2025,
            dividenden=1_000.0,
            fx_verluste=-5_000.0,
        )
        erg = berechne_verlusttoepfe(inp)
        assert erg.kap_z19 == 0.0
        assert erg.vortrag_neu.allgemein == pytest.approx(-4_000.0, abs=0.01)

    def test_vortrag_vorjahr_wird_verrechnet(self):
        """Verlustvortrag aus Vorjahr mindert KAP-19"""
        inp = KapitaleinkunfteInput(steuerjahr=2025, dividenden=5_000.0)
        vv  = VerlustvortragState(allgemein=-2_000.0)
        erg = berechne_verlusttoepfe(inp, vortrag_vorjahr=vv)
        assert erg.kap_z19 == pytest.approx(3_000.0, abs=0.01)
        assert erg.vortrag_neu.allgemein == 0.0

# ── Topf 2: Aktien ───────────────────────────────────────────────────────────

class TestTopf2Aktien:

    def test_aktiengewinn_in_z20(self):
        inp = KapitaleinkunfteInput(
            steuerjahr=2025, aktien_gewinne=15_000.0)
        erg = berechne_verlusttoepfe(inp)
        assert erg.kap_z20 == pytest.approx(15_000.0, abs=0.01)

    def test_aktienverlust_wird_vorgetragen(self):
        """Aktienverlust ohne Gewinne → Vortrag, NICHT mit Topf 1 verrechnet"""
        inp = KapitaleinkunfteInput(
            steuerjahr=2025,
            dividenden=10_000.0,
            aktien_verluste=-8_000.0,
        )
        erg = berechne_verlusttoepfe(inp)
        assert erg.kap_z20 == 0.0
        assert erg.vortrag_neu.aktien == pytest.approx(-8_000.0, abs=0.01)
        # Dividenden bleiben in Topf 1 unberührt
        assert erg.kap_z19 == pytest.approx(10_000.0, abs=0.01)

    def test_aktien_getrennt_von_topf1(self):
        """§20 Abs. 6 Satz 4: Aktienverluste NICHT mit Zinsen verrechenbar"""
        inp = KapitaleinkunfteInput(
            steuerjahr=2025,
            zinsen=5_000.0,
            aktien_verluste=-20_000.0,
        )
        erg = berechne_verlusttoepfe(inp)
        assert erg.kap_z19 == pytest.approx(5_000.0, abs=0.01)  # Zinsen unbeeinflusst
        assert erg.kap_z20 == 0.0
        assert erg.vortrag_neu.aktien == pytest.approx(-20_000.0, abs=0.01)

    def test_vortrag_aktien_vorjahr(self):
        """Aktienvortrag aus Vorjahr nur mit Aktiengewinnen verrechenbar"""
        inp = KapitaleinkunfteInput(
            steuerjahr=2025,
            aktien_gewinne=12_000.0, aktien_verluste=-2_000.0,
        )
        vv = VerlustvortragState(aktien=-7_000.0)
        erg = berechne_verlusttoepfe(inp, vortrag_vorjahr=vv)
        # Netto: 12000 - 2000 - 7000 = 3000
        assert erg.kap_z20 == pytest.approx(3_000.0, abs=0.01)
        assert erg.vortrag_neu.aktien == 0.0

    def test_warnung_aktienverlust_mit_sonstigen(self):
        """Warnung wenn Aktienverluste UND andere Erträge vorhanden"""
        inp = KapitaleinkunfteInput(
            steuerjahr=2025, dividenden=3_000.0,
            aktien_gewinne=1_000.0, aktien_verluste=-5_000.0,
        )
        erg = berechne_verlusttoepfe(inp)
        assert any('§20 Abs. 6 Satz 4' in w for w in erg.warnungen)

# ── Topf 3: Termingeschäfte (§ 20 Abs. 6 Satz 5) ────────────────────────────

class TestTopf3Termingeschaefte:

    def test_cap_greift_bei_grossem_verlust(self):
        """30.000 EUR Verlust → nur 20.000 verrechenbar, 10.000 Vortrag"""
        inp = KapitaleinkunfteInput(
            steuerjahr=2025,
            termin_gewinne=25_000.0, termin_verluste=-30_000.0,
        )
        erg = berechne_verlusttoepfe(inp)
        assert erg.termin_cap_anwendbar
        assert erg.termin_verlust_vortrag_neu == pytest.approx(-10_000.0, abs=0.01)

    def test_cap_kein_vortrag_wenn_unter_grenze(self):
        """15.000 EUR Verlust → komplett verrechenbar, kein Vortrag"""
        inp = KapitaleinkunfteInput(
            steuerjahr=2025,
            termin_gewinne=20_000.0, termin_verluste=-15_000.0,
        )
        erg = berechne_verlusttoepfe(inp)
        assert erg.termin_verlust_vortrag_neu == 0.0

    def test_stillhalter_als_gegenrechnung(self):
        """Stillhalterprämien vergrößern die verrechenbaren Beträge"""
        inp = KapitaleinkunfteInput(
            steuerjahr=2025,
            stillhalter_praemien=15_000.0, stillhalter_glatt=-2_000.0,
            termin_verluste=-20_000.0,
        )
        erg = berechne_verlusttoepfe(inp)
        # Gegenrechnung = 15.000 (Stillhalter) + 0 (Termingewinn) = 15.000
        # Cap: min(20.000, 20.000) = 20.000, kann: min(20.000, 15.000) = 15.000
        assert erg.termin_verlust_verrechenbar == pytest.approx(-15_000.0, abs=0.01)
        assert erg.termin_verlust_vortrag_neu == pytest.approx(-5_000.0, abs=0.01)

    def test_vortrag_termin_vorjahr(self):
        """Terminvortrag aus Vorjahr erhöht die zu verrechnenden Verluste"""
        inp = KapitaleinkunfteInput(
            steuerjahr=2025,
            termin_gewinne=25_000.0, termin_verluste=-5_000.0,
        )
        vv  = VerlustvortragState(termingeschaefte=-18_000.0)
        erg = berechne_verlusttoepfe(inp, vortrag_vorjahr=vv)
        # Verlust total = -5.000 - 18.000 = -23.000
        # Cap: min(23.000, 20.000) = 20.000
        # Kann verrechnen: min(20.000, 25.000) = 20.000
        assert erg.termin_verlust_verrechenbar == pytest.approx(-20_000.0, abs=0.01)
        assert erg.termin_verlust_vortrag_neu == pytest.approx(-3_000.0, abs=0.01)

    def test_termin_gewinn_ohne_verlust_kein_cap(self):
        """Nur Termingewinne, kein Verlust → Cap nicht relevant"""
        inp = KapitaleinkunfteInput(
            steuerjahr=2025, termin_gewinne=10_000.0)
        erg = berechne_verlusttoepfe(inp)
        assert not erg.termin_cap_anwendbar

    def test_termingeschaefte_nicht_mit_topf1_verwechseln(self):
        """Terminverluste gehen in Topf 3, NICHT in Topf 1-Verluste"""
        inp = KapitaleinkunfteInput(
            steuerjahr=2025,
            dividenden=5_000.0,
            termin_verluste=-25_000.0,  # Über Cap
        )
        erg = berechne_verlusttoepfe(inp)
        # Dividenden bleiben in Topf 1, werden durch Terminverluste nicht reduziert
        assert erg.kap_z19 == pytest.approx(5_000.0, abs=0.01)
        # Aber Terminvortrag entsteht
        assert erg.vortrag_neu.termingeschaefte < 0

    def test_warnung_bei_cap_ueberschreitung(self):
        inp = KapitaleinkunfteInput(
            steuerjahr=2025, termin_verluste=-25_000.0)
        erg = berechne_verlusttoepfe(inp)
        assert any('20.000 EUR-Cap' in w for w in erg.warnungen)

# ── Sparer-Pauschbetrag ───────────────────────────────────────────────────────

class TestSparerPauschbetrag:

    def test_pausch_mindert_kap19(self):
        inp = KapitaleinkunfteInput(steuerjahr=2025, dividenden=3_000.0)
        erg = berechne_verlusttoepfe(inp, sparer_pauschs=1_000.0)
        assert erg.kap_z19 == pytest.approx(3_000.0, abs=0.01)
        assert erg.kap_z19_nach_sparer == pytest.approx(2_000.0, abs=0.01)

    def test_pausch_nicht_unter_null(self):
        inp = KapitaleinkunfteInput(steuerjahr=2025, dividenden=500.0)
        erg = berechne_verlusttoepfe(inp, sparer_pauschs=1_000.0)
        assert erg.kap_z19_nach_sparer == 0.0  # max(0, 500-1000) = 0

    def test_gemeinschaftskonto_halbierung(self, axel_2025):
        """Gemeinschaftskonto: alle Werte ×0,5"""
        erg = berechne_verlusttoepfe(axel_2025)
        assert abs(erg.kap_z19 * 0.5 - erg.kap_z19 / 2) < 0.01

# ── Verlustvortrag Persistenz ─────────────────────────────────────────────────

class TestVerlustvortragState:

    def test_to_dict_from_dict_roundtrip(self):
        vv = VerlustvortragState(allgemein=-500.0, aktien=-1_000.0,
                                  termingeschaefte=-8_000.0)
        recovered = VerlustvortragState.from_dict(vv.to_dict())
        assert recovered.allgemein == -500.0
        assert recovered.aktien == -1_000.0
        assert recovered.termingeschaefte == -8_000.0

    def test_leerer_vortrag_ist_null(self):
        vv = VerlustvortragState()
        assert vv.allgemein == 0.0
        assert vv.aktien == 0.0
        assert vv.termingeschaefte == 0.0

    def test_neuer_vortrag_nach_berechnung(self):
        inp = KapitaleinkunfteInput(
            steuerjahr=2025, dividenden=1_000.0, fx_verluste=-4_000.0)
        erg = berechne_verlusttoepfe(inp)
        assert erg.vortrag_neu.allgemein == pytest.approx(-3_000.0, abs=0.01)
        assert erg.vortrag_neu.aktien == 0.0
        assert erg.vortrag_neu.termingeschaefte == 0.0
