# Refundex — Normalisiertes Ertragsdatenmodell (Säule 2)

**Version:** 1.0
**Stand:** 03.07.2026
**Ablage:** `ahsub/refundex/docs/DATENMODELL_ERTRAEGE.md`
**Status:** Spezifikation (Roadmap-Item 2.6) — noch kein Code. Referenz: STRATEGIE.md Grundgesetz 6.

---

## 1. Zweck & Grundsatz

Die Quellensteuer-Logik (Cockpit 2.7, später Formular-Vorbefüllung 3.7) setzt **niemals direkt auf einem Broker-Format auf**, sondern ausschließlich auf diesem Datenmodell. Adapter übersetzen beliebige Quellen hinein; das Cockpit kennt nur den Kontrakt. Damit ist Säule 2 broker-neutral by design.

```
Flex Query CSV ──► Adapter 1 ─┐
Manuelle Eingabe ─► Adapter 2 ─┼──► ErtragsDatensatz[] ──► QSt-Cockpit
PDF (Phase 3)  ──► Adapter 3 ─┘         (dieser Kontrakt)      │
                 (nur mit Review-Gate)                          ▼
                                                    Formular-Vorbefüllung
```

**Designprinzipien:**
1. **Beträge als Ganzzahl-Cent** der jeweiligen Währung (keine Floats — Rundungsfehler sind in Steuerkontexten inakzeptabel).
2. **Jeder Datensatz trägt seine Herkunft** (`quelle`, `belegRef`) — Belegketten-Prinzip.
3. **Zwei Granularitäten erlaubt:** `EREIGNIS` (eine Dividendenzahlung, aus Adapter 1/3) und `AGGREGAT` (Jahressumme je Position/Land, aus Adapter 2). Das Cockpit rechnet mit beiden; die Formular-Vorbefüllung (3.7) verlangt `EREIGNIS`-Granularität.
4. **Keine berechneten Felder im Datensatz.** Anrechenbarkeit, Überschuss, Netto-Potenzial sind Cockpit-Output, nie Adapter-Input. Adapter erfassen nur, was in der Quelle steht.
5. **Validierung ist Pflicht, Ablehnung ist erlaubt:** Ein Adapter, der ein Feld nicht sicher befüllen kann, lehnt den Datensatz ab oder markiert ihn `unvollstaendig` — er rät niemals (No-Hallucination).

---

## 2. Der Kontrakt: `ErtragsDatensatz`

```json
{
  "schemaVersion": "1.0",
  "id": "2025-03-14_CH0038863350_DIV_001",
  "granularitaet": "EREIGNIS",

  "instrument": {
    "isin": "CH0038863350",
    "symbol": "NESN",
    "name": "Nestlé S.A.",
    "typ": "AKTIE"
  },

  "quellenland": "CH",
  "ertragsart": "DIVIDENDE",
  "zahltag": "2025-03-14",
  "steuerjahr": 2025,

  "betraege": {
    "waehrung": "CHF",
    "bruttoCent": 250000,
    "qstEinbehaltenCent": 87500,
    "nettoCent": 162500
  },

  "betraegeEur": {
    "kurs": 0.9421,
    "kursQuelle": "IBKR_FXRateToBase",
    "bruttoCent": 235525,
    "qstEinbehaltenCent": 82434
  },

  "quelle": {
    "adapter": "FLEX_QUERY",
    "adapterVersion": "1.0",
    "belegRef": "CashTransactions Zeile 214, U12074449_2025.csv",
    "erfasstAm": "2026-07-03T12:00:00Z",
    "reviewStatus": "NICHT_ERFORDERLICH"
  },

  "status": "VOLLSTAENDIG"
}
```

### Feldkatalog & Validierungsregeln

