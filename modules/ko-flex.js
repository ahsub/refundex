/**
 * ko-flex.js — Refundex Flex Query Parser
 * =========================================
 * Parst CapTrader/IBKR Flex Query Exporte.
 *
 * Unterstützte Formate:
 * 1. Lots CSV    → Offene Positionen + FIFO-Einstandspreise
 * 2. Kontoauszug → Tages-Wechselkurse (direkt von IBKR)
 * 3. Activity XML → Vollständige Trade-History (geplant)
 *
 * Version: 1.1.0
 */

"use strict";

// ── FORMAT-ERKENNUNG ─────────────────────────────────────────

/**
 * Erkennt automatisch das Format der hochgeladenen Datei.
 * @param {string} text - Dateiinhalt
 * @returns {'lots_csv'|'activity_csv'|'activity_xml'|'kontoauszug'|'unknown'}
 */
export function detectFormat(text) {
  if (text.trim().startsWith('<?xml') || text.includes('<FlexQueryResponse'))
    return 'activity_xml';
  // ki_flex_full_csv: Account Info + Trades + Cash (neue Version mit 3 Sektionen)
  if (text.includes('"Name","AccountType"') || text.includes('"ClientAccountID","Name"'))
    return 'ki_flex_full_csv';
  // ki_flex_cash_csv: Trades + Cash Transactions (älteres Format)
  if (text.includes('ClientAccountID') && text.includes('FXRateToBase') &&
      (text.includes('Dividends') || text.includes('Withholding Tax') || text.includes('Broker Interest')))
    return 'ki_flex_cash_csv';
  // ki_flex_csv: nur Trades, kein Cash
  if (text.includes('ClientAccountID') && text.includes('FXRateToBase') && text.includes('TradeDate'))
    return 'ki_flex_csv';
  // activity_flex_csv zuerst: enthält auch "Symbol" Sektion
  if (text.includes('"BOF"') && text.includes('"BOS"') && text.includes('"TRNT"'))
    return 'activity_flex_csv';
  if (text.includes('"Symbol","Description","Quantity","Multiplier"'))
    return 'lots_csv';
  if (text.includes('Transaction History,Header') || text.includes('Transaction Type'))
    return 'transaction_history';
  if (text.startsWith('Statement,Header') || text.includes('Wechselkurs der Basiswährung'))
    return 'kontoauszug';
  if (text.includes('TradeDate') && text.includes('BuySell'))
    return 'activity_csv';
  return 'unknown';
}

// ── LOTS CSV PARSER ──────────────────────────────────────────

/**
 * Parst den "Open Positions + Lots" CSV Export.
 * Enthält zwei Sektionen:
 * - Sektion 1: Aggregierte offene Positionen (für UIQ Tax-Aware)
 * - Sektion 2: Einzelne Lots mit Einstandspreisen (für FIFO)
 *
 * @param {string} csvText
 * @returns {LotsResult}
 */
export function parseLotsCSV(csvText) {
  const lines = csvText.split(/\r?\n/);

  // Beide Header-Zeilen finden
  const headerIdxs = lines
    .map((l, i) => l.startsWith('"Symbol"') ? i : -1)
    .filter(i => i >= 0);

  if (headerIdxs.length < 1) throw new Error('Kein Lots-CSV Format erkannt');

  // Sektion 1: Aggregierte Positionen
  const sec1End = headerIdxs.length > 1 ? headerIdxs[1] : lines.length;
  const positions = parseSection(lines, 0, sec1End);

  // Sektion 2: Einzelne Lots (falls vorhanden)
  const lots = headerIdxs.length > 1
    ? parseSection(lines, headerIdxs[1], lines.length)
    : [];

  // Aktien und Optionen trennen
  const stockPositions = positions.filter(p => !p.Strike?.trim());
  const optionPositions = positions.filter(p => p.Strike?.trim());
  const stockLots = lots.filter(l => !l.Strike?.trim());
  const optionLots = lots.filter(l => l.Strike?.trim());

  // FIFO-Lots aufbauen (für ko-fifo.js)
  const fifoLots = buildFifoLots(stockLots, optionLots);

  // UIQ Tax-Aware Daten
  const taxAware = buildTaxAware(stockPositions, optionPositions, stockLots, optionLots);

  return {
    format: 'lots_csv',
    positions: { stocks: stockPositions, options: optionPositions },
    lots: { stocks: stockLots, options: optionLots },
    fifoLots,
    taxAware,
    summary: buildLotsSummary(stockPositions, optionPositions, stockLots, optionLots),
  };
}

function parseSection(lines, startIdx, endIdx) {
  const rows = [];
  const headerLine = lines[startIdx];
  if (!headerLine) return rows;

  const headers = splitCSVLine(headerLine);

  for (let i = startIdx + 1; i < endIdx; i++) {
    const line = lines[i]?.trim();
    if (!line) continue;
    const vals = splitCSVLine(line);
    if (vals.length < headers.length) continue;
    const row = {};
    headers.forEach((h, idx) => { row[h] = vals[idx] || ''; });
    if (row.Symbol) rows.push(row);
  }
  return rows;
}

function splitCSVLine(line) {
  const result = [];
  let cur = '', inQ = false;
  for (const c of line) {
    if (c === '"') { inQ = !inQ; }
    else if (c === ',' && !inQ) { result.push(cur.trim()); cur = ''; }
    else cur += c;
  }
  result.push(cur.trim());
  return result;
}

// ── FIFO-LOTS AUFBAUEN ────────────────────────────────────────

/**
 * Konvertiert Lots-Daten in ko-fifo.js kompatibles Format.
 * Kann als Startpunkt für FIFO-Berechnungen verwendet werden.
 */
function buildFifoLots(stockLots, optionLots) {
  const result = {};

  // Aktien-Lots
  for (const lot of stockLots) {
    const sym = lot.UnderlyingSymbol || lot.Symbol;
    if (!sym) continue;
    const qty = parseFloat(lot.Quantity || '0');
    const cost = parseFloat(lot.CostBasis || '0');
    const price = parseFloat(lot.TradePrice || '0');
    const currency = lot.CurrencyPrimary || 'USD';

    if (!result[sym]) result[sym] = [];
    result[sym].push({
      symbol:       sym,
      date:         '',  // Datum nicht in Lots-CSV verfügbar
      qty:          Math.abs(qty),
      costPerUnit:  qty !== 0 ? Math.abs(cost / qty) : price,
      totalCostUsd: Math.abs(cost),
      currency,
      isShort:      qty < 0,
      source:       'lots_csv',
    });
  }

  // Optionen-Lots (Short = Stillhalter, Long = Termingeschäft)
  for (const lot of optionLots) {
    const underlying = lot.UnderlyingSymbol || lot.Symbol?.split(' ')[0];
    const sym = lot.Symbol;
    if (!sym) continue;
    const qty = parseFloat(lot.Quantity || '0');
    const cost = parseFloat(lot.CostBasis || '0');
    const price = parseFloat(lot.TradePrice || '0');
    const strike = parseFloat(lot.Strike || '0');
    const putCall = lot['Put/Call'] || '';
    const expiry = lot.Expiry || '';
    const mult = parseFloat(lot.Multiplier || '100');
    const currency = lot.CurrencyPrimary || 'USD';

    const key = underlying + '_opts';
    if (!result[key]) result[key] = [];
    result[key].push({
      symbol:      sym,
      underlying,
      date:        '',
      qty:         Math.abs(qty),
      costPerUnit: qty !== 0 ? Math.abs(cost / qty) : price,
      totalCostUsd: Math.abs(cost),
      currency,
      isShort:     qty < 0,
      putCall,
      strike,
      expiry,
      multiplier:  mult,
      source:      'lots_csv',
      // Steuerliche Klassifizierung
      taxType:     qty < 0 ? 'stillhalter' : 'termingeschaeft',
    });
  }

  return result;
}

