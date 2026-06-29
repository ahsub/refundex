"""pytest test_aktien_fifo.py — Tests für Aktien-FIFO § 20 Abs. 2 Nr. 1 EStG"""
import sys, pytest
sys.path.insert(0, '/home/claude')
from aktien_fifo import (
    compute_aktien_fifo, AktienLot, AktienTransaktion,
    _parse_stk_transaktionen
)
from unittest.mock import patch, MagicMock
import xml.etree.ElementTree as ET

XMLS = [
    '/mnt/user-data/uploads/1782742593101_Steuerauswertung.xml',
    '/mnt/user-data/uploads/1782742593100_Steuerauswertung-2.xml',
    '/mnt/user-data/uploads/1782742593100_Steuerauswertung-3.xml',
]

# ── Integration: Axel 2025 ───────────────────────────────────────────────────

class TestAxel2025:
    def test_keine_aktienverkaufe_2025(self):
        """Axel hält alle Positionen — kein Verkauf in 2025"""
        erg = compute_aktien_fifo(XMLS, '2025')
        assert not erg.hat_verkaufe
        assert erg.netto == 0.0

    def test_keine_warnungen_ohne_verkauf(self):
        """Ohne Verkauf keine FIFO-Warnungen"""
        erg = compute_aktien_fifo(XMLS, '2025')
        assert len(erg.warnungen) == 0

    def test_topf2_eingabe_korrekt(self):
        """aktien_gewinne und aktien_verluste für verlusttoepfe.py"""
        from verlusttoepfe import KapitaleinkunfteInput, berechne_verlusttoepfe
        erg = compute_aktien_fifo(XMLS, '2025')
        inp = KapitaleinkunfteInput(
            steuerjahr      = 2025,
            aktien_gewinne  = erg.gewinne,
            aktien_verluste = erg.verluste,
        )
        vt = berechne_verlusttoepfe(inp)
        assert vt.kap_z20 == 0.0

# ── Unit-Tests FIFO-Logik ────────────────────────────────────────────────────

