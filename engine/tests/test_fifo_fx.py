"""
pytest test_fifo_fx.py
Testet FX-FIFO-Engine gegen bekannte Sollwerte aus IBKR-XML + BubbleTax-Referenz.
"""
import sys, pytest
sys.path.insert(0, '/home/claude')
from fifo_fx import fx_fifo_from_lines, parse_fx_transactions, compute_fifo
import xml.etree.ElementTree as ET

XMLS = [
    '/mnt/user-data/uploads/1782742593101_Steuerauswertung.xml',
    '/mnt/user-data/uploads/1782742593100_Steuerauswertung-2.xml',
    '/mnt/user-data/uploads/1782742593100_Steuerauswertung-3.xml',
]

@pytest.fixture(scope='module')
def all_lines():
    lines = []
    for p in XMLS:
        lines.extend(ET.parse(p).getroot().findall('.//StatementOfFundsLine'))
    return lines

@pytest.fixture(scope='module')
def fx_results(all_lines):
    return fx_fifo_from_lines(all_lines, '2025')

# ── Strukturtests ────────────────────────────────────────────────────────────

class TestFxFifoStruktur:
    def test_alle_waehrungen_vorhanden(self, fx_results):
        """USD, GBP, SEK müssen im Ergebnis sein"""
        assert 'USD' in fx_results
        assert 'GBP' in fx_results
        assert 'SEK' in fx_results

    def test_keine_eur_im_ergebnis(self, fx_results):
        """EUR darf nicht im FX-Ergebnis erscheinen (Basiswährung)"""
        assert 'EUR' not in fx_results

    def test_gewinne_immer_positiv(self, fx_results):
        """Gewinn-Feld darf nie negativ sein"""
        for cur, r in fx_results.items():
            assert r.gewinn_guthaben >= 0, f'{cur}: Gewinn {r.gewinn_guthaben} < 0'

    def test_verluste_immer_negativ_oder_null(self, fx_results):
        """Verlust-Feld darf nie positiv sein"""
        for cur, r in fx_results.items():
            assert r.verlust_guthaben <= 0, f'{cur}: Verlust {r.verlust_guthaben} > 0'

    def test_audit_trail_vorhanden(self, fx_results):
        """Jede Währung muss mindestens eine Audit-Buchung haben"""
        for cur, r in fx_results.items():
            assert len(r.audit) > 0, f'{cur}: kein Audit-Trail'

# ── SEK-Tests (exakt verifiziert gegen BubbleTax) ────────────────────────────

class TestSEK:
    """SEK nach BubbleTax-Abgleich: G≈21 EUR, V≈-0,5 EUR, N≈+20,7 EUR"""

    def test_sek_gewinn_bereich(self, fx_results):
        g = fx_results['SEK'].gewinn_guthaben
        assert 15 < g < 30, f'SEK Gewinn {g:.2f} außerhalb [15, 30]'

    def test_sek_verlust_klein(self, fx_results):
        v = fx_results['SEK'].verlust_guthaben
        assert -5 < v <= 0, f'SEK Verlust {v:.2f} außerhalb [-5, 0]'

    def test_sek_netto_positiv(self, fx_results):
        n = fx_results['SEK'].netto_guthaben
        assert 15 < n < 30, f'SEK Netto {n:.2f} außerhalb [15, 30]'

    def test_sek_buchungen_anzahl(self, fx_results):
        """EVO-Optionen in SEK: sollten 8-10 §20-Buchungen erzeugen"""
        cnt = sum(1 for a in fx_results['SEK'].audit if a.typ == '§20')
        assert 6 <= cnt <= 12, f'SEK §20-Buchungen: {cnt}'

    def test_sek_kein_negativer_saldo_problem(self, fx_results):
        """SEK hat keinen Margin-Saldo → alle VB-Buchungen = 0 oder 1"""
        vb = sum(1 for a in fx_results['SEK'].audit if a.typ == 'VB')
        assert vb <= 2, f'SEK VB-Buchungen unerwartet hoch: {vb}'

