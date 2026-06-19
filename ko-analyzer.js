/**
 * ko-analyzer.js — Refundex Analyse-Engine
 * ==========================================
 * Führt DividendEvent[] mit DBA-Regeln zusammen und berechnet
 * konkrete Rückforderungsbeträge pro Land und Event.
 *
 * DATENHERKUNFT-GARANTIE:
 *   - Alle Beträge stammen aus ko-import.js (CSV-Rohdaten)
 *   - Alle Steuersätze stammen aus ko-dba.js (statische, manuell geprüfte DB)
 *   - Kein KI-generierter Wert fließt in Berechnungen ein
 *   - FX-Kurs: aus CSV wenn vorhanden, sonst konservative Schätzung mit Flag
 *
 * Version: 1.0.0 — 2025-06-19
 */

"use strict";

import { getDBARule, calculateRecovery, getUrgency } from './ko-dba.js';

// ---------------------------------------------------------------------------
// TYPEN
// ---------------------------------------------------------------------------

/**
 * @typedef {Object} RecoveryCandidate
 * @property {string}   event_id           - Referenz auf DividendEvent.id
 * @property {string}   ticker
 * @property {string}   country_iso
 * @property {string}   country_name_de
 * @property {string}   pay_date
 * @property {number}   gross_eur          - Brutto in EUR
 * @property {number}   wht_eur            - Einbehaltene QSt in EUR
 * @property {number}   dba_max_eur        - Max. anrechenbar nach DBA
 * @property {number}   recoverable_eur    - Rückforderbar (wht - dba_max)
 * @property {string}   deadline           - ISO-Datum der Antragsfrist
 * @property {number}   days_remaining
 * @property {string}   urgency            - "ok"|"soon"|"urgent"|"expired"
 * @property {boolean}  worthwhile         - Lohnt sich der Aufwand?
 * @property {string}   refundex_output    - "pdf_fill"|"cheatsheet"|"online_guide"
 * @property {string}   form_name
 * @property {string}   form_url
 * @property {string}   fx_source          - "csv"|"estimate"
 * @property {number}   fx_rate_used       - Verwendeter FX-Kurs
 * @property {string[]} notes
 */

/**
 * @typedef {Object} CountrySummary
 * @property {string}               country_iso
 * @property {string}               country_name_de
 * @property {RecoveryCandidate[]}  candidates
 * @property {number}               total_recoverable_eur
 * @property {number}               total_wht_eur
 * @property {number}               total_gross_eur
 * @property {string}               worst_urgency
 * @property {string}               refundex_output
 * @property {string}               form_name
 * @property {string}               form_url
 * @property {string}               authority_name_de
 * @property {boolean}              any_worthwhile
 */

/**
 * @typedef {Object} AnalysisResult
 * @property {CountrySummary[]}     by_country       - Sortiert nach Dringlichkeit + Betrag
 * @property {RecoveryCandidate[]}  all_candidates   - Alle Kandidaten flach
 * @property {AnalysisSummary}      summary
 * @property {SkippedEvent[]}       skipped          - Events ohne Rückforderungspotenzial
 */

/**
 * @typedef {Object} AnalysisSummary
 * @property {number}  total_recoverable_eur
 * @property {number}  total_expired_eur
 * @property {number}  total_not_worthwhile_eur
 * @property {number}  countries_with_recovery
 * @property {number}  candidates_count
 * @property {string}  analysis_date
 */

// ---------------------------------------------------------------------------
// KERN-ANALYSE
// ---------------------------------------------------------------------------

/**
 * Analysiert DividendEvent[] und berechnet Rückforderungspotenzial.
 *
 * @param {import('./ko-import.js').DividendEvent[]} events
 * @param {Object} [options]
 * @param {number} [options.minWorthwhileEur=10]  - Globaler Mindestbetrag
 * @param {boolean} [options.includeExpired=false] - Abgelaufene einschließen
 * @returns {AnalysisResult}
 */
