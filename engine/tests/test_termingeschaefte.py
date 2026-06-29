"""pytest test_termingeschaefte.py — Tests für Termingeschäfte § 20 Abs. 2 Nr. 3"""
import sys, pytest
sys.path.insert(0, '/home/claude')
from termingeschaefte import compute_termingeschaefte, TerminLot, TERMIN_ASSET_CATS
import xml.etree.ElementTree as ET
import tempfile, os

XMLS = [
    '/mnt/user-data/uploads/1782742593101_Steuerauswertung.xml',
    '/mnt/user-data/uploads/1782742593100_Steuerauswertung-2.xml',
    '/mnt/user-data/uploads/1782742593100_Steuerauswertung-3.xml',
]

def make_xml(trades_data):
    """Erstellt minimales XML mit Trade-Elementen"""
    root  = ET.Element('FlexQueryResponse')
    stmts = ET.SubElement(root, 'FlexStatements', count='1')
    stmt  = ET.SubElement(stmts, 'FlexStatement',
                          accountId='T', fromDate='2020-01-01', toDate='2025-12-31')
    ET.SubElement(stmt, 'StmtFunds')  # leer
    trades_el = ET.SubElement(stmt, 'Trades')
    for td in trades_data:
        ET.SubElement(trades_el, 'Trade', **td)
    f = tempfile.NamedTemporaryFile(mode='wb', suffix='.xml', delete=False)
    ET.ElementTree(root).write(f)
    f.close()
    return f.name

# ── Integration: Axel 2025 ───────────────────────────────────────────────────

class TestAxel2025:
    def test_keine_termingeschaefte_2025(self):
        """Axel: nur Stillhalter (OPT SELL/O) — keine Long-Optionen"""
        rep = compute_termingeschaefte(XMLS, '2025')
        assert not rep.hat_positionen

    def test_topf3_null(self):
        """Kein § 20 Abs. 6 Satz 5 relevant"""
        rep = compute_termingeschaefte(XMLS, '2025')
        assert rep.netto == 0.0
        assert not rep.cap_relevant

# ── Unit-Tests Long-Optionen ─────────────────────────────────────────────────

class TestLongOptionen:
    BASE = {'assetCategory':'OPT','isin':'','currency':'EUR','netCash':'0','fxRateToBase':'1'}

    def test_long_option_gewinn(self):
        """Kauf 200 EUR, Verkauf 300 EUR → +100 EUR Gewinn (Topf 3)"""
        xml_file = make_xml([
            {**self.BASE,'tradeDate':'2024-06-01','symbol':'AAPL C150',
             'buySell':'BUY','openCloseIndicator':'O',
             'quantity':'1','netCash':'-200'},
            {**self.BASE,'tradeDate':'2025-03-01','symbol':'AAPL C150',
             'buySell':'SELL','openCloseIndicator':'C',
             'quantity':'1','netCash':'300'},
        ])
        try:
            rep = compute_termingeschaefte([xml_file], '2025')
            assert len(rep.ergebnisse) == 1
            assert rep.ergebnisse[0].gl_eur == pytest.approx(100.0, abs=0.01)
            assert rep.gewinne == pytest.approx(100.0, abs=0.01)
        finally: os.unlink(xml_file)

    def test_long_option_verfall_totalverlust(self):
        """Option verfällt wertlos → Totalverlust = volle AK"""
        xml_file = make_xml([
            {**self.BASE,'tradeDate':'2025-01-10','symbol':'SPY P400',
             'buySell':'BUY','openCloseIndicator':'O',
             'quantity':'2','netCash':'-500'},
            {**self.BASE,'tradeDate':'2025-04-20','symbol':'SPY P400',
             'buySell':'','openCloseIndicator':'',
             'activityCode':'EXP','quantity':'0','netCash':'0'},
        ])
        try:
            rep = compute_termingeschaefte([xml_file], '2025')
            # EXP mit vorhandenem FIFO-Lot → Totalverlust
            verluste = [e for e in rep.ergebnisse if e.gl_eur < 0]
            assert len(verluste) == 1
            assert verluste[0].gl_eur == pytest.approx(-500.0, abs=0.01)
        finally: os.unlink(xml_file)

    def test_long_option_verlust(self):
        """Kauf 500 EUR, Verkauf 200 EUR → -300 EUR Verlust"""
        xml_file = make_xml([
            {**self.BASE,'tradeDate':'2025-01-05','symbol':'NVDA C800',
             'buySell':'BUY','openCloseIndicator':'O',
             'quantity':'3','netCash':'-500'},
            {**self.BASE,'tradeDate':'2025-02-15','symbol':'NVDA C800',
             'buySell':'SELL','openCloseIndicator':'C',
             'quantity':'3','netCash':'200'},
        ])
        try:
            rep = compute_termingeschaefte([xml_file], '2025')
            assert rep.verluste == pytest.approx(-300.0, abs=0.01)
            assert rep.cap_relevant
        finally: os.unlink(xml_file)

    def test_stillhalter_nicht_als_termin_erkannt(self):
        """SELL/O = Stillhalter → gehört zu Topf 1, nicht Topf 3"""
        xml_file = make_xml([
            {**self.BASE,'tradeDate':'2025-03-01','symbol':'AAPL P140',
             'buySell':'SELL','openCloseIndicator':'O',  # Stillhalter!
             'quantity':'-1','netCash':'500'},
        ])
        try:
            rep = compute_termingeschaefte([xml_file], '2025')
            # Stillhalter-SELL/O darf NICHT in Topf 3
            assert not rep.hat_positionen
        finally: os.unlink(xml_file)

# ── Integration mit verlusttoepfe.py ─────────────────────────────────────────

class TestTerminTopf3Integration:
    def test_termin_verlust_in_topf3(self):
        """Terminverluste gehen in Topf 3, nicht Topf 1"""
        from verlusttoepfe import KapitaleinkunfteInput, berechne_verlusttoepfe
        inp = KapitaleinkunfteInput(
            steuerjahr=2025,
            dividenden=5_000.0,
            termin_verluste=-8_000.0,
        )
        vt = berechne_verlusttoepfe(inp)
        # Dividenden (Topf 1) bleiben unberührt durch Terminverluste
        assert vt.kap_z19 == pytest.approx(5_000.0, abs=0.01)
        # Terminverlust → Vortrag (kein Topf-1-Gegenrechnung)
        assert vt.vortrag_neu.termingeschaefte == pytest.approx(-8_000.0, abs=0.01)

    def test_termin_asset_categories(self):
        """OPT, WAR, CFD, FUT sind Termingeschäfte — STK, BOND nicht"""
        assert 'OPT' in TERMIN_ASSET_CATS
        assert 'WAR' in TERMIN_ASSET_CATS
        assert 'CFD' in TERMIN_ASSET_CATS
        assert 'FUT' in TERMIN_ASSET_CATS
        assert 'STK' not in TERMIN_ASSET_CATS
        assert 'BOND' not in TERMIN_ASSET_CATS
