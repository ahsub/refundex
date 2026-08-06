# Refundex — Datenmodell Trade-Journal

**Version:** 1.0
**Stand:** 06.08.2026
**Ablage:** `ahsub/refundex/docs/DATENMODELL_JOURNAL.md`
**Abhängigkeit:** ROADMAP.md § 2.8 (XML-Migration) und § 2.9 (Trade-Journal-Modul)

---

## 1. Architektur-Entscheidung (05.08.2026)

**Trade-Journal gehört in Refundex, nicht in UIQ.**

| Kriterium | UIQ | Refundex → Journal |
|---|---|---|
| Zeitpunkt | Vor dem Trade (Entscheidung) | Nach dem Trade (Bewirtschaftung + Lernen) |
| Datenbasis | Live-Marktdaten, Scanner | Flex-XML (abgeschlossene Positionen, P&L) |
| Kern-Output | Signal, Regime, Underlying-Empfehlung | P&L-Auswertung, Setup-Analyse, Regelkonformität |
| Datenpflege | Automatisch (Aggregator) | Automatisch (Flex-XML) + manuell (subjektiv) |

Konsequenz: Kein Journal-Code in `axel-scanner` oder `ko-aggregator`. Implementierung ausschließlich in `ahsub/refundex`.

---

## 2. Datenbasis — Flex Query XML

### 2.1 Warum XML statt CSV

IBKR/CapTrader plant die mittelfristige Deprecation des CSV-Exports. XML ist das
zukunftssichere Primärformat:

- Versions-Fingerprint im Root-Tag (`queryName`, `type`, `fromDate`/`toDate`)
- Kein Trennzeichen-Ambiguitätsproblem (Komma in Firmennamen, Dezimaltrennzeichen)
- Reicheres Schema: verschachtelte Strukturen, Attribute, Namespaces
- `ko-flex.js` erkennt XML bereits (`detectFormat` → `'activity_xml'`); Parser ist als Stub vorhanden (`'coming soon'`)

### 2.2 Relevante Flex-XML-Sektionen für das Journal

```xml
<FlexQueryResponse queryName="..." type="AF">
  <FlexStatements count="1">
    <FlexStatement accountId="..." fromDate="..." toDate="...">

      <!-- Trades: ein Eintrag pro Fill -->
      <Trades>
        <Trade
          accountId="U1234567"
          symbol="AAPL"
          description="APPLE INC"
          assetCategory="STK"           <!-- STK / OPT / FUT -->
          currency="USD"
          tradeDate="20260801"
          settleDate="20260803"
          transactionType="ExchTrade"
          buySell="BUY"                 <!-- BUY / SELL -->
          quantity="100"
          tradePrice="185.50"
          tradeMoney="18550.00"
          proceeds="-18550.00"
          ibCommission="-1.00"
          ibCommissionCurrency="USD"
          netCash="-18551.00"
          fxRateToBase="1.0"            <!-- Kurs USD→EUR zum Trade-Datum -->
          openCloseIndicator="O"        <!-- O=Open, C=Close, C;O=Teilschluss -->
          fifoPnlRealized="0"
          mtmPnl="0"
          tradeID="123456789"
          ibOrderID="987654321"
        />
      </Trades>

      <!-- Closed Lots: zusammengeführte FIFO-Paare (Open + Close) -->
      <ClosedLots>
        <ClosedLot
          symbol="AAPL"
          assetCategory="STK"
          currency="USD"
          openDateTime="20260801;093000"
          closeDateTime="20260815;143000"
          quantity="100"
          openPrice="185.50"
          closePrice="192.30"
          openMoney="18550.00"
          closeMoney="19230.00"
          fifoPnlRealized="680.00"      <!-- Kern-P&L-Feld -->
          mtmPnl="0"
          fxRateToBase="1.08"           <!-- Kurs zum Close-Datum -->
          tradeID="123456799"
          openOrderID="987654321"
        />
      </ClosedLots>

      <!-- Optionen: gleiches Schema, assetCategory="OPT" -->
      <!-- zusätzliche Felder bei OPT: -->
      <!--   expiry="20260919", strike="190", putCall="C"/"P",
             multiplier="100", underlyingSymbol="AAPL" -->

    </FlexStatement>
  </FlexStatements>
</FlexQueryResponse>
```

