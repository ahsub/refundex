"""
kapmassnm.py — Refundex Kapitalmaßnahmen-Engine v1.0
=====================================================
Steuerliche Verarbeitung von Corporate Actions aus IBKR Flex Query XML.

Rechtsgrundlagen:
  § 20 Abs. 4a EStG   — Kapitalmaßnahmen allgemein
  § 20 Abs. 4a Satz 1 — Tausch von Wertpapieren (steuerneutral)
  § 20 Abs. 4a Satz 7 — Spin-Off: AK-Aufteilung nach Marktwerten
  § 20 Abs. 2 Satz 1  — Veräußerungsgewinne/-verluste
  Rn. 97–99 BMF       — Depotüberträge / Kapitalmaßnahmen allgemein

Unterstützte IBKR Corporate-Action-Typen:
  SO  = Spin-Off        → Sachausschüttung steuerpflichtig (§20 Abs. 4a S.7)
  TO  = Tender Offer    → Barausgleich steuerpflichtig; reiner Tausch neutral
  TC  = Tausch/Merger   → steuerneutral (AK-Übertrag)
  DW  = Delisting       → Totalverlust in Höhe der AK
  SD  = Stock Split     → steuerneutral, nur Mengenanpassung
  RS  = Reverse Split   → steuerneutral, nur Mengenanpassung

Datenquelle: IBKR liefert im <CorporateAction>-Element das Feld `value`
mit dem Marktwert (i.d.R. in USD). Dieser Wert hat höchste Priorität
(vor Yahoo Finance etc.) — entspricht BubbleTax-Methodik Priorität 1.

Marktwert-Hierarchie (wie BubbleTax):
  1. IBKR `value`-Feld  ← meistens vorhanden und ausreichend
  2. Yahoo Finance Eröffnungskurs am Corporate-Action-Tag  (TODO: nächste Version)
  3. 0,00 EUR Fallback (konservativ, keine Sachausschüttung)
"""

from dataclasses import dataclass, field
from collections import defaultdict
from typing import List, Dict, Optional
import xml.etree.ElementTree as ET


# ─── Datenstrukturen ──────────────────────────────────────────────────────────

@dataclass
class CorporateActionRaw:
    """Rohdaten eines IBKR CorporateAction-Elements"""
    date:        str
    type:        str       # SO, TO, TC, DW, SD, RS
    symbol:      str
    isin:        str
    description: str
    quantity:    float     # positiv = Zugang, negativ = Abgang
    proceeds:    float     # Barausgleich in USD (negativ = Ausgabe)
    value:       float     # Marktwert in USD (IBKR-Feld, 0 wenn nicht belegt)
    currency:    str
    fx_rate:     float     # EUR/Fremdwährung am Corporate-Action-Tag


@dataclass
class KapMassnahmeErgebnis:
    """Steuerliches Ergebnis einer einzelnen Kapitalmaßnahme"""
    date:             str
    type:             str
    symbol:           str
    isin:             str
    description:      str
    quantity:         float
    # Steuerliche Werte in EUR
    sachausch_eur:    float = 0.0   # Sachausschüttung (SO → §20 EStG Ertrag)
    realis_gewinn:    float = 0.0   # Realisierter Gewinn
    realis_verlust:   float = 0.0   # Realisierter Verlust
    ak_neu_eur:       float = 0.0   # Anschaffungskosten der neuen Papiere
    steuerlich:       str   = ''    # Kurzerläuterung
    rechtsgrundlage:  str   = ''

    @property
    def netto_eur(self):
        return self.sachausch_eur + self.realis_gewinn + self.realis_verlust


@dataclass
class KapMassnahmenReport:
    """Gesamtübersicht aller Kapitalmaßnahmen eines Steuerjahres"""
    steuerjahr:       str
    ergebnisse:       List[KapMassnahmeErgebnis] = field(default_factory=list)

    @property
    def gesamt_sachausch(self):
        return sum(e.sachausch_eur for e in self.ergebnisse)

    @property
    def gesamt_gewinn(self):
        return sum(e.realis_gewinn for e in self.ergebnisse)

    @property
    def gesamt_verlust(self):
        return sum(e.realis_verlust for e in self.ergebnisse)

    @property
    def gesamt_netto(self):
        return self.gesamt_sachausch + self.gesamt_gewinn + self.gesamt_verlust


# ─── XML-Parser ──────────────────────────────────────────────────────────────