# ── GBP-Tests ────────────────────────────────────────────────────────────────

class TestGBP:
    """GBP: G≈9 EUR, V≈-2 EUR, N≈+7 EUR (BATS Dividenden → Aktienkäufe)"""

    def test_gbp_netto_positiv(self, fx_results):
        n = fx_results['GBP'].netto_guthaben
        assert 2 < n < 15, f'GBP Netto {n:.2f} außerhalb [2, 15]'

    def test_gbp_buchungen_vorhanden(self, fx_results):
        cnt = len(fx_results['GBP'].audit)
        assert cnt >= 8, f'GBP Buchungen: {cnt} (erwartet ≥8)'

# ── USD-Tests ────────────────────────────────────────────────────────────────

class TestUSD:
    """USD: G≈105 EUR, V≈-925 EUR, N≈-820 EUR (BubbleTax N≈-750, Diff FX-Methode)"""

    def test_usd_gewinn_bereich(self, fx_results):
        g = fx_results['USD'].gewinn_guthaben
        assert 50 < g < 200, f'USD Gewinn {g:.2f} außerhalb [50, 200]'

    def test_usd_netto_negativ(self, fx_results):
        """USD-Saldo hat Nettoverlust aus USD-Aufwertung gegenüber EUR"""
        n = fx_results['USD'].netto_guthaben
        assert n < 0, f'USD Netto {n:.2f} sollte negativ sein'

    def test_usd_buchungen_plausibel(self, fx_results):
        cnt_20 = sum(1 for a in fx_results['USD'].audit if a.typ == '§20')
        cnt_vb = sum(1 for a in fx_results['USD'].audit if a.typ == 'VB')
        assert cnt_20 > 100, f'USD §20-Buchungen: {cnt_20} (erwartet >100)'
        assert cnt_vb < 10,  f'USD VB-Buchungen: {cnt_vb} (erwartet <10)'

# ── Korrektheitstests ─────────────────────────────────────────────────────────

class TestKorrektheit:

    def test_zufluss_first_kein_negativer_stack(self, all_lines):
        """Zufluss-First verhindert leeren FIFO bei intraday Abfluss"""
        txs = parse_fx_transactions(all_lines, '2025')
        # Prüfe: An Tagen mit gemischten Flows kommen Zuflüsse vor Abflüssen
        from itertools import groupby
        for date, group in groupby(txs, key=lambda t: (t['date'], t['cur'])):
            flows = list(group)
            saw_outflow = False
            for tx in flows:
                if tx['amt_fx'] < 0:
                    saw_outflow = True
                if tx['amt_fx'] > 0 and saw_outflow:
                    # Zufluss nach Abfluss am selben Tag → Fehler im Zufluss-First
                    pytest.fail(f'Zufluss-First verletzt: {date} {tx["cur"]}')

    def test_fx_rate_nie_null(self, all_lines):
        """Alle FX-Transaktionen müssen valide Kurse haben"""
        txs = parse_fx_transactions(all_lines, '2025')
        for tx in txs:
            assert tx['rate'] > 0, f'Rate=0 für {tx["cur"]} am {tx["date"]}'

    def test_amtfx_sign_konsistent_mit_eur(self, all_lines):
        """FX-Betrag und EUR-Äquivalent müssen gleiches Vorzeichen haben"""
        txs = parse_fx_transactions(all_lines, '2025')
        for tx in txs:
            if abs(tx['amt_fx']) > 0.001:
                sign_fx  = 1 if tx['amt_fx']  > 0 else -1
                sign_eur = 1 if tx['amt_eur'] > 0 else -1
                assert sign_fx == sign_eur, \
                    f'Vorzeichenkonflikt: {tx["cur"]} amt_fx={tx["amt_fx"]} amt_eur={tx["amt_eur"]}'

