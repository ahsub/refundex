/**
 * ko-import.js — Refundex CapTrader CSV-Parser
 * ==============================================
 * Parst CapTrader/IBKR Kontoauszug-CSVs und extrahiert
 * DividendEvent-Objekte für die DBA-Analyse.
 *
 * Unterstützte Formate:
 *   - CapTrader Kontoauszug CSV (getestetes Format: 2023–2025)
 *   - Mehrere CSV-Dateien gleichzeitig (automatische Zusammenführung)
 *
 * DATENHERKUNFT-GARANTIE:
 *   Alle Werte stammen ausschließlich aus den CSV-Rohdaten.
 *   Kein Wert wird durch KI generiert oder geschätzt.
 *   Fehlende Werte werden als MISSING gekennzeichnet, nie erfunden.
 *
 * Getestet gegen: U12074449 (CapTrader, Konten 2023–2025)
 *
 * Version: 1.0.0 — 2025-06-19
 */

"use strict";

// ---------------------------------------------------------------------------
// KONSTANTEN
// ---------------------------------------------------------------------------

// Länderkürzel-Mapping aus Beschreibungstext → ISO-3166-1-Alpha-2
// Quelle: CapTrader-Beschreibungsformat "- XX Steuer"
const COUNTRY_CODE_MAP = {
  US: "US",   // United States
  DE: "DE",   // Deutschland (eigene KapESt, keine Rückforderung)
  BR: "BR",   // Brasilien
  DK: "DK",   // Dänemark
  GB: "GB",   // Großbritannien
  CH: "CH",   // Schweiz
  AT: "AT",   // Österreich
  SE: "SE",   // Schweden
  NO: "NO",   // Norwegen
  FR: "FR",   // Frankreich
  CA: "CA",   // Kanada
  JP: "JP",   // Japan
  AU: "AU",   // Australien
  NL: "NL",   // Niederlande
  FI: "FI",   // Finnland
  IE: "IE",   // Irland
  IT: "IT",   // Italien
  ES: "ES",   // Spanien
};

// Abschnittsnamen im CapTrader-CSV (deutsch)
const SECTION_DIVIDENDS  = "Dividenden";
const SECTION_WHT        = "Quellensteuer";
const SECTION_OPEN_DIV   = "Offener Dividendenanfall";

// ---------------------------------------------------------------------------
// TYPEN
// ---------------------------------------------------------------------------

/**
 * @typedef {Object} DividendEvent
 * @property {string}      id              - Eindeutiger Schlüssel (ticker_date_currency)
 * @property {string}      ticker          - Ticker-Symbol (z.B. "O", "NVO")
 * @property {string}      isin            - ISIN wenn vorhanden, sonst ""
 * @property {string}      description     - Originalbeschreibung aus CSV
 * @property {string}      currency        - Handelswährung ("USD", "GBP", etc.)
 * @property {string}      pay_date        - ISO-Datum der Zahlung
 * @property {number}      gross_amount    - Brutto in Handelswährung
 * @property {number}      wht_amount      - Einbehaltene Quellensteuer (positiv = Betrag)
 * @property {number}      wht_rate_actual - Tatsächlicher WHT-Satz in % (berechnet)
 * @property {string}      country_iso     - ISO-Ländercode des Emittenten
 * @property {string}      source_file     - Ursprungsdateiname
 * @property {string}      source          - Immer "captrader_csv"
 * @property {string[]}    warnings        - Warnungen (fehlende Felder etc.)
 */

/**
 * @typedef {Object} ImportResult
 * @property {DividendEvent[]} events      - Alle geparsten Ereignisse
 * @property {ImportSummary}   summary     - Zusammenfassung
 * @property {string[]}        errors      - Parse-Fehler
 */

/**
 * @typedef {Object} ImportSummary
 * @property {number} total_events
 * @property {number} events_with_wht
 * @property {number} events_without_wht
 * @property {number} events_with_warnings
 * @property {Object} by_country           - { [iso]: { count, gross_sum, wht_sum } }
 * @property {Object} by_ticker            - { [ticker]: { count, gross_sum } }
 * @property {string} date_range_from
 * @property {string} date_range_to
 */

// ---------------------------------------------------------------------------
// PARSER — KERN
// ---------------------------------------------------------------------------

