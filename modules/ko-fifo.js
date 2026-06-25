/**
 * ko-fifo.js — Refundex FIFO-Engine
 * ===================================
 * FIFO-Berechnung nach § 20 Abs. 4 Satz 7 EStG für:
 *   - Aktienveräußerungen (Topf 2)
 *   - Stillhaltergeschäfte / Short-Optionen (§ 20 Abs. 1 Nr. 11 → Topf 1)
 *   - Termingeschäfte / Long-Optionen (§ 20 Abs. 6 → Topf 3, max. €20.000 Verlustverrechnung)
 *   - Devisengewinne (§ 23 EStG, Freigrenze €600)
 *
 * Input:  Transaktionen[] aus ko-import.js
 *         FX-Kurse aus ko-fx.js
 * Output: FIFOResult mit Verlustverrechnungstöpfen + Einzelnachweisen
 *
 * Modul-Version: 1.0.0
 * Rechtliche Grundlage: § 20 Abs. 4 Satz 7 EStG, BMF-Schreiben v. 19.05.2022
 */

"use strict";

// ── KONSTANTEN ───────────────────────────────────────────────

/** Maximaler Verlust aus Termingeschäften verrechenbar pro Jahr (§ 20 Abs. 6 Satz 5) */
const TERMINGESCHAEFTE_VERLUST_LIMIT = 20000;

/** Trade-Codes aus IBKR/CapTrader CSV */
const CODE = {
  OPEN:     'O',   // Position eröffnet
  CLOSE:    'C',   // Position geschlossen
  ASSIGNED: 'A',   // Option ausgeübt/zugeteilt
  EXPIRED:  'Ep',  // Option wertlos verfallen
  PARTIAL:  'P',   // Teilausführung
};

// ── TYPEN (JSDoc) ─────────────────────────────────────────────

/**
 * @typedef {Object} Trade
 * @property {string} assetClass  - 'Aktien' | 'Aktien- und Indexoptionen' | 'Devisen'
 * @property {string} currency    - 'USD' | 'EUR' | 'GBP' etc.
 * @property {string} symbol      - z.B. 'AAPL' oder 'AAPL 19APR24 180 C'
 * @property {string} dateTime    - ISO-Datum 'YYYY-MM-DD HH:MM:SS'
 * @property {string} date        - 'YYYY-MM-DD'
 * @property {number} qty         - positiv=Kauf/Short-Open, negativ=Verkauf/Short-Close
 * @property {number} price       - Preis je Einheit (in Handelswährung)
 * @property {number} proceeds    - Erlös (negativ=Kauf, positiv=Verkauf)
 * @property {number} commFee     - Provision/Gebühr (immer negativ)
 * @property {number} basis       - Einstandswert incl. Gebühren
 * @property {number} realizedPnL - Realisierter G&V laut Broker
 * @property {string[]} codes     - ['O'] | ['C','MLG'] | ['A','O'] etc.
 */

/**
 * @typedef {Object} FIFOLot
 * @property {string} symbol
 * @property {string} date
 * @property {number} qty         - verbleibende Stückzahl
 * @property {number} costPerUnit - Einstandspreis je Einheit in EUR (EZB-Tageskurs)
 * @property {number} totalCostEur
 * @property {string} currency
 */

/**
 * @typedef {Object} TaxEvent
 * @property {string}  type       - 'aktie' | 'stillhalter' | 'termingeschaeft' | 'devisen'
 * @property {string}  symbol
 * @property {string}  closeDate
 * @property {number}  qty
 * @property {number}  proceedsEur
 * @property {number}  costEur
 * @property {number}  gainLossEur  - positiv=Gewinn, negativ=Verlust
 * @property {string}  openDate     - Datum des Kaufs (FIFO-Lot)
 * @property {number}  fxRate       - verwendeter EZB-Kurs
 * @property {string}  topf         - '1_allgemein' | '2_aktien' | '3_termin'
 */

/**
 * @typedef {Object} FIFOResult
 * @property {TaxEvent[]} events            - alle steuerlichen Ereignisse
 * @property {Object}     toepfe            - Verlustverrechnungstöpfe
 * @property {Object}     anlagekap         - KAP-Zeilen direkt
 * @property {Object}     verlustvortraege  - Vorträge ins Folgejahr
 * @property {Object}     summary           - Zusammenfassung
 */

