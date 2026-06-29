# Refundex Engine

Python-basierte Steuerberechnungs-Engine für deutsche IBKR/CapTrader-Depot-Auswertungen.

## Dateien

| Datei | Beschreibung | Status |
|-------|-------------|--------|
| `fifo_fx.py` | FX-FIFO-Berechnung (§20 Abs. 2 Nr. 7 EStG, Rn. 131 BMF) | ✅ v1.1 |
| `build_report.py` | HTML-Steuerreport-Generator (Anlage KAP) | ✅ v2 |
| `kapmassnm.py` | Kapitalmaßnahmen / Spin-Offs (§20 Abs. 4a EStG) | ⬜ geplant |

## Nutzung

```bash
# 3 IBKR Flex Query XML-Exporte bereitstellen (Vorjahre für FIFO-Stack)
python build_report.py
# → erzeugt: Steuerreport_2025_UXXXXXXX.html + fx_audit_2025.json
```

## Rechtliche Grundlagen

- § 20 EStG — Einkünfte aus Kapitalvermögen  
- § 20 Abs. 2 Nr. 7 — Fremdwährungsgewinne  
- § 20 Abs. 1 Nr. 11 — Stillhaltergeschäfte  
- Rn. 131 BMF-Schreiben (BStBl I 2025) — FX-FIFO-Methodik

## Wichtig

Generierte Reports enthalten persönliche Steuerdaten → **niemals ins Repo pushen!**  
`.gitignore` sollte `*_U12074449*.html`, `*_audit_*.json` ausschließen.
