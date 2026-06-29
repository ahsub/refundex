"""
termingeschaefte.py — Refundex Termingeschäfte-Engine v1.0
===========================================================
Gewinn-/Verlustermittlung aus Termingeschäften nach § 20 Abs. 2 Nr. 3 EStG.
Ergebnis fließt in TOPF 3 — unterliegt der 20.000 EUR/Jahr-Verlustgrenze.

Rechtsgrundlagen:
  § 20 Abs. 2 Nr. 3 EStG  — Termingeschäfte (Differenzausgleich)
  § 20 Abs. 6 Satz 5 EStG — Verlustverrechnungsgrenze 20.000 EUR/Jahr
  BMF Rz. 36              — Futures: Erfassung bei Beendigung

Was sind Termingeschäfte i.S. § 20 Abs. 2 Nr. 3?
  ✓ Long-Optionskäufe (BUY einer Option, dann SELL oder EXP)
  ✓ CFD (Contract for Difference)
  ✓ Futures und Forwards
  ✓ Optionsscheine (Warrants, WAR) — Long-Seite
  ✗ Stillhalterprämien (§ 20 Abs. 1 Nr. 11) → Topf 1!
  ✗ Knock-Out-Zertifikate → Topf 1 (Schuldverschreibung, kein Termingeschäft)!

Erkennung in IBKR Flex Query:
  Long-Optionen: Trade.buySell='BUY' + openCloseIndicator='O' (Open)
                 Trade.buySell='SELL' + openCloseIndicator='C' (Close)
                 activityCode='EXP' → wertloser Verfall = Totalverlust
  CFD:   assetCategory='CFD'
  FUT:   assetCategory='FUT'
  WAR:   assetCategory='WAR' (Warrants/Optionsscheine)
"""

from dataclasses import dataclass, field
from collections import defaultdict, deque
from typing import List, Dict
import xml.etree.ElementTree as ET


# ─── Datenstrukturen ─────────────────────────────────────────────────────────

@dataclass
class TerminLot:
    """Ein Long-Termingeschäft (Kauf)"""
    date:       str
    symbol:     str
    isin:       str
    qty:        float
    cost_eur:   float    # Gesamtkosten in EUR
    asset_cat:  str      # OPT | WAR | CFD | FUT

    @property
    def cost_per_unit(self) -> float:
        return self.cost_eur / self.qty if self.qty > 0 else 0.0


@dataclass
class TerminErgebnis:
    """Realisiertes Ergebnis einer Terminposition"""
    date:        str
    symbol:      str
    asset_cat:   str
    art:         str      # 'VERKAUF' | 'VERFALL' | 'CFD_SETTLEMENT' | 'FUT_SETTLEMENT'
    qty:         float
    erloese_eur: float
    ak_eur:      float
    gl_eur:      float    # positiv = Gewinn, negativ = Verlust


@dataclass
class TermingeschaefteReport:
    """Gesamtergebnis Termingeschäfte → Topf 3"""
    steuerjahr:  int
    ergebnisse:  List[TerminErgebnis] = field(default_factory=list)
    warnungen:   List[str]            = field(default_factory=list)

    @property
    def gewinne(self) -> float:
        return sum(e.gl_eur for e in self.ergebnisse if e.gl_eur > 0)

    @property
    def verluste(self) -> float:
        return sum(e.gl_eur for e in self.ergebnisse if e.gl_eur < 0)

    @property
    def netto(self) -> float:
        return self.gewinne + self.verluste

    @property
    def hat_positionen(self) -> bool:
        return len(self.ergebnisse) > 0

    @property
    def cap_relevant(self) -> bool:
        return self.verluste < -0.01


# ─── Hilfsfunktionen ─────────────────────────────────────────────────────────

TERMIN_ASSET_CATS = {'OPT', 'WAR', 'CFD', 'FUT'}


def _ist_long_open(trade) -> bool:
    """True wenn der Trade eine Long-Position eröffnet."""
    bs  = trade.get('buySell', '')
    oci = trade.get('openCloseIndicator', '')
    return bs == 'BUY' and 'O' in oci


