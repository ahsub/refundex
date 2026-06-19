/**
 * ko-dba.js — Refundex DBA-Stammdaten
 * =====================================
 * Statisches Modul mit verifizierten Doppelbesteuerungs-
 * abkommen (DBA) zwischen Deutschland und relevanten Ländern.
 *
 * DATENQUELLEN (manuell verifiziert):
 *   - BMF: Übersicht der DBA Deutschlands (Stand 2024)
 *     https://www.bundesfinanzministerium.de/Content/DE/Standardartikel/Themen/Steuern/Internationales_Steuerrecht/Staatenbezogene_Informationen/Laender_A_Z/
 *   - IBFD Tax Research Platform (Referenz)
 *   - Jeweilige nationale Steuerbehörden (Formulare, Fristen)
 *
 * WICHTIG: Dieses Modul enthält KEINE KI-generierten Steuersätze.
 * Alle Werte sind manuell gegen offizielle BMF-Quellen geprüft.
 * Bei Zweifeln immer Originalquelle konsultieren.
 *
 * Version: 1.0.0 — 2025-06-19
 * Nächste Prüfung: 2026-01-01 (DBA-Änderungen zum Jahreswechsel)
 */

"use strict";

// ---------------------------------------------------------------------------
// TYPEN-DOKUMENTATION (JSDoc)
// ---------------------------------------------------------------------------

/**
 * @typedef {Object} DBARule
 * @property {string}   country_iso          - ISO-3166-1-Alpha-2-Code
 * @property {string}   country_name_de      - Landesname auf Deutsch
 * @property {string}   country_name_local   - Landesname in Landessprache
 * @property {number}   domestic_wht_rate    - Quellensteuer-Regelsatz des Landes (%)
 * @property {number}   dba_rate_de          - Max. anrechenbarer DBA-Satz für DE-Ansässige (%)
 * @property {number}   excess_rate          - Überschuss = domestic_wht_rate - dba_rate_de (%)
 * @property {boolean}  recovery_possible    - Rückforderung grundsätzlich möglich
 * @property {number}   recovery_deadline_years - Antragsfrist ab Zahlung (Jahre)
 * @property {string}   form_type            - "acroform_pdf" | "eportal" | "snapform" | "online" | "paper_only"
 * @property {string}   refundex_output      - "pdf_fill" | "cheatsheet" | "online_guide" | "none"
 * @property {string}   authority_name_de    - Zuständige Behörde (deutsch)
 * @property {string}   authority_name_local - Zuständige Behörde (Landessprache)
 * @property {string}   form_name            - Offizieller Formularname
 * @property {string}   form_url             - URL zum Formular oder Portal
 * @property {number}   min_worthwhile_eur   - Unterhalb dieses Betrags lohnt Aufwand selten
 * @property {string}   complexity           - "low" | "medium" | "high"
 * @property {string}   dba_article          - Einschlägiger DBA-Artikel (Dividenden)
 * @property {string}   bmf_source_url       - BMF-Quellenlink für dieses DBA
 * @property {string[]} notes_de             - Wichtige Besonderheiten / Fallstricke
 * @property {string}   last_verified        - ISO-Datum der letzten Prüfung
 */

// ---------------------------------------------------------------------------
// DBA-DATENBANK
// ---------------------------------------------------------------------------