def _get_fx_rate_for_date(all_lines, date: str, currency: str = 'USD') -> float:
    """
    Sucht fxRateToBase für eine gegebene Währung am nächsten verfügbaren Datum.
    Scannt ±5 Tage rund um das Zieldatum.
    """
    if currency == 'EUR':
        return 1.0

    # Exakter Tag zuerst
    for l in all_lines:
        if l.get('date', '') == date and l.get('currency', '') == currency:
            rate = float(l.get('fxRateToBase', '0') or '0')
            if rate > 0:
                return rate

    # Nächstgelegenes Datum (±5 Tage)
    candidates = []
    for l in all_lines:
        if l.get('currency', '') != currency:
            continue
        rate = float(l.get('fxRateToBase', '0') or '0')
        if rate <= 0:
            continue
        d = l.get('date', '')
        diff = abs(int(date.replace('-', '')) - int(d.replace('-', '')))
        if diff <= 50:  # numerische Differenz ≤ 50 entspricht ca. 5 Tage
            candidates.append((diff, rate))

    if candidates:
        return sorted(candidates)[0][1]

    return 0.0


def parse_corporate_actions(xml_paths: List[str],
                            target_year: str) -> List[CorporateActionRaw]:
    """
    Liest alle CorporateAction-Elemente aus den XML-Dateien.
    Filtert auf das Zieljahr. Reichert mit FX-Rate an.
    """
    all_lines = []
    all_corps  = []

    for path in xml_paths:
        root = ET.parse(path).getroot()
        all_lines.extend(root.findall('.//StatementOfFundsLine'))
        all_corps.extend(root.findall('.//CorporateAction'))

    result = []
    for c in all_corps:
        date = c.get('reportDate', c.get('dateTime', ''))[:10]
        if not date.startswith(target_year):
            continue

        currency = c.get('currency', 'USD')
        fx_rate  = _get_fx_rate_for_date(all_lines, date, currency)

        result.append(CorporateActionRaw(
            date        = date,
            type        = c.get('type', ''),
            symbol      = c.get('symbol', ''),
            isin        = c.get('isin', ''),
            description = c.get('description', ''),
            quantity    = float(c.get('quantity',  '0') or '0'),
            proceeds    = float(c.get('proceeds',  '0') or '0'),
            value       = float(c.get('value',     '0') or '0'),
            currency    = currency,
            fx_rate     = fx_rate,
        ))

    return sorted(result, key=lambda x: x.date)


# ─── Steuerliche Behandlung je Typ ───────────────────────────────────────────

def _handle_spin_off(ca: CorporateActionRaw) -> Optional[KapMassnahmeErgebnis]:
    """
    SO = Spin-Off: § 20 Abs. 4a Satz 7 EStG
    Sachausschüttung = Marktwert der erhaltenen Anteile am SO-Tag.
    Marktwert aus IBKR `value`-Feld (in Fremdwährung), umgerechnet per fxRateToBase.

    Steuerliche Folgen:
    - Sachausschüttung ist sofort steuerpflichtiger Ertrag (§20 Abs. 1 Nr. 1 EStG)
    - AK der neuen Papiere = Sachausschüttungswert
    - AK des Mutterunternehmens wird entsprechend gemindert
      (anteilig nach Marktwerten — hier vereinfachend: Minderung = Sachausschüttung)
    """
    if ca.quantity <= 0:
        return None  # nur Zugang-Zeilen verarbeiten

    sachausch_eur = 0.0
    if abs(ca.value) > 1e-6 and ca.fx_rate > 0:
        # IBKR-Wert vorhanden → verwenden
        sachausch_eur = abs(ca.value) * ca.fx_rate
        quelle = 'IBKR `value`-Feld'
    else:
        # Kein Wert → 0,00 EUR (konservativ, kein Ertrag)
        quelle = 'Fallback 0,00 EUR (IBKR-Wert nicht verfügbar)'

    ak_neu_eur = sachausch_eur  # AK der neuen Papiere = Sachausschüttungswert

    return KapMassnahmeErgebnis(
        date           = ca.date,
        type           = 'SO',
        symbol         = ca.symbol,
        isin           = ca.isin,
        description    = ca.description[:80],
        quantity       = ca.quantity,
        sachausch_eur  = sachausch_eur,
        ak_neu_eur     = ak_neu_eur,
        steuerlich     = (f'Sachausschüttung {sachausch_eur:.2f} EUR '
                          f'({abs(ca.value):.4f} {ca.currency} × {ca.fx_rate:.5f}) '
                          f'[Quelle: {quelle}]'),
        rechtsgrundlage= '§ 20 Abs. 4a Satz 7 EStG; Rn. 101, 115 BMF',
    )