// ── HAUPTFUNKTION ─────────────────────────────────────────────

/**
 * FIFO-Berechnung für alle Transaktionen eines Jahres.
 *
 * @param {Trade[]} trades    - Transaktionen aus ko-import.js
 * @param {Object}  fxRateMap - EZB-Tageskurse aus ko-fx.js { "USD:2024-04-15": 0.9231 }
 * @param {string}  year      - Steuerjahr '2024'
 * @returns {FIFOResult}
 */
export function calculateFIFO(trades, fxRateMap = {}, year = '2024') {
  // FIFO-Stacks je Ticker { symbol: FIFOLot[] }
  const stockLots   = {};  // Aktien
  const optionLots  = {};  // Long-Optionen (Termingeschäfte)
  const fxLots      = {};  // Fremdwährungsbestände (§ 23)

  // Steuerliche Ereignisse
  const events = [];

  // Trades chronologisch sortieren
  const sorted = [...trades].sort((a, b) => a.dateTime.localeCompare(b.dateTime));

  for (const trade of sorted) {
    const tradeYear = trade.date.slice(0, 4);
    if (tradeYear !== year) continue;  // nur aktuelles Steuerjahr

    const eurRate = getEURRate(trade.currency, trade.date, fxRateMap, year);

    switch (trade.assetClass) {
      case 'Aktien':
        processStock(trade, stockLots, events, eurRate);
        break;
      case 'Aktien- und Indexoptionen':
        processOption(trade, optionLots, events, eurRate);
        break;
      case 'Devisen':
        // EUR.USD = automatische Margin-Konvertierung, KEIN §23 EStG
        // §23 gilt nur für bewusste Devisenspekulation (kommt aus FX-CSV)
        if (trade.symbol !== 'EUR.USD' && trade.symbol !== 'USD.EUR') {
          processFX(trade, fxLots, events, eurRate);
        }
        break;
    }
  }

  // Verlustverrechnungstöpfe berechnen
  const toepfe = calcToepfe(events);

  // Anlage KAP Zeilen ableiten
  const anlagekap = calcAnlageKAP(toepfe, year);

  return {
    events,
    toepfe,
    anlagekap,
    verlustvortraege: calcVerlustvortraege(toepfe),
    summary: calcSummary(events, toepfe),
  };
}

// ── AKTIEN (FIFO nach § 20 Abs. 4 Satz 7 EStG) ──────────────

function processStock(trade, lots, events, eurRate) {
  const sym = trade.symbol;
  if (!lots[sym]) lots[sym] = [];

  if (trade.qty > 0) {
    // KAUF → Lot hinzufügen
    const costEur = Math.abs(trade.proceeds + (trade.commFee || 0)) * eurRate;
    lots[sym].push({
      symbol:       sym,
      date:         trade.date,
      qty:          trade.qty,
      costPerUnit:  costEur / trade.qty,
      totalCostEur: costEur,
      currency:     trade.currency,
      fxRate:       eurRate,
    });
  } else if (trade.qty < 0) {
    // VERKAUF → FIFO abarbeiten
    let qtyToSell = Math.abs(trade.qty);
    const proceedsEur = Math.abs(trade.proceeds) * eurRate -
                        Math.abs(trade.commFee || 0) * eurRate;

    let totalCostEur = 0;
    let firstOpenDate = lots[sym]?.[0]?.date || trade.date;

    while (qtyToSell > 0 && lots[sym]?.length > 0) {
      const lot = lots[sym][0];

      if (lot.qty <= qtyToSell) {
        // Lot vollständig verkauft
        totalCostEur += lot.totalCostEur;
        qtyToSell    -= lot.qty;
        lots[sym].shift();
      } else {
        // Lot teilweise verkauft
        const partCost = lot.costPerUnit * qtyToSell;
        totalCostEur  += partCost;
        lot.qty        -= qtyToSell;
        lot.totalCostEur -= partCost;
        qtyToSell       = 0;
      }
    }

    const gainLoss = round2(proceedsEur - totalCostEur);

    events.push({
      type:        gainLoss >= 0 ? 'aktie_gewinn' : 'aktie_verlust',
      symbol:      sym,
      closeDate:   trade.date,
      openDate:    firstOpenDate,
      qty:         Math.abs(trade.qty),
      proceedsEur: round2(proceedsEur),
      costEur:     round2(totalCostEur),
      gainLossEur: gainLoss,
      fxRate:      eurRate,
      topf:        '2_aktien',
      currency:    trade.currency,
    });
  }
}