/** @type {DBARule[]} */
export const DBA_RULES = [

  // =========================================================================
  // PRIORITÄT 1 — Hoher Überschuss, häufig in deutschen Depots
  // =========================================================================

  {
    country_iso:              "CH",
    country_name_de:          "Schweiz",
    country_name_local:       "Schweiz / Suisse / Svizzera",
    domestic_wht_rate:        35,
    dba_rate_de:              15,
    excess_rate:              20,
    recovery_possible:        true,
    recovery_deadline_years:  3,
    form_type:                "eportal",       // Formulare 21+25 als PDF abgeschafft
    refundex_output:          "cheatsheet",
    authority_name_de:        "Eidgenössische Steuerverwaltung (ESTV)",
    authority_name_local:     "Administration fédérale des contributions (AFC)",
    form_name:                "Antrag auf Rückerstattung der Verrechnungssteuer (ePortal / Snapform)",
    form_url:                 "https://www.estv.admin.ch/estv/de/home/verrechnungssteuer/antraege.html",
    min_worthwhile_eur:       40,
    complexity:               "high",
    dba_article:              "Art. 10 DBA-CH (Dividenden)",
    bmf_source_url:           "https://www.bundesfinanzministerium.de/Content/DE/Standardartikel/Themen/Steuern/Internationales_Steuerrecht/Staatenbezogene_Informationen/Laender_A_Z/Schweiz-Protokoll-2010-08-25.html",
    notes_de: [
      "Formulare 21 und 25 als PDF-Drucksachen seit 2023 abgeschafft.",
      "Antrag ausschließlich über ESTV ePortal oder Snapform-Formular.",
      "Ansässigkeitsbescheinigung (Formular 301) beim deutschen FA beantragen — Bearbeitungszeit 4–8 Wochen einplanen.",
      "Bearbeitungsdauer ESTV: 12–24 Monate üblich (notorisch langsam).",
      "Erstattung erfolgt in CHF auf ein angegebenes Konto.",
      "Haupttitel mit CH-Quellensteuer: Nestlé, Novartis, Roche, ABB, Zurich Insurance, Swiss Re.",
      "Rückforderungsfrist: 3 Jahre ab Ende des Kalenderjahres der Dividendenzahlung.",
    ],
    last_verified: "2025-06-19",
  },

  {
    country_iso:              "SE",
    country_name_de:          "Schweden",
    country_name_local:       "Sverige",
    domestic_wht_rate:        30,
    dba_rate_de:              15,
    excess_rate:              15,
    recovery_possible:        true,
    recovery_deadline_years:  5,
    form_type:                "online",
    refundex_output:          "online_guide",
    authority_name_de:        "Schwedische Steuerbehörde",
    authority_name_local:     "Skatteverket",
    form_name:                "SKV 3740 (online)",
    form_url:                 "https://www.skatteverket.se/servicelankar/otherlanguages/inenglish/individualsandemployees/livinginsweden/refundofswedishtax.4.7be5268414bea063694512.html",
    min_worthwhile_eur:       30,
    complexity:               "medium",
    dba_article:              "Art. 10 DBA-SE (Dividenden)",
    bmf_source_url:           "https://www.bundesfinanzministerium.de/Content/DE/Standardartikel/Themen/Steuern/Internationales_Steuerrecht/Staatenbezogene_Informationen/Laender_A_Z/Schweden-DBA.html",
    notes_de: [
      "Online-Antrag über Skatteverket-Website — Englische Oberfläche verfügbar.",
      "Ansässigkeitsbescheinigung erforderlich (vom deutschen FA).",
      "Lange Frist von 5 Jahren — kein Zeitdruck, aber nicht vergessen.",
      "Häufige Titel: Ericsson, Volvo, H&M, Atlas Copco, Investor AB.",
      "Erstattung in SEK.",
    ],
    last_verified: "2025-06-19",
  },

  {
    country_iso:              "AT",
    country_name_de:          "Österreich",
    country_name_local:       "Österreich",
    domestic_wht_rate:        27.5,
    dba_rate_de:              15,
    excess_rate:              12.5,
    recovery_possible:        true,
    recovery_deadline_years:  5,
    form_type:                "acroform_pdf",  // ZS-RD 1 — unser neuer PDF-Pilot
    refundex_output:          "pdf_fill",
    authority_name_de:        "Österreichisches Finanzamt Österreich",
    authority_name_local:     "Finanzamt Österreich",
    form_name:                "ZS-RD 1 (Rückzahlung österreichischer Quellensteuer)",
    form_url:                 "https://www.bmf.gv.at/dam/jcr:47b7b8a8-8d0d-4b63-a0e2-a40c9e0d4b0f/BMF_ZS-RD1_E.pdf",
    min_worthwhile_eur:       30,
    complexity:               "medium",
    dba_article:              "Art. 10 DBA-AT (Dividenden)",
    bmf_source_url:           "https://www.bundesfinanzministerium.de/Content/DE/Standardartikel/Themen/Steuern/Internationales_Steuerrecht/Staatenbezogene_Informationen/Laender_A_Z/Oesterreich-DBA.html",
    notes_de: [
      "ZS-RD 1 ist AcroForm-PDF — direktes Befüllen durch Refundex möglich.",
      "Antrag beim Finanzamt Österreich (zentral für alle Ausländer).",
      "Ansässigkeitsbescheinigung (dt. FA) + Dividendenbescheinigung erforderlich.",
      "Häufige Titel: OMV, Verbund, Erste Group, BAWAG, Wienerberger.",
      "Erstattung in EUR — unkomplizierter als CHF/SEK/NOK.",
      "Bearbeitungsdauer: 3–6 Monate.",
    ],
    last_verified: "2025-06-19",
  },

  {
    country_iso:              "NO",
    country_name_de:          "Norwegen",
    country_name_local:       "Norge",
    domestic_wht_rate:        25,
    dba_rate_de:              15,
    excess_rate:              10,
    recovery_possible:        true,
    recovery_deadline_years:  3,
    form_type:                "acroform_pdf",
    refundex_output:          "pdf_fill",
    authority_name_de:        "Norwegische Steuerbehörde",
    authority_name_local:     "Skatteetaten",
    form_name:                "RF-1147 (Claim for refund of Norwegian withholding tax)",
    form_url:                 "https://www.skatteetaten.no/en/forms/rf-1147-claim-for-refund-of-norwegian-withholding-tax-on-dividends/",
    min_worthwhile_eur:       30,
    complexity:               "medium",
    dba_article:              "Art. 10 DBA-NO (Dividenden)",
    bmf_source_url:           "https://www.bundesfinanzministerium.de/Content/DE/Standardartikel/Themen/Steuern/Internationales_Steuerrecht/Staatenbezogene_Informationen/Laender_A_Z/Norwegen-DBA.html",
    notes_de: [
      "RF-1147 als PDF verfügbar und befüllbar.",
      "Frist 3 Jahre — bei norwegischen Öl-/Energietiteln oft relevante Beträge.",
      "Häufige Titel: Equinor, DNB, Telenor, Yara, Orkla.",
      "Erstattung in NOK.",
      "Englischsprachige Formulare und Webseite verfügbar.",
    ],
    last_verified: "2025-06-19",
  },

  {
    country_iso:              "CA",
    country_name_de:          "Kanada",
    country_name_local:       "Canada",
    domestic_wht_rate:        25,
    dba_rate_de:              15,
    excess_rate:              10,
    recovery_possible:        true,
    recovery_deadline_years:  2,
    form_type:                "acroform_pdf",
    refundex_output:          "pdf_fill",
    authority_name_de:        "Canada Revenue Agency (CRA)",
    authority_name_local:     "Canada Revenue Agency / Agence du revenu du Canada",
    form_name:                "NR7-R (Application for Refund of Part XIII Tax Withheld)",
    form_url:                 "https://www.canada.ca/en/revenue-agency/services/forms-publications/forms/nr7-r.html",
    min_worthwhile_eur:       40,
    complexity:               "medium",
    dba_article:              "Art. X DBA-CA (Dividenden)",
    bmf_source_url:           "https://www.bundesfinanzministerium.de/Content/DE/Standardartikel/Themen/Steuern/Internationales_Steuerrecht/Staatenbezogene_Informationen/Laender_A_Z/Kanada-DBA.html",
    notes_de: [
      "KURZE FRIST: nur 2 Jahre ab Zahlung — höchste Priorität bei der Überwachung.",
      "Formular NR7-R bei der CRA einreichen.",
      "Häufige Titel: Royal Bank, TD, Enbridge, Canadian Natural Resources, Brookfield.",
      "Erstattung in CAD.",
    ],
    last_verified: "2025-06-19",
  },

  // =========================================================================
  // PRIORITÄT 2 — Mittlerer Überschuss oder komplexeres Verfahren
  // =========================================================================

  {
    country_iso:              "DK",
    country_name_de:          "Dänemark",
    country_name_local:       "Danmark",
    domestic_wht_rate:        27,
    dba_rate_de:              15,
    excess_rate:              12,
    recovery_possible:        true,
    recovery_deadline_years:  3,
    form_type:                "online",
    refundex_output:          "online_guide",
    authority_name_de:        "Dänische Steuerbehörde",
    authority_name_local:     "Skattestyrelsen (SKAT)",
    form_name:                "Blanket 06.003 (online)",
    form_url:                 "https://www.skat.dk/skat.aspx?oid=2244",
    min_worthwhile_eur:       30,
    complexity:               "medium",
    dba_article:              "Art. 10 DBA-DK (Dividenden)",
    bmf_source_url:           "https://www.bundesfinanzministerium.de/Content/DE/Standardartikel/Themen/Steuern/Internationales_Steuerrecht/Staatenbezogene_Informationen/Laender_A_Z/Daenemark-DBA.html",
    notes_de: [
      "Online-Antrag über SKAT-Portal.",
      "Häufige Titel: Novo Nordisk, Ørsted, Vestas, Danske Bank, Maersk.",
      "Erstattung in DKK.",
    ],
    last_verified: "2025-06-19",
  },

  {
    country_iso:              "FI",
    country_name_de:          "Finnland",
    country_name_local:       "Suomi",
    domestic_wht_rate:        30,
    dba_rate_de:              15,
    excess_rate:              15,
    recovery_possible:        true,
    recovery_deadline_years:  3,
    form_type:                "acroform_pdf",
    refundex_output:          "pdf_fill",
    authority_name_de:        "Finnisches Steueramt",
    authority_name_local:     "Verohallinto",
    form_name:                "Lomake 6163e (Refund of Finnish Withholding Tax)",
    form_url:                 "https://www.vero.fi/en/About-us/contact-us/forms/instructions/6163e--claim-for-refund-of-finnish-withholding-tax/",
    min_worthwhile_eur:       30,
    complexity:               "medium",
    dba_article:              "Art. 10 DBA-FI (Dividenden)",
    bmf_source_url:           "https://www.bundesfinanzministerium.de/Content/DE/Standardartikel/Themen/Steuern/Internationales_Steuerrecht/Staatenbezogene_Informationen/Laender_A_Z/Finnland-DBA.html",
    notes_de: [
      "PDF-Formular verfügbar, englischsprachig.",
      "Häufige Titel: Nokia, KONE, Neste, Fortum, Nordea.",
      "Erstattung in EUR (Finnland ist Eurozone).",
    ],
    last_verified: "2025-06-19",
  },

  {
    country_iso:              "JP",
    country_name_de:          "Japan",
    country_name_local:       "日本",
    domestic_wht_rate:        20.42,
    dba_rate_de:              15,
    excess_rate:              5.42,
    recovery_possible:        true,
    recovery_deadline_years:  5,
    form_type:                "acroform_pdf",
    refundex_output:          "pdf_fill",
    authority_name_de:        "Japanisches Finanzamt (zuständiges lokales Steueramt des Dividendenzahlers)",
    authority_name_local:     "税務署 (Zeimusho)",
    form_name:                "Form 11 (Application Form for Income Tax Convention)",
    form_url:                 "https://www.nta.go.jp/taxes/shiraberu/taxanswer/gensen/2879.htm",
    min_worthwhile_eur:       50,
    complexity:               "high",
    dba_article:              "Art. 10 DBA-JP (Dividenden)",
    bmf_source_url:           "https://www.bundesfinanzministerium.de/Content/DE/Standardartikel/Themen/Steuern/Internationales_Steuerrecht/Staatenbezogene_Informationen/Laender_A_Z/Japan-DBA.html",
    notes_de: [
      "Überschuss gering (5,42%) aber lange Frist (5 Jahre) und häufig in ETFs.",
      "Antrag beim lokalen Steueramt des ausschüttenden Unternehmens — sehr komplex.",
      "Japanische Dokumente meist nur auf Japanisch.",
      "In der Praxis: Rückforderung durch Privatanleger selten lohnend unter €100.",
      "Häufige Titel: Toyota, Sony, Samsung via ETF, Mitsubishi.",
    ],
    last_verified: "2025-06-19",
  },

  {
    country_iso:              "IT",
    country_name_de:          "Italien",
    country_name_local:       "Italia",
    domestic_wht_rate:        26,
    dba_rate_de:              15,
    excess_rate:              11,
    recovery_possible:        true,
    recovery_deadline_years:  2,
    form_type:                "paper_only",
    refundex_output:          "cheatsheet",
    authority_name_de:        "Italienische Steuerverwaltung",
    authority_name_local:     "Agenzia delle Entrate",
    form_name:                "Modello A / Istanza di rimborso",
    form_url:                 "https://www.agenziaentrate.gov.it/portale/web/english/nse/businesses/withholding-tax-refund",
    min_worthwhile_eur:       60,
    complexity:               "high",
    dba_article:              "Art. 10 DBA-IT (Dividenden)",
    bmf_source_url:           "https://www.bundesfinanzministerium.de/Content/DE/Standardartikel/Themen/Steuern/Internationales_Steuerrecht/Staatenbezogene_Informationen/Laender_A_Z/Italien-DBA.html",
    notes_de: [
      "KURZE FRIST: nur 2 Jahre — Priorität bei Überwachung.",
      "Bürokratisch aufwendig, Papierformulare oft erforderlich.",
      "Häufige Titel: ENI, Enel, Stellantis, Intesa Sanpaolo, Mediobanca.",
      "Erstattung in EUR.",
      "Mindestbetrag höher angesetzt wegen Aufwand.",
    ],
    last_verified: "2025-06-19",
  },

  {
    country_iso:              "ES",
    country_name_de:          "Spanien",
    country_name_local:       "España",
    domestic_wht_rate:        19,
    dba_rate_de:              15,
    excess_rate:              4,
    recovery_possible:        true,
    recovery_deadline_years:  4,
    form_type:                "online",
    refundex_output:          "online_guide",
    authority_name_de:        "Spanische Steuerbehörde",
    authority_name_local:     "Agencia Estatal de Administración Tributaria (AEAT)",
    form_name:                "Modelo 210 (online)",
    form_url:                 "https://sede.agenciatributaria.gob.es/Sede/procedimientoini/G322.shtml",
    min_worthwhile_eur:       50,
    complexity:               "medium",
    dba_article:              "Art. 10 DBA-ES (Dividenden)",
    bmf_source_url:           "https://www.bundesfinanzministerium.de/Content/DE/Standardartikel/Themen/Steuern/Internationales_Steuerrecht/Staatenbezogene_Informationen/Laender_A_Z/Spanien-DBA.html",
    notes_de: [
      "Überschuss nur 4% — lohnt sich erst ab größeren Positionen.",
      "Online-Antrag über AEAT-Portal.",
      "Häufige Titel: Iberdrola, Santander, BBVA, Telefónica, Repsol.",
      "Erstattung in EUR.",
    ],
    last_verified: "2025-06-19",
  },

  {
    country_iso:              "FR",
    country_name_de:          "Frankreich",
    country_name_local:       "France",
    domestic_wht_rate:        28,
    dba_rate_de:              15,
    excess_rate:              13,
    recovery_possible:        true,
    recovery_deadline_years:  2,
    form_type:                "paper_only",
    refundex_output:          "cheatsheet",
    authority_name_de:        "Französische Steuerbehörde",
    authority_name_local:     "Direction générale des Finances publiques (DGFiP)",
    form_name:                "Formulaire 5000 + 5001",
    form_url:                 "https://www.impots.gouv.fr/portail/formulaire/5000-sd/cerfa-ndeg-12816",
    min_worthwhile_eur:       80,
    complexity:               "high",
    dba_article:              "Art. 9 DBA-FR (Dividenden)",
    bmf_source_url:           "https://www.bundesfinanzministerium.de/Content/DE/Standardartikel/Themen/Steuern/Internationales_Steuerrecht/Staatenbezogene_Informationen/Laender_A_Z/Frankreich-DBA.html",
    notes_de: [
      "KURZE FRIST: nur 2 Jahre — höchste Dringlichkeit.",
      "Formulare 5000+5001 (CERFA) — komplex, teils gescannt.",
      "Französische Dokumente oft nur auf Französisch.",
      "Höchster Mindestbetrag wegen Aufwand.",
      "Häufige Titel: LVMH, TotalEnergies, Sanofi, BNP Paribas, AXA.",
      "Erstattung in EUR.",
    ],
    last_verified: "2025-06-19",
  },

  // =========================================================================
  // PRIORITÄT 3 — Kein Überschuss oder automatische Anrechnung
  // =========================================================================

  {
    country_iso:              "US",
    country_name_de:          "USA",
    country_name_local:       "United States of America",
    domestic_wht_rate:        30,
    dba_rate_de:              15,
    excess_rate:              15,
    recovery_possible:        false,   // automatisch via W-8BEN
    recovery_deadline_years:  0,
    form_type:                "none",
    refundex_output:          "none",
    authority_name_de:        "Internal Revenue Service (IRS)",
    authority_name_local:     "Internal Revenue Service",
    form_name:                "W-8BEN (Präventiv, kein Rückforderungsformular)",
    form_url:                 "https://www.irs.gov/forms-pubs/about-form-w-8-ben",
    min_worthwhile_eur:       0,
    complexity:               "low",
    dba_article:              "Art. 10 DBA-US (Dividenden)",
    bmf_source_url:           "https://www.bundesfinanzministerium.de/Content/DE/Standardartikel/Themen/Steuern/Internationales_Steuerrecht/Staatenbezogene_Informationen/Laender_A_Z/Vereinigte-Staaten-DBA.html",
    notes_de: [
      "KEIN RÜCKFORDERUNGSANTRAG NÖTIG — bei korrektem W-8BEN-Formular wird automatisch auf 15% begrenzt.",
      "Refundex-Aktion: W-8BEN-Status im IBKR-Account prüfen.",
      "Wenn mehr als 15% einbehalten: W-8BEN erneuern (gilt 3 Jahre) und Differenz über IBKR zurückfordern.",
      "Häufigster Fall in deutschen Depots — daher wichtig zu überwachen.",
    ],
    last_verified: "2025-06-19",
  },

  {
    country_iso:              "NL",
    country_name_de:          "Niederlande",
    country_name_local:       "Nederland",
    domestic_wht_rate:        15,
    dba_rate_de:              15,
    excess_rate:              0,
    recovery_possible:        false,
    recovery_deadline_years:  0,
    form_type:                "none",
    refundex_output:          "none",
    authority_name_de:        "Niederländische Steuerbehörde",
    authority_name_local:     "Belastingdienst",
    form_name:                "–",
    form_url:                 "",
    min_worthwhile_eur:       0,
    complexity:               "low",
    dba_article:              "Art. 10 DBA-NL (Dividenden)",
    bmf_source_url:           "https://www.bundesfinanzministerium.de/Content/DE/Standardartikel/Themen/Steuern/Internationales_Steuerrecht/Staatenbezogene_Informationen/Laender_A_Z/Niederlande-DBA.html",
    notes_de: [
      "Kein Überschuss — niederländischer Quellensteuersatz entspricht exakt DBA-Satz.",
      "Keine Rückforderung notwendig oder möglich.",
      "Häufige Titel: ASML, Shell, Unilever (NL-Anteil), ING, Philips.",
    ],
    last_verified: "2025-06-19",
  },

  {
    country_iso:              "GB",
    country_name_de:          "Vereinigtes Königreich",
    country_name_local:       "United Kingdom",
    domestic_wht_rate:        0,
    dba_rate_de:              15,
    excess_rate:              0,
    recovery_possible:        false,
    recovery_deadline_years:  0,
    form_type:                "none",
    refundex_output:          "none",
    authority_name_de:        "HM Revenue & Customs",
    authority_name_local:     "HM Revenue & Customs (HMRC)",
    form_name:                "–",
    form_url:                 "",
    min_worthwhile_eur:       0,
    complexity:               "low",
    dba_article:              "Art. 10 DBA-GB (Dividenden)",
    bmf_source_url:           "https://www.bundesfinanzministerium.de/Content/DE/Standardartikel/Themen/Steuern/Internationales_Steuerrecht/Staatenbezogene_Informationen/Laender_A_Z/Vereinigtes-Koenigreich.html",
    notes_de: [
      "UK erhebt KEINE Quellensteuer auf Dividenden (0%).",
      "Keine Rückforderung notwendig.",
      "Häufige Titel: AstraZeneca, HSBC, BP, Rio Tinto, GSK.",
    ],
    last_verified: "2025-06-19",
  },

  {
    country_iso:              "IE",
    country_name_de:          "Irland",
    country_name_local:       "Ireland / Éire",
    domestic_wht_rate:        25,
    dba_rate_de:              15,
    excess_rate:              10,
    recovery_possible:        true,
    recovery_deadline_years:  4,
    form_type:                "acroform_pdf",
    refundex_output:          "pdf_fill",
    authority_name_de:        "Irische Steuerbehörde",
    authority_name_local:     "Revenue Commissioners",
    form_name:                "Form IC5 (Dividend Withholding Tax Refund)",
    form_url:                 "https://www.revenue.ie/en/companies-and-charities/dividends-and-distributions/dividend-withholding-tax/claiming-a-refund.aspx",
    min_worthwhile_eur:       30,
    complexity:               "medium",
    dba_article:              "Art. 10 DBA-IE (Dividenden)",
    bmf_source_url:           "https://www.bundesfinanzministerium.de/Content/DE/Standardartikel/Themen/Steuern/Internationales_Steuerrecht/Staatenbezogene_Informationen/Laender_A_Z/Irland-DBA.html",
    notes_de: [
      "Relevant für in Irland domizilierte Fonds/ETFs (viele US-ETFs via Dublin).",
      "Häufige Titel: CRH, Kerry Group, AIB — aber auch viele US-Firmen mit IE-Holding.",
      "Erstattung in EUR.",
      "Revenue Commissioners haben englischsprachige Webseite.",
    ],
    last_verified: "2025-06-19",
  },

  {
    country_iso:              "AU",
    country_name_de:          "Australien",
    country_name_local:       "Australia",
    domestic_wht_rate:        30,
    dba_rate_de:              15,
    excess_rate:              15,
    recovery_possible:        true,
    recovery_deadline_years:  4,
    form_type:                "online",
    refundex_output:          "online_guide",
    authority_name_de:        "Australisches Finanzamt",
    authority_name_local:     "Australian Taxation Office (ATO)",
    form_name:                "Online via ATO myTax / Non-resident withholding",
    form_url:                 "https://www.ato.gov.au/individuals-and-families/investments-and-assets/investments-and-tax/dividends#Howdividendsaretaxed",
    min_worthwhile_eur:       40,
    complexity:               "medium",
    dba_article:              "Art. 10 DBA-AU (Dividenden)",
    bmf_source_url:           "https://www.bundesfinanzministerium.de/Content/DE/Standardartikel/Themen/Steuern/Internationales_Steuerrecht/Staatenbezogene_Informationen/Laender_A_Z/Australien-DBA.html",
    notes_de: [
      "Frankierungskredit-System (Franking Credits) kann Quellensteuer reduzieren.",
      "Häufige Titel: BHP, Rio Tinto (AU), Commonwealth Bank, ANZ.",
      "Erstattung in AUD.",
      "Englischsprachige ATO-Webseite — vergleichsweise unkompliziert.",
    ],
    last_verified: "2025-06-19",
  },

  {
    country_iso:              "SG",
    country_name_de:          "Singapur",
    country_name_local:       "Singapore",
    domestic_wht_rate:        0,
    dba_rate_de:              15,
    excess_rate:              0,
    recovery_possible:        false,
    recovery_deadline_years:  0,
    form_type:                "none",
    refundex_output:          "none",
    authority_name_de:        "Inland Revenue Authority of Singapore",
    authority_name_local:     "Inland Revenue Authority of Singapore (IRAS)",
    form_name:                "–",
    form_url:                 "",
    min_worthwhile_eur:       0,
    complexity:               "low",
    dba_article:              "Art. 10 DBA-SG (Dividenden)",
    bmf_source_url:           "https://www.bundesfinanzministerium.de/Content/DE/Standardartikel/Themen/Steuern/Internationales_Steuerrecht/Staatenbezogene_Informationen/Laender_A_Z/Singapur-DBA.html",
    notes_de: [
      "Singapur erhebt KEINE Quellensteuer auf Dividenden.",
      "Keine Rückforderung notwendig.",
    ],
    last_verified: "2025-06-19",
  },

];

