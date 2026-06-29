"""
fifo_fx.py — Refundex FX-FIFO Engine v1.1
==========================================
Fremdwährungs-Gewinnermittlung nach deutschem Steuerrecht.

Rechtsgrundlagen:
  § 20 Abs. 2 Satz 1 Nr. 7 i.V.m. Abs. 4 EStG
  § 23 Abs. 1 Nr. 2 Satz 3 EStG (FIFO-Prinzip, analog)
  Rn. 131 BMF-Schreiben (BStBl I 2025)

Kernregeln:
  1. FIFO je Währung — zuerst erworbene Bestände zuerst veräußert
  2. Nur positive Guthaben → §20 EStG steuerpflichtig
     Negativer Saldo (Margin/Verbindlichkeit) → separat ausgewiesen
  3. Zufluss-First: gleicher Buchungstag → Zuflüsse VOR Abflüssen
     (IBKR exportiert ohne Uhrzeiten → BubbleTax-Methodik)
  4. amount-Feld in Fremdwährungs-Zeilen = FX-Betrag (NICHT EUR!)
     EUR-Äquivalent = amount × fxRateToBase

Bug-History:
  v1.0: amount fälschlich als EUR interpretiert → amt_fx = amount/rate (falsch)
  v1.1: Korrektur → amt_fx = amount direkt; eur = amount * rate
"""

from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import List, Dict

@dataclass
class FxLot:
    """Ein FIFO-Lot in Fremdwährung"""
    menge: float    # Betrag in Fremdwährung
    rate:  float    # EUR/FX-Kurs bei Erwerb (fxRateToBase)
    date:  str      # Erwerbsdatum

@dataclass
class FxAuditEntry:
    date:       str
    cur:        str
    menge:      float
    rate_kauf:  float
    rate_vk:    float
    gl_eur:     float
    desc:       str
    typ:        str   # '§20' oder 'VB'

@dataclass
class FxResult:
    """Steuerliches Ergebnis je Fremdwährung"""
    gewinn_guthaben:  float = 0.0   # §20 EStG Gewinne (Guthaben)
    verlust_guthaben: float = 0.0   # §20 EStG Verluste (Guthaben)
    gewinn_verbindl:  float = 0.0   # Verbindlichkeitsdifferenzen (nicht §20)
    verlust_verbindl: float = 0.0
    audit: List[FxAuditEntry] = field(default_factory=list)

    @property
    def netto_guthaben(self):  return self.gewinn_guthaben + self.verlust_guthaben
    @property
    def netto_verbindl(self):  return self.gewinn_verbindl + self.verlust_verbindl


def parse_fx_transactions(lines, target_year: str):
    """
    Normalisiert StatementOfFundsLines zu (date, cur, amt_fx, rate, desc, is_target).

    WICHTIG: 'amount' in nicht-EUR-Zeilen ist in der Fremdwährung (z.B. SEK, GBP, USD).
             EUR-Äquivalent = amount × fxRateToBase.
             Zufluss-First-Sortierung: Zuflüsse (amt_fx > 0) vor Abflüssen am gleichen Tag.
    """
    raw = []
    for l in lines:
        cur = l.get('currency', 'EUR')
        if cur == 'EUR':
            continue
        # amount ist in FX-Währung (nicht EUR!)
        amt_fx = float(l.get('amount', '0') or '0')
        if abs(amt_fx) < 1e-9:
            continue
        rate = float(l.get('fxRateToBase', '1') or '1')
        if rate == 0:
            continue
        date = l.get('date', '')
        raw.append({
            'date':       date,
            'cur':        cur,
            'amt_fx':     amt_fx,                  # in FX
            'amt_eur':    amt_fx * rate,            # in EUR
            'rate':       rate,                     # EUR je 1 FX
            'code':       l.get('activityCode', ''),
            'desc':       l.get('activityDescription', '')[:60],
            'is_target':  date.startswith(target_year),
        })

    # Zufluss-First: Datum ASC, dann pos vor neg
    raw.sort(key=lambda t: (t['date'], 0 if t['amt_fx'] > 0 else 1))
    return raw