// ── OPTIONEN ─────────────────────────────────────────────────

function processOption(trade, lots, events, eurRate) {
  const sym   = trade.symbol;
  const codes = trade.codes || [];
  const isShort = trade.qty < 0 && codes.includes(CODE.OPEN);   // Short = Stillhalter
  const isClose = codes.includes(CODE.CLOSE) || codes.includes(CODE.ASSIGNED);
  const isExpired = codes.includes(CODE.EXPIRED);

  if (!lots[sym]) lots[sym] = [];

  if (isShort) {
    // SHORT OPTION ERÖFFNEN (Stillhalter) — Prämieneinnahme §20 Abs.1 Nr.11
    const premiumEur = Math.abs(trade.proceeds) * eurRate -
                       Math.abs(trade.commFee || 0) * eurRate;
    // Prämie sofort als Einnahme erfassen (realisiert bei Erhalt)
    events.push({
      type:        'stillhalter_praemie',
      symbol:      sym,
      closeDate:   trade.date,
      openDate:    trade.date,
      qty:         Math.abs(trade.qty),
      proceedsEur: round2(premiumEur),
      costEur:     0,
      gainLossEur: round2(premiumEur),
      fxRate:      eurRate,
      topf:        '1_allgemein',  // Stillhalter → Topf 1 (§20 Abs.1 Nr.11)
      currency:    trade.currency,
      codes,
    });

    // Lot für spätere Glattstellung merken
    lots[sym].push({
      symbol:       sym,
      date:         trade.date,
      qty:          Math.abs(trade.qty),
      costPerUnit:  premiumEur / Math.abs(trade.qty),
      totalCostEur: premiumEur,
      currency:     trade.currency,
      fxRate:       eurRate,
      isShort:      true,
    });

  } else if (codes.includes(CODE.OPEN) && trade.qty > 0) {
    // LONG OPTION KAUFEN (Termingeschäft §20 Abs.6)
    const costEur = Math.abs(trade.proceeds + (trade.commFee || 0)) * eurRate;
    lots[sym].push({
      symbol:       sym,
      date:         trade.date,
      qty:          trade.qty,
      costPerUnit:  costEur / trade.qty,
      totalCostEur: costEur,
      currency:     trade.currency,
      fxRate:       eurRate,
      isShort:      false,
    });

  } else if (isClose || isExpired) {
    // GLATTSTELLUNG oder VERFALL
    if (lots[sym]?.length > 0) {
      const lot = lots[sym][0];
      const isShortLot = lot.isShort;

      let gainLoss;
      if (isExpired && isShortLot) {
        // Short Option verfallen → Prämie vollständig behalten, Kosten = 0
        gainLoss = 0;  // Prämie bereits bei Eröffnung erfasst
        lots[sym].shift();
        return;
      }

      const closeProceeds = Math.abs(trade.proceeds) * eurRate -
                            Math.abs(trade.commFee || 0) * eurRate;

      if (isShortLot) {
        // Short glattstellen → Rückkaufkosten gegen Prämie
        gainLoss = round2(lot.totalCostEur - closeProceeds);
        events.push({
          type:        gainLoss >= 0 ? 'stillhalter_gewinn' : 'stillhalter_verlust',
          symbol:      sym,
          closeDate:   trade.date,
          openDate:    lot.date,
          qty:         Math.abs(trade.qty),
          proceedsEur: round2(lot.totalCostEur),
          costEur:     round2(closeProceeds),
          gainLossEur: gainLoss,
          fxRate:      eurRate,
          topf:        '1_allgemein',
          currency:    trade.currency,
          codes,
        });
      } else {
        // Long Option schließen → Termingeschäft §20 Abs.6
        gainLoss = round2(closeProceeds - lot.totalCostEur);
        events.push({
          type:        gainLoss >= 0 ? 'termin_gewinn' : 'termin_verlust',
          symbol:      sym,
          closeDate:   trade.date,
          openDate:    lot.date,
          qty:         Math.abs(trade.qty),
          proceedsEur: round2(closeProceeds),
          costEur:     round2(lot.totalCostEur),
          gainLossEur: gainLoss,
          fxRate:      eurRate,
          topf:        '3_termin',
          currency:    trade.currency,
          codes,
        });
      }

      lots[sym].shift();
    }
  }
}