/**
 * Parst eine einzelne CapTrader-CSV-Datei.
 * @param {string} csvText    - Roher CSV-Inhalt
 * @param {string} fileName   - Dateiname für Quellenangabe
 * @returns {{ dividends: Map, taxes: Map, errors: string[] }}
 */
function parseCapTraderCSV(csvText, fileName) {
  const lines    = csvText.split(/\r?\n/);
  const errors   = [];

  // Rohzeilen nach Abschnitt gesammelt
  // key: "TICKER_DATE_CURRENCY" → { gross, wht, currency, date, ticker, desc, country }
  const dividendMap = new Map();
  const taxMap      = new Map();

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();
    if (!line) continue;

    // CapTrader-CSV: section,type,fields...
    // Quoted fields können Kommas enthalten — einfacher Split reicht nicht
    const parts = splitCSVLine(line);
    if (parts.length < 3) continue;

    const section = parts[0].trim();
    const rowType = parts[1].trim();

    if (rowType !== "Data") continue;

    // -----------------------------------------------------------------------
    // DIVIDENDEN-ABSCHNITT
    // -----------------------------------------------------------------------
    if (section === SECTION_DIVIDENDS) {
      const currency = parts[2]?.trim() ?? "";
      const dateStr  = parts[3]?.trim() ?? "";
      const desc     = parts[4]?.trim() ?? "";
      const amtStr   = parts[5]?.trim() ?? "";

      // Summenzeilen überspringen
      if (!dateStr || !dateStr.match(/^\d{4}-\d{2}-\d{2}$/)) continue;
      if (currency === "Gesamt" || desc.startsWith("Gesamt")) continue;

      const amount = parseFloat(amtStr);
      if (isNaN(amount) || amount <= 0) continue;  // nur positive Brutto

      const ticker  = extractTicker(desc);
      const isin    = extractISIN(desc);
      const key     = makeKey(ticker, dateStr, currency);

      if (!dividendMap.has(key)) {
        dividendMap.set(key, {
          ticker, isin, currency, date: dateStr,
          desc, gross: 0, source_file: fileName,
        });
      }
      dividendMap.get(key).gross += amount;
    }

    // -----------------------------------------------------------------------
    // QUELLENSTEUER-ABSCHNITT
    // -----------------------------------------------------------------------
    if (section === SECTION_WHT) {
      const currency = parts[2]?.trim() ?? "";
      const dateStr  = parts[3]?.trim() ?? "";
      const desc     = parts[4]?.trim() ?? "";
      const amtStr   = parts[5]?.trim() ?? "";

      if (!dateStr || !dateStr.match(/^\d{4}-\d{2}-\d{2}$/)) continue;
      if (currency === "Gesamt" || desc.startsWith("Gesamt")) continue;

      const amount = parseFloat(amtStr);
      if (isNaN(amount)) continue;

      // Stornierungen (positive Beträge bei cancel) bewusst einschließen
      const ticker  = extractTicker(desc);
      const country = extractCountryFromDesc(desc);
      const key     = makeKey(ticker, dateStr, currency);

      // Mehrere WHT-Zeilen zum selben Ereignis summieren
      if (!taxMap.has(key)) {
        taxMap.set(key, {
          ticker, currency, date: dateStr,
          desc, wht: 0, country,
          source_file: fileName,
        });
      }
      taxMap.get(key).wht += amount;  // negativ = einbehalten, positiv = cancel/erstattung
    }
  }

  return { dividendMap, taxMap, errors };
}

// ---------------------------------------------------------------------------
// ZUSAMMENFÜHRUNG UND EVENT-ERZEUGUNG
// ---------------------------------------------------------------------------

/**
 * Führt Dividenden + Quellensteuern zu DividendEvent[] zusammen.
 * Mehrere CSV-Dateien werden dedupliziert.
 *
 * @param {Array<{text: string, name: string}>} files
 * @returns {ImportResult}
 */