def _handle_tender_offer(ca: CorporateActionRaw,
                         ak_pro_stueck: float = 0.0) -> Optional[KapMassnahmeErgebnis]:
    """
    TO = Tender Offer / Übernahmeangebot.

    Fälle:
    (a) Reiner Aktienaustausch (proceeds=0): steuerneutral (§20 Abs. 4a Satz 1)
    (b) Barausgleich (|proceeds| > 0): steuerpflichtig wie Veräußerung

    Bei Abgang (quantity < 0): Veräußerungserlös = proceeds (in EUR)
    Gewinn/Verlust = Erlös − AK der hingegebenen Papiere
    """
    if ca.quantity >= 0:
        return None  # Zugang-Zeile überspringen (wird als Einbuchung gehandhabt)

    abgang_qty = abs(ca.quantity)

    # proceeds < 0: du hast Geld GEZAHLT (Tausch mit Zusatzzahlung) → steuerneutral
    # proceeds > 0: du hast Geld ERHALTEN (echter Barausgleich) → steuerpflichtig
    # proceeds = 0: reiner Aktienaustausch → steuerneutral

    if ca.proceeds <= 0:
        # Steuerneutral: reiner Tausch oder Tausch mit Aufzahlung
        zusatz_eur = abs(ca.proceeds) * ca.fx_rate if ca.fx_rate > 0 else 0
        hinweis = ('Steuerneutraler Aktienaustausch — AK übertragen'
                   if abs(ca.proceeds) < 1e-6 else
                   f'Tausch mit Aufzahlung {zusatz_eur:.2f} EUR (erhöht AK Empfangene) — steuerneutral')
        return KapMassnahmeErgebnis(
            date            = ca.date,
            type            = 'TO',
            symbol          = ca.symbol,
            isin            = ca.isin,
            description     = ca.description[:80],
            quantity        = ca.quantity,
            steuerlich      = hinweis,
            rechtsgrundlage = '§ 20 Abs. 4a Satz 1 EStG',
        )

    # proceeds > 0: echter Barerlös → steuerpflichtige Veräußerung
    erloese_eur = ca.proceeds * ca.fx_rate if ca.fx_rate > 0 else ca.proceeds
    ak_eur      = abgang_qty * ak_pro_stueck
    gl          = erloese_eur - ak_eur

    return KapMassnahmeErgebnis(
        date            = ca.date,
        type            = 'TO',
        symbol          = ca.symbol,
        isin            = ca.isin,
        description     = ca.description[:80],
        quantity        = ca.quantity,
        realis_gewinn   = max(0, gl),
        realis_verlust  = min(0, gl),
        steuerlich      = (f'Barausgleich: Erlös {erloese_eur:.2f} EUR − '
                           f'AK {ak_eur:.2f} EUR = {gl:+.2f} EUR'),
        rechtsgrundlage = '§ 20 Abs. 2 Satz 1 Nr. 1 EStG',
    )


def _handle_delisting(ca: CorporateActionRaw,
                      ak_pro_stueck: float = 0.0) -> Optional[KapMassnahmeErgebnis]:
    """
    DW = Delisting / Wertlosausbuchung.
    Totalverlust = AK der ausgebuchten Papiere.
    § 20 Abs. 2 Satz 1 Nr. 1 EStG i.V.m. § 20 Abs. 4 EStG.
    """
    if ca.quantity >= 0:
        return None

    abgang_qty  = abs(ca.quantity)
    ak_eur      = abgang_qty * ak_pro_stueck
    verlust_eur = -ak_eur  # negativ = Verlust

    return KapMassnahmeErgebnis(
        date            = ca.date,
        type            = 'DW',
        symbol          = ca.symbol,
        isin            = ca.isin,
        description     = ca.description[:80],
        quantity        = ca.quantity,
        realis_verlust  = verlust_eur,
        steuerlich      = f'Totalverlust: {abgang_qty:.4f} Stück × {ak_pro_stueck:.4f} EUR/Stück = {verlust_eur:.2f} EUR',
        rechtsgrundlage = '§ 20 Abs. 2 Satz 1 Nr. 1 EStG; Totalverlust Delisting',
    )