def _ist_long_close(trade) -> bool:
    """True wenn der Trade eine Long-Position schließt."""
    bs  = trade.get('buySell', '')
    oci = trade.get('openCloseIndicator', '')
    return bs == 'SELL' and ('C' in oci or oci == '')


def _ist_verfall(trade) -> bool:
    """True bei wertlosem Verfall (Expiry)."""
    return trade.get('activityCode', '') == 'EXP'


def _get_eur_amount(trade, lines_by_trade_id: Dict) -> float:
    """
    Gibt den EUR-Betrag einer Trade zurück.
    Sucht in StmtFunds nach dem EUR-Äquivalent (base currency).
    Fallback: netCash × fxRateToBase (falls vorhanden).
    """
    tid = trade.get('transactionID', '')
    if tid and tid in lines_by_trade_id:
        return float(lines_by_trade_id[tid].get('amount', '0') or '0')

    # Fallback: Aus dem Trade selbst
    net_cash = float(trade.get('netCash', '0') or '0')
    fx_rate  = float(trade.get('fxRateToBase', '1') or '1')
    if fx_rate != 0 and fx_rate != 1:
        return net_cash * fx_rate
    return net_cash


# ─── Hauptberechnung ─────────────────────────────────────────────────────────

def compute_termingeschaefte(
        xml_paths: List[str],
        target_year: str,
) -> TermingeschaefteReport:
    """
    Berechnet Termingeschäfte-G/V für das Zieljahr.

    Strategie:
    - Long-Optionen/Warrants: FIFO über openCloseIndicator
    - CFD/FUT: P&L aus den jeweiligen StmtFunds-Zeilen
    """
    report = TermingeschaefteReport(steuerjahr=int(target_year))
    fifo: Dict[str, deque] = defaultdict(deque)   # symbol → deque of TerminLot
    EPS = 1e-6

    for path in xml_paths:
        root   = ET.parse(path).getroot()
        trades = root.findall('.//Trade')
        lines  = root.findall('.//StatementOfFundsLine')

        # EUR-Index: transactionID → StmtFundsLine (für EUR-Betrag)
        lines_eur = {
            l.get('transactionID', ''): l
            for l in lines
            if l.get('currency') == 'EUR' and l.get('transactionID')
        }

        # Trades sortieren: Öffnungen vor Schließungen am selben Tag
        sorted_trades = sorted(
            trades,
            key=lambda t: (
                t.get('tradeDate', t.get('reportDate', '')),
                0 if _ist_long_open(t) else 1,
            )
        )

        for t in sorted_trades:
            cat        = t.get('assetCategory', '')
            trade_date = t.get('tradeDate', t.get('reportDate', ''))
            is_target  = trade_date.startswith(target_year)
            symbol     = t.get('symbol', '')
            isin       = t.get('isin', '')
            qty_raw    = float(t.get('quantity', '0') or '0')
            eur_amt    = _get_eur_amount(t, lines_eur)

            if cat not in TERMIN_ASSET_CATS:
                continue

            # ── LONG OPEN: Kauf einer Termin-Position ────────────────────
            if _ist_long_open(t) and qty_raw > 0:
                lot = TerminLot(
                    date      = trade_date,
                    symbol    = symbol,
                    isin      = isin,
                    qty       = qty_raw,
                    cost_eur  = abs(eur_amt),
                    asset_cat = cat,
                )
                fifo[symbol].append(lot)

            # ── LONG CLOSE: Verkauf einer Long-Position ───────────────────
            elif _ist_long_close(t) and qty_raw > 0 and is_target:
                to_close = qty_raw
                proceeds = abs(eur_amt) if eur_amt > 0 else 0.0
                ak_total = 0.0

                while to_close > EPS and fifo[symbol]:
                    lot     = fifo[symbol][0]
                    use     = min(to_close, lot.qty)
                    ak_total += use * lot.cost_per_unit
                    to_close -= use
                    if use >= lot.qty - EPS:
                        fifo[symbol].popleft()
                    else:
                        remaining = lot.qty - use
                        fifo[symbol][0] = TerminLot(
                            date=lot.date, symbol=lot.symbol, isin=lot.isin,
                            qty=remaining, cost_eur=remaining * lot.cost_per_unit,
                            asset_cat=lot.asset_cat)

                report.ergebnisse.append(TerminErgebnis(
                    date=trade_date, symbol=symbol, asset_cat=cat,
                    art='VERKAUF', qty=qty_raw - to_close,
                    erloese_eur=round(proceeds, 2),
                    ak_eur=round(ak_total, 2),
                    gl_eur=round(proceeds - ak_total, 2),
                ))

            # ── VERFALL (EXP): wertloser Verfall einer Long-Position ──────
            elif _ist_verfall(t) and is_target:
                # Prüfen ob Long-Position im FIFO
                if fifo[symbol]:
                    lot = fifo[symbol].popleft()
                    # Totalverlust = volle AK
                    report.ergebnisse.append(TerminErgebnis(
                        date=trade_date, symbol=symbol, asset_cat=cat,
                        art='VERFALL', qty=lot.qty,
                        erloese_eur=0.0,
                        ak_eur=round(lot.cost_eur, 2),
                        gl_eur=round(-lot.cost_eur, 2),
                    ))

            # ── CFD / FUT: Settlement-Buchungen ─────────────────────────
            elif cat in ('CFD', 'FUT') and is_target and eur_amt != 0:
                # Alle P&L-Buchungen direkt erfassen (kein FIFO nötig)
                report.ergebnisse.append(TerminErgebnis(
                    date=trade_date, symbol=symbol, asset_cat=cat,
                    art=f'{cat}_SETTLEMENT', qty=abs(qty_raw),
                    erloese_eur=max(0, eur_amt),
                    ak_eur=max(0, -eur_amt),
                    gl_eur=round(eur_amt, 2),
                ))

    # Warnungen
    for sym, stack in fifo.items():
        if stack and any(l.asset_cat in TERMIN_ASSET_CATS for l in stack):
            total_ak = sum(l.cost_eur for l in stack)
            report.warnungen.append(
                f'Offene Long-Position {sym}: {sum(l.qty for l in stack):.4f} Stück, '
                f'AK {total_ak:.2f} EUR — noch nicht realisiert (kein Steuerereignis 2025).')

    return report


