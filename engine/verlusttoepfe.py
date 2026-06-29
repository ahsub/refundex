"""
verlusttoepfe.py — Refundex Verlustverrechnungs-Engine v1.0
============================================================
Verlustverrechnungstöpfe nach § 20 Abs. 6 EStG.
Fundament der gesamten KAP-Berechnung — alle anderen Module liefern
ihre Ergebnisse hier ein.

Rechtsgrundlagen:
  § 20 Abs. 6 Satz 3 EStG — Allgemeiner Verlustverrechnungstopf
  § 20 Abs. 6 Satz 4 EStG — Aktienverlust-Topf (nur mit Aktiengewinnen)
  § 20 Abs. 6 Satz 5 EStG — Termingeschäfte-Topf (max 20.000 EUR/Jahr)
  § 43a Abs. 3 EStG       — Verlustverrechnung bei auszahlenden Stellen
  BMF-Schreiben Rn. 118   — Verlustverrechnungssystematik

Die 3 Töpfe:
┌─────────────────────────────────────────────────────────────────┐
│  TOPF 1: ALLGEMEIN (§ 20 Abs. 6 Satz 3)                       │
│  Dividenden, Zinsen, Stillhalter, FX, Zertifikate, KOs         │
│  Verrechnung: Mit allem aus Topf 1                              │
│  Vortrag: Unbegrenzt                                            │
├─────────────────────────────────────────────────────────────────┤
│  TOPF 2: AKTIEN (§ 20 Abs. 6 Satz 4)                          │
│  Aktienveräußerungsgewinne/-verluste                            │
│  Verrechnung: NUR mit Aktiengewinnen (nicht mit Topf 1/3!)     │
│  Vortrag: Unbegrenzt                                            │
├─────────────────────────────────────────────────────────────────┤
│  TOPF 3: TERMINGESCHÄFTE (§ 20 Abs. 6 Satz 5)                 │
│  CFD, Long-Optionen, Futures, Optionsscheine (Long)            │
│  Verrechnung: Mit Termingewinnen + Stillhalterprämien          │
│  MAX: 20.000 EUR Verlust/Jahr (Rest → Vortrag nächstes Jahr)  │
└─────────────────────────────────────────────────────────────────┘

WICHTIG — Häufige Irrtümer:
  ✗ Knock-Out Zertifikate sind KEINE Termingeschäfte → Topf 1!
  ✗ Stillhalter-Verluste sind KEINE Termingeschäfte → Topf 1!
  ✓ Long-Optionskäufe (wenn Verlust) → Topf 3
  ✓ CFD-Verluste → Topf 3
  ✓ Futures → Topf 3
"""

from dataclasses import dataclass, field
from typing import Optional
import json, os

# ─── Konstanten ───────────────────────────────────────────────────────────────
TERMIN_VERLUST_CAP = 20_000.0   # § 20 Abs. 6 Satz 5: max. 20.000 EUR/Jahr
SPARER_PAUSCHBETRAG = 1_000.0   # § 20 Abs. 9 EStG (je Person)


# ─── Eingabe-Kategorien ───────────────────────────────────────────────────────

