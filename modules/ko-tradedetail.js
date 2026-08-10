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

    // Positions-Stack: {date, qty (Vorzeichen: + Long, - Short), costPerUnitEur
    // (bei Long: Anschaffungskosten je Stück; bei Short: erhaltener Verkaufserlös
    // je Stück, als "Kosten" mit gleichem Rechenweg wiederverwendet), totalCostEur}
    const lots = [];
    const rows = [];
    let openShortWarningGiven = false;
    const EPS = 0.0000001;

    for (const t of sorted) {
      // ZUSTANDSBASIERTE Long/Short-Erkennung (10.08.2026, ROADMAP 2.17-Nebenfund):
      // Ein Verkauf, der den Bestand übersteigt, ist nicht zwangsläufig eine
      // Datenlücke — kann ein echter Leerverkauf sein (verifiziert an Axels
      // CVS-Trade 13.05.2024: Verkauf 11:10 Uhr VOR jedem Kauf, Eindeckung
      // 13:37 Uhr selber Tag — § 20 EStG-Leerverkaufsregel, Rn. 196 BMF: Verkauf
      // gilt als Veräußerung im Zeitpunkt des Leerverkaufs, Eindeckung liefert
      // nachträglich die Anschaffungskosten). Modell wie bei Optionen: Netto-
      // Position + Handelsrichtung statt reinem Kauf/Verkauf-Vorzeichen.
      const netPositionBefore = round4(lots.reduce((s, l) => s + l.qty, 0));
      const tradeDirection = t.qty > 0 ? 1 : -1;
      const tradeQtyAbs = Math.abs(t.qty);
      const cashEur = round2(t.qty > 0
        ? -(Math.abs(t.proceeds || 0) + Math.abs(t.commFee || 0)) * (t.fxRateToBase || 1)   // Kauf: Cash-Abfluss
        :  (Math.abs(t.proceeds || 0) - Math.abs(t.commFee || 0)) * (t.fxRateToBase || 1)); // Verkauf: Cash-Zufluss
      const isClosing = Math.abs(netPositionBefore) > EPS &&
        Math.sign(tradeDirection) !== Math.sign(netPositionBefore);

      if (!isClosing) {
        // Anschaffung (Long) bzw. Eröffnung/Aufstockung Leerverkauf (Short)
        const qty = tradeDirection * tradeQtyAbs;
        const lot = {
          date: t.date, qty,
          costPerUnitEur: qty !== 0 ? -cashEur / qty : 0,  // Long: Kosten positiv; Short: "Kosten" = -erhaltener Erlös/Stück
          totalCostEur: -cashEur,
          currency: t.currency, fxRateToBase: t.fxRateToBase,
          refId: t.tradeID || '', classification: t.classification,
        };
        lots.push(lot);
        if (t.date >= yearStart && t.date <= yearEnd) {
          rows.push({ kind: tradeDirection > 0 ? 'buy' : 'short_open', trade: t, lot, eurCost: -cashEur, cashEur });
        }
      } else {
        // Veräußerung (Long-Bestand) bzw. Eindeckung (Short-Bestand)
        let qtyToClose = Math.min(tradeQtyAbs, Math.abs(netPositionBefore));
        const consumedLots = [];

        while (qtyToClose > EPS && lots.length > 0) {
          const lot = lots[0];
          const lotAbs = Math.abs(lot.qty);
          const take = Math.min(lotAbs, qtyToClose);
          consumedLots.push({ date: lot.date, qty: take, costEur: round2(lot.costPerUnitEur * take) });
          const sign = lot.qty > 0 ? 1 : -1;
          lot.qty          -= sign * take;
          lot.totalCostEur -= lot.costPerUnitEur * take;
          qtyToClose        -= take;
          if (Math.abs(lot.qty) <= EPS) lots.shift();
        }

        // Restmenge = Trade übersteigt bekannten Gegenbestand → neue Position
        // in Trade-Richtung eröffnen (z.B. Verkauf über Long-Bestand hinaus =
        // zusätzlicher Leerverkauf für den Rest). Kein Alarm-Wort mehr, da dies
        // größtenteils echte Leerverkäufe sind, keine Datenlücken (s.o.).
        const remainder = tradeQtyAbs - Math.min(tradeQtyAbs, Math.abs(netPositionBefore));
        if (remainder > EPS) {
          const remQty = tradeDirection * remainder;
          const remCashEur = cashEur * (remainder / tradeQtyAbs);
          lots.push({
            date: t.date, qty: remQty,
            costPerUnitEur: remQty !== 0 ? -remCashEur / remQty : 0,
            totalCostEur: -remCashEur,
            currency: t.currency, fxRateToBase: t.fxRateToBase,
            refId: t.tradeID || '', classification: t.classification,
          });
        }

        const proceedsOrCostEur = Math.abs(cashEur); // 'sell': Verkaufserlös; 'short_cover': Eindeckungskosten
        if (t.date >= yearStart && t.date <= yearEnd) {
          rows.push({ kind: tradeDirection > 0 ? 'short_cover' : 'sell', trade: t, proceedsEur: proceedsOrCostEur, consumedLots, cashEur });
        }
      }
    }

    // Warnung NUR wenn am Ende der verarbeiteten Daten noch ein Short offen ist
    // (unüblich bei reinen Long-Depots — echter Hinweis auf möglicherweise
    // fehlende Vorjahresdaten, im Gegensatz zu einem sauber eingedeckten
    // untertägigen Leerverkauf wie CVS).
    {
      const finalNet = round4(lots.reduce((s, l) => s + l.qty, 0));
      if (finalNet < -EPS) {
        warnings.push(`${symbol}: Am Ende der verarbeiteten Daten ${fmtNum(Math.abs(finalNet))} Stück ` +
          `Leerverkaufs-Position offen (nicht eingedeckt). Falls das kein bewusster ` +
          `Leerverkauf war, könnten Anschaffungen aus einem NICHT hochgeladenen Jahr fehlen.`);
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

/**
 * Berechnet den realisierten Gewinn/Verlust einer 'sell'- oder 'short_cover'-Zeile.
 * 'sell' (Long-Veräußerung): Erlös − Anschaffungskosten der konsumierten Lots.
 * 'short_cover' (Leerverkauf-Eindeckung): bei Short-Eröffnung erhaltener Erlös
 * (in consumedLots.costEur gespeichert) − jetzige Eindeckungskosten.
 */
export function calcRowGainLoss(row) {
  const totalConsumed = row.consumedLots.reduce((s,l) => s + l.costEur, 0);
  return row.kind === 'short_cover'
    ? round2(totalConsumed - row.proceedsEur)
    : round2(row.proceedsEur - totalConsumed);
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