# ─── CLI / Demo ──────────────────────────────────────────────────────────────

if __name__ == '__main__':
    XMLS = [
        '/mnt/user-data/uploads/1782742593101_Steuerauswertung.xml',
        '/mnt/user-data/uploads/1782742593100_Steuerauswertung-2.xml',
        '/mnt/user-data/uploads/1782742593100_Steuerauswertung-3.xml',
    ]
    rep = compute_termingeschaefte(XMLS, '2025')
    print(f'\n══ Termingeschäfte 2025 ══')
    print(f'  Positionen realisiert: {len(rep.ergebnisse)}')

    if rep.hat_positionen:
        for e in rep.ergebnisse:
            sign = '+' if e.gl_eur >= 0 else ''
            print(f'  {e.date} [{e.asset_cat}] {e.symbol:25} '
                  f'[{e.art}]  G/V={sign}{e.gl_eur:.2f} EUR')
        print(f'\n  Gewinne:  +{rep.gewinne:.2f} EUR')
        print(f'  Verluste:  {rep.verluste:.2f} EUR')
        print(f'  Netto:     {rep.netto:+.2f} EUR  → Topf 3')
        if rep.cap_relevant:
            print(f'  ⚠️  § 20 Abs. 6 Satz 5 Cap prüfen! Verluste > 0 → max 20.000 EUR/Jahr')
    else:
        print('  Keine Termingeschäfte in 2025 (keine Long-Optionen, CFD oder Futures).')
        print('  → Topf 3: 0,00 EUR — § 20 Abs. 6 Satz 5 Cap nicht relevant')

    if rep.warnungen:
        for w in rep.warnungen:
            print(f'  ⚠️  {w}')
