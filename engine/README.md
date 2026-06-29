# Refundex Engine

Python-basierte Steuerberechnungs-Engine für deutsche IBKR/CapTrader-Depot-Auswertungen.

## Module

| Datei | § EStG | Topf | Status |
|-------|--------|------|--------|
| `fifo_fx.py` | § 20 Abs. 2 Nr. 7, Rn. 131 BMF | 1 | ✅ v1.1 |
| `kapmassnm.py` | § 20 Abs. 4a (SO/TO/TC/DW) | 1 | ✅ v1.0 |
| `vorabpauschale.py` | § 18 InvStG, § 20 InvStG | KAP-INV | ✅ v1.0 |
| `verlusttoepfe.py` | § 20 Abs. 6 Satz 3/4/5 | 1+2+3 | ✅ v1.0 |
| `aktien_fifo.py` | § 20 Abs. 2 Nr. 1 | **2 (Aktien)** | ✅ v1.0 |
| `termingeschaefte.py` | § 20 Abs. 2 Nr. 3 | **3 (Termin, Cap 20k)** | ✅ v1.0 |
| `build_report.py` | Anlage KAP HTML | — | ✅ v3.0 |
| `config.py` | Konfiguration | — | ✅ v1.0 |

## Tests: 95/95 ✅

```
test_fifo_fx.py          18 Tests
test_kapmassnm.py        11 Tests
test_vorabpauschale.py   25 Tests
test_verlusttoepfe.py    25 Tests
test_aktien_fifo.py       8 Tests
test_termingeschaefte.py  8 Tests
```

## Verlustverrechnungstöpfe

```
TOPF 1 — Allgemein (§ 20 Abs. 6 Satz 3)
├── Dividenden / Zinsen / SYEP         fifo_fx.py + build_report.py
├── Stillhalterprämien / FX            fifo_fx.py
├── Kapitalmaßnahmen (SO/TO/DW)        kapmassnm.py
└── Zertifikate / Knock-Outs           ⬜ (zertifikate.py geplant)

TOPF 2 — Aktien (§ 20 Abs. 6 Satz 4)  aktien_fifo.py
├── Nur mit Aktiengewinnen verrechenbar
└── FIFO je ISIN, jahresübergreifend

TOPF 3 — Termingeschäfte (§ 20 Abs. 6 Satz 5)  termingeschaefte.py
├── Long-Optionen / CFD / Futures / Warrants
├── Verrechenbar mit Termin-Gewinnen + Stillhalterprämien
└── MAX 20.000 EUR Verlust/Jahr → verlusttoepfe.py
```

**Häufige Irrtümer (bereits abgefangen):**
- Knock-Out Zertifikate → Topf 1 (keine Termingeschäfte!)
- Stillhalter-Verluste → Topf 1 (kein Cap!)
- Long-Option-Verluste → Topf 3 (Cap 20.000 EUR!)

## Quickstart

```bash
python build_report.py  # → output/Steuerreport_YYYY.html
pytest tests/ -v        # → 95/95 ✅
```

---
*Refundex Engine · ahsub/refundex/engine*
