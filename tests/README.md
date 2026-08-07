# Refundex Test-Dateien

## test_flex_2025.xml
Minimaler realistischer Flex-XML-Export für 2025.

Enthält:
- AAPL Kauf + Verkauf (STK, Topf 1, +197 USD Gewinn)
- NVDA CSP Stillhalter (OPT Short, Topf 1, +640 USD Prämie)
- Dividenden AAPL + O mit US-Quellensteuer (15% DBA)
- Offene Position MSFT

Steuerliche Erwartungswerte:
- Topf 1 Aktien: +182 EUR
- Topf 1 Stillhalter: +588 EUR
- Dividenden netto: +58 EUR
- Quellensteuer anrechenbar: 10 EUR

Verwendung: kap.html → Datei hochladen → Ergebnisse prüfen

## Kirchensteuer-Test (manuell im ⚙ Kontoprofil)

Inhaber 1: NRW, KiSt 9%
  → Auf 5.000 EUR Kapitalertrag:
  → AbgSt: 1.222,49 EUR (24,45%)
  → KiSt:    110,02 EUR
  → Gesamt: 1.332,52 EUR

Inhaber 2: Bayern, KiSt 8%
  → Auf 5.000 EUR Kapitalertrag:
  → AbgSt: 1.225,49 EUR (24,51%)
  → KiSt:     98,04 EUR
  → Gesamt: 1.323,53 EUR

## Vorabpauschale-Test (manuell im ⚙ Kontoprofil → ETF)

iShares Core MSCI World (IE00B4L5Y983):
  Fondstyp: Aktienfonds (TFS 30%)
  120 Anteile · Kurs 01.01.: 78,50€ · Kurs 31.12.: 85,20€
  Thesaurierend · Basiszins 2025: 2,53%
  → Vorabpauschale: 166,83€ brutto
  → Steuerpflichtig: 116,78€ (nach TFS 30%)
  → Anlage KAP-INV Zeile 9
