"""
vorabpauschale.py — Refundex Vorabpauschale-Engine v1.0
=========================================================
Berechnung der Vorabpauschale für Investmentfonds (ETFs) nach deutschem InvStG.

Rechtsgrundlagen:
  § 16 InvStG   — Besteuerung von Investmenterträgen
  § 18 InvStG   — Vorabpauschale (Berechnung)
  § 18 Abs. 3   — Zufluss am ersten Werktag des Folgejahres
  § 20 InvStG   — Teilfreistellung (TFS) nach Fondstyp
  § 56 InvStG   — Übergangsregelung (Alt-Anteile vor 2018)
  Anlage KAP-INV — Steuerformular (nicht Anlage KAP!)

Berechnungsformel:
  Basisertrag  = Rücknahmepreis 01.01. × Basiszins × 0,70 × Anteile
  Begrenzt auf: Wertzuwachs im Jahr (d.h. Basisertrag ≤ NAV-Anstieg)
  Vorabpauschale = max(0, Basisertrag − tatsächliche Ausschüttungen)
  Steuerpflichtig = Vorabpauschale × (1 − Teilfreistellungssatz)

Teilfreistellungssätze (§ 20 InvStG):
  Aktienfonds:          30 % steuerfrei → 70 % steuerpflichtig
  Mischfonds:           15 % steuerfrei → 85 % steuerpflichtig
  Immobilienfonds DE:   60 % steuerfrei → 40 % steuerpflichtig
  Immobilienfonds Ausl: 80 % steuerfrei → 20 % steuerpflichtig
  Sonstige (Anleihen):   0 % steuerfrei → 100 % steuerpflichtig

Fälligkeit: erster Werktag des Folgejahres (§ 18 Abs. 3 InvStG).
  → 2025er Vorabpauschale fließt z.B. am 02.01.2026 zu.
  → Steuerlich relevant für Veranlagungszeitraum 2025.

Hinweis ausländischer Broker:
  IBKR / CapTrader führen die Vorabpauschale NICHT automatisch ab.
  Der Anleger muss sie selbst ermitteln und in der Anlage KAP-INV erklären.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import date
import calendar

# ─── Basiszins-Tabelle (BMF-Veröffentlichungen) ───────────────────────────────
# Quelle: BMF-Schreiben jeweils zu Jahresbeginn
# Formel: Basiszins = 70 % des Jahres-Basiszinssatzes der Deutschen Bundesbank
# https://www.bundesfinanzministerium.de → Steuern → Kapitalvermögen

BASISZINS: Dict[int, float] = {
    2019: 0.0052,   # 0,52 %
    2020: 0.0000,   # 0,00 % (negativ → 0 gesetzt, keine Vorabpauschale)
    2021: 0.0000,   # 0,00 %
    2022: 0.0000,   # -0,88 % → negativ → 0 gesetzt
    2023: 0.0255,   # 2,55 %  (BMF-Schreiben Jan 2023)
    2024: 0.0229,   # 2,29 %  (BMF-Schreiben Jan 2024)
    2025: 0.0253,   # 2,53 %  ← ⚠️ Bitte mit aktuellem BMF-Schreiben verifizieren!
}
# ⚠️ WICHTIG: 2025er Basiszins muss gegen offizielle BMF-Veröffentlichung
#              abgeglichen werden! kap.html verwendet 2,30 % (ältere Version).

# ─── Teilfreistellungssätze (§ 20 InvStG) ────────────────────────────────────
TEILFREISTELLUNG: Dict[str, float] = {
    'aktien':        0.30,   # Aktienfonds ≥ 51 % Aktienquote
    'misch':         0.15,   # Mischfonds  ≥ 25 % Aktienquote
    'immobilien_de': 0.60,   # Immobilienfonds ≥ 51 % dt. Immobilien
    'immobilien_aus':0.80,   # Immobilienfonds ≥ 51 % ausländische Immobilien
    'anleihen':      0.00,   # Renten-/Anleihenfonds (keine TFS)
    'sonstige':      0.00,   # Alle anderen Fonds
}

FONDSTYP_LABEL: Dict[str, str] = {
    'aktien':        'Aktienfonds (≥51 % Aktien)',
    'misch':         'Mischfonds (≥25 % Aktien)',
    'immobilien_de': 'Immobilienfonds Inland (≥51 % DE)',
    'immobilien_aus':'Immobilienfonds Ausland (≥51 % Ausl.)',
    'anleihen':      'Anleihenfonds (keine TFS)',
    'sonstige':      'Sonstige Fonds (keine TFS)',
}


# ─── Datenstrukturen ─────────────────────────────────────────────────────────

@dataclass
class ETFPosition:
    """
    Eine ETF/Fonds-Position für die Vorabpauschale-Berechnung.
    Daten müssen manuell oder aus Jahressteuerbescheinigung eingepflegt werden,
    da IBKR diese nicht im Flex Query liefert.
    """
    isin:          str
    name:          str
    fondstyp:      str    # Schlüssel aus TEILFREISTELLUNG
    anteile:       float  # Anzahl Anteile am 01.01. des Steuerjahres
    kurs_01_01:    float  # Rücknahmepreis am 01.01. in EUR
    kurs_31_12:    float  # Rücknahmepreis am 31.12. in EUR (für Wertzuwachsbegrenzung)
    ausschuettung: float  # Tatsächliche Ausschüttungen im Jahr in EUR (0 bei Thesaurierern)
    thesaurierend: bool   # True = thesaurierend (kein Abzug von Ausschüttungen)


@dataclass
class VorabpauschaleErgebnis:
    """Berechnungsergebnis für eine einzelne ETF-Position"""
    isin:               str
    name:               str
    fondstyp:           str
    anteile:            float
    kurs_01_01:         float
    kurs_31_12:         float
    basiszins:          float
    basisertrag_pa:     float   # Basisertrag pro Anteil
    basisertrag_gesamt: float   # × Anteile
    wertzuwachs:        float   # Kursanstieg im Jahr (Begrenzungsgrundlage)
    basisertrag_begr:   float   # Basisertrag nach Wertzuwachsbegrenzung
    ausschuettung:      float   # Tatsächliche Ausschüttungen
    vorabpauschale:     float   # Brutto (vor TFS)
    tfs_satz:           float   # Teilfreistellungssatz
    steuerpflichtig:    float   # Netto (nach TFS) → in KAP-INV
    faelligkeit:        str     # Erster Werktag des Folgejahres
    kap_inv_zeile:      str     # Zugehörige KAP-INV-Zeile
    hinweis:            str     = ''


@dataclass
class VorabpauschaleReport:
    """Gesamtergebnis aller ETF-Positionen"""
    steuerjahr:     int
    basiszins:      float
    positionen:     List[VorabpauschaleErgebnis] = field(default_factory=list)
    faelligkeit:    str  = ''

    @property
    def gesamt_brutto(self):
        return sum(e.vorabpauschale for e in self.positionen)

    @property
    def gesamt_steuerpflichtig(self):
        return sum(e.steuerpflichtig for e in self.positionen)

    @property
    def keine_vorabpauschale(self):
        return all(e.vorabpauschale == 0 for e in self.positionen)


# ─── Hilfsfunktionen ─────────────────────────────────────────────────────────

def _erster_werktag(jahr: int) -> str:
    """
    Gibt den ersten Werktag (Mo-Fr, kein Feiertag) des Folgejahres zurück.
    01.01. = Neujahr ist immer Feiertag → Start bei 02.01.
    Bundeseinheitliche Feiertage berücksichtigt (Neujahr, ggf. Heilige Drei Könige).
    """
    from datetime import timedelta
    # Neujahr ist immer Feiertag → frühestens 02.01.
    d = date(jahr + 1, 1, 2)
    # Hl. Drei Könige (06.01.) ist in BW, BY, ST Feiertag — hier konservativ ignoriert
    while d.weekday() >= 5:  # 5=Samstag, 6=Sonntag
        d = d + timedelta(days=1)
    return d.isoformat()


def _kap_inv_zeile(fondstyp: str, thesaurierend: bool) -> str:
    """Ordnet Fondstyp der KAP-INV-Zeile zu."""
    mapping = {
        'aktien':         'Zeile 9 (Aktienfonds)',
        'misch':          'Zeile 12 (Mischfonds)',
        'immobilien_de':  'Zeile 15 (Immobilienfonds Inland)',
        'immobilien_aus': 'Zeile 18 (Immobilienfonds Ausland)',
        'anleihen':       'Zeile 6 (Sonstige)',
        'sonstige':       'Zeile 6 (Sonstige)',
    }
    return mapping.get(fondstyp, 'Zeile 6')


# ─── Hauptberechnung ─────────────────────────────────────────────────────────

def berechne_vorabpauschale(pos: ETFPosition,
                             steuerjahr: int) -> VorabpauschaleErgebnis:
    """
    Berechnet die Vorabpauschale für eine ETF-Position.

    Formel (§ 18 InvStG):
      Basisertrag p.A. = Kurs_01.01 × Basiszins × 0,70
      Basisertrag Ges. = Basisertrag_p.A. × Anteile
      Begrenzung       = min(Basisertrag_Ges., Wertzuwachs)
                         (Wertzuwachs = max(0, Kurs_31.12 - Kurs_01.01) × Anteile)
      Vorabpauschale   = max(0, Begrenzung − tatsächliche Ausschüttungen)
      Steuerpflichtig  = Vorabpauschale × (1 − TFS-Satz)
    """
    basiszins = BASISZINS.get(steuerjahr, 0.0)
    tfs_satz  = TEILFREISTELLUNG.get(pos.fondstyp, 0.0)

    # Basisertrag
    basisertrag_pa     = pos.kurs_01_01 * basiszins * 0.70
    basisertrag_gesamt = basisertrag_pa * pos.anteile

    # Wertzuwachsbegrenzung
    kursanstieg   = max(0.0, pos.kurs_31_12 - pos.kurs_01_01)
    wertzuwachs   = kursanstieg * pos.anteile
    basisertrag_b = min(basisertrag_gesamt, wertzuwachs)

    # Vorabpauschale (thesaurierend: keine Ausschüttung abzuziehen)
    ausschuettung  = 0.0 if pos.thesaurierend else pos.ausschuettung
    vorabpauschale = max(0.0, basisertrag_b - ausschuettung)

    # Steuerpflichtig nach TFS
    steuerpflichtig = round(vorabpauschale * (1 - tfs_satz), 2)

    # Hinweise
    hinweis = ''
    if basiszins <= 0:
        hinweis = f'Basiszins {steuerjahr} ≤ 0 % → keine Vorabpauschale'
    elif basisertrag_b < basisertrag_gesamt:
        diff = round(basisertrag_gesamt - basisertrag_b, 2)
        hinweis = f'Basisertrag durch Wertzuwachs begrenzt (−{diff:.2f} EUR)'
    elif vorabpauschale < basisertrag_b:
        hinweis = f'Basisertrag durch Ausschüttungen gemindert (−{ausschuettung:.2f} EUR)'

    return VorabpauschaleErgebnis(
        isin               = pos.isin,
        name               = pos.name,
        fondstyp           = pos.fondstyp,
        anteile            = pos.anteile,
        kurs_01_01         = pos.kurs_01_01,
        kurs_31_12         = pos.kurs_31_12,
        basiszins          = basiszins,
        basisertrag_pa     = round(basisertrag_pa, 6),
        basisertrag_gesamt = round(basisertrag_gesamt, 2),
        wertzuwachs        = round(wertzuwachs, 2),
        basisertrag_begr   = round(basisertrag_b, 2),
        ausschuettung      = round(ausschuettung, 2),
        vorabpauschale     = round(vorabpauschale, 2),
        tfs_satz           = tfs_satz,
        steuerpflichtig    = steuerpflichtig,
        faelligkeit        = _erster_werktag(steuerjahr),
        kap_inv_zeile      = _kap_inv_zeile(pos.fondstyp, pos.thesaurierend),
        hinweis            = hinweis,
    )


def compute_vorabpauschale(positionen: List[ETFPosition],
                            steuerjahr: int) -> VorabpauschaleReport:
    """Berechnet Vorabpauschale für alle ETF-Positionen."""
    basiszins = BASISZINS.get(steuerjahr, 0.0)
    report    = VorabpauschaleReport(
        steuerjahr  = steuerjahr,
        basiszins   = basiszins,
        faelligkeit = _erster_werktag(steuerjahr),
    )
    for pos in positionen:
        report.positionen.append(berechne_vorabpauschale(pos, steuerjahr))
    return report


# ─── CLI / Demo ──────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print('══ Vorabpauschale Demo-Berechnung ══\n')
    print(f'Basiszinsen: {BASISZINS}\n')

    # Typische Beispiel-Portfolios
    demo_positionen = [
        ETFPosition(
            isin='IE00B4L5Y983', name='iShares Core MSCI World ETF',
            fondstyp='aktien', anteile=100,
            kurs_01_01=80.00, kurs_31_12=88.00,
            ausschuettung=0, thesaurierend=True
        ),
        ETFPosition(
            isin='IE00B3RBWM25', name='Vanguard FTSE All-World ETF (ausschüttend)',
            fondstyp='aktien', anteile=50,
            kurs_01_01=110.00, kurs_31_12=118.00,
            ausschuettung=95.0,   # z.B. 1,90 EUR/Anteil × 50
            thesaurierend=False
        ),
        ETFPosition(
            isin='IE00BKX55T58', name='Vanguard FTSE Developed World ETF (thes.)',
            fondstyp='aktien', anteile=200,
            kurs_01_01=35.00, kurs_31_12=33.00,  # Kursrückgang!
            ausschuettung=0, thesaurierend=True
        ),
        ETFPosition(
            isin='DE0009807016', name='Deka ImmobilienEuropa (Inland)',
            fondstyp='immobilien_de', anteile=30,
            kurs_01_01=50.00, kurs_31_12=52.00,
            ausschuettung=15.0, thesaurierend=False
        ),
    ]

    report = compute_vorabpauschale(demo_positionen, 2025)

    print(f'Steuerjahr:  {report.steuerjahr}')
    print(f'Basiszins:   {report.basiszins*100:.2f} %')
    print(f'Fälligkeit:  {report.faelligkeit} (erster Werktag 2026)')
    print()

    for e in report.positionen:
        print(f'── {e.name} ({e.isin}) ──')
        print(f'   Fondstyp:        {FONDSTYP_LABEL[e.fondstyp]}  |  TFS: {e.tfs_satz*100:.0f} %')
        print(f'   Anteile:         {e.anteile}')
        print(f'   Kurs 01.01.:     {e.kurs_01_01:.2f} EUR')
        print(f'   Kurs 31.12.:     {e.kurs_31_12:.2f} EUR')
        print(f'   Basisertrag p.A.:{e.basisertrag_pa:.4f} EUR/Anteil')
        print(f'   Basisertrag ges.:{e.basisertrag_gesamt:.2f} EUR')
        print(f'   Wertzuwachs:     {e.wertzuwachs:.2f} EUR  → begrenzt auf: {e.basisertrag_begr:.2f} EUR')
        print(f'   Ausschüttung:    {e.ausschuettung:.2f} EUR')
        print(f'   Vorabpauschale:  {e.vorabpauschale:.2f} EUR (brutto)')
        print(f'   Steuerpflichtig: {e.steuerpflichtig:.2f} EUR  →  {e.kap_inv_zeile}')
        if e.hinweis:
            print(f'   ⚠️  {e.hinweis}')
        print()

    print('══ Gesamtergebnis ══')
    print(f'   Vorabpauschale brutto:       {report.gesamt_brutto:.2f} EUR')
    print(f'   Steuerpflichtig (nach TFS):  {report.gesamt_steuerpflichtig:.2f} EUR')
    print(f'   → Anlage KAP-INV einzutragen')
    print()
    print('⚠️  Basiszins 2025 (2,53 %): Bitte mit aktuellem BMF-Schreiben abgleichen!')
    print('   kap.html verwendet 2,30 % → ggf. kap.html aktualisieren nötig')
