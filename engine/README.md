# Refundex Engine

Python-basierte Steuerberechnungs-Engine für deutsche IBKR/CapTrader-Depot-Auswertungen.

## Module

| Datei | Beschreibung | Status |
|-------|-------------|--------|
| `fifo_fx.py` | FX-FIFO (§ 20 Abs. 2 Nr. 7 EStG, Rn. 131 BMF) — Guthaben/VB-Trennung, Zufluss-First | ✅ v1.1 |
| `kapmassnm.py` | Kapitalmaßnahmen (§ 20 Abs. 4a EStG) — SO/TO/TC/DW, IBKR value-Feld | ✅ v1.0 |
| `build_report.py` | HTML-Steuerreport-Generator — Anlage KAP, Einzel/Gemeinschaftskonto | ✅ v2 |
| `requirements.txt` | Abhängigkeiten (Python stdlib only) | ✅ |
| `dividenden.py` | Dividenden + QST-Anrechnung je DBA | ⬜ geplant |
| `pytest/` | Unit-Tests je §-Paragraph | ⬜ geplant |

## Nutzung

```bash
# 3 IBKR Flex Query XML-Exporte bereitstellen (mind. 3 Jahre für korrekten FIFO-Stack)
python build_report.py
# → erzeugt lokal:
#     Steuerreport_2025_UXXXXXXX.html   (druckbares PDF)
#     fx_audit_2025.json                (Prüfnachweis Finanzamt)
```

## Ergebnisqualität (Abgleich mit BubbleTax 2025)

| Kategorie | Engine | BubbleTax | Status |
|-----------|--------|-----------|--------|
| Stillhaltergeschäfte | 27.532 / −22.994 EUR | 26.XXX / −22.XXX EUR | ✅ |
| Dividenden | 3.722 EUR | 3.7XX EUR | ✅ |
| QST anrechenbar | 280,36 EUR | 28X EUR | ✅ |
| FX SEK | +20,70 EUR | +2X EUR | ✅ |
| FX GBP | +6,68 EUR | +X EUR | ✅ |
| ENVXW SO | +156,24 EUR | +15X EUR | ✅ |
| ENVXW DW | −3,12 EUR | −X EUR | ✅ |

## Rechtliche Grundlagen

- § 20 EStG — Einkünfte aus Kapitalvermögen
- § 20 Abs. 1 Nr. 11 — Stillhaltergeschäfte
- § 20 Abs. 2 Nr. 7 — Fremdwährungsgewinne
- § 20 Abs. 4a — Kapitalmaßnahmen
- § 20 Abs. 6 Satz 5 — Termingeschäft-Verlustbeschränkung
- Rn. 131 BMF (BStBl I 2025) — FX-FIFO-Methodik

## Datenschutz

Generierte Reports enthalten persönliche Steuerdaten — **niemals ins Repo!**

`.gitignore` muss enthalten:
```
engine/Steuerreport_*.html
engine/*_audit_*.json
engine/*.xml
```
