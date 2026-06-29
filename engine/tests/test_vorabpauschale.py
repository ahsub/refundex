"""
pytest test_vorabpauschale.py
Testet Vorabpauschale-Engine gegen § 18 InvStG Berechnungsregeln.
"""
import sys, pytest
sys.path.insert(0, '/home/claude')
from vorabpauschale import (
    berechne_vorabpauschale, compute_vorabpauschale,
    ETFPosition, BASISZINS, TEILFREISTELLUNG, _erster_werktag
)

# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def msci_world_thes():
    """Thesaurierender Aktienfonds mit Kursanstieg"""
    return ETFPosition(
        isin='IE00B4L5Y983', name='iShares MSCI World',
        fondstyp='aktien', anteile=100,
        kurs_01_01=80.0, kurs_31_12=88.0,
        ausschuettung=0, thesaurierend=True
    )

@pytest.fixture
def fonds_kursrueckgang():
    """Thesaurierender Fonds mit Kursrückgang → VP=0"""
    return ETFPosition(
        isin='TEST001', name='Verlusttopf ETF',
        fondstyp='aktien', anteile=100,
        kurs_01_01=100.0, kurs_31_12=90.0,
        ausschuettung=0, thesaurierend=True
    )

@pytest.fixture
def ausschuettend_hohe_div():
    """Ausschüttender Fonds: Div > Basisertrag → VP=0"""
    return ETFPosition(
        isin='TEST002', name='Hohe Ausschüttung ETF',
        fondstyp='aktien', anteile=100,
        kurs_01_01=100.0, kurs_31_12=103.0,
        ausschuettung=500.0,  # Deutlich mehr als Basisertrag
        thesaurierend=False
    )

# ── Basiszins-Tests ──────────────────────────────────────────────────────────

class TestBasiszins:
    def test_basiszins_2023_korrekt(self):
        assert abs(BASISZINS[2023] - 0.0255) < 0.0001

    def test_basiszins_2024_korrekt(self):
        assert abs(BASISZINS[2024] - 0.0229) < 0.0001

    def test_basiszins_negativ_jahre_null(self):
        """2020/2021/2022: Basiszins ≤ 0 → keine Vorabpauschale"""
        for jahr in [2020, 2021, 2022]:
            assert BASISZINS[jahr] <= 0, f'{jahr} sollte 0 sein'

    def test_basiszins_2025_positiv(self):
        assert BASISZINS[2025] > 0, '2025 Basiszins muss positiv sein'

# ── Teilfreistellungs-Tests ──────────────────────────────────────────────────

class TestTeilfreistellung:
    def test_aktien_30_prozent(self):
        assert TEILFREISTELLUNG['aktien'] == 0.30

    def test_misch_15_prozent(self):
        assert TEILFREISTELLUNG['misch'] == 0.15

    def test_immobilien_de_60_prozent(self):
        assert TEILFREISTELLUNG['immobilien_de'] == 0.60

    def test_immobilien_aus_80_prozent(self):
        """Ausländische Immobilienfonds: 80 % TFS — höher als Inland!"""
        assert TEILFREISTELLUNG['immobilien_aus'] == 0.80

    def test_anleihen_null_prozent(self):
        assert TEILFREISTELLUNG['anleihen'] == 0.00

# ── Berechnungstests ─────────────────────────────────────────────────────────

