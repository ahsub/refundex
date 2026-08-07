/**
 * ko-journal.js — Trade-Journal-Modul für Refundex
 * =================================================
 * Version: 1.0.0
 * Stand: 07.08.2026
 * ROADMAP: 2.9 (Trade-Journal-Modul)
 *
 * Architektur-Entscheidung (05.08.2026):
 *   Journal gehört in Refundex (Positions-Bewirtschaftung nach dem Trade),
 *   nicht in UIQ (Entscheidungs-Tool vor dem Trade).
 *
 * Datenbasis: parseActivityXML() aus ko-flex.js (ROADMAP 2.8)
 *   → Trades (Fills, P&L)
 *   → OptionEAE (Assignment/Expiry/Exercise)
 *   → CashTransactions (Dividenden + QSt)
 *
 * Speicher: localStorage (key: 'rx_journal_entries')
 *   → Datensouveränität (Grundgesetz 3)
 *   → Kein Server-Upload von Depotdaten
 *
 * Export: JSON (Backup) + DOCX (Jahresauswertung, via ko-flex Infrastruktur)
 *
 * Datenmodell: docs/DATENMODELL_JOURNAL.md v1.1
 */

// ── Konstanten ────────────────────────────────────────────────

const JOURNAL_VERSION  = '1.0.0';
const STORAGE_KEY      = 'rx_journal_entries';
const STORAGE_KEY_PREFS = 'rx_journal_prefs';

// ── Hilfsfunktionen ───────────────────────────────────────────

function _round2(n) { return Math.round((n || 0) * 100) / 100; }

function _holdingDays(openDate, closeDate) {
  if (!openDate || !closeDate) return null;
  const d1 = new Date(openDate);
  const d2 = new Date(closeDate);
  return Math.round((d2 - d1) / 86400000);
}

function _generateId(symbol, openDate, closeDate) {
  return `${symbol}-${(openDate || '').replace(/-/g, '')}-${(closeDate || '').replace(/-/g, '')}`;
}

// ── Kern-Funktion: Flex-Ergebnis → Journal-Einträge ──────────

/**
 * Konvertiert das Ergebnis von parseActivityXML() oder parseActivityFlexCSV()
 * in Journal-Einträge gemäß DATENMODELL_JOURNAL.md.
 *
 * Strategie:
 *   1. Close-Trades (OCI='C') mit fifoPnlRealized ≠ 0 = abgeschlossene Positionen
 *   2. OptionEAE-Einträge = Assignment/Expiry/Exercise
 *   3. Offene Positionen werden nicht als Journal-Einträge behandelt
 *
 * @param {Object} flexResult — Rückgabe von parseFlexFile() / parseActivityXML()
 * @returns {JournalEntry[]}
 */