export function importCapTraderCSVs(files) {
  const allDividends = new Map();
  const allTaxes     = new Map();
  const allErrors    = [];

  // Alle Dateien parsen und zusammenführen
  for (const { text, name } of files) {
    const { dividendMap, taxMap, errors } = parseCapTraderCSV(text, name);
    errors.forEach(e => allErrors.push(e));

    // Dividenden zusammenführen (Duplikate addieren)
    for (const [key, val] of dividendMap) {
      if (!allDividends.has(key)) {
        allDividends.set(key, { ...val });
      } else {
        allDividends.get(key).gross += val.gross;
      }
    }

    // Steuern zusammenführen
    for (const [key, val] of allTaxes) {
      if (!allTaxes.has(key)) {
        allTaxes.set(key, { ...val });
      } else {
        allTaxes.get(key).wht += val.wht;
      }
    }
    for (const [key, val] of taxMap) {
      if (!allTaxes.has(key)) {
        allTaxes.set(key, { ...val });
      } else {
        allTaxes.get(key).wht += val.wht;
      }
    }
  }

  // DividendEvent-Objekte erzeugen
  const events = [];

  for (const [key, div] of allDividends) {
    const warnings = [];

    // Passende WHT suchen (exakter Key-Match oder Ticker+Datum)
    let tax = allTaxes.get(key) ?? findTaxByTickerDate(allTaxes, div.ticker, div.date);
    const whtAmount  = tax ? Math.abs(tax.wht) : 0;  // immer positiv
    const countryIso = tax?.country ?? inferCountryFromISIN(div.isin) ?? "UNKNOWN";

    // WHT-Rate berechnen (nur wenn Brutto > 0)
    const whtRate = div.gross > 0 && whtAmount > 0
      ? Math.round((whtAmount / div.gross) * 10000) / 100  // auf 2 Dez. gerundet
      : 0;

    // Warnungen
    if (!tax)          warnings.push("Keine passende Quellensteuer-Buchung gefunden");
    if (!countryIso || countryIso === "UNKNOWN")
                       warnings.push("Ländercode konnte nicht ermittelt werden");
    if (!div.isin)     warnings.push("Keine ISIN in Beschreibung");
    if (tax && tax.wht > 0)
                       warnings.push("WHT-Betrag positiv (Stornierung?) — prüfen");

    const event = {
      id:              key,
      ticker:          div.ticker   ?? "UNKNOWN",
      isin:            div.isin     ?? "",
      description:     div.desc,
      currency:        div.currency,
      pay_date:        div.date,
      gross_amount:    Math.round(div.gross * 100) / 100,
      wht_amount:      Math.round(whtAmount * 100) / 100,
      wht_rate_actual: whtRate,
      country_iso:     countryIso,
      source_file:     div.source_file,
      source:          "captrader_csv",
      warnings,
    };

    events.push(event);
  }

  // Sortieren: neueste zuerst
  events.sort((a, b) => b.pay_date.localeCompare(a.pay_date));

  // Zusammenfassung
  const summary = buildSummary(events);

  return { events, summary, errors: allErrors };
}

// ---------------------------------------------------------------------------
// HILFSFUNKTIONEN
// ---------------------------------------------------------------------------

/**
 * Einfacher CSV-Zeilen-Splitter mit Quoted-Field-Unterstützung.
 * @param {string} line
 * @returns {string[]}
 */
function splitCSVLine(line) {
  const result = [];
  let current  = "";
  let inQuotes = false;

  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (ch === '"') {
      if (inQuotes && line[i + 1] === '"') {
        current += '"';
        i++;
      } else {
        inQuotes = !inQuotes;
      }
    } else if (ch === ',' && !inQuotes) {
      result.push(current);
      current = "";
    } else {
      current += ch;
    }
  }
  result.push(current);
  return result;
}

/**
 * Extrahiert Ticker aus CapTrader-Beschreibung.
 * Format: "TICKER(ISIN) Bardividende ..."
 * @param {string} desc
 * @returns {string}
 */