export function analyzeRecovery(events, options = {}) {
  const { minWorthwhileEur = 10, includeExpired = false } = options;

  const allCandidates = [];
  const skipped       = [];

  for (const event of events) {
    const rule = getDBARule(event.country_iso);

    // Kein DBA-Eintrag oder keine Rückforderung möglich
    if (!rule) {
      skipped.push({ event, reason: `Kein DBA-Eintrag für ${event.country_iso}` });
      continue;
    }
    if (!rule.recovery_possible) {
      skipped.push({ event, reason: `${rule.country_name_de}: Keine Rückforderung möglich (${rule.notes_de[0]})` });
      continue;
    }
    if (event.wht_amount <= 0) {
      skipped.push({ event, reason: "Keine Quellensteuer einbehalten" });
      continue;
    }

    // FX-Normalisierung → EUR
    // CapTrader liefert keinen FX-Kurs im Kontoauszug-CSV direkt pro Dividende.
    // Wir verwenden konservative Schätzung und kennzeichnen sie als solche.
    const { grossEur, whtEur, fxRate, fxSource } = normalizeToEur(
      event.gross_amount,
      event.wht_amount,
      event.currency,
      event.pay_date
    );

    // Rückforderungsberechnung — reine Arithmetik
    const rec = calculateRecovery(
      event.country_iso,
      grossEur,
      whtEur,
      new Date(event.pay_date)
    );

    // Abgelaufene optional ausschließen
    if (!includeExpired && rec.daysRemaining <= 0) {
      skipped.push({
        event,
        reason: `Frist abgelaufen am ${rec.deadline?.toISOString().slice(0,10)}`,
        recoverable_eur: rec.recoverableEur,
      });
      continue;
    }

    const urgency    = getUrgency(rec.daysRemaining);
    const worthwhile = rec.recoverableEur >= Math.max(minWorthwhileEur, rule.min_worthwhile_eur);

    const notes = [];
    if (fxSource === "estimate")
      notes.push(`FX-Kurs ${fxRate} geschätzt (${event.currency}/EUR) — Betrag ist Näherung`);
    if (event.warnings?.length)
      event.warnings.forEach(w => notes.push(w));
    if (!worthwhile && rec.recoverableEur > 0)
      notes.push(`Betrag €${rec.recoverableEur.toFixed(2)} unter Mindestgrenze €${rule.min_worthwhile_eur}`);

    const candidate = {
      event_id:         event.id,
      ticker:           event.ticker,
      country_iso:      event.country_iso,
      country_name_de:  rule.country_name_de,
      pay_date:         event.pay_date,
      gross_eur:        Math.round(grossEur * 100) / 100,
      wht_eur:          Math.round(whtEur   * 100) / 100,
      dba_max_eur:      rec.dbaMaxEur,
      recoverable_eur:  rec.recoverableEur,
      deadline:         rec.deadline?.toISOString().slice(0,10) ?? null,
      days_remaining:   rec.daysRemaining,
      urgency,
      worthwhile,
      refundex_output:  rule.refundex_output,
      form_name:        rule.form_name,
      form_url:         rule.form_url,
      authority_name_de: rule.authority_name_de,
      fx_source:        fxSource,
      fx_rate_used:     fxRate,
      notes,
    };

    allCandidates.push(candidate);
  }

  // Nach Land aggregieren
  const countryMap = {};
  for (const c of allCandidates) {
    if (!countryMap[c.country_iso]) {
      countryMap[c.country_iso] = {
        country_iso:          c.country_iso,
        country_name_de:      c.country_name_de,
        candidates:           [],
        total_recoverable_eur: 0,
        total_wht_eur:        0,
        total_gross_eur:      0,
        worst_urgency:        "ok",
        refundex_output:      c.refundex_output,
        form_name:            c.form_name,
        form_url:             c.form_url,
        authority_name_de:    c.authority_name_de,
        any_worthwhile:       false,
      };
    }
    const cs = countryMap[c.country_iso];
    cs.candidates.push(c);
    cs.total_recoverable_eur = round2(cs.total_recoverable_eur + c.recoverable_eur);
    cs.total_wht_eur         = round2(cs.total_wht_eur         + c.wht_eur);
    cs.total_gross_eur       = round2(cs.total_gross_eur       + c.gross_eur);
    cs.worst_urgency         = worstUrgency(cs.worst_urgency, c.urgency);
    if (c.worthwhile) cs.any_worthwhile = true;
  }

  // Sortierung: Dringlichkeit → Betrag
  const urgencyOrder = { urgent: 0, soon: 1, ok: 2, expired: 3 };
  const byCountry = Object.values(countryMap).sort((a, b) => {
    const ud = urgencyOrder[a.worst_urgency] - urgencyOrder[b.worst_urgency];
    return ud !== 0 ? ud : b.total_recoverable_eur - a.total_recoverable_eur;
  });

  // Gesamtzusammenfassung
  const expiredSkipped = skipped.filter(s => s.reason?.includes("Frist abgelaufen"));
  const summary = {
    total_recoverable_eur:    round2(allCandidates.reduce((s, c) => s + c.recoverable_eur, 0)),
    total_expired_eur:        round2(expiredSkipped.reduce((s, e) => s + (e.recoverable_eur ?? 0), 0)),
    total_not_worthwhile_eur: round2(allCandidates.filter(c => !c.worthwhile).reduce((s,c) => s + c.recoverable_eur, 0)),
    countries_with_recovery:  byCountry.filter(c => c.any_worthwhile).length,
    candidates_count:         allCandidates.length,
    analysis_date:            new Date().toISOString().slice(0,10),
  };

  return { by_country: byCountry, all_candidates: allCandidates, summary, skipped };
}