// ── UIQ TAX-AWARE DATEN ───────────────────────────────────────

/**
 * Bereitet Daten für den UIQ Tax-Aware Screener auf.
 * Zeigt: offene Prämien, unrealisierte G/V, Topf-Auslastung.
 */
function buildTaxAware(stockPos, optionPos, stockLots, optionLots) {
  const byUnderlying = {};

  // Aktien-Positionen
  for (const pos of stockPos) {
    const sym = pos.Symbol;
    if (!byUnderlying[sym]) byUnderlying[sym] = initTaxAware(sym);
    byUnderlying[sym].stockQty    = parseFloat(pos.Quantity || '0');
    byUnderlying[sym].stockCostBasis = parseFloat(pos.CostBasisPrice || '0');
    byUnderlying[sym].markPrice   = parseFloat(pos.MarkPrice || '0');
    byUnderlying[sym].currency    = pos.CurrencyPrimary || 'USD';
    byUnderlying[sym].unrealizedPnl = parseFloat(pos.FifoPnlUnrealized || '0');
  }

  // Optionen nach Underlying gruppieren
  for (const lot of optionLots) {
    const underlying = lot.UnderlyingSymbol || lot.Symbol?.split(' ')[0];
    if (!underlying) continue;
    if (!byUnderlying[underlying]) byUnderlying[underlying] = initTaxAware(underlying);

    const qty = parseFloat(lot.Quantity || '0');
    const cost = parseFloat(lot.CostBasis || '0');
    const strike = parseFloat(lot.Strike || '0');
    const putCall = lot['Put/Call'] || '';
    const expiry = lot.Expiry || '';
    const mult = parseFloat(lot.Multiplier || '100');

    if (qty < 0) {
      // Short Option (Stillhalter) — erhaltene Prämie
      byUnderlying[underlying].shortOptions.push({
        symbol: lot.Symbol, qty: Math.abs(qty),
        premium: Math.abs(cost), strike, putCall, expiry, mult,
      });
      byUnderlying[underlying].totalPremiumReceived += Math.abs(cost);
    } else if (qty > 0 && cost > 0) {
      // Long Option (Termingeschäft) — investiertes Kapital
      byUnderlying[underlying].longOptions.push({
        symbol: lot.Symbol, qty: Math.abs(qty),
        cost: Math.abs(cost), strike, putCall, expiry, mult,
      });
      byUnderlying[underlying].totalLongCost += Math.abs(cost);
    }
  }

  return byUnderlying;
}

function initTaxAware(sym) {
  return {
    symbol: sym,
    stockQty: 0, stockCostBasis: 0, markPrice: 0,
    currency: 'USD', unrealizedPnl: 0,
    shortOptions: [], longOptions: [],
    totalPremiumReceived: 0, totalLongCost: 0,
  };
}

function buildLotsSummary(stockPos, optionPos, stockLots, optionLots) {
  // Short-CostBasis = erhaltene Prämien (negativ im CSV)
  const totalPremiumBrutto = optionLots
    .filter(l => parseFloat(l.Quantity || '0') < 0)
    .reduce((s, l) => s + Math.abs(parseFloat(l.CostBasis || '0')), 0);

  // Long-CostBasis mit positivem Wert = Rückkäufe (Glattstellungen)
  const totalRueckkauf = optionLots
    .filter(l => parseFloat(l.Quantity || '0') > 0 && parseFloat(l.CostBasis || '0') > 0)
    .reduce((s, l) => s + parseFloat(l.CostBasis || '0'), 0);

  // Netto = erhaltene Prämien - bezahlte Rückkäufe
  const totalPremiumNetto = totalPremiumBrutto - totalRueckkauf;

  return {
    stockPositions:       stockPos.length,
    optionPositions:      optionPos.length,
    stockLots:            stockLots.length,
    optionLots:           optionLots.length,
    shortOptions:         optionLots.filter(l => parseFloat(l.Quantity||'0') < 0).length,
    longOptions:          optionLots.filter(l => parseFloat(l.Quantity||'0') > 0).length,
    totalPremiumBruttoUsd: Math.round(totalPremiumBrutto * 100) / 100,
    totalRueckkaufUsd:    Math.round(totalRueckkauf * 100) / 100,
    totalPremiumNettoUsd: Math.round(totalPremiumNetto * 100) / 100,
  };
}

// ── KONTOAUSZUG PARSER (Wechselkurse) ────────────────────────

/**
 * Parst den CapTrader Tages-Kontoauszug.
 * Extrahiert IBKR-eigene Wechselkurse — für EZB-unabhängige Umrechnung.
 *
 * @param {string} csvText
 * @returns {KontoauszugResult}
 */