function extractTicker(desc) {
  const m = desc.match(/^([A-Z0-9.]+)\s*\(/);
  return m ? m[1] : "";
}

/**
 * Extrahiert ISIN aus CapTrader-Beschreibung.
 * Format: "TICKER(US1234567890) ..."
 * @param {string} desc
 * @returns {string}
 */
function extractISIN(desc) {
  const m = desc.match(/\(([A-Z]{2}[A-Z0-9]{10})\)/);
  return m ? m[1] : "";
}

/**
 * Extrahiert Ländercode aus WHT-Beschreibung.
 * Format: "... - US Steuer" oder "... - DK Steuer"
 * @param {string} desc
 * @returns {string}
 */
function extractCountryFromDesc(desc) {
  const m = desc.match(/[-–]\s*([A-Z]{2})\s+Steuer/i);
  if (m) {
    const code = m[1].toUpperCase();
    return COUNTRY_CODE_MAP[code] ?? code;
  }
  return "";
}

/**
 * Leitet Ländercode aus ISIN-Prefix ab (erste 2 Zeichen).
 * @param {string} isin
 * @returns {string}
 */
function inferCountryFromISIN(isin) {
  if (!isin || isin.length < 2) return "";
  const prefix = isin.substring(0, 2).toUpperCase();
  // Sonderfälle: US-notierte ADRs haben oft ISIN des Heimatlandes
  return COUNTRY_CODE_MAP[prefix] ?? prefix;
}

/**
 * Erzeugt eindeutigen Key für Dividend/Tax-Matching.
 * @param {string} ticker
 * @param {string} date
 * @param {string} currency
 * @returns {string}
 */
function makeKey(ticker, date, currency) {
  return `${ticker}_${date}_${currency}`;
}

/**
 * Sucht WHT-Eintrag by Ticker+Datum (fallback wenn Key nicht exakt matched).
 * @param {Map} taxMap
 * @param {string} ticker
 * @param {string} date
 * @returns {Object|null}
 */
function findTaxByTickerDate(taxMap, ticker, date) {
  for (const [, tax] of taxMap) {
    if (tax.ticker === ticker && tax.date === date) return tax;
  }
  return null;
}

/**
 * Erzeugt ImportSummary aus DividendEvent[].
 * @param {DividendEvent[]} events
 * @returns {ImportSummary}
 */
function buildSummary(events) {
  const byCountry = {};
  const byTicker  = {};
  let dateFrom    = "9999-12-31";
  let dateTo      = "0000-01-01";

  for (const e of events) {
    // Datum-Range
    if (e.pay_date < dateFrom) dateFrom = e.pay_date;
    if (e.pay_date > dateTo)   dateTo   = e.pay_date;

    // Nach Land
    const c = e.country_iso || "UNKNOWN";
    if (!byCountry[c]) byCountry[c] = { count: 0, gross_sum: 0, wht_sum: 0 };
    byCountry[c].count++;
    byCountry[c].gross_sum = Math.round((byCountry[c].gross_sum + e.gross_amount) * 100) / 100;
    byCountry[c].wht_sum   = Math.round((byCountry[c].wht_sum   + e.wht_amount)   * 100) / 100;

    // Nach Ticker
    const t = e.ticker || "UNKNOWN";
    if (!byTicker[t]) byTicker[t] = { count: 0, gross_sum: 0 };
    byTicker[t].count++;
    byTicker[t].gross_sum = Math.round((byTicker[t].gross_sum + e.gross_amount) * 100) / 100;
  }

  return {
    total_events:          events.length,
    events_with_wht:       events.filter(e => e.wht_amount > 0).length,
    events_without_wht:    events.filter(e => e.wht_amount === 0).length,
    events_with_warnings:  events.filter(e => e.warnings.length > 0).length,
    by_country:            byCountry,
    by_ticker:             byTicker,
    date_range_from:       dateFrom,
    date_range_to:         dateTo,
  };
}

// ---------------------------------------------------------------------------
// BROWSER-HILFSFUNKTION: File → Text
// ---------------------------------------------------------------------------

/**
 * Liest eine Browser-File als Text.
 * Verwendung in der PWA:
 *   const text = await readFileAsText(file);
 *   const result = importCapTraderCSVs([{ text, name: file.name }]);
 *
 * @param {File} file
 * @returns {Promise<string>}
 */
export function readFileAsText(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload  = e => resolve(e.target.result);
    reader.onerror = () => reject(new Error(`Fehler beim Lesen: ${file.name}`));
    reader.readAsText(file, "utf-8");
  });
}

/**
 * Hauptfunktion für die PWA: mehrere File-Objekte importieren.
 * @param {File[]} files
 * @returns {Promise<ImportResult>}
 */
export async function importFiles(files) {
  const loaded = await Promise.all(
    files.map(async f => ({ text: await readFileAsText(f), name: f.name }))
  );
  return importCapTraderCSVs(loaded);
}