@dataclass
class KapitaleinkunfteInput:
    """
    Alle Kapitaleinkünfte eines Steuerjahres — aufgeteilt nach Töpfen.
    Werte in EUR. Positiv = Gewinn/Ertrag, Negativ = Verlust.

    Befüllung durch die anderen Engine-Module:
      fifo_fx.py     → fx_guthaben
      kapmassnm.py   → sachausch_km, gl_km
      stillhalter    → stillhalter_praemien, stillhalter_glatt
      aktien_fifo.py → aktien_gewinne, aktien_verluste  (⬜ geplant)
      termingesch.py → termin_gewinne, termin_verluste   (⬜ geplant)
      vorabpauschale → vorabpauschale_steuerpflichtig
    """
    steuerjahr: int

    # ── TOPF 1: Allgemein ────────────────────────────────────────────────────
    # Stillhaltergeschäfte (§ 20 Abs. 1 Nr. 11)
    stillhalter_praemien:   float = 0.0   # Eingenommene Prämien (positiv)
    stillhalter_glatt:      float = 0.0   # Glattstellungskosten (negativ)

    # Dividenden (§ 20 Abs. 1 Nr. 1)
    dividenden:             float = 0.0   # Brutto (positiv)

    # Zinsen + Wertpapierleihe (§ 20 Abs. 1 Nr. 7)
    zinsen:                 float = 0.0   # Guthabenzinsen (positiv)
    syep:                   float = 0.0   # Wertpapierleihe (positiv)

    # FX-Guthaben (§ 20 Abs. 2 Nr. 7)
    fx_gewinne:             float = 0.0   # Aus FX-FIFO (positiv)
    fx_verluste:            float = 0.0   # Aus FX-FIFO (negativ)

    # Kapitalmaßnahmen (§ 20 Abs. 4a)
    km_sachausch:           float = 0.0   # Sachausschüttungen SO (positiv)
    km_gl:                  float = 0.0   # Realisierte G/V aus KM (pos/neg)

    # Zertifikate/Knock-Outs (§ 20 Abs. 2 Nr. 1) — Topf 1!
    zertifikate_gewinne:    float = 0.0   # ⬜ noch nicht implementiert
    zertifikate_verluste:   float = 0.0   # ⬜ noch nicht implementiert

    # ── TOPF 2: Aktien ───────────────────────────────────────────────────────
    aktien_gewinne:         float = 0.0   # ⬜ aktien_fifo.py (geplant)
    aktien_verluste:        float = 0.0   # ⬜ aktien_fifo.py (geplant)

    # ── TOPF 3: Termingeschäfte ──────────────────────────────────────────────
    termin_gewinne:         float = 0.0   # CFD/Long-Opt/Fut Gewinne ⬜
    termin_verluste:        float = 0.0   # CFD/Long-Opt/Fut Verluste ⬜

    # ── Vorabpauschale (KAP-INV, separat) ────────────────────────────────────
    vorabpauschale_stpfl:   float = 0.0   # vorabpauschale.py (nach TFS)

    # ── Anrechenbare Quellensteuer ────────────────────────────────────────────
    quellensteuer_anr:      float = 0.0   # DBA-begrenzt, KAP Zeile 41

    # ── Sollzinsen (NICHT abzugsfähig) ───────────────────────────────────────
    sollzinsen:             float = 0.0   # § 20 Abs. 9 — dokumentieren, nicht abziehen

    @property
    def stillhalter_netto(self):
        return self.stillhalter_praemien + self.stillhalter_glatt

    @property
    def topf1_brutto_positiv(self):
        """Alle positiven Bestandteile Topf 1"""
        return (self.stillhalter_praemien
                + self.dividenden
                + self.zinsen + self.syep
                + self.fx_gewinne
                + self.km_sachausch
                + max(0, self.km_gl)
                + self.zertifikate_gewinne)

    @property
    def topf1_brutto_negativ(self):
        """Alle negativen Bestandteile Topf 1"""
        return (self.stillhalter_glatt
                + self.fx_verluste
                + min(0, self.km_gl)
                + self.zertifikate_verluste)

    @property
    def topf1_netto(self):
        return self.topf1_brutto_positiv + self.topf1_brutto_negativ

    @property
    def topf2_netto(self):
        return self.aktien_gewinne + self.aktien_verluste

    @property
    def topf3_netto(self):
        return self.termin_gewinne + self.termin_verluste


# ─── Verlustvortrag-Persistenz ────────────────────────────────────────────────

@dataclass
class VerlustvortragState:
    """Jahresübergreifender Verlustvortrag je Topf."""
    allgemein:       float = 0.0   # Topf 1 Vortrag (negativ = Verlust)
    aktien:          float = 0.0   # Topf 2 Vortrag (negativ)
    termingeschaefte: float = 0.0  # Topf 3 Vortrag (negativ)

    def to_dict(self):
        return {
            'allgemein': self.allgemein,
            'aktien': self.aktien,
            'termingeschaefte': self.termingeschaefte,
        }

    @classmethod
    def from_dict(cls, d: dict) -> 'VerlustvortragState':
        return cls(
            allgemein        = float(d.get('allgemein', 0)),
            aktien           = float(d.get('aktien', 0)),
            termingeschaefte = float(d.get('termingeschaefte', 0)),
        )