// ── DEVISEN (§ 23 EStG) ──────────────────────────────────────

function processFX(trade, lots, events, eurRate) {
  const cur = trade.currency;
  if (!lots[cur]) lots[cur] = [];

  const amount = Math.abs(trade.qty || trade.proceeds);  // Betrag in Fremdwährung

  if ((trade.proceeds || 0) < 0) {
    // KAUF Fremdwährung (Eingang)
    const costEur = Math.abs(trade.proceeds) * eurRate;
    lots[cur].push({
      symbol:       cur,
      date:         trade.date,
      qty:          amount,
      costPerUnit:  costEur / amount,
      totalCostEur: costEur,
      currency:     cur,
      fxRate:       eurRate,
    });
  } else if ((trade.proceeds || 0) > 0) {
    // VERKAUF Fremdwährung → FIFO
    let qtyToSell   = amount;
    let totalCostEur = 0;
    const proceedsEur = trade.proceeds * eurRate;

    while (qtyToSell > 0 && lots[cur]?.length > 0) {
      const lot = lots[cur][0];
      if (lot.qty <= qtyToSell) {
        totalCostEur += lot.totalCostEur;
        qtyToSell    -= lot.qty;
        lots[cur].shift();
      } else {
        totalCostEur += lot.costPerUnit * qtyToSell;
        lot.qty      -= qtyToSell;
        lot.totalCostEur -= lot.costPerUnit * qtyToSell;
        qtyToSell     = 0;
      }
    }

    const gainLoss = round2(proceedsEur - totalCostEur);
    if (Math.abs(gainLoss) > 0.01) {  // Minimalbetrag ignorieren
      events.push({
        type:        gainLoss >= 0 ? 'devisen_gewinn' : 'devisen_verlust',
        symbol:      cur,
        closeDate:   trade.date,
        openDate:    trade.date,
        qty:         amount,
        proceedsEur: round2(proceedsEur),
        costEur:     round2(totalCostEur),
        gainLossEur: gainLoss,
        fxRate:      eurRate,
        topf:        'anlage_so',
        currency:    cur,
      });
    }
  }
}

// ── VERLUSTVERRECHNUNGSTÖPFE ──────────────────────────────────