class TestFifoLogik:
    """Synthetische Tests mit fiktiven XML-Daten"""

    def _make_xml(self, transaktionen):
        """Erstellt minimales Flex-XML mit STK-Transaktionen"""
        root = ET.Element('FlexQueryResponse')
        stmts = ET.SubElement(root, 'FlexStatements', count='1')
        stmt  = ET.SubElement(stmts, 'FlexStatement',
                              accountId='TEST', fromDate='2020-01-01',
                              toDate='2025-12-31')
        funds = ET.SubElement(stmt, 'StmtFunds')
        for tx in transaktionen:
            ET.SubElement(funds, 'StatementOfFundsLine', **tx)
        import tempfile, os
        f = tempfile.NamedTemporaryFile(mode='wb', suffix='.xml', delete=False)
        ET.ElementTree(root).write(f)
        f.close()
        return f.name

    def test_einfacher_gewinn(self):
        """Kauf für 100 EUR, Verkauf für 150 EUR → +50 EUR"""
        xml_file = self._make_xml([
            {'assetCategory':'STK','currency':'EUR','activityCode':'BUY',
             'date':'2024-01-15','symbol':'TEST','securityID':'DE123',
             'tradeQuantity':'10','amount':'-100'},
            {'assetCategory':'STK','currency':'EUR','activityCode':'SELL',
             'date':'2025-06-01','symbol':'TEST','securityID':'DE123',
             'tradeQuantity':'-10','amount':'150'},
        ])
        try:
            erg = compute_aktien_fifo([xml_file], '2025')
            assert len(erg.verkaufe) == 1
            assert erg.verkaufe[0].gewinn_eur == pytest.approx(50.0, abs=0.01)
            assert erg.gewinne == pytest.approx(50.0, abs=0.01)
            assert erg.verluste == 0.0
        finally:
            import os; os.unlink(xml_file)

    def test_einfacher_verlust(self):
        """Kauf für 100 EUR, Verkauf für 70 EUR → -30 EUR"""
        xml_file = self._make_xml([
            {'assetCategory':'STK','currency':'EUR','activityCode':'BUY',
             'date':'2024-02-01','symbol':'LOSS','securityID':'US456',
             'tradeQuantity':'5','amount':'-100'},
            {'assetCategory':'STK','currency':'EUR','activityCode':'SELL',
             'date':'2025-03-01','symbol':'LOSS','securityID':'US456',
             'tradeQuantity':'-5','amount':'70'},
        ])
        try:
            erg = compute_aktien_fifo([xml_file], '2025')
            assert erg.verluste == pytest.approx(-30.0, abs=0.01)
        finally:
            import os; os.unlink(xml_file)

    def test_fifo_reihenfolge(self):
        """Älteste Lots werden zuerst verkauft (FIFO)"""
        xml_file = self._make_xml([
            # Lot 1: 5 Stk à 10 EUR = 50 EUR AK
            {'assetCategory':'STK','currency':'EUR','activityCode':'BUY',
             'date':'2023-01-01','symbol':'FIF','securityID':'XX1',
             'tradeQuantity':'5','amount':'-50'},
            # Lot 2: 5 Stk à 20 EUR = 100 EUR AK
            {'assetCategory':'STK','currency':'EUR','activityCode':'BUY',
             'date':'2024-06-01','symbol':'FIF','securityID':'XX1',
             'tradeQuantity':'5','amount':'-100'},
            # Verkauf 5 Stk → FIFO nutzt Lot 1 (AK 50 EUR)
            {'assetCategory':'STK','currency':'EUR','activityCode':'SELL',
             'date':'2025-01-15','symbol':'FIF','securityID':'XX1',
             'tradeQuantity':'-5','amount':'80'},
        ])
        try:
            erg = compute_aktien_fifo([xml_file], '2025')
            v = erg.verkaufe[0]
            assert v.ak_eur == pytest.approx(50.0, abs=0.01)   # Lot 1 (älteres)
            assert v.gewinn_eur == pytest.approx(30.0, abs=0.01)
        finally:
            import os; os.unlink(xml_file)

    def test_teilverkauf(self):
        """Nur 3 von 10 Stück verkauft → anteilige AK"""
        xml_file = self._make_xml([
            {'assetCategory':'STK','currency':'EUR','activityCode':'BUY',
             'date':'2024-01-01','symbol':'PART','securityID':'XY2',
             'tradeQuantity':'10','amount':'-200'},  # 20 EUR/Stk
            {'assetCategory':'STK','currency':'EUR','activityCode':'SELL',
             'date':'2025-05-01','symbol':'PART','securityID':'XY2',
             'tradeQuantity':'-3','amount':'75'},  # 25 EUR/Stk
        ])
        try:
            erg = compute_aktien_fifo([xml_file], '2025')
            v = erg.verkaufe[0]
            assert v.ak_eur == pytest.approx(60.0, abs=0.01)   # 3 × 20 EUR
            assert v.gewinn_eur == pytest.approx(15.0, abs=0.01)  # 75 - 60
        finally:
            import os; os.unlink(xml_file)

    def test_topf2_getrennt_von_topf1(self):
        """Aktiengewinne gehen in kap_z20, nicht kap_z19"""
        from verlusttoepfe import KapitaleinkunfteInput, berechne_verlusttoepfe
        inp = KapitaleinkunfteInput(
            steuerjahr=2025, dividenden=2_000.0,
            aktien_gewinne=5_000.0,
        )
        vt = berechne_verlusttoepfe(inp)
        assert vt.kap_z19 == pytest.approx(2_000.0, abs=0.01)  # nur Dividenden
        assert vt.kap_z20 == pytest.approx(5_000.0, abs=0.01)  # nur Aktien