def lade_verlustvortrag(pfad: str, steuerjahr: int) -> VerlustvortragState:
    """Lädt Verlustvortrag aus JSON-Datei für das Vorjahr."""
    if not os.path.exists(pfad):
        return VerlustvortragState()
    try:
        with open(pfad) as f:
            data = json.load(f)
        vorjahr = str(steuerjahr - 1)
        if vorjahr in data:
            return VerlustvortragState.from_dict(data[vorjahr])
    except (json.JSONDecodeError, KeyError):
        pass
    return VerlustvortragState()


def speichere_verlustvortrag(pfad: str, steuerjahr: int,
                              vortrag: VerlustvortragState):
    """Speichert neuen Verlustvortrag ins JSON-File."""
    data = {}
    if os.path.exists(pfad):
        try:
            with open(pfad) as f:
                data = json.load(f)
        except json.JSONDecodeError:
            pass
    data[str(steuerjahr)] = vortrag.to_dict()
    with open(pfad, 'w') as f:
        json.dump(data, f, indent=2)


# ─── Ergebnis-Struktur ────────────────────────────────────────────────────────

@dataclass
class VerlusttoepfeErgebnis:
    """
    Steuerliches Endergebnis nach Verlustverrechnung.
    Enthält alle KAP-Zeilen-Werte und den neuen Verlustvortrag.
    """
    steuerjahr: int

    # ── KAP-Zeilen (Eingabe ins Steuerformular) ───────────────────────────────
    kap_z19:  float = 0.0   # Ausländische Kapitalerträge (Topf 1 + Termin)
    kap_z20:  float = 0.0   # Aktiengewinne (Topf 2)
    kap_z22:  float = 0.0   # Verluste in Z19 (ohne Aktien) — absolut!
    kap_z23:  float = 0.0   # Aktienverluste — absolut!
    kap_z41:  float = 0.0   # Anrechenbare Quellensteuer

    # ── Sparer-Pauschbetrag ───────────────────────────────────────────────────
    sparer_einzel:    float = SPARER_PAUSCHBETRAG
    kap_z19_nach_sparer: float = 0.0
    kap_z20_nach_sparer: float = 0.0

    # ── Termingeschäfte-Cap Detail ────────────────────────────────────────────
    termin_cap_anwendbar: bool  = False
    termin_verlust_gesamt: float = 0.0
    termin_verlust_verrechenbar: float = 0.0
    termin_verlust_vortrag_neu: float = 0.0

    # ── Neuer Verlustvortrag (für nächstes Jahr) ──────────────────────────────
    vortrag_neu: VerlustvortragState = field(
        default_factory=VerlustvortragState)

    # ── Audit-Trail ───────────────────────────────────────────────────────────
    audit: list = field(default_factory=list)

    # ── Warnungen ─────────────────────────────────────────────────────────────
    warnungen: list = field(default_factory=list)


# ─── Hauptberechnung ─────────────────────────────────────────────────────────