function calcToepfe(events) {
  const t = {
    topf1_allgemein: {
      stillhalterGewinn:  0,
      stillhalterVerlust: 0,
      sonstigeGewinn:     0,
      sonstigeVerlust:    0,
      saldo:              0,
    },
    topf2_aktien: {
      gewinn:  0,
      verlust: 0,
      saldo:   0,
    },
    topf3_termin: {
      gewinn:      0,
      verlust:     0,
      verrechenbar: 0,
      vortrag:     0,
      saldo:       0,
    },
    anlage_so: {
      gewinn:  0,
      verlust: 0,
      saldo:   0,
    },
  };

  for (const e of events) {
    const g = e.gainLossEur;
    switch (e.topf) {
      case '1_allgemein':
        if (e.type.startsWith('stillhalter')) {
          if (g >= 0) t.topf1_allgemein.stillhalterGewinn  += g;
          else        t.topf1_allgemein.stillhalterVerlust += g;
        } else {
          if (g >= 0) t.topf1_allgemein.sonstigeGewinn  += g;
          else        t.topf1_allgemein.sonstigeVerlust += g;
        }
        break;
      case '2_aktien':
        if (g >= 0) t.topf2_aktien.gewinn  += g;
        else        t.topf2_aktien.verlust += g;
        break;
      case '3_termin':
        if (g >= 0) t.topf3_termin.gewinn  += g;
        else        t.topf3_termin.verlust += g;
        break;
      case 'anlage_so':
        if (g >= 0) t.anlage_so.gewinn  += g;
        else        t.anlage_so.verlust += g;
        break;
    }
  }

  // Saldi berechnen
  t.topf1_allgemein.saldo = round2(
    t.topf1_allgemein.stillhalterGewinn + t.topf1_allgemein.stillhalterVerlust +
    t.topf1_allgemein.sonstigeGewinn    + t.topf1_allgemein.sonstigeVerlust
  );

  t.topf2_aktien.saldo = round2(t.topf2_aktien.gewinn + t.topf2_aktien.verlust);

  // Topf 3: §20 Abs.6 Verlustbeschränkung
  const terminVerlustAbs = Math.abs(t.topf3_termin.verlust);
  const terminGewinn     = t.topf3_termin.gewinn;
  // Verluste verrechenbar: erst gegen Gewinne, dann max. €20.000 gegen andere
  const verrechenbarGesamt = terminGewinn + Math.min(
    terminVerlustAbs - terminGewinn, TERMINGESCHAEFTE_VERLUST_LIMIT
  );
  t.topf3_termin.verrechenbar = round2(Math.min(terminVerlustAbs, verrechenbarGesamt));
  t.topf3_termin.vortrag      = round2(Math.max(0, terminVerlustAbs - t.topf3_termin.verrechenbar));
  t.topf3_termin.saldo        = round2(terminGewinn - terminVerlustAbs);

  t.anlage_so.saldo = round2(t.anlage_so.gewinn + t.anlage_so.verlust);

  // Runden
  for (const topf of Object.values(t)) {
    for (const [key, val] of Object.entries(topf)) {
      topf[key] = round2(val);
    }
  }

  return t;
}

// ── ANLAGE KAP ABLEITUNG ─────────────────────────────────────

function calcAnlageKAP(toepfe, year) {
  const t1 = toepfe.topf1_allgemein;
  const t2 = toepfe.topf2_aktien;
  const t3 = toepfe.topf3_termin;

  return {
    // Zeile 7: Kapitalerträge allgemein (Stillhalterprämien + Sonstiges)
    z7_kapitalertraege: round2(
      t1.stillhalterGewinn + t1.stillhalterVerlust +
      t1.sonstigeGewinn    + t1.sonstigeVerlust
    ),

    // Zeile 8: Gewinne aus Aktienveräußerungen
    z8_aktienGewinn: round2(t2.gewinn),

    // Zeile 9: Verluste aus Aktienveräußerungen (als positiver Betrag)
    z9_aktienVerlust: round2(Math.abs(t2.verlust)),

    // Zeile 12: Gewinne aus Termingeschäften
    z12_terminGewinn: round2(t3.gewinn),

    // Zeile 13: Verluste aus Termingeschäften §20 Abs.6 (als positiver Betrag)
    z13_terminVerlust: round2(Math.abs(t3.verlust)),

    // Verlustverrechnungsbeschränkung §20 Abs.6
    terminVerlustVortrag: t3.vortrag,
    terminVerrechenbar:   t3.verrechenbar,

    // Anlage SO: Devisensaldo
    anlage_so_saldo: toepfe.anlage_so.saldo,
  };
}

function calcVerlustvortraege(toepfe) {
  return {
    termingeschaefte: toepfe.topf3_termin.vortrag,
    aktien:           toepfe.topf2_aktien.saldo < 0 ? Math.abs(toepfe.topf2_aktien.saldo) : 0,
  };
}

function calcSummary(events, toepfe) {
  return {
    totalEvents:        events.length,
    aktienEvents:       events.filter(e => e.topf === '2_aktien').length,
    optionenEvents:     events.filter(e => e.topf === '1_allgemein' || e.topf === '3_termin').length,
    devisenEvents:      events.filter(e => e.topf === 'anlage_so').length,
    topf1Saldo:         toepfe.topf1_allgemein.saldo,
    topf2Saldo:         toepfe.topf2_aktien.saldo,
    topf3Saldo:         toepfe.topf3_termin.saldo,
    topf3Vortrag:       toepfe.topf3_termin.vortrag,
    soSaldo:            toepfe.anlage_so.saldo,
    soSteuerpflichtig:  Math.abs(toepfe.anlage_so.saldo) > 600,
  };
}