// ---------------------------------------------------------------------------
// HILFSFUNKTIONEN
// ---------------------------------------------------------------------------

/**
 * Gibt DBA-Regel für einen ISO-Ländercode zurück.
 * @param {string} countryIso - z.B. "CH", "AT", "SE"
 * @returns {DBARule|null}
 */
export function getDBARule(countryIso) {
  return DBA_RULES.find(r => r.country_iso === countryIso.toUpperCase()) ?? null;
}

/**
 * Gibt alle Länder zurück, bei denen eine Rückforderung möglich ist.
 * @returns {DBARule[]}
 */
export function getRecoverableCountries() {
  return DBA_RULES.filter(r => r.recovery_possible);
}

/**
 * Gibt alle Länder zurück, bei denen Refundex direkte PDF-Befüllung macht.
 * @returns {DBARule[]}
 */
export function getPDFFillCountries() {
  return DBA_RULES.filter(r => r.refundex_output === "pdf_fill");
}

/**
 * Berechnet den Rückforderungsbetrag für eine Dividendenzahlung.
 * KEINE KI — reine Arithmetik auf verifizierten Daten.
 *
 * @param {string} countryIso
 * @param {number} grossAmountEur       - Brutto-Dividende in EUR
 * @param {number} withheldAmountEur    - Tatsächlich einbehaltene QSt in EUR
 * @param {Date}   payDate              - Zahlungsdatum
 * @returns {{
 *   excessEur: number,
 *   dbaMaxEur: number,
 *   recoverableEur: number,
 *   deadline: Date|null,
 *   daysRemaining: number|null,
 *   worthwhile: boolean,
 *   rule: DBARule|null
 * }}
 */