def berechne_verlusttoepfe(
        inp: KapitaleinkunfteInput,
        vortrag_vorjahr: Optional[VerlustvortragState] = None,
        sparer_pauschs: float = SPARER_PAUSCHBETRAG,
        ) -> VerlusttoepfeErgebnis:
    """
    Verrechnet alle Kapitaleinkünfte nach den drei Töpfen.

    Reihenfolge (gemäß § 20 Abs. 6 EStG):
      1. Topf 3 (Termingeschäfte) — Cap 20.000 EUR prüfen
      2. Topf 2 (Aktien) — isoliert, kein Übertrag
      3. Topf 1 (Allgemein) — verbleibende Termingewinne einschließen
      4. Verlustvorträge aus Vorjahr anwenden
      5. Sparer-Pauschbetrag abziehen
    """
    vv = vortrag_vorjahr or VerlustvortragState()
    erg = VerlusttoepfeErgebnis(steuerjahr=inp.steuerjahr)
    audit = erg.audit

    # ─────────────────────────────────────────────────────────────────────────
    # SCHRITT 1: TOPF 3 — Termingeschäfte (§ 20 Abs. 6 Satz 5)
    # ─────────────────────────────────────────────────────────────────────────
    termin_g = inp.termin_gewinne
    termin_v = inp.termin_verluste   # negativ
    termin_vv = vv.termingeschaefte  # Vortrag aus Vorjahr (negativ)

    # Verrechenbare Gewinne = Termingewinne + Stillhalterprämien
    # (§ 20 Abs. 6 Satz 5: "Einkünfte aus Kapitalvermögen im Sinne des
    #  Abs. 1 Nr. 11" = Stillhalterprämien sind verrechenbar!)
    termin_gegenrechnung = termin_g + inp.stillhalter_praemien

    # Verluste inkl. Vortrag
    termin_verlust_total = termin_v + termin_vv  # negativ
    erg.termin_verlust_gesamt = termin_verlust_total

    termin_vortrag_neu = 0.0
    termin_in_topf1   = 0.0  # Netto-Termingewinn geht in Topf 1

    if termin_verlust_total < -0.005:
        erg.termin_cap_anwendbar = True
        # Verrechnung: min(|Verlust|, 20.000 + Vorjahresvortrag was schon cap-reduziert)
        # Cap gilt pro Jahr auf die zu verrechnenden Verluste
        max_verrechenbar = min(abs(termin_verlust_total), TERMIN_VERLUST_CAP)
        kann_verrechnen  = min(max_verrechenbar, max(0, termin_gegenrechnung))

        erg.termin_verlust_verrechenbar = -kann_verrechnen
        # Rest wird vorgetragen
        termin_vortrag_neu = termin_verlust_total + kann_verrechnen
        erg.termin_verlust_vortrag_neu = termin_vortrag_neu

        # Netto Terminergebnis für Topf 1
        termin_in_topf1 = termin_gegenrechnung - kann_verrechnen

        if abs(termin_verlust_total) > TERMIN_VERLUST_CAP:
            erg.warnungen.append(
                f'§20 Abs. 6 Satz 5: Termingeschäft-Verluste {termin_verlust_total:.2f} EUR '
                f'übersteigen 20.000 EUR-Cap. '
                f'Verrechenbar: {-kann_verrechnen:.2f} EUR. '
                f'Vortrag: {termin_vortrag_neu:.2f} EUR.')

        audit.append({
            'schritt': 'Topf3 Termingeschäfte',
            'termin_gewinne': termin_g,
            'termin_verluste': termin_v,
            'vortrag_vorjahr': termin_vv,
            'stillhalter_als_gegenrechnung': inp.stillhalter_praemien,
            'max_cap': TERMIN_VERLUST_CAP,
            'verrechenbar': kann_verrechnen,
            'neuer_vortrag': termin_vortrag_neu,
        })
    else:
        # Keine Terminverluste → alle Termingewinne in Topf 1
        termin_in_topf1 = termin_g

    # ─────────────────────────────────────────────────────────────────────────
    # SCHRITT 2: TOPF 2 — Aktien (§ 20 Abs. 6 Satz 4)
    # ─────────────────────────────────────────────────────────────────────────
    aktien_g  = inp.aktien_gewinne
    aktien_v  = inp.aktien_verluste   # negativ
    aktien_vv = vv.aktien              # Vortrag (negativ)

    aktien_netto = aktien_g + aktien_v + aktien_vv
    aktien_vortrag_neu = 0.0

    if aktien_netto >= 0:
        kap_z20 = aktien_netto
    else:
        kap_z20 = 0.0
        aktien_vortrag_neu = aktien_netto  # Vortrag nächstes Jahr

    erg.kap_z20 = kap_z20
    audit.append({
        'schritt': 'Topf2 Aktien',
        'aktien_gewinne': aktien_g,
        'aktien_verluste': aktien_v,
        'vortrag_vorjahr': aktien_vv,
        'aktien_netto': aktien_netto,
        'kap_z20': kap_z20,
        'vortrag_neu': aktien_vortrag_neu,
    })

    if aktien_g > 0 and aktien_v < -0.005:
        erg.warnungen.append(
            '§20 Abs. 6 Satz 4: Aktienverluste können NUR mit Aktiengewinnen '
            'verrechnet werden — nicht mit Zinsen, Dividenden oder Stillhalterprämien!')

    # ─────────────────────────────────────────────────────────────────────────
    # SCHRITT 3: TOPF 1 — Allgemein (§ 20 Abs. 6 Satz 3)
    # ─────────────────────────────────────────────────────────────────────────
    topf1_pos = (inp.stillhalter_praemien
                 + inp.dividenden
                 + inp.zinsen + inp.syep
                 + inp.fx_gewinne
                 + inp.km_sachausch
                 + max(0, inp.km_gl)
                 + inp.zertifikate_gewinne
                 + max(0, termin_in_topf1))   # Netto-Termingewinn falls vorhanden

    topf1_neg = (inp.stillhalter_glatt
                 + inp.fx_verluste
                 + min(0, inp.km_gl)
                 + inp.zertifikate_verluste)

    topf1_netto_aktuell = topf1_pos + topf1_neg

    # Vorjahresvortrag Topf 1 anwenden
    topf1_mit_vortrag = topf1_netto_aktuell + vv.allgemein
    topf1_vortrag_neu = 0.0

    if topf1_mit_vortrag >= 0:
        kap_z19 = topf1_mit_vortrag
    else:
        kap_z19 = 0.0
        topf1_vortrag_neu = topf1_mit_vortrag

    # KAP Zeile 22: Verluste die in Z19 enthalten sind (absolut, für Formular)
    # = Summe der negativen Einzelposten aus Topf 1
    verluste_in_z19_abs = abs(topf1_neg)
    # + Terminverluste die verrechnet wurden (aber begrenzt auf was tatsächlich verrechnet)
    verluste_in_z19_abs += abs(erg.termin_verlust_verrechenbar)

    erg.kap_z19 = kap_z19
    erg.kap_z22 = verluste_in_z19_abs
    erg.kap_z41 = inp.quellensteuer_anr

    audit.append({
        'schritt': 'Topf1 Allgemein',
        'positiv': topf1_pos,
        'negativ': topf1_neg,
        'netto_aktuell': topf1_netto_aktuell,
        'vortrag_vorjahr': vv.allgemein,
        'mit_vortrag': topf1_mit_vortrag,
        'kap_z19': kap_z19,
        'kap_z22_verluste': verluste_in_z19_abs,
        'vortrag_neu': topf1_vortrag_neu,
    })

    # ─────────────────────────────────────────────────────────────────────────
    # SCHRITT 4: Sparer-Pauschbetrag (§ 20 Abs. 9)
    # ─────────────────────────────────────────────────────────────────────────
    erg.sparer_einzel = sparer_pauschs
    erg.kap_z19_nach_sparer = max(0.0, kap_z19 - sparer_pauschs)
    erg.kap_z20_nach_sparer = max(0.0, kap_z20 - max(0, sparer_pauschs - kap_z19))

    # ─────────────────────────────────────────────────────────────────────────
    # SCHRITT 5: Neuer Verlustvortrag speichern
    # ─────────────────────────────────────────────────────────────────────────
    erg.vortrag_neu = VerlustvortragState(
        allgemein        = round(topf1_vortrag_neu, 2),
        aktien           = round(aktien_vortrag_neu, 2),
        termingeschaefte = round(termin_vortrag_neu, 2),
    )

    return erg