### 2.3 Flex-Query-Konfiguration (empfohlen)

Für das Journal-Modul wird eine dedizierte Flex Query benötigt (oder die bestehende
`ki_flex_full_csv`-Query als XML-Variante):

| Setting | Wert |
|---|---|
| Format | XML |
| Sections | Trades, ClosedLots, (CashTransactions für Dividenden) |
| Date Range | Letztes Quartal oder Steuerjahr |
| Delivery | Manual Download (kein Token erforderlich) |

---

## 3. Journal-Eintrag — JSON-Schema v1.0

Ein Journal-Eintrag entspricht einer **abgeschlossenen Position** (ClosedLot),
nicht einem einzelnen Fill. Mehrere Teilfills werden zu einem Eintrag aggregiert.

```jsonc
{
  // ── AUTOMATISCH AUS FLEX-XML (ClosedLots + Trades) ──────────────────
  "id":               "AAPL-20260801-20260815",   // symbol + openDate + closeDate
  "source":           "flex_xml",                 // "flex_xml" | "manual"
  "importedAt":       "2026-08-15T18:30:00Z",

  // Instrument
  "symbol":           "AAPL",
  "description":      "APPLE INC",
  "assetCategory":    "STK",                      // "STK" | "OPT" | "FUT"
  "currency":         "USD",

  // Optionen-spezifisch (nur wenn assetCategory = "OPT")
  "option": {
    "expiry":         "2026-09-19",
    "strike":         190.00,
    "putCall":        "C",                         // "C" | "P"
    "multiplier":     100,
    "underlying":     "AAPL",
    "strategy":       "CC"                         // "CSP"|"CC"|"SPREAD"|"NAKED"|null
  },

  // Zeitraum
  "openDate":         "2026-08-01",
  "closeDate":        "2026-08-15",
  "holdingDays":      14,                          // berechnet

  // Richtung
  "direction":        "LONG",                      // "LONG" | "SHORT"
  "quantity":         100,

  // Preise (in Handelswährung)
  "openPrice":        185.50,
  "closePrice":       192.30,
  "commission":       -2.00,                       // Summe aller Fills

  // P&L
  "pnlGross":         680.00,                      // fifoPnlRealized aus XML
  "pnlNet":           678.00,                      // pnlGross + commission
  "pnlNetEur":        627.78,                      // pnlNet / fxRateToBase (Close)
  "fxRateClose":      1.08,                        // EUR/USD zum Close-Datum
  "returnPct":        3.67,                        // pnlNet / (openPrice * quantity) * 100

  // ── MANUELL ERGÄNZT (subjektive Dimension) ──────────────────────────
  "setup": {
    "type":           "VCP",    // "VCP"|"BASE"|"Breakout"|"Pullback"|"MeanRev"|"CSP"|"CC"|null
    "regime":         "BULL_QUIET",               // MSE-Regime zum Entry-Zeitpunkt
    "regimeConfidence": 0.82,                     // aus UIQ KV (optional, manuell)
    "rsRankEntry":    87,                         // RS-Rank zum Entry (aus UIQ, optional)
    "entryReason":    "VCP-Breakout über 52W-High, Vol +150%",
    "exitReason":     "Ziel erreicht (+3,5%), geordneter Ausstieg"
  },

  "rule": {
    "planCompliant":  true,     // Wurde der Trade-Plan eingehalten?
    "stopRespected":  true,     // Stop-Loss respektiert?
    "positionSize":   "OK",     // "OK" | "ZU_GROSS" | "ZU_KLEIN"
    "deviation":      null      // Freitext: was wich vom Plan ab?
  },

  "learning": {
    "whatWorked":     "Einstieg exakt am Breakout-Punkt, kein Vorgriff.",
    "whatFailed":     null,
    "nextTime":       "Volumen-Filter früher prüfen.",
    "tags":           ["vcp", "momentum", "regelkonform"]
  },

  // Metadaten
  "broker":           "CapTrader",
  "account":          "U1234567",
  "updatedAt":        "2026-08-15T20:00:00Z"
}
```

---

## 4. Aggregations-Schema (Journal-Statistik)

Für die P&L-Auswertungs-Ansicht werden Einzel-Einträge zu Statistiken verdichtet:

```jsonc
{
  "period":           "2026-Q3",
  "generatedAt":      "2026-08-15T20:00:00Z",
  "tradesTotal":      47,
  "tradesWin":        31,
  "tradesLoss":       16,
  "winRate":          0.66,

  "pnlNetEur":        4820.50,
  "avgWinEur":        280.00,
  "avgLossEur":       -145.00,
  "profitFactor":     1.93,           // avgWin * wins / (|avgLoss| * losses)
  "expectancy":       102.57,         // avg P&L pro Trade in EUR

  "byAssetCategory": {
    "STK":  { "trades": 30, "pnlNetEur": 3200.00, "winRate": 0.70 },
    "OPT":  { "trades": 17, "pnlNetEur": 1620.50, "winRate": 0.59 }
  },

  "bySetupType": {
    "VCP":  { "trades": 12, "pnlNetEur": 1850.00, "winRate": 0.75 },
    "CSP":  { "trades":  8, "pnlNetEur":  980.00, "winRate": 0.75 },
    "CC":   { "trades":  5, "pnlNetEur":  420.00, "winRate": 0.60 }
  },

  "byRegime": {
    "BULL_QUIET":       { "trades": 28, "pnlNetEur": 3100.00, "winRate": 0.71 },
    "BULL_FRAGILE":     { "trades": 10, "pnlNetEur":  900.00, "winRate": 0.60 },
    "STRESS_UNSTABLE":  { "trades":  9, "pnlNetEur": -180.00, "winRate": 0.44 }
  }
}
```

---

## 5. Speicher-Strategie

| Ebene | Speicher | Begründung |
|---|---|---|
| Einzel-Einträge | `localStorage` (Key: `rx_journal_entries`) | Datensouveränität (Grundgesetz 3); kein Server-Upload von Depotdaten |
| Aggregation | Berechnet on-the-fly im Browser | Keine Sync-Komplexität |
| Export | DOCX (Jahresauswertung) + JSON (Backup) | Analog Refundex-Report-Export |
| Import | Flex-XML Upload (→ 2.8) | Automatische Befüllung, kein manuelles Tippen |

**localStorage-Limit:** ~5 MB. Bei ~47 Trades/Quartal × ~2 KB/Eintrag = ~376 KB/Quartal →
mehrere Jahre problemlos speicherbar.

---

## 6. Implementierungs-Abhängigkeiten

```
2.8  parseActivityXML() in ko-flex.js
  ↓
2.9a  ClosedLots-Mapping → JournalEntry (automatische Felder)
  ↓
2.9b  ko-journal.js: importFromXML(), renderJournal(), exportDocx()
  ↓
2.9c  Journal-Tab in kap.html
```

**Nicht in Scope (v1.0):**
- Server-seitige Speicherung / Sync
- UIQ-Integration (Regime-Daten werden manuell eingetragen, nicht automatisch gezogen)
- Multi-Account-Konsolidierung

---

## 7. Offene Fragen (vor Implementierung zu klären)

| # | Frage | Relevanz |
|---|---|---|
| F1 | Wie liefert CapTrader XML bei Teilfills? Mehrere `<Trade>`-Einträge mit gleicher `tradeID`? | Aggregations-Logik in `importFromXML()` |
| F2 | Enthält `ClosedLots` immer das `fxRateToBase` zum Close-Datum, oder muss es aus `CashTransactions` gezogen werden? | EUR-P&L-Berechnung |
| F3 | Gibt es ein konkretes IBKR-Deprecation-Datum für CSV? | Priorisierung 2.8 vs. andere Phase-2-Items |
| F4 | Soll `regimeConfidence` + `rsRankEntry` automatisch aus UIQ-KV gezogen werden (erfordert ko-sync-Token)? | Scope 2.9 vs. manuell |

F3 sollte per CapTrader-Support-Ticket oder IBKR-Changelog verifiziert werden.

---

*Refundex Datenmodell Trade-Journal v1.0 — 06.08.2026*
*Architektur-Entscheidung: Journal in Refundex (nicht UIQ)*
*Nächster Schritt: 2.8 XML-Adapter implementieren, dann F1/F2 gegen echtes CapTrader-XML verifizieren*