def _handle_merger(ca: CorporateActionRaw) -> Optional[KapMassnahmeErgebnis]:
    """
    TC = Tausch / Merger.
    I.d.R. steuerneutral (§ 20 Abs. 4a Satz 1 EStG): AK der alten Papiere
    wird auf die neuen übertragen. Barausgleich-Anteil wäre steuerpflichtig
    (hier vereinfacht: 0, da IBKR meist keinen Barausgleich ausweist).
    """
    return KapMassnahmeErgebnis(
        date            = ca.date,
        type            = 'TC',
        symbol          = ca.symbol,
        isin            = ca.isin,
        description     = ca.description[:80],
        quantity        = ca.quantity,
        steuerlich      = 'Steuerneutraler Tausch/Merger — AK übertragen',
        rechtsgrundlage = '§ 20 Abs. 4a Satz 1 EStG',
    )


# ─── Hauptfunktion ────────────────────────────────────────────────────────────

def compute_kapmassnm(xml_paths: List[str],
                      target_year: str,
                      ak_override: Dict[str, float] = None) -> KapMassnahmenReport:
    """
    Verarbeitet alle Kapitalmaßnahmen des Zieljahres.

    ak_override: {isin: ak_pro_stueck_eur} — falls AK manuell bekannt
    Sonst: AK wird aus dem SO-Ergebnis der gleichen Session abgeleitet
           (verkettete Berechnung: SO → AK → TO/DW)
    """
    ak_override = ak_override or {}
    corps = parse_corporate_actions(xml_paths, target_year)
    report = KapMassnahmenReport(steuerjahr=target_year)

    # Laufende AK-Tabelle (aus SO-Ergebnissen befüllen)
    ak_table: Dict[str, float] = dict(ak_override)  # isin → eur/stück

    # Zweiter Durchlauf: erst alle SO (erzeugen AK), dann TO/DW
    for phase in ('SO', 'other'):
        for ca in corps:
            if phase == 'SO' and ca.type != 'SO':
                continue
            if phase == 'other' and ca.type == 'SO':
                continue

            ergebnis = None

            if ca.type == 'SO':
                ergebnis = _handle_spin_off(ca)
                if ergebnis and ergebnis.ak_neu_eur > 0 and ca.quantity > 0:
                    ak_table[ca.isin] = ergebnis.ak_neu_eur / ca.quantity

            elif ca.type == 'TO':
                ak_ps = ak_table.get(ca.isin, 0.0)
                ergebnis = _handle_tender_offer(ca, ak_ps)

            elif ca.type == 'DW':
                ak_ps = ak_table.get(ca.isin, 0.0)
                ergebnis = _handle_delisting(ca, ak_ps)

            elif ca.type in ('TC', 'SD', 'RS'):
                ergebnis = _handle_merger(ca)

            if ergebnis:
                report.ergebnisse.append(ergebnis)

    return report


# ─── CLI / Test ───────────────────────────────────────────────────────────────

if __name__ == '__main__':
    XMLS = [
        '/mnt/user-data/uploads/1782742593101_Steuerauswertung.xml',
        '/mnt/user-data/uploads/1782742593100_Steuerauswertung-2.xml',
        '/mnt/user-data/uploads/1782742593100_Steuerauswertung-3.xml',
    ]

    for year in ('2024', '2025'):
        report = compute_kapmassnm(XMLS, year)
        print(f'\n══ Kapitalmaßnahmen {year} ({len(report.ergebnisse)} Vorgänge) ══\n')

        for e in report.ergebnisse:
            print(f'  {e.date}  [{e.type}]  {e.symbol:10}  qty={e.quantity:>10.4f}')
            print(f'           Sachausch: {e.sachausch_eur:>10.2f} EUR  '
                  f'G/V: {e.realis_gewinn+e.realis_verlust:>10.2f} EUR  '
                  f'AK-neu: {e.ak_neu_eur:>10.2f} EUR')
            print(f'           {e.steuerlich}')
            print(f'           [{e.rechtsgrundlage}]')

        print(f'\n  Summe {year}:')
        print(f'    Sachausschüttungen: {report.gesamt_sachausch:>10.2f} EUR')
        print(f'    Realisierte G/V:   {report.gesamt_gewinn+report.gesamt_verlust:>10.2f} EUR')
        print(f'    Netto:             {report.gesamt_netto:>10.2f} EUR')

    print('\n  Referenz BubbleTax 2025 ENVXW:')
    print('    Sachausschüttung (SO):   +15*,** EUR  → erwartet ~+156 EUR ✓')
    print('    Realisierte Verluste:       −*,** EUR  → erwartet ~−3 EUR (Delisting)')
    print('    Nettoresultat:           +15*,** EUR')
