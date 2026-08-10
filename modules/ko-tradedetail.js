/**
 * ko-tradedetail.js — Refundex Trade-Detail-Report (ROADMAP 2.16)
 * ==================================================================
 * Erzeugt eine vollständige Trade-Auflistung mit FIFO-Los-Zuordnung
 * und tagesaktuellem Wechselkurs je Fremdwährungstransaktion —
 * strukturell an BubbleTax Anhang A.1 angelehnt (Referenzstandard,
 * PDF-Beispiel Axel 10.08.2026, Konto U12074449).
 *
 * WICHTIG — Abgrenzung zur bestehenden G&V-Berechnung:
 * Dieses Modul berechnet KEINE eigenen Gewinne/Verluste und ersetzt
 * NICHT die bestehende Z.21/Z.24-Cash-Basis-Formel (validiert gegen
 * PWC 2023-2025, s. ROADMAP.md 2.3/2.4). Es dient ausschließlich der
 * TRANSPARENTEN AUFLISTUNG: welche Anschaffung(en) einem Verkauf per
 * FIFO zugeordnet werden, mit welchem Tageskurs. Bei Abweichungen
 * zwischen diesem Report und der Cash-Basis-Formel gilt weiterhin
 * die Cash-Basis-Formel als maßgeblich für die Steuerwerte.
 *
 * Bekannte Grenzen (Stand 10.08.2026, UNVERIFIZIERT gegen echte
 * Assignment-Fälle — bitte gegen echte Daten prüfen):
 *  - Nur Aktien (assetClass === 'Aktien'). Optionen/Optionsscheine
 *    folgen in einem späteren Ausbauschritt.
 *  - Setzt voraus, dass ALLE Jahre ab Depoteröffnung hochgeladen
 *    wurden (sonst ist der Startbestand des Report-Jahres unvollständig
 *    und die Los-Zuordnung entsprechend lückenhaft — wird im Report
 *    als Warnung ausgegeben, wenn das erste Trade-Datum eines Symbols
 *    NICHT vor dem 01.01. des frühesten hochgeladenen Jahres liegt UND
 *    gleichzeitig ein Verkauf mehr Stück abbaut als bekannte Lots halten
 *    — dann werden Lots mit Stückzahl 0 und Kommentar "Altbestand
 *    unbekannt" synthetisch ergänzt, damit die Rechnung nicht negativ wird).
 *  - Assignment-Dedupe (s.u.) ist nach Aktenlage plausibel, aber nicht
 *    gegen einen echten Assignment-Fall in Axels XML-Daten verifiziert.
 *
 * Modul-Version: 1.0.0 (10.08.2026)
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

export const TRADEDETAIL_MODULE_META = {
  version: '1.0.0',
  created: '2026-08-10',
  purpose: 'Vollständige Trade-Auflistung mit FIFO-Los-Zuordnung und Tageskurs (BubbleTax-Vorbild)',
};
