"""
aktien_fifo.py — Refundex Aktien-FIFO v1.0
===========================================
Gewinnermittlung aus Aktienveräußerungen nach § 20 Abs. 2 Nr. 1 EStG.
Ergebnis fließt in TOPF 2 (Aktien) — strikt getrennt von Topf 1 und 3.

Rechtsgrundlagen:
  § 20 Abs. 2 Nr. 1 EStG  — Veräußerungsgewinne aus Aktien
  § 20 Abs. 4 Satz 7 EStG — FIFO-Methode (zuerst erworbene zuerst veräußert)
  § 20 Abs. 6 Satz 4 EStG — Aktienverluste NUR mit Aktiengewinnen verrechenbar

FIFO-Strategie:
  Alle BUY/ASSIGN aus mehreren Jahren werden als Lot-Stack aufgebaut.
  Verkäufe im Zieljahr werden gegen den Stack verrechnet (FIFO).
  Verwendung der EUR-Basiswährungszeilen aus StmtFunds (fxRateToBase bereits angewandt).

Inputs aus IBKR Flex Query:
  StmtFunds activityCode=BUY/SELL/ASSIGN, assetCategory=STK, currency=EUR
  Assignments durch Optionsausübung (Short Put zugeteilt → AK = Strike-Preis × Stücke)

Hinweis: Für korrekte FIFO-Berechnung werden alle verfügbaren Jahre benötigt
(nicht nur das Zieljahr), da offene Positionen aus Vorjahren stammen können.
"""

from dataclasses import dataclass, field
from collections import defaultdict, deque
from typing import List, Dict, Tuple
import xml.etree.ElementTree as ET


# ─── Datenstrukturen ─────────────────────────────────────────────────────────

@dataclass
class AktienLot:
    """Ein FIFO-Lot einer Aktienposition"""
    date:       str
    qty:        float    # Anzahl Aktien
    cost_eur:   float    # Gesamtkosten in EUR (inkl. Gebühren)
    isin:       str
    source:     str      # 'BUY' | 'ASSIGN' | 'OPENPOS'

    @property
    def cost_per_share(self) -> float:
        return self.cost_eur / self.qty if self.qty > 0 else 0.0


@dataclass
class AktienTransaktion:
    """Eine einzelne Aktientransaktion"""
    date:      str
    isin:      str
    symbol:    str
    code:      str    # BUY | SELL | ASSIGN
    qty:       float  # positiv = Kauf, negativ = Verkauf
    amount_eur: float # EUR-Betrag (negativ bei Kauf, positiv bei Verkauf)


@dataclass
class AktienVerkauf:
    """Realisiertes Ergebnis eines Aktienverkaufs"""
    date:        str
    isin:        str
    symbol:      str
    qty:         float
    erloese_eur: float   # Verkaufserlös in EUR
    ak_eur:      float   # Anschaffungskosten (FIFO) in EUR
    gewinn_eur:  float   # positiv = Gewinn, negativ = Verlust


@dataclass
class AktienFifoErgebnis:
    """Gesamtergebnis aller Aktienverkäufe im Zieljahr → Topf 2"""
    steuerjahr:  int
    verkaufe:    List[AktienVerkauf] = field(default_factory=list)
    warnungen:   List[str]          = field(default_factory=list)

    @property
    def gewinne(self) -> float:
        return sum(v.gewinn_eur for v in self.verkaufe if v.gewinn_eur > 0)

    @property
    def verluste(self) -> float:
        return sum(v.gewinn_eur for v in self.verkaufe if v.gewinn_eur < 0)

    @property
    def netto(self) -> float:
        return self.gewinne + self.verluste

    @property
    def hat_verkaufe(self) -> bool:
        return len(self.verkaufe) > 0


# ─── XML-Parser ──────────────────────────────────────────────────────────────

def _parse_stk_transaktionen(lines) -> List[AktienTransaktion]:
    """
    Extrahiert STK-Transaktionen aus StatementOfFundsLines.
    Nur EUR-Basiswährungszeilen (currency=EUR, bereits umgerechnet).
    """
    txs = []
    for l in lines:
        if l.get('assetCategory') != 'STK': continue
        if l.get('currency') != 'EUR': continue
        code = l.get('activityCode', '')
        if code not in ('BUY', 'SELL', 'ASSIGN'): continue

        qty_raw = float(l.get('tradeQuantity', '0') or '0')
        if qty_raw == 0:
            # tradeQuantity fehlt manchmal — aus Amount ableiten
            continue

        txs.append(AktienTransaktion(
            date       = l.get('date', ''),
            isin       = l.get('securityID', ''),
            symbol     = l.get('symbol', ''),
            code       = code,
            qty        = qty_raw,
            amount_eur = float(l.get('amount', '0') or '0'),
        ))

    # Chronologisch sortieren, Käufe vor Verkäufen am selben Tag (Zufluss-First)
    txs.sort(key=lambda t: (t.date, 0 if t.qty > 0 else 1))
    return txs


