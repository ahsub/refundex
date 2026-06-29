# Refundex Engine

Python-basierte Steuerberechnungs-Engine für deutsche IBKR/CapTrader-Depot-Auswertungen.

## Module

| Datei | Beschreibung | Status |
|-------|-------------|--------|
| `fifo_fx.py` | FX-FIFO (§ 20 Abs. 2 Nr. 7 EStG, Rn. 131 BMF) — Guthaben/VB-Trennung, Zufluss-First | ✅ v1.1 |
| `kapmassnm.py` | Kapitalmaßnahmen (§ 20 Abs. 4a EStG) — SO/TO/TC/DW, IBKR value-Feld | ✅ v1.0 |
| `vorabpauschale.py` | Vorabpauschale (§ 18 InvStG) — Aktienfonds/Misch/Immobilien DE+Ausl., Fälligkeit | ✅ v1.0 |
| `build_report.py` | HTML-Report Anlage KAP — Einzel/Gemeinschaftskonto, §20 Abs. 6 Satz 5 | ✅ v3.0 |
| `config.py` | Zentrale Konfiguration — XML-Pfade, DBA-Sätze, Basiszins | ✅ v1.0 |

## Schnellstart

```bash
# 1. XML-Exporte in data/ ablegen, config.py anpassen
python build_report.py    # → output/Steuerreport_YYYY_UXXXXXXX.html
pytest tests/ -v          # → 54/54 passed ✅
```

## Vorabpauschale (§ 18 InvStG)

```python
from vorabpauschale import ETFPosition, compute_vorabpauschale

positionen = [
    ETFPosition(
        isin='IE00B4L5Y983', name='iShares MSCI World',
        fondstyp='aktien',       # 'aktien' | 'misch' | 'immobilien_de' | 'immobilien_aus' | 'anleihen'
        anteile=100,
        kurs_01_01=80.0,         # Rücknahmepreis 01.01. in EUR
        kurs_31_12=88.0,         # Rücknahmepreis 31.12. in EUR (für Begrenzung)
        ausschuettung=0,         # Tatsächliche Ausschüttungen im Jahr (EUR)
        thesaurierend=True
    ),
]
report = compute_vorabpauschale(positionen, steuerjahr=2025)
print(f'Steuerpflichtig: {report.gesamt_steuerpflichtig:.2f} EUR → Anlage KAP-INV')
```

Basiszinsen: 2023=2,55% · 2024=2,29% · 2025=2,53%*

*⚠️ 2025 Basiszins bitte gegen aktuelles BMF-Schreiben verifizieren. kap.html zeigt 2,30% (ältere Quelle).

Teilfreistellung:
- Aktienfonds: 30 % steuerfrei
- Mischfonds: 15 % steuerfrei
- Immobilienfonds Inland: 60 % steuerfrei
- Immobilienfonds Ausland: 80 % steuerfrei ← höher als Inland!
- Anleihen/Sonstige: 0 %

**Wichtig:** IBKR/CapTrader führen Vorabpauschale nicht automatisch ab.
Muss vom Anleger selbst ermittelt und in Anlage KAP-INV erklärt werden.

## Tests: 54/54 ✅

```
tests/test_fifo_fx.py       18 Tests — FX-FIFO, SEK/GBP/USD, Zufluss-First
tests/test_kapmassnm.py     11 Tests — ENVXW SO/TO/DW, BubbleTax-Referenz
tests/test_vorabpauschale.py 25 Tests — Basiszins, TFS, Begrenzung, Fälligkeit
```

## Ergebnisqualität (BubbleTax-Abgleich 2025)

| Kategorie | Engine | BubbleTax | Δ |
|-----------|--------|-----------|---|
| Dividenden | 3.722,47 EUR | 3.7**,** EUR | ✅ |
| QST anrechenbar | 280,36 EUR | 28*,** EUR | ✅ |
| FX SEK Netto | +20,70 EUR | +2*,** EUR | ✅ |
| ENVXW SO Sachausch. | +156,24 EUR | +15*,** EUR | ✅ |
| ENVXW Netto | +153,12 EUR | +15*,** EUR | ✅ |
| Stillhalter Netto | +4.537 EUR | +3.2** EUR | ~IBKR vs EZB Kurse |

## Rechtsgrundlagen

- § 18 InvStG — Vorabpauschale
- § 20 InvStG — Teilfreistellung
- § 20 EStG — Einkünfte aus Kapitalvermögen
- § 20 Abs. 4a — Kapitalmaßnahmen
- § 20 Abs. 6 Satz 5 — Termingeschäft-Verlustgrenze
- § 32d Abs. 3 — Pflichtveranlagung bei ausländischem Broker
- Rn. 131 BMF (BStBl I 2025) — FX-FIFO

---
*Refundex Engine · ahsub/refundex/engine*