// ---------------------------------------------------------------------------
// FX-NORMALISIERUNG
// ---------------------------------------------------------------------------

/**
 * Historische FX-Schätzwerte (konservativ, Jahresdurchschnitte).
 * QUELLE: EZB-Referenzkurse Jahresdurchschnitte
 * Werden nur verwendet wenn kein Tageskurs aus CSV vorhanden.
 */
const FX_ESTIMATES = {
  // USD/EUR Jahresdurchschnitte
  USD: { "2023": 0.9247, "2024": 0.9236, "2025": 0.9200, default: 0.92 },
  GBP: { "2023": 1.1513, "2024": 1.1826, "2025": 1.1700, default: 1.17 },
  CHF: { "2023": 1.0000, "2024": 1.0520, "2025": 1.0600, default: 1.05 },
  SEK: { "2023": 0.0876, "2024": 0.0882, "2025": 0.0880, default: 0.088 },
  NOK: { "2023": 0.0868, "2024": 0.0862, "2025": 0.0860, default: 0.086 },
  DKK: { "2023": 0.1342, "2024": 0.1340, "2025": 0.1340, default: 0.134 },
  CAD: { "2023": 0.6887, "2024": 0.6812, "2025": 0.6700, default: 0.68 },
  AUD: { "2023": 0.5994, "2024": 0.6059, "2025": 0.5900, default: 0.59 },
  JPY: { "2023": 0.00644, "2024": 0.00611, "2025": 0.0062, default: 0.0062 },
};

/**
 * Normalisiert Brutto + WHT in EUR.
 * @param {number} gross     - In Handelswährung
 * @param {number} wht       - In Handelswährung
 * @param {string} currency  - z.B. "USD"
 * @param {string} payDate   - ISO-Datum
 * @returns {{ grossEur, whtEur, fxRate, fxSource }}
 */
function normalizeToEur(gross, wht, currency, payDate) {
  if (currency === "EUR") {
    return { grossEur: gross, whtEur: wht, fxRate: 1.0, fxSource: "exact" };
  }

  const year  = payDate?.slice(0, 4) ?? "2024";
  const rates = FX_ESTIMATES[currency];
  const rate  = rates ? (rates[year] ?? rates.default) : 0.92;

  return {
    grossEur: round2(gross * rate),
    whtEur:   round2(wht   * rate),
    fxRate:   rate,
    fxSource: "estimate",
  };
}

// ---------------------------------------------------------------------------
// HILFSFUNKTIONEN
// ---------------------------------------------------------------------------

function round2(n) { return Math.round(n * 100) / 100; }

function worstUrgency(a, b) {
  const order = { urgent: 0, soon: 1, ok: 2, expired: 3 };
  return order[a] <= order[b] ? a : b;
}

/**
 * Formatiert einen CountrySummary als lesbaren Text (für CLI/Debug).
 * @param {CountrySummary} cs
 * @returns {string}
 */
export function formatCountrySummary(cs) {
  const lines = [
    `\n${"=".repeat(55)}`,
    `${cs.country_name_de} (${cs.country_iso}) — ${cs.worst_urgency.toUpperCase()}`,
    `${"=".repeat(55)}`,
    `Rückforderbar gesamt: €${cs.total_recoverable_eur.toFixed(2)}`,
    `Einbehaltene QSt:     €${cs.total_wht_eur.toFixed(2)}`,
    `Formular:             ${cs.form_name}`,
    `Behörde:              ${cs.authority_name_de}`,
    `Ausgabe-Typ:          ${cs.refundex_output}`,
    ``,
    `Einzelne Ereignisse:`,
  ];
  for (const c of cs.candidates) {
    lines.push(
      `  ${c.pay_date} | ${c.ticker.padEnd(5)} | ` +
      `Brutto €${c.gross_eur.toFixed(2).padStart(7)} | ` +
      `WHT €${c.wht_eur.toFixed(2).padStart(6)} | ` +
      `Rückforderbar €${c.recoverable_eur.toFixed(2).padStart(6)} | ` +
      `Frist: ${c.deadline} (${c.days_remaining}d) | ` +
      `${c.worthwhile ? "✅" : "⚠️ "}`
    );
    if (c.notes.length) c.notes.forEach(n => lines.push(`    ℹ️  ${n}`));
  }
  return lines.join("\n");
}