export function flexResultToJournalEntries(flexResult) {
  if (!flexResult || flexResult.error) return [];

  const entries = [];
  const trades  = flexResult.trades || [];
  const eae     = flexResult.eaeTrades || [];

  // ── 1. Close-Trades mit realisiertem P&L ─────────────────────
  const closeTrades = trades.filter(t =>
    t.openCloseIndicator === 'C' &&
    t.fifoPnlUsd !== 0 &&
    !t.eaeSource  // EAE-Trades separat verarbeiten
  );

  for (const t of closeTrades) {
    // Nur STK und OPT (kein CASH/FX)
    if (t.assetClass !== 'Aktien' && t.assetClass !== 'Aktien- und Indexoptionen') continue;

    const isOpt = t.assetClass === 'Aktien- und Indexoptionen';
    const id    = _generateId(t.symbol, '', t.date);

    const entry = _buildEntry({
      id,
      source:       'flex_xml',
      symbol:       t.symbol,
      description:  t.description,
      assetCategory: isOpt ? 'OPT' : 'STK',
      currency:     t.currency,
      openDate:     null,        // Close-Trade allein kennt das Open-Datum nicht
      closeDate:    t.date,
      direction:    t.qty < 0 ? 'SHORT' : 'LONG',
      quantity:     Math.abs(t.qty),
      closePrice:   t.price,
      commission:   t.commFee,
      pnlGross:     t.fifoPnlUsd,
      fxRateClose:  t.fxRateToBase,
      // Optionen-spezifisch
      option: isOpt ? {
        expiry:     t.expiry,
        strike:     t.strike,
        putCall:    t.putCall,
        multiplier: t.multiplier,
        underlying: t.underlying,
        strategy:   _inferStrategy(t.classification),
      } : null,
      broker:     'CapTrader',
      notes:      t.codes || [],
      classification: t.classification,
    });

    entries.push(entry);
  }

  // ── 2. OptionEAE (Assignment/Expiry/Exercise) ─────────────────
  // Nur OPT-Zeilen (STK-Zeilen = entstehende Aktienposition, separat)
  const optEAE = eae.filter(t => t.assetClass === 'Aktien- und Indexoptionen');

  for (const t of optEAE) {
    const id = _generateId(t.symbol, '', t.date) + '-eae';

    const entry = _buildEntry({
      id,
      source:       'flex_xml_eae',
      symbol:       t.symbol,
      description:  t.description,
      assetCategory: 'OPT',
      currency:     t.currency,
      openDate:     null,
      closeDate:    t.date,
      direction:    'SHORT',   // EAE-Events betreffen meist verkaufte Optionen
      quantity:     Math.abs(t.qty),
      closePrice:   t.price,
      commission:   t.commFee,
      pnlGross:     t.fifoPnlUsd,
      fxRateClose:  t.fxRateToBase,
      option: {
        expiry:     t.expiry,
        strike:     t.strike,
        putCall:    t.putCall,
        multiplier: t.multiplier,
        underlying: t.underlying,
        strategy:   _inferStrategy(t.classification),
      },
      broker:     'CapTrader',
      notes:      t.codes || [],
      classification: t.classification,
    });

    entries.push(entry);
  }

  return entries;
}

/**
 * Baut einen vollständigen Journal-Eintrag gemäß DATENMODELL_JOURNAL.md.
 * Automatische Felder: berechnet.
 * Manuelle Felder: leer (user-editierbar).
 */
function _buildEntry(data) {
  const pnlNet    = _round2((data.pnlGross || 0) + (data.commission || 0));
  const pnlNetEur = _round2(pnlNet * (data.fxRateClose || 1));
  const holdDays  = _holdingDays(data.openDate, data.closeDate);
  const retPct    = data.openPrice && data.quantity
    ? _round2(pnlNet / (data.openPrice * data.quantity) * 100)
    : null;

  return {
    // ── Identifikation ──────────────────────────────────────────
    id:             data.id,
    source:         data.source || 'flex_xml',
    importedAt:     new Date().toISOString(),

    // ── Instrument ─────────────────────────────────────────────
    symbol:         data.symbol        || '',
    description:    data.description   || '',
    assetCategory:  data.assetCategory || 'STK',
    currency:       data.currency      || 'USD',

    // ── Optionen-spezifisch (null für STK) ──────────────────────
    option:         data.option || null,

    // ── Zeitraum ───────────────────────────────────────────────
    openDate:       data.openDate  || null,
    closeDate:      data.closeDate || null,
    holdingDays:    holdDays,

    // ── Richtung ───────────────────────────────────────────────
    direction:      data.direction || 'LONG',
    quantity:       data.quantity  || 0,

    // ── Preise ─────────────────────────────────────────────────
    openPrice:      data.openPrice  || null,
    closePrice:     data.closePrice || null,
    commission:     _round2(data.commission || 0),

    // ── P&L ────────────────────────────────────────────────────
    pnlGross:       _round2(data.pnlGross || 0),
    pnlNet,
    pnlNetEur,
    fxRateClose:    data.fxRateClose || 1,
    returnPct:      retPct,

    // ── Broker/Konto ───────────────────────────────────────────
    broker:         data.broker   || 'CapTrader',
    account:        data.account  || '',

    // ── Klassifizierung ────────────────────────────────────────
    classification: data.classification || '',
    notes:          data.notes || [],

    // ── MANUELLE FELDER (user-editierbar, initial leer) ─────────
    setup: {
      type:             null,    // 'VCP'|'BASE'|'Breakout'|'CSP'|'CC'|...
      regime:           null,    // MSE-Regime zum Entry (aus UIQ)
      regimeConfidence: null,    // 0–1
      rsRankEntry:      null,    // RS-Rank zum Entry
      entryReason:      '',
      exitReason:       '',
    },
    rule: {
      planCompliant:    null,    // true|false
      stopRespected:    null,
      positionSize:     null,    // 'OK'|'ZU_GROSS'|'ZU_KLEIN'
      deviation:        '',
    },
    learning: {
      whatWorked:       '',
      whatFailed:       '',
      nextTime:         '',
      tags:             [],
    },

    updatedAt: new Date().toISOString(),
  };
}