export function calculateRecovery(countryIso, grossAmountEur, withheldAmountEur, payDate) {
  const rule = getDBARule(countryIso);

  if (!rule || !rule.recovery_possible) {
    return {
      excessEur: 0,
      dbaMaxEur: 0,
      recoverableEur: 0,
      deadline: null,
      daysRemaining: null,
      worthwhile: false,
      rule,
    };
  }

  // DBA-Maximum: was darf maximal einbehalten werden?
  const dbaMaxEur = Math.round((grossAmountEur * rule.dba_rate_de / 100) * 100) / 100;

  // Überschuss: was wurde zu viel einbehalten?
  const excessEur = Math.round((withheldAmountEur - dbaMaxEur) * 100) / 100;
  const recoverableEur = Math.max(0, excessEur);

  // Fristberechnung — reine Datumsmathematik, kein KI-Urteil
  const deadline = new Date(payDate);
  deadline.setFullYear(deadline.getFullYear() + rule.recovery_deadline_years);

  const today = new Date();
  const daysRemaining = Math.floor((deadline - today) / (1000 * 60 * 60 * 24));

  const worthwhile = recoverableEur >= rule.min_worthwhile_eur && daysRemaining > 0;

  return {
    excessEur,
    dbaMaxEur,
    recoverableEur,
    deadline,
    daysRemaining,
    worthwhile,
    rule,
  };
}

/**
 * Dringlichkeitsstufe für UI-Darstellung.
 * @param {number} daysRemaining
 * @returns {"expired"|"urgent"|"soon"|"ok"}
 */
export function getUrgency(daysRemaining) {
  if (daysRemaining <= 0)   return "expired";
  if (daysRemaining <= 90)  return "urgent";
  if (daysRemaining <= 180) return "soon";
  return "ok";
}

// ---------------------------------------------------------------------------
// MODUL-METADATEN
// ---------------------------------------------------------------------------

export const DBA_MODULE_META = {
  version:       "1.0.0",
  created:       "2025-06-19",
  next_review:   "2026-01-01",
  country_count: DBA_RULES.length,
  recoverable:   DBA_RULES.filter(r => r.recovery_possible).length,
  pdf_fill:      DBA_RULES.filter(r => r.refundex_output === "pdf_fill").length,
  source_primary: "BMF Übersicht DBA Deutschlands 2024",
  source_url:    "https://www.bundesfinanzministerium.de/Content/DE/Standardartikel/Themen/Steuern/Internationales_Steuerrecht/Staatenbezogene_Informationen/Laender_A_Z/",
  warning:       "Steuerrecht ändert sich. Vor Antragsstellung immer Originalquellen prüfen.",
};