export function parseKontoauszug(csvText) {
  const lines = csvText.split(/\r?\n/);
  const fxRates = {};
  let date = '';
  let accountId = '';
  let kontoName = '';

  for (const line of lines) {
    const p = line.split(',');

    // Datum
    if (p[0] === 'Statement' && p[1] === 'Data' && p[2] === 'Period') {
      const raw = p[3]?.replace(/"/g, '').trim();
      // "Juni 24, 2026" → "2026-06-24"
      const m = raw.match(/(\w+)\s+(\d+),\s+(\d{4})/);
      if (m) {
        const months = {
          'Januar':1,'Februar':2,'März':3,'April':4,'Mai':5,'Juni':6,
          'Juli':7,'August':8,'September':9,'Oktober':10,'November':11,'Dezember':12
        };
        const mon = months[m[1]] || 1;
        date = `${m[3]}-${String(mon).padStart(2,'0')}-${String(m[2]).padStart(2,'0')}`;
      }
    }

    // Kontoinhaber
    if (p[0] === 'Kontoinformation' && p[1] === 'Data' && p[2] === 'Name')
      kontoName = p[3]?.replace(/"/g, '').trim();
    if (p[0] === 'Kontoinformation' && p[1] === 'Data' && p[2] === 'Account')
      accountId = p[3]?.replace(/"/g, '').trim();

    // Wechselkurse (EUR-Basis)
    if (p[0] === 'Wechselkurs der Basiswährung' && p[1] === 'Data') {
      const currency = p[2]?.replace(/"/g, '').trim();
      const rate = parseFloat(p[3]?.replace(/"/g, '').trim() || '0');
      if (currency && rate > 0) fxRates[currency] = rate;
    }
  }

  // Offene Dividenden
  const pendingDividends = [];
  for (const line of lines) {
    const p = line.split(',');
    if (p[0] === 'Offener Dividendenanfall' && p[1] === 'Data' && p[3]) {
      pendingDividends.push({
        assetClass: p[2]?.replace(/"/g,'').trim(),
        currency:   p[3]?.replace(/"/g,'').trim(),
        symbol:     p[4]?.replace(/"/g,'').trim(),
        exDate:     p[5]?.replace(/"/g,'').trim(),
        payDate:    p[6]?.replace(/"/g,'').trim(),
        quantity:   parseFloat(p[7] || '0'),
        tax:        parseFloat(p[8] || '0'),
        grossRate:  parseFloat(p[10] || '0'),
        grossAmount: parseFloat(p[11] || '0'),
        netAmount:  parseFloat(p[12] || '0'),
      });
    }
  }

  return {
    format: 'kontoauszug',
    date,
    accountId,
    kontoName,
    fxRates,        // { USD: 0.8804, GBP: 1.1593, ... }
    pendingDividends,
    summary: {
      date,
      currencies: Object.keys(fxRates).length,
      usdRate: fxRates['USD'] || null,
      gbpRate: fxRates['GBP'] || null,
      pendingDividends: pendingDividends.length,
    },
  };
}

// ── UNIVERSELLER PARSER ───────────────────────────────────────

/**
 * Erkennt Format automatisch und parst entsprechend.
 * @param {string} text
 * @returns {LotsResult|KontoauszugResult|ActivityResult}
 */
export function parseFlexFile(text) {
  const format = detectFormat(text);
  switch (format) {
    case 'lots_csv':     return parseLotsCSV(text);
    case 'kontoauszug':  return parseKontoauszug(text);
    case 'ki_flex_full_csv':    return parseKiFlexFullCSV(text);
    case 'ki_flex_cash_csv':    return parseKiFlexCashCSV(text);
    case 'ki_flex_csv':         return parseKiFlexCSV(text);
    case 'activity_flex_csv':   return parseActivityFlexCSV(text);
    case 'activity_xml':        return { format, error: 'Activity XML Parser — coming soon' };
    case 'activity_csv':        return { format, error: 'Activity CSV Parser — coming soon' };
    case 'transaction_history': return parseTransactionHistory(text);
    default: throw new Error('Unbekanntes Dateiformat. Bitte Flex Query CSV oder XML hochladen.');
  }
}


// ── TRANSACTION HISTORY CSV PARSER ───────────────────────────

/**
 * Parst den CapTrader "Transaction History" CSV Export.
 * (Umsatzübersicht → Export als CSV)
 *
 * Vorteile gegenüber Jahresauszug CSV:
 * - Transaction Type ist eindeutig (Buy/Sell/Assignment)
 * - Kein Code-Rätselraten (O/C/A/Ep)
 * - Leerverkäufe klar erkennbar
 * - Assignment eindeutig (Put vs Call)
 *
 * @param {string} csvText
 * @returns {TransactionResult}
 */
export function parseTransactionHistory(csvText) {
  const lines = csvText.split(/\r?\n/);

  // Header finden
  const thIdx = lines.findIndex(l => l.startsWith('Transaction History,Header'));
  if (thIdx < 0) throw new Error('Kein Transaction History Format erkannt');

  // CSV parsen
  const rows = [];
  for (let i = thIdx; i < lines.length; i++) {
    const row = splitCSVLine(lines[i]);
    if (row[0] === 'Transaction History') rows.push(row);
  }

  const header = rows[0].slice(2).map(h => h.trim());
  const rawData = rows.slice(1)
    .filter(r => r[1] === 'Data')
    .map(r => {
      const obj = {};
      header.forEach((h, i) => obj[h] = (r[i+2] || '').trim());
      return obj;
    });

  // Trades klassifizieren
  const trades = [];
  const dividends = [];
  const interest = [];

  for (const d of rawData) {
    const type = d['Transaction Type'] || '';
    const sym  = d['Symbol'] || '';
    const qty  = parseFloat(d['Quantity'] || '0') || 0;
    const price = parseFloat(d['Price'] || '0') || 0;
    const gross = parseFloat(d['Gross Amount'] || '0') || 0;
    const comm  = parseFloat(d['Commission'] || '0') || 0;
    const date  = d['Date'] || '';
    const cur   = d['Price Currency'] || 'USD';
    const desc  = d['Description'] || '';

    // Option erkennen: Symbol länger als 6 Zeichen mit Ziffern
    const isOption = sym.length > 8 && /\d/.test(sym);
    const underlying = isOption ? sym.split(/\s+/)[0] : sym;

    // Klassifizierung
    let classification = '';
    let assetClass = '';
    let topf = '';

    if (type === 'Buy' && !isOption) {
      classification = qty > 0 ? 'stock_buy' : 'short_sell_cover';
      assetClass = 'Aktien';
      topf = '2_aktien';
    } else if (type === 'Sell' && !isOption) {
      classification = qty < 0 ? 'stock_sell' : 'short_sell_open';
      assetClass = 'Aktien';
      topf = '2_aktien';
    } else if (type === 'Sell' && isOption && qty < 0) {
      classification = 'short_option_open';  // Stillhalter
      assetClass = 'Aktien- und Indexoptionen';
      topf = '1_allgemein';
    } else if (type === 'Buy' && isOption && qty > 0) {
      classification = 'long_option_open';   // Termingeschäft
      assetClass = 'Aktien- und Indexoptionen';
      topf = '3_termin';
    } else if (type === 'Buy' && isOption && qty < 0) {
      classification = 'short_option_close'; // Glattstellung Short
      assetClass = 'Aktien- und Indexoptionen';
      topf = '1_allgemein';
    } else if (type === 'Sell' && isOption && qty > 0) {
      classification = 'long_option_close';  // Glattstellung Long
      assetClass = 'Aktien- und Indexoptionen';
      topf = '3_termin';
    } else if (type === 'Assignment' && qty > 0) {
      classification = 'put_assignment';     // Short Put ausgeübt → Aktien kaufen
      assetClass = 'Aktien';
      topf = '2_aktien';
    } else if (type === 'Assignment' && qty < 0) {
      classification = 'call_assignment';    // Short Call ausgeübt → Aktien liefern
      assetClass = 'Aktien';
      topf = '2_aktien';
    } else if (type === 'Dividend' || type === 'Payment in Lieu') {
      dividends.push({ date, symbol: sym, amount: gross, currency: cur, type, description: desc });
      continue;
    } else if (type === 'Foreign Tax Withholding') {
      dividends.push({ date, symbol: sym, amount: gross, currency: cur, type: 'wht', description: desc });
      continue;
    } else if (type === 'Credit Interest' || type === 'Debit Interest') {
      interest.push({ date, amount: gross, currency: cur, type });
      continue;
    } else {
      continue; // Deposit, Adjustment, etc. ignorieren
    }

    trades.push({
      date,
      dateTime: date + ' 00:00:00',
      assetClass,
      currency: cur,
      symbol: sym,
      underlying,
      description: desc,
      qty,
      price,
      proceeds: gross,
      commFee: comm,
      netAmount: parseFloat(d['Net Amount'] || '0') || 0,
      classification,
      topf,
      isOption,
      // Codes für ko-fifo.js Kompatibilität
      codes: buildCodes(classification),
      // Aus Transaction Type ableitbar
      buySell: type === 'Buy' ? 'BUY' : 'SELL',
      openCloseIndicator: (classification === 'short_option_open' || classification === 'long_option_open' || classification === 'stock_buy') ? 'O' : 'C',
    });
  }

  // Dividenden zusammenfassen
  const divTotal = dividends
    .filter(d => d.type === 'Dividend' || d.type === 'Payment in Lieu')
    .reduce((s, d) => s + d.amount, 0);
  const whtTotal = dividends
    .filter(d => d.type === 'wht')
    .reduce((s, d) => s + Math.abs(d.amount), 0);
  const interestTotal = interest.reduce((s, i) => s + i.amount, 0);

  return {
    format: 'transaction_history',
    period: extractPeriod(lines),
    accountId: extractAccountId(lines),
    trades: trades.sort((a, b) => a.dateTime.localeCompare(b.dateTime)),
    dividends,
    interest,
    summary: {
      totalTrades:      trades.length,
      stockBuys:        trades.filter(t => t.classification === 'stock_buy').length,
      stockSells:       trades.filter(t => t.classification === 'stock_sell').length,
      shortOptions:     trades.filter(t => t.classification === 'short_option_open').length,
      longOptions:      trades.filter(t => t.classification === 'long_option_open').length,
      assignments:      trades.filter(t => t.classification.includes('assignment')).length,
      dividendsUSD:     Math.round(divTotal * 100) / 100,
      whtUSD:           Math.round(whtTotal * 100) / 100,
      interestUSD:      Math.round(interestTotal * 100) / 100,
    },
  };
}

function buildCodes(classification) {
  switch(classification) {
    case 'short_option_open':  return ['O'];          // Stillhalter eröffnen
    case 'long_option_open':   return ['O'];           // Long Option kaufen
    case 'short_option_close': return ['C'];           // Short glattstellen
    case 'long_option_close':  return ['C'];           // Long verkaufen
    case 'put_assignment':     return ['A', 'O'];      // Put ausgeübt → Aktien kaufen
    case 'call_assignment':    return ['A', 'C'];      // Call ausgeübt → Aktien liefern
    case 'stock_buy':          return ['O'];
    case 'stock_sell':         return ['C'];
    default: return ['O'];
  }
}

function extractPeriod(lines) {
  const l = lines.find(l => l.includes('Period'));
  return l ? l.split(',').slice(-1)[0].replace(/"/g,'').trim() : '';
}

function extractAccountId(lines) {
  const l = lines.find(l => l.includes('Account,U'));
  return l ? l.split(',').find(p => p.startsWith('U')) || '' : '';
}

// ── ACTIVITY FLEX QUERY CSV PARSER ───────────────────────────

/**
 * Parst den CapTrader "Kontoumsatz-Flex-Query" CSV Export.
 * 
 * Struktur:
 *   BOF  → Datei-Header
 *   BOS POST → Open Positions (13 Spalten)
 *   BOS TRNT → Trades (31 Spalten inkl. FXRateToBase, CostBasis)
 *   BOS RATE → Wechselkurse je Tag (5850+ Zeilen)
 *
 * Vorteile:
 *   ✅ FXRateToBase direkt je Trade → kein EZB-API-Call nötig
 *   ✅ CostBasis = IBKR FIFO-Einstand → kein eigenes FIFO nötig
 *   ✅ FifoPnlRealized = bereits berechneter G/V
 *   ✅ Buy/Sell + OpenCloseIndicator eindeutig
 *   ✅ ISIN für ETF-Erkennung
 *
 * @param {string} csvText
 * @returns {ActivityFlexResult}
 */
export function parseActivityFlexCSV(csvText) {
  const lines = csvText.split(/\r?\n/);

  // Sektionen lokalisieren
  const bosIdxs = {};
  lines.forEach((l, i) => {
    const p = splitCSVLine(l);
    if (p[0] === 'BOS') bosIdxs[p[1]] = i;
  });

  // Meta-Daten aus BOF
  const bofLine = lines.find(l => l.startsWith('"BOF"'));
  const bofParts = bofLine ? splitCSVLine(bofLine) : [];
  const accountId = bofParts[1] || '';
  const queryName  = bofParts[2] || '';
  const fromDate   = bofParts[4] || '';
  const toDate     = bofParts[5] || '';

  // Open Positions (BOS POST)
  const postStart = (bosIdxs['POST'] || 0) + 1;
  const postEnd   = bosIdxs['TRNT'] || postStart;
  const positions = parseSection(lines, postStart, postEnd)
    .filter(r => r.Symbol && r.Quantity);

  // Trades (BOS TRNT)
  const trntStart = (bosIdxs['TRNT'] || 0) + 1;
  const trntEnd   = bosIdxs['RATE'] || lines.length;
  const allTrades = parseSection(lines, trntStart, trntEnd);
  const trades = allTrades.filter(r =>
    r['AssetClass'] === 'STK' || r['AssetClass'] === 'OPT'
  );

  // Wechselkurse (BOS RATE)
  const rateStart = (bosIdxs['RATE'] || 0) + 1;
  const rateLines = lines.slice(rateStart);
  const fxRateMap = parseRates(rateLines);

  // Trades klassifizieren und in ko-fifo.js Format konvertieren
  const fifoTrades = trades.map(t => convertToFifoTrade(t));

  // Positionen für FIFO-Lots aufbereiten
  const fifoLots = buildActivityFifoLots(positions, fxRateMap, toDate);

  return {
    format:      'activity_flex_csv',
    accountId,
    queryName,
    fromDate,
    toDate,
    trades:      fifoTrades,
    positions,
    fxRateMap,
    fifoLots,
    summary:     buildActivitySummary(fifoTrades, positions, fxRateMap),
  };
}

function parseRates(lines) {
  const map = {};
  // Header: "Date/Time","FromCurrency","ToCurrency","Rate"
  const reader = lines.slice(1); // Header überspringen
  for (const line of reader) {
    if (!line.trim()) continue;
    const p = splitCSVLine(line);
    if (!p[0] || !p[0].match(/^\d{4}/)) continue;
    const date = p[0].slice(0, 10); // "2026-01-01"
    const from = p[1];
    const rate = parseFloat(p[3]) || 0;
    if (from && rate) map[`${from}:${date}`] = rate;
  }
  return map;
}

function convertToFifoTrade(t) {
  const assetClass = t['AssetClass'] === 'STK'
    ? 'Aktien'
    : 'Aktien- und Indexoptionen';

  const buySell = t['Buy/Sell'] || '';
  const oci     = t['Open/CloseIndicator'] || '';
  const qty     = parseFloat(t['Quantity'] || '0');
  const putCall = t['Put/Call'] || '';
  const notes   = (t['Notes/Codes'] || '').split(/[;,]/).map(c => c.trim()).filter(Boolean);

  // Klassifizierung
  let classification = '';
  if (t['AssetClass'] === 'STK') {
    if (buySell === 'BUY'  && oci === 'O') classification = 'stock_buy';
    else if (buySell === 'SELL' && oci === 'C') classification = 'stock_sell';
    else if (buySell === 'SELL' && oci === 'O') classification = 'short_sell_open';
    else if (buySell === 'BUY'  && oci === 'C') classification = 'short_sell_cover';
    else if (notes.includes('A') && buySell === 'BUY')  classification = 'put_assignment';
    else if (notes.includes('A') && buySell === 'SELL') classification = 'call_assignment';
  } else {
    if (buySell === 'SELL' && oci === 'O') classification = putCall === 'P' ? 'short_put' : 'short_call';
    else if (buySell === 'BUY' && oci === 'O') classification = putCall === 'P' ? 'long_put' : 'long_call';
    else if (oci === 'C' && notes.includes('Ep')) classification = 'option_expired';
    else if (oci === 'C' && notes.includes('A'))  classification = 'option_assigned';
    else if (oci === 'C') classification = buySell === 'BUY' ? 'short_option_close' : 'long_option_close';
  }

  const fxRate   = parseFloat(t['FXRateToBase'] || '1') || 1;
  const proceeds = parseFloat(t['Proceeds'] || '0');
  const costBasis = parseFloat(t['CostBasis'] || '0');
  const fifoPnl  = parseFloat(t['FifoPnlRealized'] || '0');

  return {
    // Standard-Felder (ko-fifo.js kompatibel)
    assetClass,
    currency:    t['CurrencyPrimary'] || 'USD',
    symbol:      t['Symbol'] || '',
    underlying:  t['UnderlyingSymbol'] || t['Symbol'] || '',
    description: t['Description'] || '',
    dateTime:    (t['DateTime'] || '').replace(';', ' '),
    date:        (t['TradeDate'] || '').slice(0, 10),
    qty:         buySell === 'BUY' ? Math.abs(qty) : -Math.abs(qty),
    price:       parseFloat(t['TradePrice'] || '0'),
    proceeds,
    commFee:     parseFloat(t['IBCommission'] || '0'),
    codes:       notes,

    // Flex-spezifisch
    buySell,
    openCloseIndicator: oci,
    classification,
    putCall,
    strike:      parseFloat(t['Strike'] || '0') || null,
    expiry:      t['Expiry'] || '',
    multiplier:  parseFloat(t['Multiplier'] || '1'),
    isin:        t['ISIN'] || '',
    settleDate:  t['SettleDateTarget'] || '',

    // IBKR FIFO-Daten (direkt verwendbar!)
    fxRateToBase:   fxRate,
    costBasisUsd:   costBasis,
    costBasisEur:   round2(Math.abs(costBasis) * fxRate),
    proceedsEur:    round2(proceeds * fxRate),
    fifoPnlUsd:     fifoPnl,
    fifoPnlEur:     round2(fifoPnl * fxRate),
  };
}

function buildActivityFifoLots(positions, fxRateMap, toDate) {
  const lots = {};
  for (const pos of positions) {
    const sym = pos.Symbol;
    const qty = parseFloat(pos.Quantity || '0');
    if (!sym || qty === 0) continue;

    const currency = pos.CurrencyPrimary || 'USD';
    // Open Positions haben CostBasisPrice (pro Aktie) nicht CostBasis
    const costBasisPrice = parseFloat(pos.CostBasisPrice || '0');
    const costBasis = costBasisPrice * Math.abs(qty);  // Gesamt-Einstand
    const fxKey = `${currency}:${toDate}`;
    const fxRate = fxRateMap[fxKey] || 1;

    if (!lots[sym]) lots[sym] = [];
    lots[sym].push({
      symbol:       sym,
      date:         toDate,
      qty:          Math.abs(qty),
      costPerUnit:  qty !== 0 ? Math.abs(costBasis / qty) : 0,
      totalCostUsd: Math.abs(costBasis),
      totalCostEur: round2(Math.abs(costBasis) * fxRate),
      currency,
      fxRate,
      isShort:      qty < 0,
      source:       'activity_flex',
    });
  }
  return lots;
}

function buildActivitySummary(trades, positions, fxRateMap) {
  const stk = trades.filter(t => t.assetClass === 'Aktien');
  const opt = trades.filter(t => t.assetClass !== 'Aktien');
  const shortOpts = opt.filter(t => t.classification?.includes('short'));
  const longOpts  = opt.filter(t => t.classification?.includes('long'));

  // Netto-Prämien
  const premBrutto = shortOpts.reduce((s,t) => s + Math.abs(t.proceedsEur), 0);
  // Rückkäufe = Short-Option Close (BUY mit positivem CostBasis)
  const closes = opt.filter(t => t.classification === 'short_option_close');
  const rueckkauf = closes.reduce((s,t) => s + t.costBasisEur, 0);

  return {
    fromDate:             trades[0]?.date || '',
    toDate:               trades[trades.length-1]?.date || '',
    totalTrades:          trades.length,
    stockBuys:            stk.filter(t => t.classification === 'stock_buy').length,
    stockSells:           stk.filter(t => t.classification === 'stock_sell').length,
    shortOptions:         shortOpts.length,
    longOptions:          longOpts.length,
    fxCurrencies:         Object.keys(fxRateMap).map(k => k.split(':')[0])
                           .filter((v,i,a) => a.indexOf(v)===i).length,
    premiumBruttoEur:     round2(premBrutto),
    rueckkaufEur:         round2(rueckkauf),
    premiumNettoEur:      round2(premBrutto - rueckkauf),
  };
}

function round2(n) { return Math.round((n||0)*100)/100; }

// ── KI-FLEX QUERY CSV PARSER ─────────────────────────────────

/**
 * Parst das KI-generierte CapTrader Flex Query CSV Format.
 * (Kontoumsatz-Flex-Query, KI-assistiert)
 *
 * Unterschiede zum Activity Flex CSV:
 * - Kein BOF/BOS Header — direkte CSV-Zeilen
 * - Datum: yyyyMMdd (z.B. "20240122")
 * - DateTime: "yyyyMMdd;HHmmss" (z.B. "20240122;135347")
 * - Kein separater Wechselkurs-Abschnitt
 * - FXRateToBase direkt je Trade-Zeile
 *
 * Vorteile:
 *   ✅ FifoPnlRealized × FXRateToBase = exakter EUR-Betrag
 *   ✅ CostBasis = IBKR FIFO-Einstand
 *   ✅ Buy/Sell + Open/CloseIndicator eindeutig
 *   ✅ UnderlyingSymbol, Multiplier, Strike, Expiry, Put/Call
 *   ✅ Notes/Codes für Expired, Assignment
 *   ✅ Mehriahres-Export möglich
 *
 * @param {string} csvText
 * @returns {KiFlexResult}
 */
export function parseKiFlexCSV(csvText) {
  const lines = csvText.split(/\r?\n/);
  const header = lines[0];
  if (!header || !header.includes('TradeDate') || !header.includes('FXRateToBase')) {
    throw new Error('Kein KI-Flex CSV Format erkannt');
  }

  // CSV parsen
  const allRows = [];
  for (let i = 1; i < lines.length; i++) {
    if (!lines[i].trim()) continue;
    const vals = splitCSVLine(lines[i]);
    const cols  = splitCSVLine(header);
    const row   = {};
    cols.forEach((c, idx) => row[c.trim()] = (vals[idx] || '').trim());
    if (row['TradeDate']) allRows.push(row);
  }

  // Nach Jahren gruppieren
  const byYear = {};
  for (const row of allRows) {
    const year = row['TradeDate'].slice(0, 4);
    if (!byYear[year]) byYear[year] = [];
    byYear[year].push(row);
  }

  // Trades konvertieren
  const trades = allRows
    .filter(r => ['STK','OPT'].includes(r['AssetClass']))
    .map(r => convertKiFlexTrade(r));

  // FX-Map aus Trade-Daten aufbauen
  const fxRateMap = {};
  for (const r of allRows) {
    const fx = parseFloat(r['FXRateToBase'] || '0');
    const cur = r['CurrencyPrimary'] || '';
    const date = formatDate(r['TradeDate']);
    if (fx > 0 && cur && date) fxRateMap[`${cur}:${date}`] = fx;
  }

  // Jahresweise Auswertung
  const years = Object.keys(byYear).sort();
  const yearlyResults = {};
  for (const year of years) {
    const ytrades = byYear[year].filter(r => ['STK','OPT'].includes(r['AssetClass']));
    yearlyResults[year] = calcYearlyTax(ytrades, year);
  }

  return {
    format:         'ki_flex_csv',
    accountId:      allRows[0]?.['ClientAccountID'] || '',
    dateRange:      { from: formatDate(allRows[0]?.['TradeDate'] || ''),
                      to:   formatDate(allRows[allRows.length-1]?.['TradeDate'] || '') },
    trades,
    fxRateMap,
    yearlyResults,
    summary:        buildKiFlexSummary(trades, yearlyResults),
  };
}

function convertKiFlexTrade(r) {
  const buySell = r['Buy/Sell'] || '';
  const oci     = r['Open/CloseIndicator'] || '';
  const ac      = r['AssetClass'] || '';
  const notes   = (r['Notes/Codes'] || '').split(/[;,]/).map(c => c.trim()).filter(Boolean);
  const qty     = parseFloat(r['Quantity'] || '0');
  const putCall = r['Put/Call'] || '';
  const fx      = parseFloat(r['FXRateToBase'] || '1') || 1;
  const proceeds = parseFloat(r['Proceeds'] || '0');
  const costBasis = parseFloat(r['CostBasis'] || '0');
  const fifoPnl  = parseFloat(r['FifoPnlRealized'] || '0');
  const date     = formatDate(r['TradeDate']);
  const dateTime = formatDateTime(r['DateTime']);

  // Klassifizierung
  let classification = '';
  let topf = '';
  if (ac === 'STK') {
    if      (buySell==='BUY'  && oci==='O' && !notes.includes('A')) { classification='stock_buy';         topf='2_aktien'; }
    else if (buySell==='SELL' && oci==='C' && !notes.includes('A')) { classification='stock_sell';        topf='2_aktien'; }
    else if (buySell==='SELL' && oci==='O')                          { classification='short_sell_open';   topf='2_aktien'; }
    else if (buySell==='BUY'  && oci==='C' && !notes.includes('A')) { classification='short_sell_cover';  topf='2_aktien'; }
    else if (notes.includes('A') && buySell==='BUY')                 { classification='put_assignment';    topf='2_aktien'; }
    else if (notes.includes('A') && buySell==='SELL')                { classification='call_assignment';   topf='2_aktien'; }
  } else if (ac === 'OPT') {
    if      (buySell==='SELL' && oci==='O')        { classification='short_option_open';  topf='1_allgemein'; }
    else if (buySell==='BUY'  && oci==='C' && !notes.includes('Ep') && !notes.includes('A'))
                                                    { classification='short_option_close'; topf='1_allgemein'; }
    else if (buySell==='BUY'  && oci==='O')        { classification='long_option_open';   topf='3_termin'; }
    else if (buySell==='SELL' && oci==='C')        { classification='long_option_close';  topf='3_termin'; }
    else if (notes.includes('Ep'))                  { classification='option_expired';     topf=putCall==='P'?'1_allgemein':'3_termin'; }
    else if (notes.includes('A'))                   { classification='option_assigned';    topf='1_allgemein'; }
  }

  return {
    // Standard
    assetClass:   ac === 'STK' ? 'Aktien' : 'Aktien- und Indexoptionen',
    assetCategory: ac,
    currency:     r['CurrencyPrimary'] || 'USD',
    symbol:       r['Symbol'] || '',
    underlying:   r['UnderlyingSymbol'] || r['Symbol'] || '',
    description:  r['Description'] || '',
    date,
    dateTime,
    qty:          buySell === 'BUY' ? Math.abs(qty) : -Math.abs(qty),
    price:        parseFloat(r['TradePrice'] || '0'),
    proceeds,
    commFee:      parseFloat(r['IBCommission'] || '0'),
    codes:        notes,
    // Flex-spezifisch
    buySell,
    openCloseIndicator: oci,
    classification,
    topf,
    putCall,
    strike:       parseFloat(r['Strike'] || '0') || null,
    expiry:       r['Expiry'] || '',
    multiplier:   parseFloat(r['Multiplier'] || '1'),
    // IBKR FIFO-Daten (direkt verwenden!)
    fxRateToBase:  fx,
    costBasisUsd:  costBasis,
    costBasisEur:  round2(Math.abs(costBasis) * fx),
    proceedsEur:   round2(proceeds * fx),
    fifoPnlUsd:    fifoPnl,
    fifoPnlEur:    round2(fifoPnl * fx),
  };
}

function calcYearlyTax(trades, year) {
  const stk = trades.filter(t => t['AssetClass']==='STK');
  const opt  = trades.filter(t => t['AssetClass']==='OPT');

  // Aktien: FifoPnlRealized × FXRateToBase
  const stkGainEur = stk
    .filter(r => parseFloat(r['FifoPnlRealized']||0) > 0)
    .reduce((s,r) => s + parseFloat(r['FifoPnlRealized']||0) * parseFloat(r['FXRateToBase']||1), 0);
  const stkLossEur = stk
    .filter(r => parseFloat(r['FifoPnlRealized']||0) < 0)
    .reduce((s,r) => s + parseFloat(r['FifoPnlRealized']||0) * parseFloat(r['FXRateToBase']||1), 0);

  // Optionen: Gewinne und Verluste getrennt
  const optGainEur = opt
    .filter(r => parseFloat(r['FifoPnlRealized']||0) > 0)
    .reduce((s,r) => s + parseFloat(r['FifoPnlRealized']||0) * parseFloat(r['FXRateToBase']||1), 0);
  const optLossEur = opt
    .filter(r => parseFloat(r['FifoPnlRealized']||0) < 0)
    .reduce((s,r) => s + parseFloat(r['FifoPnlRealized']||0) * parseFloat(r['FXRateToBase']||1), 0);

  return {
    year,
    // Anlage KAP Zeilen (direkt von IBKR)
    z8_aktienGewinn:   round2(stkGainEur),
    z9_aktienVerlust:  round2(Math.abs(stkLossEur)),
    z20_optGewinn:     round2(optGainEur),
    z21_optVerlust:    round2(Math.abs(optLossEur)),
    z20_saldo:         round2(optGainEur + optLossEur),
    // Rohdaten
    stkGainEur:  round2(stkGainEur),
    stkLossEur:  round2(stkLossEur),
    optGainEur:  round2(optGainEur),
    optLossEur:  round2(optLossEur),
  };
}

function buildKiFlexSummary(trades, yearlyResults) {
  return {
    totalTrades:  trades.length,
    years:        Object.keys(yearlyResults).sort(),
    byYear:       yearlyResults,
  };
}

function formatDate(raw) {
  // "20240122" → "2024-01-22"
  if (!raw || raw.length < 8) return raw || '';
  return `${raw.slice(0,4)}-${raw.slice(4,6)}-${raw.slice(6,8)}`;
}

function formatDateTime(raw) {
  // "20240122;135347" → "2024-01-22 13:53:47"
  if (!raw) return '';
  const parts = raw.split(';');
  const date = formatDate(parts[0]);
  const time = parts[1]
    ? `${parts[1].slice(0,2)}:${parts[1].slice(2,4)}:${parts[1].slice(4,6)}`
    : '00:00:00';
  return `${date} ${time}`;
}

// ── KI-FLEX CASH CSV PARSER (Trades + Cash Transactions) ─────

/**
 * Parst das kombinierte Flex Query CSV mit Trades UND Cash Transactions.
 * Die Datei enthält zwei Sektionen mit unterschiedlichen Headern.
 *
 * Sektion 1: Trades (FifoPnlRealized × FXRateToBase = exakter EUR-G/V)
 * Sektion 2: Cash Transactions (Dividenden, WHT, Zinsen mit FXRateToBase)
 *
 * → Eine einzige Datei ersetzt: Jahresauszug + Dividenden HTML + FX-CSV
 *
 * @param {string} csvText
 * @returns {KiFlexCashResult}
 */
export function parseKiFlexCashCSV(csvText) {
  const lines = csvText.split(/\r?\n/);

  // Zwei Header-Zeilen finden
  const headerIdxs = lines
    .map((l, i) => l.startsWith('"ClientAccountID"') ? i : -1)
    .filter(i => i >= 0);

  if (headerIdxs.length < 2) {
    // Nur Trades, keine Cash Transactions → Fallback
    return parseKiFlexCSV(csvText);
  }

  const tradeHeaderIdx = headerIdxs[0];
  const cashHeaderIdx  = headerIdxs[1];

  // Sektion 1: Trades parsen
  const tradeLines = lines.slice(tradeHeaderIdx, cashHeaderIdx);
  const tradeCols  = splitCSVLine(tradeLines[0]);
  const tradeRows  = tradeLines.slice(1)
    .filter(l => l.trim())
    .map(l => {
      const vals = splitCSVLine(l);
      const row  = {};
      tradeCols.forEach((c, i) => row[c] = (vals[i] || '').trim());
      return row;
    })
    .filter(r => ['STK','OPT'].includes(r['AssetClass']));

  // Sektion 2: Cash Transactions parsen
  const cashLines = lines.slice(cashHeaderIdx);
  const cashCols  = splitCSVLine(cashLines[0]);
  const cashRows  = cashLines.slice(1)
    .filter(l => l.trim())
    .map(l => {
      const vals = splitCSVLine(l);
      const row  = {};
      cashCols.forEach((c, i) => row[c] = (vals[i] || '').trim());
      return row;
    })
    .filter(r => r['Type']?.trim());

  // Trades konvertieren (gleich wie parseKiFlexCSV)
  const trades = tradeRows.map(r => convertKiFlexTrade(r));

  // Cash Transactions klassifizieren
  const cashResult = parseCashTransactions(cashRows);

  // AccountId + Zeitraum
  const accountId = tradeRows[0]?.['ClientAccountID'] || cashRows[0]?.['ClientAccountID'] || '';
  const allDates  = tradeRows.map(r => formatDate(r['TradeDate']))
    .concat(cashRows.map(r => formatDate((r['Date/Time'] || '').slice(0, 8))))
    .filter(Boolean).sort();

  // Jahre aus Trades und Cash
  const years = [...new Set([
    ...tradeRows.map(r => r['TradeDate']?.slice(0, 4)),
    ...cashRows.map(r => (r['Date/Time'] || '').slice(0, 4)),
  ].filter(Boolean))].sort();

  // Jahresweise Auswertung
  const yearlyResults = {};
  for (const year of years) {
    const ytrades = tradeRows.filter(r => r['TradeDate']?.slice(0, 4) === year);
    const ycash   = cashRows.filter(r => (r['Date/Time'] || '').slice(0, 4) === year);
    yearlyResults[year] = calcYearlyTaxFull(ytrades, ycash, year);
  }

  return {
    format:        'ki_flex_cash_csv',
    accountId,
    dateRange:     { from: allDates[0] || '', to: allDates[allDates.length-1] || '' },
    trades,
    cashTransactions: cashResult,
    yearlyResults,
    summary:       buildKiFlexCashSummary(trades, cashResult, yearlyResults),
  };
}

function parseCashTransactions(rows) {
  const dividenden    = [];
  const quellensteuer = [];
  const zinsen        = [];

  for (const r of rows) {
    const type   = r['Type'] || '';
    const amt    = parseFloat(r['Amount'] || '0');
    const fx     = parseFloat(r['FXRateToBase'] || '1') || 1;
    const amtEur = round2(amt * fx);
    const date   = formatDate((r['Date/Time'] || '').slice(0, 8));
    const sym    = r['Symbol'] || '';
    const desc   = r['Description'] || '';
    const cur    = r['CurrencyPrimary'] || 'EUR';

    if (type === 'Dividends' || type === 'Payment In Lieu Of Dividends') {
      dividenden.push({ date, symbol: sym, description: desc,
        amount: amt, currency: cur, fxRate: fx, amountEur: amtEur,
        type: type === 'Dividends' ? 'dividende' : 'ersatzdividende' });

    } else if (type === 'Withholding Tax' && amt < 0) {
      quellensteuer.push({ date, symbol: sym, description: desc,
        amount: Math.abs(amt), currency: cur, fxRate: fx,
        amountEur: Math.abs(amtEur) });

    } else if (type.includes('Interest')) {
      zinsen.push({ date, description: desc,
        amount: amt, currency: cur, fxRate: fx, amountEur: amtEur,
        type: amt >= 0 ? 'haben' : 'soll' });
    }
  }

  return { dividenden, quellensteuer, zinsen };
}

function calcYearlyTaxFull(trades, cash, year) {
  // G/V aus Trades (exakt: FifoPnlRealized × FXRateToBase)
  const base = calcYearlyTax(trades, year);

  // Dividenden aus Cash
  const divs = cash.filter(r =>
    r['Type'] === 'Dividends' || r['Type'] === 'Payment In Lieu Of Dividends');
  const whts = cash.filter(r =>
    r['Type'] === 'Withholding Tax' && parseFloat(r['Amount'] || '0') < 0);
  const ints = cash.filter(r =>
    r['Type']?.includes('Interest') && parseFloat(r['Amount'] || '0') > 0);

  const divEur = round2(divs.reduce((s, r) =>
    s + parseFloat(r['Amount'] || '0') * (parseFloat(r['FXRateToBase'] || '1') || 1), 0));
  const whtEur = round2(whts.reduce((s, r) =>
    s + Math.abs(parseFloat(r['Amount'] || '0')) * (parseFloat(r['FXRateToBase'] || '1') || 1), 0));
  const intEur = round2(ints.reduce((s, r) =>
    s + parseFloat(r['Amount'] || '0') * (parseFloat(r['FXRateToBase'] || '1') || 1), 0));

  return {
    ...base,
    // Anlage KAP Zeilen komplett
    z7_dividenden:  divEur,
    z41_quellensteuer: whtEur,
    z14_zinsen:     intEur,
    // Rohdaten
    divEur, whtEur, intEur,
    divCount: divs.length,
    whtCount: whts.length,
  };
}

function buildKiFlexCashSummary(trades, cash, yearlyResults) {
  return {
    totalTrades:      trades.length,
    totalDividenden:  cash.dividenden.length,
    totalQuellensteuer: cash.quellensteuer.length,
    totalZinsen:      cash.zinsen.length,
    years:            Object.keys(yearlyResults).sort(),
    byYear:           yearlyResults,
  };
}

// ── KI-FLEX FULL CSV PARSER (Account Info + Trades + Cash) ───

/**
 * Parst das neue Flex Query Format mit 3 Sektionen:
 * 1. Account Information (Name, AccountType)
 * 2. Trades (FifoPnlRealized, FXRateToBase, CostBasis, etc.)
 * 3. Cash Transactions (Dividenden, WHT, Zinsen)
 *
 * Ermöglicht automatische Erkennung von:
 * - Einzel- vs. Gemeinschaftskonto (AND im Namen)
 * - Kontoinhaber-Namen für DOCX-Header
 *
 * @param {string} csvText
 * @returns {KiFlexFullResult}
 */
export function parseKiFlexFullCSV(csvText) {
  const lines = csvText.split(/\r?\n/);

  // Alle Header-Zeilen finden
  const headerIdxs = lines
    .map((l, i) => l.startsWith('"ClientAccountID"') ? i : -1)
    .filter(i => i >= 0);

  if (headerIdxs.length < 2) throw new Error('Ungültiges ki_flex_full Format');

  // Sektion 1: Account Information
  const accLine   = lines[1] || '';
  const accParts  = splitCSVLine(accLine);
  const kontoName = accParts[1] || '';
  const accType   = accParts[2] || '';
  const accountId = accParts[0] || '';
  const isJoint   = / and /i.test(kontoName);
  const inhaber   = isJoint
    ? kontoName.split(/ and /i).map(n => n.trim())
    : [kontoName];

  // Sektion 2: Trades (headerIdxs[1] bis headerIdxs[2])
  const tradeStart = headerIdxs[1];
  const tradeEnd   = headerIdxs.length > 2 ? headerIdxs[2] : lines.length;
  const tradeCols  = splitCSVLine(lines[tradeStart]);
  const tradeRows  = [];
  for (let i = tradeStart + 1; i < tradeEnd; i++) {
    if (!lines[i]?.trim()) continue;
    const vals = splitCSVLine(lines[i]);
    const row  = {};
    tradeCols.forEach((c, idx) => row[c] = (vals[idx] || '').trim());
    if (['STK','OPT'].includes(row['AssetClass'])) tradeRows.push(row);
  }

  // Sektion 3: Cash Transactions
  const cashStart = headerIdxs.length > 2 ? headerIdxs[2] : tradeEnd;
  const cashCols  = splitCSVLine(lines[cashStart]);
  const cashRows  = [];
  for (let i = cashStart + 1; i < lines.length; i++) {
    if (!lines[i]?.trim()) continue;
    const vals = splitCSVLine(lines[i]);
    const row  = {};
    cashCols.forEach((c, idx) => row[c] = (vals[idx] || '').trim());
    if (row['Type']) cashRows.push(row);
  }

  // Trades konvertieren
  const trades = tradeRows.map(r => convertKiFlexTrade(r));

  // Cash klassifizieren
  const cashResult = parseCashTransactions(cashRows);

  // Jahres-Ergebnisse berechnen
  // Jahr aus Cash Transactions (zuverlässig) oder TradeDate
  const cashYears = [...new Set(cashRows.map(r => (r['Date/Time']||'').slice(0,4)).filter(Boolean))];
  const tradeYears = [...new Set(tradeRows.map(r => r['TradeDate']?.slice(0,4)).filter(Boolean))];
  const years = [...new Set([...cashYears, ...tradeYears])].sort();

  const yearlyResults = {};
  for (const year of years) {
    // Trades haben kein TradeDate → alle Trades diesem Jahr zuordnen
    // (jede Datei enthält nur ein Steuerjahr)
    const hasTradeDate = tradeRows.some(r => r['TradeDate']);
    const yt = hasTradeDate
      ? tradeRows.filter(r => r['TradeDate']?.slice(0,4) === year)
      : tradeRows;  // kein TradeDate → alle Trades gehören zu diesem Jahr
    const yc = cashRows.filter(r => (r['Date/Time']||'').slice(0,4) === year);
    yearlyResults[year] = calcYearlyTaxFull(yt, yc, year);
  }

  // Datumsbereich
  const allDates = [
    ...tradeRows.map(r => formatDate(r['TradeDate']||'')),
    ...cashRows.map(r => formatDate((r['Date/Time']||'').slice(0,8))),
  ].filter(Boolean).sort();

  return {
    format:       'ki_flex_full_csv',
    accountId,
    kontoName,
    accType,
    isJoint,
    inhaber,
    dateRange:    { from: allDates[0]||'', to: allDates[allDates.length-1]||'' },
    trades,
    cashTransactions: cashResult,
    yearlyResults,
    summary:      buildKiFlexCashSummary(trades, cashResult, yearlyResults),
  };
}

export const FLEX_MODULE_META = {
  version:   '1.1.0',
  created:   '2026-06-26',
  formats:   ['lots_csv', 'kontoauszug', 'transaction_history', 'ki_flex_full_csv', 'ki_flex_cash_csv', 'ki_flex_csv', 'activity_flex_csv', 'activity_xml (planned)'],
  nextStep:  'Activity Flex Query mit TradeDate, BuySell, OpenCloseIndicator',
};
