# Refundex Engine

Python-basierte Steuerberechnungs-Engine für deutsche IBKR/CapTrader-Depot-Auswertungen.
Erstellt druckbare HTML-Reports für die Anlage KAP der deutschen Einkommensteuererklärung.

## Verzeichnisstruktur

```
engine/
├── config.py           ← Konfiguration (XML-Pfade, Steuerjahr, DBA-Sätze)
├── fifo_fx.py          ← FX-FIFO Engine (§ 20 Abs. 2 Nr. 7 EStG)
├── kapmassnm.py        ← Kapitalmaßnahmen (§ 20 Abs. 4a EStG)
├── build_report.py     ← HTML-Report-Generator (Anlage KAP)
├── requirements.txt    ← Abhängigkeiten
├── data/               ← IBKR XML-Exporte (NICHT im Repo — .gitignore)
│   ├── Steuerauswertung_2023.xml
│   ├── Steuerauswertung_2024.xml
│   └── Steuerauswertung_2025.xml
├── output/             ← Generierte Reports (NICHT im Repo — .gitignore)
└── tests/
    ├── test_fifo_fx.py     ← 18 Tests
    └── test_kapmassnm.py   ← 11 Tests
```

## Schnellstart

```bash
# 1. XML-Exporte aus IBKR in data/ ablegen
# 2. config.py anpassen (Pfade, Steuerjahr, Konto-ID)
# 3. Report generieren
python build_report.py
# → output/Steuerreport_2025_U12074449.html

# Tests ausführen
pip install pytest
pytest tests/ -v
# → 29/29 passed ✅
```

## Module

| Datei | Beschreibung | Status |
|-------|-------------|--------|
| `fifo_fx.py` | FX-FIFO: Guthaben/VB-Trennung, Zufluss-First, Rn. 131 BMF | ✅ v1.1 |
| `kapmassnm.py` | SO/TO/TC/DW: IBKR value-Feld, BubbleTax-Match | ✅ v1.0 |
| `build_report.py` | HTML-Report: Anlage KAP, Einzel/Gemeinschaftskonto, §20 Abs. 6 Satz 5 | ✅ v3.0 |
| `config.py` | Zentrale Konfiguration (kein Hardcoding in Modulen) | ✅ v1.0 |

## Ergebnisqualität (Abgleich BubbleTax 2025)

| Kategorie | Engine | BubbleTax | Δ |
|-----------|--------|-----------|---|
| Dividenden | 3.722,47 EUR | 3.7**,** EUR | ✅ |
| QST anrechenbar | 280,36 EUR | 28*,** EUR | ✅ |
| FX SEK Netto | +20,70 EUR | +2*,** EUR | ✅ |
| FX GBP Netto | +6,68 EUR | +*,** EUR | ✅ |
| ENVXW SO Sachausch. | +156,24 EUR | +15*,** EUR | ✅ |
| ENVXW Netto | +153,12 EUR | +15*,** EUR | ✅ |
| Stillhalter | 27.532 / -22.994 EUR | 26.*** / 22.*** EUR | ~1.300 EUR* |

*Differenz: IBKR-Kurse (fxRateToBase) vs. EZB-Referenzkurse über ~300 Transaktionen

## Rechtsgrundlagen

- § 20 EStG — Einkünfte aus Kapitalvermögen
- § 20 Abs. 1 Nr. 11 — Stillhaltergeschäfte (kein Termingeschäft-Cap)
- § 20 Abs. 2 Nr. 7 — Fremdwährungsgewinne
- § 20 Abs. 4a — Kapitalmaßnahmen (SO/TO/TC/DW)
- § 20 Abs. 6 Satz 5 — Termingeschäft-Verlustgrenze (2025: nicht anwendbar)
- § 32d Abs. 3 — Pflichtveranlagung bei ausländischem Broker
- Rn. 131 BMF (BStBl I 2025) — FX-FIFO-Methodik

## Datenschutz ⚠️

Generierte Reports und XML-Exporte enthalten persönliche Steuerdaten.
**Niemals in ein öffentliches Repository pushen!**
Beide Verzeichnisse (`data/`, `output/`) sind in `.gitignore` ausgeschlossen.

---
*Erstellt mit Refundex · ahsub/refundex/engine*