function _inferStrategy(classification) {
  if (!classification) return null;
  if (classification === 'short_put')    return 'CSP';
  if (classification === 'short_call')   return 'CC';
  if (classification.includes('spread')) return 'SPREAD';
  if (classification === 'long_put')     return 'LONG_PUT';
  if (classification === 'long_call')    return 'LONG_CALL';
  return null;
}

// ── localStorage API ─────────────────────────────────────────

/**
 * Lädt alle Journal-Einträge aus localStorage.
 * @returns {JournalEntry[]}
 */
export function loadJournal() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch (e) {
    console.error('[ko-journal] loadJournal Fehler:', e);
    return [];
  }
}

/**
 * Speichert alle Journal-Einträge in localStorage.
 * @param {JournalEntry[]} entries
 */
export function saveJournal(entries) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(entries));
    return true;
  } catch (e) {
    console.error('[ko-journal] saveJournal Fehler:', e);
    return false;
  }
}

/**
 * Importiert neue Einträge aus einem Flex-Ergebnis.
 * Dedupliziert über entry.id (kein Überschreiben manueller Felder).
 *
 * @param {Object} flexResult — Rückgabe von parseFlexFile()
 * @returns {{ added: number, skipped: number, total: number }}
 */
export function importFromFlex(flexResult) {
  const existing = loadJournal();
  const existingIds = new Set(existing.map(e => e.id));

  const newEntries = flexResultToJournalEntries(flexResult);
  let added = 0, skipped = 0;

  for (const entry of newEntries) {
    if (existingIds.has(entry.id)) {
      skipped++;
    } else {
      existing.push(entry);
      existingIds.add(entry.id);
      added++;
    }
  }

  if (added > 0) saveJournal(existing);

  return { added, skipped, total: existing.length };
}

/**
 * Aktualisiert manuelle Felder eines Eintrags (setup/rule/learning).
 * @param {string} id
 * @param {Object} updates — Teilupdate, z.B. { setup: { type: 'VCP' } }
 */
export function updateEntry(id, updates) {
  const entries = loadJournal();
  const idx = entries.findIndex(e => e.id === id);
  if (idx === -1) return false;

  // Deep-merge für setup/rule/learning
  for (const section of ['setup', 'rule', 'learning']) {
    if (updates[section]) {
      entries[idx][section] = { ...entries[idx][section], ...updates[section] };
    }
  }
  // Top-level Felder
  for (const key of Object.keys(updates)) {
    if (!['setup', 'rule', 'learning'].includes(key)) {
      entries[idx][key] = updates[key];
    }
  }
  entries[idx].updatedAt = new Date().toISOString();

  return saveJournal(entries);
}

/**
 * Löscht einen Eintrag.
 */
export function deleteEntry(id) {
  const entries = loadJournal().filter(e => e.id !== id);
  return saveJournal(entries);
}

// ── Aggregations-Statistik ───────────────────────────────────

/**
 * Berechnet Journal-Statistik für einen Zeitraum.
 * @param {JournalEntry[]} entries
 * @param {{ year?: number, quarter?: number }} filter
 * @returns {JournalStats}
 */