| Feld | Typ | Pflicht | Regel |
|---|---|---|---|
| `schemaVersion` | string | ja | Aktuell `"1.0"`; Konsumenten lehnen unbekannte Major-Versionen ab |
| `id` | string | ja | Eindeutig innerhalb des Datenbestands; Muster `<zahltag>_<isin>_<art>_<lfd>`; bei AGGREGAT `<jahr>_<isin>_<art>_AGG` |
| `granularitaet` | enum | ja | `EREIGNIS` \| `AGGREGAT` |
| `instrument.isin` | string | ja* | ISO 6166 (12 Zeichen, Prüfziffer validieren). *Bei AGGREGAT aus manueller Eingabe ersatzweise `instrument.name` Pflicht, isin = null erlaubt |
| `instrument.typ` | enum | ja | `AKTIE` \| `ETF` \| `FONDS` \| `ADR` \| `SONSTIGES` — ADR gesondert, da QSt-Land ≠ Handelsplatz-Land sein kann |
| `quellenland` | string | ja | ISO 3166-1 alpha-2 des **Quellenstaats der Steuer** (nicht der Börse!). Enum-Whitelist der unterstützten Länder, Start: `CH, DK, FR, IT, ES, NO, SE, FI, BE, AT, CA, US, DE`. Unbekanntes Land → Datensatz `unvollstaendig` |
| `ertragsart` | enum | ja | `DIVIDENDE` \| `AUSSCHUETTUNG_FONDS` \| `ZINS` — nur QSt-relevante Arten; Kursgewinne gehören NICHT in dieses Modell (Säule 1) |
| `zahltag` | date | EREIGNIS: ja / AGGREGAT: null | ISO 8601; muss im `steuerjahr` liegen |
| `steuerjahr` | int | ja | 2020–laufendes Jahr; maßgeblich für Verjährungsfristen |
| `betraege.waehrung` | string | ja | ISO 4217 |
| `betraege.bruttoCent` | int | ja | > 0 |
| `betraege.qstEinbehaltenCent` | int | ja | ≥ 0 und ≤ bruttoCent; Plausibilität: einbehaltener Satz ≤ 40 % des Brutto, sonst Warnung |
| `betraege.nettoCent` | int | nein | Wenn vorhanden: brutto − qst = netto muss aufgehen (harte Prüfung) |
| `betraegeEur.*` | object | nein | Nur wenn EUR-Umrechnung quellenbelegt (z. B. IBKR FXRateToBase); `kursQuelle` dann Pflicht. Fehlt sie: Cockpit rechnet mit EZB-Referenzkurs und kennzeichnet mit ~ |
| `quelle.adapter` | enum | ja | `FLEX_QUERY` \| `MANUELL` \| `PDF_EXTRAKTION` |
| `quelle.belegRef` | string | ja | Menschenlesbarer Verweis auf die Fundstelle (Datei + Zeile, PDF + Seite, oder „Handeingabe") |
| `quelle.reviewStatus` | enum | ja | `NICHT_ERFORDERLICH` (Adapter 1/2) \| `BESTAETIGT` \| `OFFEN` — PDF-Datensätze mit `OFFEN` dürfen das Cockpit NIE erreichen (Review-Gate, hart) |
| `status` | enum | ja | `VOLLSTAENDIG` \| `UNVOLLSTAENDIG` — unvollständige Datensätze erscheinen im Cockpit nur als Hinweis, nie in Summen |

### Container-Format (Datei/localStorage)

```json
{
  "schemaVersion": "1.0",
  "erstelltAm": "2026-07-03T12:00:00Z",
  "kontoLabel": "U12074449 (Gemeinschaftskonto)",
  "kontoTyp": "GEMEINSCHAFT",
  "datensaetze": [ /* ErtragsDatensatz[] */ ]
}
```

`kontoTyp` (`EINZEL` | `GEMEINSCHAFT`) steuert die Projektions-Schicht — der 50%-Faktor wird wie in Säule 1 ausschließlich in `projiziereErgebnis()` angewendet, niemals in den Datensätzen.

---

## 3. Adapter-Verantwortlichkeiten

### Adapter 1 — `FLEX_QUERY` (Mapping aus Bestandsdaten)
Quelle: Cash-Transactions-Section der bereits geparsten Flex Query (ko-flex.js). Mapping: ISIN/Symbol direkt; `quellenland` aus ISIN-Präfix **mit ADR-Sonderbehandlung** (ISIN-Land US bei z. B. NVO-ADR ≠ QSt-Land DK → Auflösung über WHT-Zeilen-Zuordnung der Flex Query, im Zweifel `UNVOLLSTAENDIG` statt raten); Beträge aus Dividend/WHT-Zeilen paarweise; `betraegeEur` aus FXRateToBase. Granularität: EREIGNIS. reviewStatus: NICHT_ERFORDERLICH (deterministische Quelle).

### Adapter 2 — `MANUELL` (universeller Fallback, jede Depotbank)
Eingabeformular je Position: Name/ISIN (optional), Quellenland (Dropdown aus Whitelist), Steuerjahr, Bruttodividende, einbehaltene QSt, Währung. Granularität: AGGREGAT. Validierung clientseitig nach Feldkatalog; belegRef = „Handeingabe lt. Ertragsaufstellung <Bankname>". Persistenz: localStorage (Muster ETF-Karten). **Damit ist jede deutsche Depotbank ab Tag 1 abgedeckt** — der Nutzer überträgt drei Zahlen pro Position aus seiner Jahres-Ertragsaufstellung.

### Adapter 3 — `PDF_EXTRAKTION` (Phase 3, hinter Review-Gate)
KI-Extraktion mit Fundstellen-Zitat je Feld; jeder Datensatz startet mit `reviewStatus: OFFEN` und wird erst nach zeilenweiser Nutzer-Bestätigung `BESTAETIGT`. Das Cockpit filtert hart auf `reviewStatus != OFFEN`. Details: ROADMAP 3.8, Muster GuidelineIQ Strict Extraction.

---

## 4. Was das Cockpit daraus berechnet (zur Abgrenzung — NICHT Teil des Datenmodells)

Je `quellenland` × `steuerjahr`: Summe brutto, Summe QSt einbehalten, davon in DE anrechenbar (DBA-Satz × brutto, Quelle BMF-DBA-Übersicht), **Überschuss** (= Rückholpotenzial), **Netto-Potenzial** (Überschuss − Tax-Voucher-Kosten lt. CapTrader-Preisliste), Break-even-Ampel, Verjährungsfrist. Alle Referenztabellen (DBA-Sätze, Voucher-Kosten, Fristen) leben versioniert im Cockpit-Modul mit Quellenangabe + Stand-Datum — nie im Datensatz.

---

## 5. Offene Punkte (für v1.1)

1. ADR-Landauflösung: exakte Flex-Query-Felder für die WHT-Land-Zuordnung verifizieren (am Eigenfall NVO testen — passt zu Gate d).
2. Fonds-Ausschüttungen mit Teilfreistellung: Wechselwirkung mit Säule-1-Vorabpauschale klären (Doppelerfassungs-Schutz).
3. Mehrfach-Uploads/Duplikate: Dedupe-Regel über `id` genügt bei EREIGNIS; bei AGGREGAT Konto+Jahr+ISIN-Konflikt → Nutzer entscheidet (ersetzen/behalten).

---

## Fortschreibungshistorie

| Version | Datum | Änderung |
|---|---|---|
| 1.0 | 03.07.2026 | Erstfassung: Kontrakt ErtragsDatensatz, Feldkatalog mit Validierungsregeln, Container, drei Adapter-Spezifikationen, Cockpit-Abgrenzung |