# ─── Formatierung ─────────────────────────────────────────────────────────────

def fmt_eur(v: float) -> str:
    sign = '+' if v >= 0 else '−'
    return f'{sign}{abs(v):,.2f} EUR'.replace(',', 'X').replace('.', ',').replace('X', '.')


def print_kap_uebersicht(erg: VerlusttoepfeErgebnis,
                          einzel: bool = True):
    """Gibt KAP-Zeilen-Übersicht auf der Konsole aus."""
    modus = 'Einzelkonto' if einzel else 'Gemeinschaftskonto (50 %)'
    f = 1.0 if einzel else 0.5

    print(f'\n══ Anlage KAP {erg.steuerjahr} — {modus} ══\n')
    print(f'  Zeile 19  Ausländische Kapitalerträge:  {fmt_eur(erg.kap_z19 * f)}')
    if erg.kap_z20 > 0:
        print(f'  Zeile 20  Kapitalerträge aus Aktien:    {fmt_eur(erg.kap_z20 * f)}')
    print(f'  Zeile 22  Enthaltene Verluste (Z19):    {fmt_eur(erg.kap_z22 * f)}')
    if erg.kap_z23 > 0:
        print(f'  Zeile 23  Aktienverluste:               {fmt_eur(erg.kap_z23 * f)}')
    print(f'  Zeile 41  Anrechenbare Quellensteuer:   {fmt_eur(erg.kap_z41 * f)}')
    print()
    print(f'  Nach Sparer-Pauschbetrag ({fmt_eur(erg.sparer_einzel * f)}):')
    print(f'  Zeile 19  steuerpflichtig:              {fmt_eur(erg.kap_z19_nach_sparer * f)}')

    if erg.termin_cap_anwendbar:
        print()
        print(f'  ⚠️  § 20 Abs. 6 Satz 5 — Termingeschäfte-Cap:')
        print(f'     Verluste gesamt:      {fmt_eur(erg.termin_verlust_gesamt)}')
        print(f'     Verrechenbar (Max):   {fmt_eur(erg.termin_verlust_verrechenbar)}')
        print(f'     Vortrag nächstes Jahr:{fmt_eur(erg.termin_verlust_vortrag_neu)}')

    if erg.vortrag_neu.allgemein < -0.01 or \
       erg.vortrag_neu.aktien < -0.01 or \
       erg.vortrag_neu.termingeschaefte < -0.01:
        print()
        print('  Verlustvortrag ins nächste Jahr:')
        if erg.vortrag_neu.allgemein < -0.01:
            print(f'     Allgemein:           {fmt_eur(erg.vortrag_neu.allgemein)}')
        if erg.vortrag_neu.aktien < -0.01:
            print(f'     Aktien:              {fmt_eur(erg.vortrag_neu.aktien)}')
        if erg.vortrag_neu.termingeschaefte < -0.01:
            print(f'     Termingeschäfte:     {fmt_eur(erg.vortrag_neu.termingeschaefte)}')

    if erg.warnungen:
        print()
        for w in erg.warnungen:
            print(f'  ⚠️  {w}')