export function calcJournalStats(entries, filter = {}) {
  let filtered = entries.filter(e => e.pnlNetEur !== 0);

  if (filter.year) {
    filtered = filtered.filter(e =>
      e.closeDate && new Date(e.closeDate).getFullYear() === filter.year
    );
  }
  if (filter.quarter) {
    filtered = filtered.filter(e => {
      if (!e.closeDate) return false;
      return Math.ceil((new Date(e.closeDate).getMonth() + 1) / 3) === filter.quarter;
    });
  }

  const wins   = filtered.filter(e => e.pnlNetEur > 0);
  const losses = filtered.filter(e => e.pnlNetEur < 0);

  const avgWin  = wins.length   ? _round2(wins.reduce((s,e) => s + e.pnlNetEur, 0)   / wins.length)   : 0;
  const avgLoss = losses.length ? _round2(losses.reduce((s,e) => s + e.pnlNetEur, 0) / losses.length) : 0;

  const profitFactor = avgLoss !== 0
    ? _round2((avgWin * wins.length) / Math.abs(avgLoss * losses.length))
    : null;

  const expectancy = filtered.length
    ? _round2(filtered.reduce((s,e) => s + e.pnlNetEur, 0) / filtered.length)
    : 0;

  // Aufschlüsselung nach Asset-Klasse
  const byAsset = {};
  for (const e of filtered) {
    const cat = e.assetCategory || 'STK';
    if (!byAsset[cat]) byAsset[cat] = { trades: 0, pnlNetEur: 0, wins: 0 };
    byAsset[cat].trades++;
    byAsset[cat].pnlNetEur = _round2(byAsset[cat].pnlNetEur + e.pnlNetEur);
    if (e.pnlNetEur > 0) byAsset[cat].wins++;
  }
  for (const cat of Object.keys(byAsset)) {
    byAsset[cat].winRate = byAsset[cat].trades > 0
      ? _round2(byAsset[cat].wins / byAsset[cat].trades)
      : 0;
  }

  // Aufschlüsselung nach Setup-Typ
  const bySetup = {};
  for (const e of filtered) {
    const s = e.setup?.type || 'unklassifiziert';
    if (!bySetup[s]) bySetup[s] = { trades: 0, pnlNetEur: 0, wins: 0 };
    bySetup[s].trades++;
    bySetup[s].pnlNetEur = _round2(bySetup[s].pnlNetEur + e.pnlNetEur);
    if (e.pnlNetEur > 0) bySetup[s].wins++;
  }

  return {
    period:         filter.year ? `${filter.year}${filter.quarter ? `-Q${filter.quarter}` : ''}` : 'gesamt',
    generatedAt:    new Date().toISOString(),
    tradesTotal:    filtered.length,
    tradesWin:      wins.length,
    tradesLoss:     losses.length,
    winRate:        filtered.length ? _round2(wins.length / filtered.length) : 0,
    pnlNetEur:      _round2(filtered.reduce((s,e) => s + e.pnlNetEur, 0)),
    avgWinEur:      avgWin,
    avgLossEur:     avgLoss,
    profitFactor,
    expectancy,
    byAssetCategory: byAsset,
    bySetupType:     bySetup,
  };
}

// ── Export-Funktionen ─────────────────────────────────────────

/**
 * Exportiert Journal als JSON (Backup).
 */
export function exportJSON() {
  const entries = loadJournal();
  const blob = new Blob(
    [JSON.stringify({ version: JOURNAL_VERSION, exportedAt: new Date().toISOString(), entries }, null, 2)],
    { type: 'application/json' }
  );
  const url = URL.createObjectURL(blob);
  const a   = document.createElement('a');
  a.href    = url;
  a.download = `refundex-journal-${new Date().toISOString().slice(0,10)}.json`;
  a.click();
  URL.revokeObjectURL(url);
}

/**
 * Importiert Journal aus JSON-Backup.
 * @param {string} jsonText
 * @returns {{ imported: number, errors: string[] }}
 */
export function importJSON(jsonText) {
  const errors = [];
  let imported = 0;
  try {
    const data = JSON.parse(jsonText);
    const entries = Array.isArray(data) ? data : (data.entries || []);
    const existing = loadJournal();
    const ids = new Set(existing.map(e => e.id));
    for (const entry of entries) {
      if (!entry.id) { errors.push('Eintrag ohne ID übersprungen'); continue; }
      if (!ids.has(entry.id)) { existing.push(entry); ids.add(entry.id); imported++; }
    }
    saveJournal(existing);
  } catch (e) {
    errors.push('JSON Parse-Fehler: ' + e.message);
  }
  return { imported, errors };
}

/**
 * Löscht alle Journal-Einträge (mit Bestätigung).
 */
export function clearJournal() {
  localStorage.removeItem(STORAGE_KEY);
}

// ── Version ──────────────────────────────────────────────────
export const VERSION = JOURNAL_VERSION;
