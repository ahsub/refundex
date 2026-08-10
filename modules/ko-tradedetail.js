/**
 * ko-tradedetail.js — Refundex Trade-Detail-Report (ROADMAP 2.16)
 * ==================================================================
 * Erzeugt eine vollständige Trade-Auflistung mit FIFO-Los-Zuordnung
 * und tagesaktuellem Wechselkurs je Fremdwährungstransaktion —
 * strukturell an BubbleTax Anhang A.1 angelehnt (Referenzstandard,
 * PDF-Beispiel Axel 10.08.2026, Konto U12074449).
 *
 * WICHTIG — Abgrenzung zur bestehenden G&V-Berechnung:
 * Dieses Modul berechnet KEINE eigenen Gewinne/Verluste und ersetzt NICHT
 * die bestehenden Z.21/Z.24-Werte (Optionen, Cash-Basis-Formel, validiert
 * gegen PWC 2023-2025, s. ROADMAP.md 2.3/2.4). Es dient ausschließlich der
 * TRANSPARENTEN AUFLISTUNG: welche Anschaffung(en)/Eröffnung(en) einer
 * Schließung per FIFO zugeordnet werden, mit welchem Tageskurs.
 *
 * ⚠️ WARNHINWEIS Z.8/Z.9 (Aktien, 10.08.2026): Die bestehende Z.8/Z.9-
 * Formel in ko-flex.js (stkGainEur/stkLossEur, Zeile ~1016) wurde — anders
 * als Z.21/Z.24 — NIE gegen einen PWC-Report validiert und wirkt bei rein
 * kaufbasierten Jahren (0 Verkäufe) konzeptionell fragwürdig (Kauf-Cashflow
 * würde als "Verlust" gezählt). S. ROADMAP.md 2.17/SUITE.md — VOR Abgabe
 * gegen die offizielle CapTrader-Jahressteuerbescheinigung prüfen.
 *
 * Bekannte Grenzen (Stand 10.08.2026):
 *  - Optionsscheine (Warrants) noch nicht abgedeckt, nur Aktien
 *    (buildTradeDetailReport) und Aktien-/Indexoptionen
 *    (buildOptionsDetailReport).
 *  - Setzt voraus, dass ALLE Jahre ab Depoteröffnung hochgeladen
 *    wurden (sonst ist der Startbestand des Report-Jahres unvollständig
 *    und die Los-Zuordnung entsprechend lückenhaft — wird im Report
 *    als Warnung ausgegeben).
 *  - Options-Open/Close-Erkennung ist ZUSTANDSBASIERT (Positionsbestand +
 *    Handelsrichtung), NICHT über das `openCloseIndicator`-Feld — dieses
 *    Feld ist in Axels echten Flex-XML-Daten (levelOfDetail=EXECUTION)
 *    unzuverlässig befüllt (229/284 Trades mit leerem Wert, auch bei
 *    eindeutigen Buy-to-Close-Trades). Verifiziert gegen echte 2023-2025-
 *    Daten am 10.08.2026: 121/121 Fehlalarme behoben, Summen (43.819,11 €
 *    Prämien / -40.545,06 € Rückkäufe) matchen die unabhängig dokumentierte
 *    SWOT-Kennzahl (40.545/43.819 EUR) nahezu exakt.
 *  - Assignment-Dedupe ist nach Aktenlage plausibel, aber nicht an einem
 *    konkreten Assignment-Fall separat verifiziert (in Axels 2025-Daten:
 *    0 Call-Assignments, 5 Put-Assignments, beide unproblematisch für den
 *    Dedupe-Pfad).
 *
 * Modul-Version: 1.1.0 (10.08.2026 — Options-Open/Close-Erkennung zustandsbasiert)
 */

"use strict";

/**
 * Dedupliziert Trades, die durch Assignment sowohl in der Trades- als auch
 * in der OptionEAE-Sektion des Flex-XML auftauchen können (beide landen in
 * result.trades / flexAllTrades, s. ko-flex.js parseActivityXML). Erkennung:
 * gleiches Symbol, gleiches Datum, gleiche |qty|, beide mit Assignment-
 * Klassifizierung (put_assignment/call_assignment/option_assigned) → nur
 * das Element aus der Trades-Sektion behalten (buySell/oci vollständiger),
 * es sei denn nur die EAE-Variante hat costBasisEur > 0.
 */