def compute_fifo(txs, target_year: str) -> Dict[str, FxResult]:
    """
    Verarbeitet alle FX-Transaktionen mit FIFO.
    Trennt Guthaben (§20) von Verbindlichkeiten (nicht §20).
    """
    results: Dict[str, FxResult] = defaultdict(FxResult)
    fifo:    Dict[str, deque]    = defaultdict(deque)   # deque of FxLot
    saldo:   Dict[str, float]    = defaultdict(float)   # laufender FX-Saldo

    EPS = 1e-8

    for tx in txs:
        cur    = tx['cur']
        amt_fx = tx['amt_fx']
        rate   = tx['rate']
        res    = results[cur]
        is25   = tx['is_target']

        if amt_fx > EPS:
            # ── ZUFLUSS ──────────────────────────────────────────────────────
            # Verbindlichkeit tilgen (wenn Saldo negativ war)
            deficit = max(0.0, -saldo[cur])
            tilgung = min(deficit, amt_fx)
            rest    = amt_fx - tilgung

            # Verbindlichkeit teilweise ausgeglichen (kein §20-Tatbestand)
            # (Tilgung von Margin-Schulden in FX → kein Steuertatbestand)

            # Rest → Guthaben-FIFO
            if rest > EPS:
                fifo[cur].append(FxLot(menge=rest, rate=rate, date=tx['date']))

            saldo[cur] += amt_fx

        elif amt_fx < -EPS:
            # ── ABFLUSS ──────────────────────────────────────────────────────
            to_use = abs(amt_fx)
            saldo[cur] += amt_fx

            # Phase 1: aus Guthaben-FIFO → §20 G/V
            while to_use > EPS and fifo[cur]:
                lot = fifo[cur][0]
                use = min(to_use, lot.menge)

                if is25:
                    gl = use * rate - use * lot.rate   # EUR bei VK - EUR bei Kauf
                    if gl >= 0:
                        res.gewinn_guthaben  += gl
                    else:
                        res.verlust_guthaben += gl
                    res.audit.append(FxAuditEntry(
                        date=tx['date'], cur=cur, menge=use,
                        rate_kauf=lot.rate, rate_vk=rate, gl_eur=gl,
                        desc=tx['desc'], typ='§20'
                    ))

                to_use -= use
                if use >= lot.menge - EPS:
                    fifo[cur].popleft()
                else:
                    fifo[cur][0] = FxLot(menge=lot.menge - use, rate=lot.rate, date=lot.date)

            # Phase 2: FIFO erschöpft → Verbindlichkeitsbereich
            if to_use > EPS and is25:
                res.audit.append(FxAuditEntry(
                    date=tx['date'], cur=cur, menge=to_use,
                    rate_kauf=0.0, rate_vk=rate, gl_eur=0.0,
                    desc=tx['desc'], typ='VB'
                ))

    return dict(results)


def fx_fifo_from_lines(all_lines, target_year: str) -> Dict[str, FxResult]:
    """Haupteinstiegspunkt: XML-Zeilen → FX-Ergebnisse"""
    txs = parse_fx_transactions(all_lines, target_year)
    return compute_fifo(txs, target_year)


# ── CLI-Test ──────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    import xml.etree.ElementTree as ET

    XMLS = [
        '/mnt/user-data/uploads/1782742593101_Steuerauswertung.xml',
        '/mnt/user-data/uploads/1782742593100_Steuerauswertung-2.xml',
        '/mnt/user-data/uploads/1782742593100_Steuerauswertung-3.xml',
    ]
    TARGET = '2025'

    all_lines = []
    for p in XMLS:
        all_lines.extend(ET.parse(p).getroot().findall('.//StatementOfFundsLine'))

    results = fx_fifo_from_lines(all_lines, TARGET)

    print(f'\n══ FX-FIFO v1.1 · Steuerjahr {TARGET} ══\n')
    print(f'{"Währung":6}  {"G §20":>10}  {"V §20":>11}  {"N §20":>11}  {"VB-Tx":>6}')
    print('─' * 54)

    tg = tv = 0.0
    for cur, r in sorted(results.items()):
        vb_cnt = sum(1 for a in r.audit if a.typ == 'VB')
        tg += r.gewinn_guthaben;  tv += r.verlust_guthaben
        print(f'{cur:6}  {r.gewinn_guthaben:>10.2f}  '
              f'{r.verlust_guthaben:>11.2f}  '
              f'{r.netto_guthaben:>11.2f}  {vb_cnt:>6}')
    print('─' * 54)
    print(f'{"SUMME":6}  {tg:>10.2f}  {tv:>11.2f}  {tg+tv:>11.2f}')

    print()
    print('BubbleTax-Referenz (maskiert):')
    print('  USD: G≈1XX  V≈-86X  N≈-75X')
    print('  GBP: G≈X    V≈-X    N≈+X')
    print('  SEK: G≈2X   V≈-X    N≈+2X')
    print('  Ges: G≈14X  V≈-87X  N≈-73X')

    # SEK-Detail
    if 'SEK' in results:
        print('\n── SEK Audit (alle §20-Buchungen) ──')
        for a in results['SEK'].audit:
            if a.typ == '§20':
                print(f'  {a.date}  {a.menge:>9.3f} SEK  '
                      f'AK={a.rate_kauf:.6f}  VK={a.rate_vk:.6f}  '
                      f'G/V={a.gl_eur:>+8.3f} EUR')
        print(f'  → SEK-Netto: {results["SEK"].netto_guthaben:+.2f} EUR')