# ─── FIFO-Berechnung ─────────────────────────────────────────────────────────

def compute_aktien_fifo(
        xml_paths: List[str],
        target_year: str,
) -> AktienFifoErgebnis:
    """
    Berechnet Aktien-G/V für das Zieljahr.

    Lädt Transaktionen aus ALLEN übergebenen XML-Dateien (für FIFO-Stack),
    verrechnet Verkäufe nur im Zieljahr.
    """
    ergebnis  = AktienFifoErgebnis(steuerjahr=int(target_year))
    fifo: Dict[str, deque] = defaultdict(deque)   # isin → deque of AktienLot
    EPS = 1e-6

    # Alle Transaktionen aus allen Jahren laden
    all_txs = []
    for path in xml_paths:
        root = ET.parse(path).getroot()
        lines = root.findall('.//StatementOfFundsLine')
        all_txs.extend(_parse_stk_transaktionen(lines))

    all_txs.sort(key=lambda t: (t.date, 0 if t.qty > 0 else 1))

    for tx in all_txs:
        is_target = tx.date.startswith(target_year)

        if tx.qty > 0:
            # ── KAUF / ZUTEILUNG → Lot hinzufügen ────────────────────────
            lot = AktienLot(
                date     = tx.date,
                qty      = tx.qty,
                cost_eur = abs(tx.amount_eur),
                isin     = tx.isin,
                source   = tx.code,
            )
            fifo[tx.isin].append(lot)

        elif tx.qty < 0 and is_target:
            # ── VERKAUF → FIFO-Auflösung und G/V-Berechnung ──────────────
            to_sell    = abs(tx.qty)
            erloese    = abs(tx.amount_eur)   # Verkaufserlös in EUR
            ak_gesamt  = 0.0
            isin       = tx.isin

            if not fifo[isin]:
                ergebnis.warnungen.append(
                    f'FIFO leer für {tx.symbol} ({isin}) am {tx.date} — '
                    f'Anschaffungsdaten unvollständig. Ggf. ältere XML-Exporte importieren.')
                continue

            qty_remain = to_sell
            while qty_remain > EPS and fifo[isin]:
                lot     = fifo[isin][0]
                use_qty = min(qty_remain, lot.qty)
                use_ak  = use_qty * lot.cost_per_share
                ak_gesamt += use_ak
                qty_remain -= use_qty

                if use_qty >= lot.qty - EPS:
                    fifo[isin].popleft()
                else:
                    # Lot teilweise verbraucht
                    remaining_cost = (lot.qty - use_qty) * lot.cost_per_share
                    fifo[isin][0] = AktienLot(
                        date=lot.date, qty=lot.qty - use_qty,
                        cost_eur=remaining_cost, isin=lot.isin, source=lot.source)

            # Anteiliger Erlös (bei Teilverkauf)
            anteil      = (to_sell - qty_remain) / to_sell if to_sell > 0 else 1.0
            erloes_antl = erloese * anteil
            gewinn      = erloes_antl - ak_gesamt

            ergebnis.verkaufe.append(AktienVerkauf(
                date        = tx.date,
                isin        = tx.isin,
                symbol      = tx.symbol,
                qty         = to_sell - qty_remain,
                erloese_eur = round(erloes_antl, 2),
                ak_eur      = round(ak_gesamt, 2),
                gewinn_eur  = round(gewinn, 2),
            ))

    return ergebnis


# ─── CLI / Demo ──────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import sys
    XMLS = [
        '/mnt/user-data/uploads/1782742593101_Steuerauswertung.xml',
        '/mnt/user-data/uploads/1782742593100_Steuerauswertung-2.xml',
        '/mnt/user-data/uploads/1782742593100_Steuerauswertung-3.xml',
    ]
    erg = compute_aktien_fifo(XMLS, '2025')
    print(f'\n══ Aktien-FIFO 2025 ══')
    print(f'  Aktienverkäufe: {len(erg.verkaufe)}')
    if erg.hat_verkaufe:
        for v in erg.verkaufe:
            sign = '+' if v.gewinn_eur >= 0 else ''
            print(f'  {v.date} {v.symbol:6} {v.qty:.4f} Stk  '
                  f'Erlös={v.erloese_eur:.2f}  AK={v.ak_eur:.2f}  '
                  f'G/V={sign}{v.gewinn_eur:.2f} EUR')
        print(f'  Gewinne:  +{erg.gewinne:.2f} EUR  → Topf 2 (KAP Z20)')
        print(f'  Verluste:  {erg.verluste:.2f} EUR  → Topf 2 (KAP Z23)')
        print(f'  Netto:     {erg.netto:+.2f} EUR')
    else:
        print('  Keine Aktienverkäufe in 2025 — Axel hält alle Positionen.')
        print('  → Topf 2: 0,00 EUR (kein Eintrag in KAP Z20/Z23)')
    if erg.warnungen:
        for w in erg.warnungen:
            print(f'  ⚠️  {w}')