// ── HILFSFUNKTIONEN ──────────────────────────────────────────

function round2(n) {
  return Math.round((n || 0) * 100) / 100;
}

/**
 * EZB-Tageskurs abrufen (synchron aus Cache, async via ko-fx.js)
 */
function getEURRate(currency, date, fxRateMap, year) {
  if (currency === 'EUR') return 1.0;

  const key = `${currency}:${date}`;
  if (fxRateMap[key]) return fxRateMap[key];

  // Wochenend-Fallback: letzter verfügbarer Kurs
  const available = Object.keys(fxRateMap)
    .filter(k => k.startsWith(currency + ':') && k <= key)
    .sort();
  if (available.length > 0) return fxRateMap[available[available.length - 1]];

  // Jahresdurchschnitt als letzter Fallback
  const FALLBACK = {
    USD: { '2022': 0.9498, '2023': 0.9247, '2024': 0.9236, '2025': 0.9200 },
    GBP: { '2022': 1.1703, '2023': 1.1513, '2024': 1.1826, '2025': 1.1700 },
  };
  return FALLBACK[currency]?.[year] || 0.92;
}

// ── PARSER: CSV → Trade[] ─────────────────────────────────────

/**
 * Parst den CapTrader/IBKR Jahresauszug-CSV und gibt Trades zurück.
 * Ergänzt ko-import.js um Trade-Level-Details.
 *
 * @param {string} csvText - Rohtext des Jahresauszugs
 * @returns {Trade[]}
 */
export function parseTradesFromCSV(csvText) {
  const trades = [];
  const lines  = csvText.split(/\r?\n/);

  function splitCSV(line) {
    const parts = [];
    let cur = '', inQ = false;
    for (let i = 0; i < line.length; i++) {
      const c = line[i];
      if (c === '"') { inQ = !inQ; }
      else if (c === ',' && !inQ) { parts.push(cur); cur = ''; }
      else cur += c;
    }
    parts.push(cur);
    return parts;
  }

  for (const line of lines) {
    const p = splitCSV(line.trim());
    if (p.length < 14) continue;
    if (p[0] !== 'Transaktionen' || p[1] !== 'Data') continue;

    const assetClass = p[3].trim();
    if (!['Aktien', 'Aktien- und Indexoptionen', 'Devisen'].includes(assetClass)) continue;

    const dateTime = p[6].trim();
    const date     = dateTime.slice(0, 10);
    const qty      = parseFloat(p[7])  || 0;
    const price    = parseFloat(p[8])  || 0;
    const proceeds = parseFloat(p[10]) || 0;
    const commFee  = parseFloat(p[11]) || 0;
    const basis    = parseFloat(p[12]) || 0;
    const realPnL  = parseFloat(p[13]) || 0;
    const codeStr  = (p[15] || '').trim();
    const codes    = codeStr.split(/[;,]/).map(c => c.trim()).filter(Boolean);

    if (!date || !qty) continue;

    trades.push({
      assetClass,
      currency: p[4].trim(),
      symbol:   p[5].trim(),
      dateTime,
      date,
      qty,
      price,
      proceeds,
      commFee,
      basis,
      realizedPnL: realPnL,
      codes,
    });
  }

  // Chronologisch sortieren
  return trades.sort((a, b) => a.dateTime.localeCompare(b.dateTime));
}

// ── MODUL-METADATEN ──────────────────────────────────────────

export const FIFO_MODULE_META = {
  version:       '1.0.0',
  created:       '2026-06-26',
  legal:         '§ 20 Abs. 4 Satz 7 EStG, § 20 Abs. 1 Nr. 11 EStG, § 20 Abs. 6 EStG',
  supports:      ['Aktien', 'Stillhaltergeschäfte', 'Long-Optionen', 'Devisen'],
  limitations:   ['Keine Corporate Actions', 'Keine ETF-Vorabpauschale', 'Keine Anleihen'],
  nextVersion:   'Flex Query XML Parser für robusteren Import',
};