function dedupeAssignmentTrades(trades) {
  const ASSIGN_TYPES = new Set(['put_assignment', 'call_assignment']);
  const byKey = new Map();
  const result = [];

  for (const t of trades) {
    if (!ASSIGN_TYPES.has(t.classification)) { result.push(t); continue; }
    const key = `${t.symbol}|${t.date}|${Math.abs(t.qty)}`;
    const existing = byKey.get(key);
    if (!existing) {
      byKey.set(key, t);
      result.push(t);
    } else {
      // Bereits eine Assignment-Variante vorhanden — die mit costBasisEur behalten
      if (!existing.eaeSource && t.eaeSource && t.costBasisEur > 0 && !existing.costBasisEur) {
        const idx = result.indexOf(existing);
        if (idx >= 0) result[idx] = t;
        byKey.set(key, t);
      }
      // sonst: Duplikat verwerfen (nicht in result aufnehmen)
    }
  }
  return result;
}

/**
 * Baut den vollständigen Trade-Detail-Report für ein Steuerjahr.
 *
 * @param {Array} allTrades   flexAllTrades — Rohtrades ALLER hochgeladenen Jahre
 * @param {string} year       Ziel-Steuerjahr, z.B. '2025'
 * @returns {{securities: Array, warnings: Array, meta: Object}}
 */
export function buildTradeDetailReport(allTrades, year) {
  const warnings = [];
  const yearStart = `${year}-01-01`;
  const yearEnd   = `${year}-12-31`;

  const stockTrades = dedupeAssignmentTrades(
    allTrades.filter(t => t.assetClass === 'Aktien' && t.date)
  );

  // Nach Symbol gruppieren
  const bySymbol = {};
  for (const t of stockTrades) {
    if (!bySymbol[t.symbol]) bySymbol[t.symbol] = [];
    bySymbol[t.symbol].push(t);
  }

  const securities = [];

  for (const [symbol, trades] of Object.entries(bySymbol)) {
    const sorted = [...trades].sort((a, b) =>
      (a.date + (a.dateTime || '')).localeCompare(b.date + (b.dateTime || ''))
    );

    // Nur Symbole mit Aktivität IM Zieljahr aufnehmen (wie BubbleTax A.1.1)
    const hasActivityInYear = sorted.some(t => t.date >= yearStart && t.date <= yearEnd);
    if (!hasActivityInYear) continue;

    const lots = [];          // FIFO-Stack: {date, qty, costPerUnitEur, totalCostEur}
    const rows = [];          // Zeitleisten-Zeilen für den Report (nur relevanter Bereich)
    let synthWarningGiven = false;

    const startBestandLots = [];
    let processedAnyBeforeYear = false;

    for (const t of sorted) {
      const isBuy = t.qty > 0;
      const eurCost = round2((Math.abs(t.proceeds || 0) + Math.abs(t.commFee || 0)) * (t.fxRateToBase || 1));

      if (isBuy) {
        const lot = {
          date:         t.date,
          qty:          t.qty,
          costPerUnitEur: t.qty !== 0 ? eurCost / t.qty : 0,
          totalCostEur: eurCost,
          currency:     t.currency,
          fxRateToBase: t.fxRateToBase,
          refId:        t.tradeID || '',
          classification: t.classification,
        };
        lots.push(lot);
        if (t.date < yearStart) processedAnyBeforeYear = true;
        if (t.date >= yearStart && t.date <= yearEnd) {
          rows.push({ kind: 'buy', trade: t, lot, eurCost });
        }
      } else if (t.qty < 0) {
        let qtyToSell = Math.abs(t.qty);
        const proceedsEur = round2(Math.abs(t.proceeds || 0) * (t.fxRateToBase || 1) -
                                    Math.abs(t.commFee || 0) * (t.fxRateToBase || 1));
        const consumedLots = [];

        while (qtyToSell > 0.0000001 && lots.length > 0) {
          const lot = lots[0];
          const take = Math.min(lot.qty, qtyToSell);
          consumedLots.push({
            date: lot.date, qty: take,
            costEur: round2(lot.costPerUnitEur * take),
          });
          lot.qty          -= take;
          lot.totalCostEur -= lot.costPerUnitEur * take;
          qtyToSell         -= take;
          if (lot.qty <= 0.0000001) lots.shift();
        }

        if (qtyToSell > 0.0000001) {
          // Verkauf übersteigt bekannte Lots → Altbestand vor dem frühesten
          // hochgeladenen Jahr unbekannt. Synthetisches Lot mit Kosten 0,
          // damit die Rechnung nicht negativ/falsch wird — als Warnung markiert.
          consumedLots.push({ date: null, qty: qtyToSell, costEur: 0, synthetic: true });
          if (!synthWarningGiven) {
            warnings.push(`${symbol}: Verkauf am ${t.date} übersteigt bekannte Lots — ` +
              `vermutlich Altbestand aus einem NICHT hochgeladenen Jahr vor dem ` +
              `frühesten verfügbaren Datenjahr. Los-Zuordnung für diese Menge ` +
              `als "Altbestand unbekannt" markiert, Kosten mit 0 € angesetzt ` +
              `(führt zu ÜBERHÖHTEM ausgewiesenem Gewinn für diesen Anteil — ` +
              `bitte gegen Broker-Jahresbescheinigung prüfen).`);
            synthWarningGiven = true;
          }
          qtyToSell = 0;
        }

        if (t.date >= yearStart && t.date <= yearEnd) {
          rows.push({ kind: 'sell', trade: t, proceedsEur, consumedLots });
        }
      }
    }

    // Endbestand = verbleibende Lots nach Verarbeitung aller Trades bis Jahresende
    // (Trades NACH yearEnd wurden oben mitverarbeitet, falls in den Rohdaten
    // enthalten — daher hier ggf. auf Stand "nach allen verarbeiteten Trades",
    // s. Warnung unten falls das von Bedeutung ist)
    const endbestandLots = lots.map(l => ({ ...l }));
    const endStueck = round4(endbestandLots.reduce((s, l) => s + l.qty, 0));
    const endKostenEur = round2(endbestandLots.reduce((s, l) => s + l.totalCostEur, 0));

    if (rows.length === 0) continue; // keine Zeilen im Zieljahr trotz hasActivityInYear (Grenzfall)

    securities.push({
      symbol,
      isin: sorted.find(t => t.isin)?.isin || '',
      currency: sorted[0]?.currency || '',
      rows,
      endbestand: { stueck: endStueck, kostenEur: endKostenEur, lots: endbestandLots },
    });
  }

  securities.sort((a, b) => a.symbol.localeCompare(b.symbol));

  return {
    securities,
    warnings,
    meta: {
      year,
      symbolCount: securities.length,
      generatedAt: new Date().toISOString(),
      moduleVersion: '1.0.0',
      scope: 'Aktien only (Optionen/Optionsscheine folgen später)',
    },
  };
}