# ─── CLI Demo ─────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print('══ verlusttoepfe.py Demo ══\n')

    # ── Szenario 1: Axel 2025 (nur Topf 1, kein Termin-Cap) ─────────────────
    print('--- Szenario 1: Axel 2025 (nur Stillhalter + FX + Div) ---')
    axel_2025 = KapitaleinkunfteInput(
        steuerjahr          = 2025,
        stillhalter_praemien= 27_532.11,
        stillhalter_glatt   = -22_994.13,
        dividenden          =  3_722.47,
        zinsen              =     59.56,
        syep                =      8.31,
        fx_gewinne          =    135.55,
        fx_verluste         =   -927.58,
        km_sachausch        =    156.24,
        km_gl               =     -3.12,
        quellensteuer_anr   =    280.36,
    )
    erg1 = berechne_verlusttoepfe(axel_2025)
    print_kap_uebersicht(erg1)

    # ── Szenario 2: Anleger mit Termingeschäft-Cap ───────────────────────────
    print('\n--- Szenario 2: Anleger mit CFD-Verlust über Cap ---')
    termin_anleger = KapitaleinkunfteInput(
        steuerjahr          = 2025,
        stillhalter_praemien=  8_000.0,
        stillhalter_glatt   = -1_500.0,
        dividenden          =  2_000.0,
        zinsen              =    300.0,
        termin_gewinne      =  5_000.0,
        termin_verluste     = -30_000.0,  # 30k CFD-Verlust!
        quellensteuer_anr   =    300.0,
    )
    erg2 = berechne_verlusttoepfe(termin_anleger)
    print_kap_uebersicht(erg2)

    # ── Szenario 3: Vortrag aus Vorjahr wird genutzt ─────────────────────────
    print('\n--- Szenario 3: Mit Verlustvortrag aus 2024 ---')
    vortrag_2024 = VerlustvortragState(
        allgemein        = -3_500.0,   # aus 2024
        aktien           = -8_000.0,   # aus Aktienverlusten 2024
        termingeschaefte = -15_000.0,  # Rest aus Cap 2024
    )
    anleger_2026 = KapitaleinkunfteInput(
        steuerjahr          = 2026,
        stillhalter_praemien= 12_000.0,
        stillhalter_glatt   = -4_000.0,
        dividenden          =  2_500.0,
        aktien_gewinne      = 10_000.0,
        aktien_verluste     = -1_000.0,
        termin_gewinne      =  8_000.0,
        termin_verluste     = -3_000.0,
        quellensteuer_anr   =    375.0,
    )
    erg3 = berechne_verlusttoepfe(anleger_2026, vortrag_vorjahr=vortrag_2024)
    print_kap_uebersicht(erg3)
    print(f'\n  Neuer Vortrag 2026→2027: {erg3.vortrag_neu.to_dict()}')
