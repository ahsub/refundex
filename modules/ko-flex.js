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
  if (text.includes('"Symbol","Description","Quantity","Multiplier"'))
    return 'lots_csv';
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
    case 'activity_xml': return { format, error: 'Activity XML Parser — coming soon' };
    case 'activity_csv': return { format, error: 'Activity CSV Parser — coming soon' };
    default: throw new Error('Unbekanntes Dateiformat. Bitte Flex Query CSV oder XML hochladen.');
  }
}

export const FLEX_MODULE_META = {
  version:   '1.1.0',
  created:   '2026-06-26',
  formats:   ['lots_csv', 'kontoauszug', 'activity_xml (planned)', 'activity_csv (planned)'],
  nextStep:  'Activity Flex Query mit TradeDate, BuySell, OpenCloseIndicator',
};