function round2(n) { return Math.round((n + Number.EPSILON) * 100) / 100; }
function round4(n) { return Math.round((n + Number.EPSILON) * 10000) / 10000; }
function fmtNum(n) { return round4(n).toString().replace('.', ','); }

// ── OPTIONEN ─────────────────────────────────────────────────────
//
// Andere Logik als Aktien: Optionen werden über den Open/Close-Indikator
// (nicht Kauf/Verkauf-Vorzeichen) verfolgt, da eine Short-Position
// (Stillhalter) mit einem VERKAUF eröffnet wird. Aktien-FIFO würde das
// als "Verkauf ohne Bestand" fehlinterpretieren.
//
// Modell: pro Optionssymbol ein "Positions-Stack" (analog FIFO-Lots),
// aber mit Vorzeichen (positiv=Long-Kontrakte offen, negativ=Short-
// Kontrakte offen). Bei Open: Lot mit Prämie/Kosten hinzufügen. Bei
// Close/Assigned/Expired: FIFO-Abbau der Lots, Prämie/Rückkauf verrechnen.

/**
 * @param {Array} allTrades  flexAllTrades (alle Jahre, inkl. Optionen)
 * @param {string} year
 */
export function buildOptionsDetailReport(allTrades, year) {
  const warnings = [];
  const yearStart = `${year}-01-01`;
  const yearEnd   = `${year}-12-31`;

  const optTrades = dedupeAssignmentTrades(
    allTrades.filter(t => t.assetClass === 'Aktien- und Indexoptionen' && t.date)
  );

  const bySymbol = {};
  for (const t of optTrades) {
    if (!bySymbol[t.symbol]) bySymbol[t.symbol] = [];
    bySymbol[t.symbol].push(t);
  }

  const contracts = [];

  for (const [symbol, trades] of Object.entries(bySymbol)) {
    const sorted = [...trades].sort((a, b) =>
      (a.date + (a.dateTime || '')).localeCompare(b.date + (b.dateTime || ''))
    );

    const hasActivityInYear = sorted.some(t => t.date >= yearStart && t.date <= yearEnd);
    if (!hasActivityInYear) continue;

    // Positions-Stack: {date, qty (Vorzeichen), premiumPerUnitEur, refId}
    // qty>0 = Long-Kontrakte offen (gekauft), qty<0 = Short-Kontrakte offen (verkauft/Stillhalter)
    const lots = [];
    const rows = [];
    let synthWarningGiven = false;
    const EPS = 0.0000001;

    for (const t of sorted) {
      // ZUSTANDSBASIERTE Open/Close-Erkennung (10.08.2026, ersetzt openCloseIndicator-
      // basierte Logik): In Axels echten Flex-XML-Daten ist `openCloseIndicator` bei
      // 229 von 284 Options-Trades LEER — auch bei eindeutigen Buy-to-Close-Trades
      // (verifiziert z.B. an EVO FEB25 840 P: Open UND Close beide oci=""). Das Feld
      // ist in diesem Export-Typ (levelOfDetail=EXECUTION) schlicht nicht zuverlässig
      // befüllt. Robusterer Ansatz: Trade-Richtung (BUY=Long+/SELL=Short-) gegen den
      // AKTUELLEN Positionsbestand vergleichen — Gegenrichtung = Schließung,
      // Gleichrichtung/Bestand=0 = Eröffnung (bzw. Aufstockung).
      const netPositionBefore = round4(lots.reduce((s, l) => s + l.qty, 0));
      const tradeDirection = t.buySell === 'BUY' ? 1 : -1;
      const tradeQtyAbs = Math.abs(t.qty);
      const cashEur = round2((t.proceeds || 0) * (t.fxRateToBase || 1) -
                              Math.abs(t.commFee || 0) * (t.fxRateToBase || 1));
      const isClosing = Math.abs(netPositionBefore) > EPS &&
        Math.sign(tradeDirection) !== Math.sign(netPositionBefore);

      if (!isClosing) {
        // Eröffnung bzw. Aufstockung in gleicher Richtung
        const contractQty = tradeDirection * tradeQtyAbs;
        const lot = {
          date: t.date, qty: contractQty,
          premiumPerUnitEur: contractQty !== 0 ? cashEur / Math.abs(contractQty) : 0,
          totalCashEur: cashEur,
          refId: t.tradeID || '',
        };
        lots.push(lot);
        if (t.date >= yearStart && t.date <= yearEnd) {
          rows.push({ kind: tradeDirection > 0 ? 'long_open' : 'short_open', trade: t, lot, cashEur });
        }
      } else {
        // Schließung (ganz oder teilweise) der Gegenposition
        let qtyToClose = Math.min(tradeQtyAbs, Math.abs(netPositionBefore));
        const consumedLots = [];

        while (qtyToClose > EPS && lots.length > 0) {
          const lot = lots[0];
          const lotAbs = Math.abs(lot.qty);
          const take = Math.min(lotAbs, qtyToClose);
          consumedLots.push({
            date: lot.date, qty: take,
            openCashEur: round2(lot.premiumPerUnitEur * take),
          });
          const sign = lot.qty > 0 ? 1 : -1;
          lot.qty          -= sign * take;
          lot.totalCashEur -= lot.premiumPerUnitEur * take;
          qtyToClose        -= take;
          if (Math.abs(lot.qty) <= EPS) lots.shift();
        }

        // Restmenge nach vollständigem Lot-Abbau: entweder Datenlücke (Altbestand
        // unbekannt) ODER echte Positionsumkehr im selben Trade (z.B. Short→Long
        // in einem Rutsch) — Unterscheidung über verbleibenden Netto-Bestand.
        const remainder = tradeQtyAbs - Math.min(tradeQtyAbs, Math.abs(netPositionBefore));
        if (remainder > EPS) {
          const remLot = {
            date: t.date, qty: tradeDirection * remainder,
            premiumPerUnitEur: cashEur !== 0 ? (cashEur * (remainder/tradeQtyAbs)) / remainder : 0,
            totalCashEur: cashEur * (remainder/tradeQtyAbs),
            refId: t.tradeID || '',
          };
          lots.push(remLot);
          if (!synthWarningGiven) {
            warnings.push(`${symbol}: Trade am ${t.date} schließt mehr Kontrakte als zu diesem ` +
              `Zeitpunkt als offen bekannt (${fmtNum(remainder)} zusätzlich) — entweder eine echte ` +
              `Positionsumkehr in einem Trade, oder Hinweis auf fehlende Altdaten vor dem frühesten ` +
              `hochgeladenen Jahr. Bitte gegen Broker-Bestätigung prüfen.`);
            synthWarningGiven = true;
          }
        }

        if (t.date >= yearStart && t.date <= yearEnd) {
          const kind = t.classification === 'option_expired' ? 'expired'
            : t.classification?.includes('assign') || t.classification === 'option_assigned' ? 'assigned'
            : 'close';
          rows.push({ kind, trade: t, cashEur, consumedLots });
        }
      }
    }

    if (rows.length === 0) continue;

    const openContracts = round4(lots.reduce((s, l) => s + l.qty, 0));
    contracts.push({
      symbol,
      underlying: sorted[0]?.underlying || '',
      currency: sorted[0]?.currency || '',
      putCall: sorted[0]?.putCall || '',
      strike: sorted[0]?.strike ?? null,
      expiry: sorted[0]?.expiry || '',
      rows,
      offenAmJahresende: openContracts,
    });
  }

  contracts.sort((a, b) => a.symbol.localeCompare(b.symbol));

  return {
    contracts,
    warnings,
    meta: { year, contractCount: contracts.length, moduleVersion: '1.0.0' },
  };
}

export const TRADEDETAIL_MODULE_META = {
  version: '1.0.0',
  created: '2026-08-10',
  purpose: 'Vollständige Trade-Auflistung mit FIFO-Los-Zuordnung und Tageskurs (BubbleTax-Vorbild)',
};