class TestBerechnung:

    def test_thesaurierend_vorabpauschale_positiv(self, msci_world_thes):
        """Thesaurierend + Kursanstieg → Vorabpauschale > 0"""
        r = berechne_vorabpauschale(msci_world_thes, 2025)
        assert r.vorabpauschale > 0

    def test_formel_basisertrag(self, msci_world_thes):
        """Basisertrag p.A. = Kurs × Basiszins × 0,70"""
        r = berechne_vorabpauschale(msci_world_thes, 2025)
        erwartet = 80.0 * BASISZINS[2025] * 0.70
        assert abs(r.basisertrag_pa - erwartet) < 0.0001

    def test_basisertrag_gesamt(self, msci_world_thes):
        """Basisertrag Gesamt = Basisertrag p.A. × Anteile"""
        r = berechne_vorabpauschale(msci_world_thes, 2025)
        assert abs(r.basisertrag_gesamt - r.basisertrag_pa * 100) < 0.01

    def test_wertzuwachsbegrenzung_aktiv(self, msci_world_thes):
        """Wenn Basisertrag < Wertzuwachs: keine Begrenzung"""
        r = berechne_vorabpauschale(msci_world_thes, 2025)
        # Wertzuwachs = (88-80) × 100 = 800 EUR >> Basisertrag ~141 EUR
        assert r.basisertrag_begr == r.basisertrag_gesamt  # Keine Begrenzung

    def test_kursrueckgang_keine_vorabpauschale(self, fonds_kursrueckgang):
        """Kursrückgang → Wertzuwachs = 0 → Vorabpauschale = 0"""
        r = berechne_vorabpauschale(fonds_kursrueckgang, 2025)
        assert r.vorabpauschale == 0.0
        assert r.steuerpflichtig == 0.0
        assert 'Wertzuwachs begrenzt' in r.hinweis

    def test_hohe_ausschuettung_keine_vorabpauschale(self, ausschuettend_hohe_div):
        """Ausschüttung > Basisertrag → Vorabpauschale = 0"""
        r = berechne_vorabpauschale(ausschuettend_hohe_div, 2025)
        assert r.vorabpauschale == 0.0

    def test_thesaurierend_ignoriert_ausschuettungsfeld(self):
        """Thesaurierend: ausschuettung-Feld wird ignoriert"""
        pos = ETFPosition('T', 'T', 'aktien', 100, 100.0, 105.0, 999.0, True)
        r = berechne_vorabpauschale(pos, 2025)
        assert r.ausschuettung == 0.0  # Feld wird auf 0 gesetzt

    def test_tfs_aktien_70_prozent_steuerpflichtig(self, msci_world_thes):
        """Aktienfonds: steuerpflichtig = Vorabpauschale × 0,70"""
        r = berechne_vorabpauschale(msci_world_thes, 2025)
        erwartet = round(r.vorabpauschale * 0.70, 2)
        assert abs(r.steuerpflichtig - erwartet) < 0.01

    def test_basiszins_null_keine_vorabpauschale(self, msci_world_thes):
        """Basiszins ≤ 0 (2020/21/22) → immer Vorabpauschale = 0"""
        for jahr in [2020, 2021, 2022]:
            r = berechne_vorabpauschale(msci_world_thes, jahr)
            assert r.vorabpauschale == 0.0, f'{jahr}: VP sollte 0 sein'

    def test_wertzuwachs_begrenzung_greift(self):
        """Basisertrag > Wertzuwachs → Basisertrag wird begrenzt"""
        # Kleiner Kursanstieg, viele Anteile → Wertzuwachs < Basisertrag
        pos = ETFPosition('T', 'T', 'aktien', 10000, 100.0, 100.01, 0, True)
        r = berechne_vorabpauschale(pos, 2025)
        # Basisertrag: 100 × 0.0253 × 0.7 × 10000 = 17.710 EUR
        # Wertzuwachs: 0.01 × 10000 = 100 EUR
        assert r.basisertrag_begr <= r.wertzuwachs + 0.01
        assert r.basisertrag_begr < r.basisertrag_gesamt
        assert 'Wertzuwachs begrenzt' in r.hinweis

# ── Fälligkeitstests ─────────────────────────────────────────────────────────

class TestFaelligkeit:
    def test_nie_neujahr(self):
        """01.01. ist immer Feiertag → Fälligkeit immer ≥ 02.01."""
        for jahr in range(2019, 2030):
            f = _erster_werktag(jahr)
            assert f[5:] >= '01-02', f'{jahr}: Fälligkeit {f} = Neujahr!'

    def test_kein_wochenende(self):
        """Fälligkeit darf kein Samstag oder Sonntag sein"""
        from datetime import date
        for jahr in range(2019, 2030):
            f = _erster_werktag(jahr)
            d = date.fromisoformat(f)
            assert d.weekday() < 5, f'{jahr}: Fälligkeit {f} ist Wochenende!'

    def test_2025_faelligkeit(self):
        """2025: 02.01.2026 ist Freitag → korrekte Fälligkeit"""
        from datetime import date
        f = _erster_werktag(2025)
        assert f == '2026-01-02'
        assert date.fromisoformat(f).weekday() == 4  # Freitag

# ── Report-Tests ─────────────────────────────────────────────────────────────

class TestReport:
    def test_leeres_portfolio(self):
        r = compute_vorabpauschale([], 2025)
        assert r.gesamt_brutto == 0.0
        assert r.gesamt_steuerpflichtig == 0.0
        assert r.keine_vorabpauschale

    def test_mehrere_positionen_summiert(self, msci_world_thes):
        pos2 = ETFPosition('IE00B3RBWM25', 'VG FTSE', 'aktien', 50,
                           110.0, 118.0, 95.0, False)
        r = compute_vorabpauschale([msci_world_thes, pos2], 2025)
        assert len(r.positionen) == 2
        assert r.gesamt_brutto == sum(e.vorabpauschale for e in r.positionen)

    def test_report_basiszins_korrekt(self):
        r = compute_vorabpauschale([], 2025)
        assert abs(r.basiszins - BASISZINS[2025]) < 0.0001
