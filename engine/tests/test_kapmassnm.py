"""
pytest test_kapmassnm.py
Testet Kapitalmaßnahmen-Engine gegen BubbleTax-Referenzwerte.
"""
import sys, pytest
sys.path.insert(0, '/home/claude')
from kapmassnm import compute_kapmassnm, _handle_spin_off, _handle_delisting, CorporateActionRaw

XMLS = [
    '/mnt/user-data/uploads/1782742593101_Steuerauswertung.xml',
    '/mnt/user-data/uploads/1782742593100_Steuerauswertung-2.xml',
    '/mnt/user-data/uploads/1782742593100_Steuerauswertung-3.xml',
]

@pytest.fixture(scope='module')
def report_2025():
    return compute_kapmassnm(XMLS, '2025')

@pytest.fixture(scope='module')
def report_2024():
    return compute_kapmassnm(XMLS, '2024')

# ── ENVXW 2025 ───────────────────────────────────────────────────────────────

class TestENVXW2025:

    def test_envxw_so_sachausch_bereich(self, report_2025):
        """Sachausschüttung ENVXW SO: BubbleTax +15*,** EUR → erwartet ~156 EUR"""
        so = [e for e in report_2025.ergebnisse if e.type == 'SO' and e.symbol == 'ENVXW']
        assert len(so) == 1, f'Erwarte genau 1 SO für ENVXW, gefunden: {len(so)}'
        s = so[0].sachausch_eur
        assert 145 < s < 170, f'ENVXW SO Sachausch {s:.2f} außerhalb [145, 170]'

    def test_envxw_to_steuerneutral(self, report_2025):
        """Tender Offer mit Aufzahlung ist steuerneutral (§ 20 Abs. 4a Satz 1)"""
        to = [e for e in report_2025.ergebnisse if e.type == 'TO' and e.symbol == 'ENVXW']
        assert len(to) == 1
        assert to[0].netto_eur == 0.0, f'ENVXW TO sollte 0 EUR sein, ist {to[0].netto_eur}'

    def test_envxw_dw_totalverlust(self, report_2025):
        """Delisting = Totalverlust der AK (0,5714 Stück)"""
        dw = [e for e in report_2025.ergebnisse if e.type == 'DW' and e.symbol == 'ENVXW']
        assert len(dw) == 1
        v = dw[0].realis_verlust
        assert -5 < v < 0, f'ENVXW DW Verlust {v:.2f} außerhalb [-5, 0]'

    def test_envxw_netto_positiv(self, report_2025):
        """Gesamtergebnis ENVXW: SO-Sachausch überwiegt DW-Verlust → positiv"""
        n = report_2025.gesamt_netto
        assert n > 0, f'ENVXW Netto {n:.2f} sollte positiv sein'

    def test_envxw_netto_bereich(self, report_2025):
        """BubbleTax zeigt +15*,** EUR Netto → erwartet 140-165 EUR"""
        n = report_2025.gesamt_netto
        assert 140 < n < 165, f'ENVXW Netto {n:.2f} außerhalb [140, 165]'

# ── 2024 Kapitalmaßnahmen ────────────────────────────────────────────────────

class TestKM2024:

    def test_solv_spinoff_value_null(self, report_2024):
        """SOLV Spin-Off (MMM→SOLV): IBKR value=0 → Fallback 0 EUR"""
        so = [e for e in report_2024.ergebnisse if e.type == 'SO' and e.symbol == 'SOLV']
        assert len(so) == 1
        assert so[0].sachausch_eur == 0.0, \
            f'SOLV SO sollte 0 EUR (kein IBKR-Wert), ist {so[0].sachausch_eur}'

    def test_bti_tausch_steuerneutral(self, report_2024):
        """BTI → BATS Tausch: steuerneutral"""
        to = [e for e in report_2024.ergebnisse if e.type == 'TO']
        for e in to:
            assert e.netto_eur == 0.0, f'TO {e.symbol} sollte 0 EUR sein'

# ── Unit-Tests direkte Funktionen ─────────────────────────────────────────────

class TestDirectFunctions:

    def test_handle_spinoff_mit_value(self):
        """SO mit IBKR-Wert berechnet korrekte Sachausschüttung"""
        ca = CorporateActionRaw(
            date='2025-07-17', type='SO', symbol='TEST', isin='US123',
            description='TEST SPINOFF', quantity=10.0,
            proceeds=0.0, value=100.0, currency='USD', fx_rate=0.9
        )
        result = _handle_spin_off(ca)
        assert result is not None
        assert abs(result.sachausch_eur - 90.0) < 0.01  # 100 USD × 0.9 = 90 EUR
        assert abs(result.ak_neu_eur - 90.0) < 0.01

    def test_handle_spinoff_ohne_value(self):
        """SO ohne IBKR-Wert → Fallback 0 EUR"""
        ca = CorporateActionRaw(
            date='2025-01-01', type='SO', symbol='TEST', isin='US123',
            description='TEST SPINOFF', quantity=5.0,
            proceeds=0.0, value=0.0, currency='USD', fx_rate=0.85
        )
        result = _handle_spin_off(ca)
        assert result is not None
        assert result.sachausch_eur == 0.0

    def test_handle_delisting_totalverlust(self):
        """DW berechnet korrekten Totalverlust"""
        ca = CorporateActionRaw(
            date='2025-09-29', type='DW', symbol='TEST', isin='US123',
            description='DELISTED', quantity=-2.0,
            proceeds=0.0, value=0.0, currency='USD', fx_rate=0.86
        )
        result = _handle_delisting(ca, ak_pro_stueck=10.0)
        assert result is not None
        assert abs(result.realis_verlust - (-20.0)) < 0.01  # 2 × 10 EUR = -20 EUR

    def test_handle_so_abgang_ignoriert(self):
        """SO mit negativer Menge (Abgang) wird übersprungen"""
        ca = CorporateActionRaw(
            date='2025-07-17', type='SO', symbol='TEST', isin='US123',
            description='...', quantity=-5.0,
            proceeds=0.0, value=100.0, currency='USD', fx_rate=0.9
        )
        result = _handle_spin_off(ca)
        assert result is None

