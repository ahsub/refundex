"""
pytest test_vorabpauschale.py
Testet Vorabpauschale-Engine gegen § 18 InvStG Berechnungsregeln.
Basiszins-Werte offiziell verifiziert gegen BMF-Schreiben.
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
    return ETFPosition(
        isin='IE00B4L5Y983', name='iShares MSCI World',
        fondstyp='aktien', anteile=100,
        kurs_01_01=80.0, kurs_31_12=88.0,
        ausschuettung=0, thesaurierend=True
    )

@pytest.fixture
def fonds_kursrueckgang():
    return ETFPosition(
        isin='TEST001', name='Verlusttopf ETF',
        fondstyp='aktien', anteile=100,
        kurs_01_01=100.0, kurs_31_12=90.0,
        ausschuettung=0, thesaurierend=True
    )

@pytest.fixture
def ausschuettend_hohe_div():
    return ETFPosition(
        isin='TEST002', name='Hohe Ausschuettung ETF',
        fondstyp='aktien', anteile=100,
        kurs_01_01=100.0, kurs_31_12=103.0,
        ausschuettung=500.0, thesaurierend=False
    )

# ── Basiszins-Tests (offiziell verifiziert) ───────────────────────────────────

class TestBasiszins:
    def test_basiszins_2023_korrekt(self):
        # 2,55 % — BMF-Schreiben Jan 2023
        assert abs(BASISZINS[2023] - 0.0255) < 0.0001

    def test_basiszins_2024_korrekt(self):
        # 2,29 % — BMF-Schreiben Jan 2024
        assert abs(BASISZINS[2024] - 0.0229) < 0.0001

    def test_basiszins_2025_korrekt(self):
        # 2,53 % — BMF-Schreiben 10.01.2025 (GZ IV C 1 - S 1980/00230/009/002)
        assert abs(BASISZINS[2025] - 0.0253) < 0.0001

    def test_basiszins_2026_korrekt(self):
        # 3,20 % — BMF-Schreiben 13.01.2026 (GZ IV C 1 - S 1980/00230/012/001)
        assert abs(BASISZINS[2026] - 0.0320) < 0.0001

    def test_basiszins_negativ_jahre_null(self):
        for jahr in [2020, 2021, 2022]:
            assert BASISZINS[jahr] <= 0

# ── Teilfreistellungs-Tests ──────────────────────────────────────────────────

class TestTeilfreistellung:
    def test_aktien_30_prozent(self):
        assert TEILFREISTELLUNG['aktien'] == 0.30

    def test_misch_15_prozent(self):
        assert TEILFREISTELLUNG['misch'] == 0.15

    def test_immobilien_de_60_prozent(self):
        assert TEILFREISTELLUNG['immobilien_de'] == 0.60

    def test_immobilien_aus_80_prozent(self):
        assert TEILFREISTELLUNG['immobilien_aus'] == 0.80

    def test_anleihen_null_prozent(self):
        assert TEILFREISTELLUNG['anleihen'] == 0.00

# ── Berechnungstests ─────────────────────────────────────────────────────────

class TestBerechnung:
    def test_thesaurierend_vorabpauschale_positiv(self, msci_world_thes):
        r = berechne_vorabpauschale(msci_world_thes, 2025)
        assert r.vorabpauschale > 0

    def test_formel_basisertrag(self, msci_world_thes):
        r = berechne_vorabpauschale(msci_world_thes, 2025)
        erwartet = 80.0 * BASISZINS[2025] * 0.70
        assert abs(r.basisertrag_pa - erwartet) < 0.0001

    def test_basisertrag_gesamt(self, msci_world_thes):
        r = berechne_vorabpauschale(msci_world_thes, 2025)
        assert abs(r.basisertrag_gesamt - r.basisertrag_pa * 100) < 0.01

    def test_wertzuwachsbegrenzung_aktiv(self, msci_world_thes):
        r = berechne_vorabpauschale(msci_world_thes, 2025)
        assert r.basisertrag_begr == r.basisertrag_gesamt

    def test_kursrueckgang_keine_vorabpauschale(self, fonds_kursrueckgang):
        r = berechne_vorabpauschale(fonds_kursrueckgang, 2025)
        assert r.vorabpauschale == 0.0
        assert 'Wertzuwachs begrenzt' in r.hinweis

    def test_hohe_ausschuettung_keine_vorabpauschale(self, ausschuettend_hohe_div):
        r = berechne_vorabpauschale(ausschuettend_hohe_div, 2025)
        assert r.vorabpauschale == 0.0

    def test_thesaurierend_ignoriert_ausschuettungsfeld(self):
        pos = ETFPosition('T', 'T', 'aktien', 100, 100.0, 105.0, 999.0, True)
        r = berechne_vorabpauschale(pos, 2025)
        assert r.ausschuettung == 0.0

    def test_tfs_aktien_70_prozent_steuerpflichtig(self, msci_world_thes):
        r = berechne_vorabpauschale(msci_world_thes, 2025)
        erwartet = round(r.vorabpauschale * 0.70, 2)
        assert abs(r.steuerpflichtig - erwartet) < 0.01

    def test_basiszins_null_keine_vorabpauschale(self, msci_world_thes):
        for jahr in [2020, 2021, 2022]:
            r = berechne_vorabpauschale(msci_world_thes, jahr)
            assert r.vorabpauschale == 0.0

    def test_wertzuwachs_begrenzung_greift(self):
        pos = ETFPosition('T', 'T', 'aktien', 10000, 100.0, 100.01, 0, True)
        r = berechne_vorabpauschale(pos, 2025)
        assert r.basisertrag_begr <= r.wertzuwachs + 0.01
        assert 'Wertzuwachs begrenzt' in r.hinweis

    def test_2026_hoehere_vorabpauschale_als_2025(self, msci_world_thes):
        # 3,20 % > 2,53 % → VP 2026 höher als 2025
        r25 = berechne_vorabpauschale(msci_world_thes, 2025)
        r26 = berechne_vorabpauschale(msci_world_thes, 2026)
        assert r26.vorabpauschale > r25.vorabpauschale

# ── Fälligkeitstests ─────────────────────────────────────────────────────────

class TestFaelligkeit:
    def test_nie_neujahr(self):
        for jahr in range(2019, 2030):
            f = _erster_werktag(jahr)
            assert f[5:] >= '01-02', f'{jahr}: Fälligkeit {f} = Neujahr!'

    def test_kein_wochenende(self):
        from datetime import date
        for jahr in range(2019, 2030):
            d = date.fromisoformat(_erster_werktag(jahr))
            assert d.weekday() < 5, f'{jahr}: {_erster_werktag(jahr)} ist Wochenende!'

    def test_2025_faelligkeit(self):
        # 02.01.2026 ist Freitag
        from datetime import date
        f = _erster_werktag(2025)
        assert f == '2026-01-02'
        assert date.fromisoformat(f).weekday() == 4  # Freitag

    def test_2026_faelligkeit(self):
        # 01./02./03.01.2027 = Neujahr/Sa/So → 04.01.2027 (Montag)
        from datetime import date
        f = _erster_werktag(2026)
        assert f == '2027-01-04'
        assert date.fromisoformat(f).weekday() == 0  # Montag

# ── Report-Tests ─────────────────────────────────────────────────────────────

class TestReport:
    def test_leeres_portfolio(self):
        r = compute_vorabpauschale([], 2025)
        assert r.gesamt_brutto == 0.0
        assert r.keine_vorabpauschale

    def test_mehrere_positionen_summiert(self, msci_world_thes):
        pos2 = ETFPosition('IE00B3RBWM25','VG FTSE','aktien',50,110.0,118.0,95.0,False)
        r = compute_vorabpauschale([msci_world_thes, pos2], 2025)
        assert len(r.positionen) == 2
        assert r.gesamt_brutto == sum(e.vorabpauschale for e in r.positionen)

    def test_report_basiszins_2025(self):
        r = compute_vorabpauschale([], 2025)
        assert abs(r.basiszins - 0.0253) < 0.0001

    def test_report_basiszins_2026(self):
        r = compute_vorabpauschale([], 2026)
        assert abs(r.basiszins - 0.0320) < 0.0001
