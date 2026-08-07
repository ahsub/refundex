# Refundex — Roadmap

**Version:** 1.7
**Stand:** 06.08.2026
**Ablage:** `ahsub/refundex/docs/ROADMAP.md`
**Referenzrahmen:** `docs/STRATEGIE.md` v1.0 — jedes Roadmap-Item hat den Vier-Fragen-Filter (Belegkette / 80-20 / ES6-Modularität / StBerG) bestanden oder ist entsprechend markiert.

---

## Ausgangslage (Ist-Stand 03.07.2026)

| Baustein | Stand |
|---|---|
| Frontend `kap.html` | v138, Beta-Release, BETA-Badge + Beta-Banner live |
| Python-Engine | v4 (`build_report.py`), **99/99 pytest-Tests** über 6 Testdateien |
| Engine-Module | `ko-flex.js` (Parser), `aktien_fifo.py`, `termingeschaefte.py`, `verlusttoepfe.py` (3-Töpfe + 20k-Cap + Vortrag), `vorabpauschale.py` (§18 InvStG), `kapmassnm.py` (Kapitalmaßnahmen) |
| Basiszins | 2025 = 2,53 % (BMF 10.01.2025) und 2026 = 3,20 % (BMF 13.01.2026) verifiziert integriert |
| Architektur | Projektions-Schicht (`calcKAP` brutto → `projiziereErgebnis` Gemeinschaftskonto-Faktor an genau einer Stelle) |
| Hilfe-System | Modular, lädt Markdown aus `ahsub/refundex-docs` (10 Module), `index.json` UIQ-fähig |
| Validierung | 3 Jahre Echtdaten (2023–2025) gegen CapTrader-Steuerbescheinigungen |
| JSON-Brücke | `importEngineJSON()` lädt `kap_data.json` der Engine ins Frontend |

---

## Phase 1 — Konsolidierung & Release-Reife (Q3 2026)

**Ziel:** Aus der Beta ein Werkzeug machen, das man Fremden ohne Bauchschmerzen in die Hand gibt. Kein neues Rechenfeature, bevor diese Phase steht.

| # | Item | Kriterium „fertig" | Filter-Notiz |
|---|---|---|---|
| 1.1 | ✅ **ERLEDIGT (v139, 03.07.2026)** — **Disclaimer-Verstärkung (4 Punkte)** — (a) No-Guarantee-Klausel, (b) Steuerberater-Klausel geschärft, (c) Basiszins-/Rechtsstand-Unsicherheit sichtbar, (d) explizite Nicht-Abdeckungsliste (Krypto, Edelmetalle, betriebliche Erträge) | Sichtbar in App + Report + guide.html | StBerG-Pflicht, vor allem anderen |
| 1.2 | ✅ **ERLEDIGT (03.07.2026)** — **`guide.html`** — integrierter Leitfaden: Featureliste, Haftungshinweise, Schritt-für-Schritt Flex-Query-Einrichtung (197-Zeichen-Prompt), Bedienung, Grenzen | Ein Neuling kommt ohne Rückfragen vom leeren Depotauszug zum KAP-Ergebnis | 80/20: größter Hebel für Beta-Tauglichkeit |
| 1.3 | **Feedback-Kanal real** — Platzhalter `feedback@refundex.de` durch funktionierende Adresse oder GitHub-Issues-only ersetzen | Eingehende Meldung erreicht Axel nachweislich | Beta-Voraussetzung |
| 1.4 | **§23 EStG-Randfälle dokumentieren** — physische Edelmetalle (1-Jahres-Frist), Alt-Krypto (vor 2025): zunächst nur als Hilfe-Modul + Nicht-Abdeckungshinweis (Anlage SO, persönlicher Steuersatz) | Hilfe-Modul online; Berechnung erst Phase 3 | 80/20: dokumentieren jetzt, rechnen später |
| 1.5 | ✅ **ERLEDIGT (v1.0, 03.07.2026)** — **`docs/RUNBOOK.md`** — Bus-Factor-Dokument analog UIQ: Systemlandkarte, Repo-/Deploy-Wege, Steuerjahr-Update-Prozess, Disaster Recovery | Ein technikaffiner Dritter kann das System betreiben | W1-Gegenmaßnahme |
| 1.6 | ✅ **ERLEDIGT (03.07.2026, in RUNBOOK.md §4)** — **Steuerjahr-Update-Checkliste** — jährlicher Prozess: Basiszins (BMF-Schreiben Januar), Sparer-Pauschbetrag, Rechtsänderungs-Review §20/§18/§23, Testlauf gegen Vorjahres-Referenzdaten | Checkliste in RUNBOOK.md, erstmals durchlaufen für Steuerjahr 2026 | W4-Gegenmaßnahme |
| 1.7 | **Beta-Testrunde** — Versand an 3–5 IBKR/CapTrader-Nutzer (Investmentclub), Feedback-Zyklus, Abgleich gegen deren Steuerbescheinigungen | ≥ 3 Fremd-Depots erfolgreich abgeglichen | Validierung jenseits des Eigen-Depots |
| 1.8 | 🔶 **Stufe (i) ERLEDIGT (v139): Wording + Verifikations-Aufruf live** — **Lynx-Verbreiterung** *(vorgezogen aus Phase 3.3)* — Lynx ist wie CapTrader ein IBKR-Introducing-Broker mit identischer Flex Query. **Stand 07/2026: kein Lynx-Depot im Investmentclub verfügbar.** Daher zweistufig: (i) sofort Wording in App + guide.html auf „IBKR-basierte Broker (CapTrader, Lynx)" mit ehrlichem Zusatz *„Lynx: technisch baugleich, Verifikation ausstehend"*; (ii) gezielter Aufruf in guide.html + Beta-Banner: „Lynx-Nutzer gesucht — eine anonymisierte Flex Query genügt zur Verifikation" — die Beta-Community liefert das Testdepot. Kein „verifiziert"-Claim vor echtem Lauf (No-Hallucination gilt auch fürs Marketing) | Wording live; „verifiziert" erst nach einem Lynx-Flex-Query-Lauf gegen Steuerbescheinigung | 80/20 exzellent: Zielgruppen-Verdreifachung zum Preis eines Wording-Fixes |

**Deployment-Politik:** Items 1.1–1.3 dürfen als Batch sofort deployen (Beta läuft bereits öffentlich → Disclaimer-Lücke ist ein kritischer Fall im Sinne des Arbeitsprotokolls).

---

## Phase 2 — Suite-Integration & ES6-Migration (Q4 2026)

**Ziel:** Refundex wird strukturell das, was es strategisch schon ist: ein Modul der Investment-Suite. Engine wird Single Source of Truth.

| # | Item | Kriterium „fertig" | Filter-Notiz |
|---|---|---|---|
| 2.1 | **Rechenwelten konsolidieren** — Browser-Rechenlogik in kap.html schrittweise stilllegen zugunsten Engine-JSON (`kap_data.json`) als einziger Wertequelle; Browser rechnet nur noch Darstellung/Projektion | Kein KAP-Wert entsteht mehr an zwei Stellen | W2-Gegenmaßnahme, No-Hallucination-relevant |
| 2.2 | **ES6-Modularisierung Frontend** — kap.html-Monolith in Module zerlegen (`rx-parser`, `rx-render`, `rx-state`, `rx-strings`), Muster: UIQ v2.0 / renderCard-SSoT; zentrale String-Objekte (i18n-ready) | Neue Features berühren nur noch Module, nie den Monolithen | Suite-Grundgesetz 2 |
| 2.3 | **Gemeinsame Suite-Module extrahieren** — was UIQ und Refundex teilen (Markdown-Renderer des Hilfe-Systems, DOCX-Export-Helfer, Format-/Zahlutilities) wandert nach `ko-modules` bzw. ein neues `suite-core` | Ein Bugfix wirkt in beiden Apps | Suite-Synergie S5 |
| 2.4 | **Parser-Härtung** — Flex-Query-Format-Sanity-Checks mit Versions-Fingerprint; bei Formatabweichung harte Fehlermeldung statt stiller Fehlwerte | Manipulierte/geänderte CSV führt nie zu plausibel aussehenden Falschwerten | R3, No-Hallucination |
| 2.5 | **Suite-Dach dokumentieren** — kurzes `SUITE.md` (Ablageort: ko-aggregator oder eigenes Meta-Repo): Module, Schnittstellen, gemeinsame Grundgesetze; verlinkt aus beiden STRATEGIE.md | Ein Dokument beschreibt die Klammer | Governance |
| 2.6 | 🔶 **Spezifikation ERLEDIGT (docs/DATENMODELL_ERTRAEGE.md v1.0); Implementierung offen** — **Normalisiertes Ertragsdatenmodell + Adapter 1/2** *(Fundament Säule 2)* — broker-neutrales Datenmodell (ISIN, Quellenland, Datum, Brutto, einbehaltene QSt, Währung) als JSON-Kontrakt; Adapter 1: Mapping aus vorhandenen Flex-Cash-Daten; Adapter 2: manuelles Erfassungsformular für aggregierte Werte aus Ertragsaufstellungen beliebiger Depotbanken | Identische Cockpit-Ausgabe, egal ob Daten aus Flex Query oder Handeingabe stammen | Grundgesetz 6; macht Säule 2 ab Tag 1 broker-neutral |
| 2.7 | **Quellensteuer-Cockpit (Säule 2, Stufe A)** — neue Sektion: je Land gezahlte Dividenden, einbehaltene QSt, in DE anrechenbar (Z. 41), Überschuss = Rückholpotenzial, Verjährungsfrist, Verfahrenslink; dazu Hilfe-Module je Top-Land (CH, DK, F, E, I) inkl. ehrlicher Dokumentation der Nachweis-Hürden. **Neu (v1.2): Netto-Rückholpotenzial** = Überschuss − Tax-Voucher-Kosten (Quelle: CapTrader-Preisliste 07/2026, z. B. CH 15 CHF, DK 125 DKK, I 25 €, F 125 €) mit **Break-even-Ampel je Land** (grün = Rückforderung lohnt, rot = Voucher-Kosten übersteigen Überschuss). Orientierung: CH lohnt ab ~75 CHF Bruttodividende/Jahr, F erst ab ~900 € — genau diese Ökonomie soll der Nutzer schwarz auf weiß sehen | Nutzer sieht Brutto- UND Netto-Rückholpotenzial je Land; DBA-Sätze und Voucher-Kosten quellenbelegt | Reines Rechenwerk mit Belegkette — kein Verfahrensrisiko, kein Recherche-Gate nötig |

| 2.8 | **XML-Migration (Flex Query CSV → XML, strategische Weichenstellung)** — IBKR/CapTrader plant mittelfristige Deprecation des CSV-Exports. XML ist das zukunftssichere Format: reicheres Schema, maschinenlesbar ohne Trennzeichen-Ambiguitäten, Versions-Fingerprint im Root-Tag. `ko-flex.js` erkennt `activity_xml` bereits und gibt `'coming soon'` zurück — das ist der Stub. Umfang: (a) `parseActivityXML()` in `ko-flex.js` implementieren (DOMParser, Namespace-aware), Feldmapping auf das normalisierte Datenmodell; (b) Python-Engine-Adapter in `build_report.py` (parallel zu CSV, kein Abriss); (c) `detectFormat` bleibt abwärtskompatibel (CSV-Pfade bleiben bis zur IBKR-Deprecation). Strategie: XML-first ab Implementierung, CSV als Legacy-Pfad — keine parallele Pflege neuer Features in CSV. Referenz-Schnittstelle: `docs/DATENMODELL_JOURNAL.md` (→ 2.9). | XML-Adapter liefert identische Engine-Ausgabe wie CSV-Pfad; verifiziert gegen CapTrader-Flex-XML-Exportbeispiel | R3 (Parser-Härtung), No-Hallucination; CSV-Deprecation-Risiko eliminiert |
| 2.9 | **Trade-Journal-Modul (Refundex, nicht UIQ)** — Architektur-Entscheidung 05.08.2026: Journal gehört in Refundex (Positions-Bewirtschaftung nach dem Trade, P&L-Auswertung), nicht in UIQ (Entscheidungs-Tool vor dem Trade). Datenbasis: Flex-XML (→ 2.8) liefert P&L, Fills, Laufzeit automatisch; manuelle Felder nur für subjektive Dimension (Setup-Typ, Regelkonformität, Lernnotiz). Datenstruktur: `docs/DATENMODELL_JOURNAL.md` (Spezifikation v1.0, 06.08.2026). Implementierung: neues Modul `modules/ko-journal.js` + Journal-Tab in `kap.html`; localStorage-first (Datensouveränität), optionaler DOCX-Export. Abhängigkeit: 2.8 vor 2.9 — XML-Adapter muss stehen, bevor Journal automatisch befüllt werden kann. | Journal-Einträge werden automatisch aus Flex-XML befüllt; manuelle Felder ergänzbar; P&L-Auswertung korrekt | Grundgesetz 3 (Datensouveränität), 80/20: automatische Befüllung aus Flex-Query eliminiert manuellen Overhead |

| 2.10 | **`flex_client.py` — Automatisierter Flex Web Service Pull (Python)** — Zwei-Schritt-API: (1) `SendRequest?t=TOKEN&q=QUERY_ID&v=3` → `ReferenceCode`; (2) `GetStatement?t=TOKEN&q=ReferenceCode&v=3` → XML. Token + QueryID aus `.env` (`IB_FLEX_TOKEN`, `IB_FLEX_QUERY_ID`), nie im Code. Retry-Logik (IBKR generiert Report asynchron, typisch 10–30s Wartezeit), XML-Fehlerresponse-Erkennung. Rückgabe: validiertes XML-String-Objekt, direkt an `parseActivityXML()` übergebar. Verwendung: `build_report.py` ruft `flex_client.py` auf statt CSV-Upload — vollautomatische Steuerberechnung ohne manuellen Download. Ablage: `engine/flex_client.py`. Credentials: `.env` + `.gitignore` (nie committen). | Liefert identisches XML wie manueller Download; verifiziert gegen CapTrader Flex Web Service | Datensouveränität, R3, Grundgesetz 1 |
| 2.11 | **`ko-flex-proxy` Cloudflare Worker — Browser-seitiger Flex Pull (CORS-Bridge)** — IBKR setzt keine CORS-Header → direkter Fetch aus `kap.html` schlägt fehl. Lösung: minimaler CF Worker als transparenter Proxy. Architektur: Browser sendet `{token, queryId}` → Worker ruft IBKR SendRequest + GetStatement auf → gibt XML zurück. Token verlässt Browser nur in Richtung eigener Worker-Infrastruktur. Worker-Route: `ko-flex-proxy.ahildebrand.workers.dev`. Token im Browser-`localStorage` (analog ko-sync-Token), kein Server-Logging. `kap.html` erhält „Direkt von CapTrader laden"-Button als Alternative zum Upload. Abhängigkeit: 2.8 (XML-Parser) muss stehen. | Browser-Pull liefert identisches XML wie Upload; Token nie im Klartext geloggt | Datensouveränität, UX: Upload-Schritt entfällt |

| 2.12 | **OptionsCoach + OptionsDoktor — KI Options-Coaching** *(SUITE.md Backlog №37)* — Eigenständiges Coaching-Modul auf Basis der Flex-XML-Datenbasis. Zwei Modi: (1) OptionsCoach (prospektiv): Regime-Check, Earnings-Gate, IV-Rank, Delta-Wahl vor Trade-Eröffnung. (2) OptionsDoktor (retrospektiv/laufend): Diagnose abgeschlossener Positionen ("was lief schief?"), Handlungsoptionen bei laufenden Positionen (Rollen/Rückkauf/Hedge), Lernmuster-Engine über 50+ Trades. Datenfluss: Flex-XML → Position-Aggregation (Roll = ein Ereignis) → UIQ-Kontext (Regime/IV-Rank zum Entry) → Claude Strict-Extraction-Analyse → Diagnose + Lernpunkt. Alleinstellungsmerkmal: einzige Kombination aus echten Trade-Daten + Marktbedingungen zum Entry + steuerlicher Einordnung + KI-Coaching im DACH-Raum. Abhängigkeit: 2.9 (ko-journal.js ✅), UIQ IV-Rank (ab 11.08.2026 ✅). **Trigger: nach 01.10.2026** (Track Record reif, Datenbasis vollständig). | Lernmuster-Engine erkennt systematische Fehler über ≥20 Positionen | Grundgesetz 1 (No-Hallucination: nur Fakten aus Flex-XML + UIQ-Daten), 80/20: höchster edukativer Mehrwert |

**Reihenfolge-Logik:** 2.1 vor 2.2. 2.6 vor 2.7. **2.8 vor 2.9** ✅. **2.10+2.11 parallel zu 2.8** ✅. **2.9 vor 2.12** — Journal ist Datenbasis des Coaches.

**Reihenfolge-Logik:** 2.1 vor 2.2 — erst die Wertequelle vereinheitlichen, dann die Fassade modularisieren. Sonst wird Doppel-Logik mitmigriert. 2.6 vor 2.7 — erst das Datenmodell, dann das Cockpit darauf. **2.8 vor 2.9** — XML-Adapter ist Datenbasis des Journals; Journal-Modul baut darauf auf. **2.10 + 2.11 parallel zu 2.8** — Pull-Infrastruktur und Parser sind unabhängig entwickelbar, konvergieren beim ersten Durchstich (Pull → Parse → Journal).

---

## Phase 3 — Erweiterung unter 80/20-Vorbehalt (2027)

**Ziel:** Nische verbreitern, ohne die Kernqualität zu verwässern. Jedes Item einzeln durch den Vier-Fragen-Filter; kein Item ist gesetzt.

| # | Kandidat | 80/20-Einschätzung |
|---|---|---|
| 3.1 | **§23-Berechnung (Anlage SO)** — Edelmetalle, Alt-Krypto, Devisengewinne konsolidiert | Mittlerer Aufwand, klar abgrenzbar; Devisen-Grundlage existiert bereits |
| 3.2 | **Steuerjahr 2026-Release** — Basiszins 3,20 % ist integriert; Pflichtdurchlauf der Update-Checkliste (1.6) | Geringer Aufwand, jährlicher Pflichttermin Q1 2027 |
| 3.3 | **Multi-Broker-Prüfung Säule 1** — Lynx nach Phase 1.8 vorgezogen; weitere KAP-Broker (Degiro & Co. = echte Parser-Neubauten) nur bei nachgewiesener Nachfrage | Erst Nachfrage, dann Code |
| 3.7 | **Formular-Vorbefüllung QSt (Säule 2, Stufe B) — hinter Recherche-Gate.** Start: Schweiz (Formular 85; 35 % Abzug, 20 Punkte rückholbar), danach ggf. DK. **Gate-Protokoll (Stand 03.07.2026):** (a) Desk-Research ESTV-Wegleitung — **offen**, übernimmt Claude in Websuche-Session, Ergebnis als `docs/RECHERCHE_QST_CH.md`; (b) CapTrader Tax Voucher — **im Kern erfüllt ✓** via CapTrader-FAQ 07/2026: Voucher für 11 Länder inkl. CH/DK/F/I, Preisliste dokumentiert (siehe 2.7); Restfragen per laufendem Support-Ticket: Gebührenbezug (pro Wertpapier / Antrag / Steuerjahr / Dividendenereignis?), Bearbeitungszeit, Format (elektronisch?); (c) Investmentclub-Umfrage — **erfüllt ✓**: null Rückforderungs-Erfahrung im Club, einhelliger Grund „zu kompliziert" (zugleich Produkthypothesen-Beleg, s. STRATEGIE O6); (d) Eigenfall-Testballon (CH- oder DK-Position, z. B. NVO) — **offen**, sinnvoll erst nach (a) und Ticket-Antwort | Gate bestanden → Bau-Entscheidung; Gate gescheitert → Cockpit bleibt bei Verfahrenslink + Doku | Deterministische PDF-Befüllung aus Datenmodell; StBerG: mechanische Ausfüllhilfe nach allgemeinen Regeln, gleiche Disclaimer wie KAP |
| 3.8 | **PDF-Dump-Adapter (Säule 2, Adapter 3) — nur mit Extraction-Review-Gate.** Freitext-Extraktion aus Bankabrechnungen beliebiger Institute im Strict-Extraction-Muster (GuidelineIQ): KI extrahiert mit Fundstellen-Zitat, Nutzer bestätigt jede Zeile gegen das PDF, erst dann übernimmt die Engine. Stille Übernahme ist ausgeschlossen | Kein Wert erreicht die Engine ohne explizite Nutzer-Bestätigung je Zeile | No-Hallucination-kritischstes Item der gesamten Roadmap; nur bauen, wenn Adapter 2 nachweislich als zu mühsam empfunden wird |
| 3.9 | **QSt-Tracking (Säule 2, Stufe C)** — Status eingereicht/erstattet, Frist-Erinnerung, localStorage | Nice-to-have, bewusst letzte Priorität |
| 3.4 | **Suite-Cross-Verlinkung** — dezenter Verweis UIQ ↔ Refundex (identische Zielgruppe) | Minimaler Aufwand; Formulierung StBerG-/BaFin-sauber halten |
| 3.5 | **Monetarisierungs-Entscheidung** — frei / Spende / Freemium; erst nach Beta-Feedback (1.7) entscheiden | Entscheidung, kein Code; Impressums-/AGB-Fragen dann klären |
| 3.6 | **i18n-Vorbereitung** | ⚠️ Anders als bei UIQ vorerst **nein**: deutsches Steuerrecht ist das Produkt, EN-Version hätte kaum Zielgruppe. Nur String-Zentralisierung (2.2) als Option offen halten |

---

## Nicht-Ziele (bewusst verworfen)

Diese Liste ist Teil der Roadmap, damit sie nicht in jeder Session neu diskutiert wird:

1. **ELSTER-Direktschnittstelle (ERiC)** — Zertifizierungs- und Haftungsaufwand ohne Verhältnis zum Nutzen; der manuelle Übertrag per Checkliste ist der 80/20-Weg.
2. **Steueroptimierungs-Empfehlungen** (Tax-Loss-Harvesting-Vorschläge o. Ä.) — StBerG-Grenze, Filter-Frage 4 dauerhaft negativ.
3. **Server-seitige Depotdaten-Verarbeitung** — widerspricht Kernversprechen Datensouveränität (S4).
4. **KI-berechnete Steuerwerte** — No-Hallucination-Gebot; KI bleibt auf Erklären/Formulieren beschränkt. Einzige, eng umzäunte Ausnahme: PDF-**Extraktion** (nicht Berechnung) im Strict-Extraction-Muster mit zeilenweiser Nutzer-Bestätigung (Item 3.8) — stille KI-Übernahme in die Engine bleibt dauerhaft Nicht-Ziel.
5. **Vollständigkeit aller Exoten** (strukturierte Produkte, Wertlos-Ausbuchungs-Sonderfälle jenseits der Engine-Abdeckung) — dokumentierte Grenze + Steuerberater-Verweis statt Feature.

---

## Fortschreibungshistorie

| Version | Datum | Änderung |
|---|---|---|
| 1.0 | 03.07.2026 | Erstfassung: Ist-Stand, Phasen 1–3, Nicht-Ziele |
| 1.1 | 03.07.2026 | Lynx von 3.3 nach 1.8 vorgezogen; Säule 2 aufgenommen: 2.6 Ertragsdatenmodell + Adapter 1/2, 2.7 QSt-Cockpit, 3.7 Formular-Vorbefüllung CH/DK hinter Recherche-Gate (4 Bedingungen), 3.8 PDF-Adapter nur mit Extraction-Review-Gate, 3.9 Tracking; Nicht-Ziel 4 präzisiert |
| 1.2 | 03.07.2026 | Gate-Protokoll 3.7: (b) im Kern erfüllt (CapTrader-FAQ: Voucher für 11 Länder + Preisliste, Restfragen per Ticket), (c) erfüllt (Club-Umfrage); 2.7 um Netto-Rückholpotenzial + Break-even-Ampel erweitert; 1.8 zweistufig (Wording sofort, Verifikation via Beta-Community-Aufruf, kein Lynx-Depot im Club) |
| 1.3 | 03.07.2026 | Erledigungsstände: 1.1 ✅ (kap.html v139: 4-Punkte-Haftungsblock, Basiszins-Hinweis, Nicht-Abdeckungsliste), 1.5 ✅ + 1.6 ✅ (RUNBOOK.md v1.0 inkl. Steuerjahr-Checkliste), 1.8 Stufe i ✅ (Lynx-Wording + Aufruf), 2.6 Spec ✅ (DATENMODELL_ERTRAEGE.md v1.0) |
| 1.5 | 06.08.2026 | Phase 2: 2.8 XML-Migration (CSV-Deprecation-Strategie, `ko-flex.js`-Stub dokumentiert, Abhängigkeit für 2.9) + 2.9 Trade-Journal-Modul (Architektur-Entscheidung: Journal in Refundex, nicht UIQ; Spezifikation `docs/DATENMODELL_JOURNAL.md` v1.0); Reihenfolge-Logik 2.8→2.9 ergänzt |
| 1.6 | 06.08.2026 | Phase 2: 2.10
| 1.7 | 07.08.2026 | 2.12 OptionsCoach + OptionsDoktor (SUITE.md №37): KI-Coaching auf Basis Flex-XML + UIQ-Kontext, Lernmuster-Engine, Trigger 01.10.2026 | `flex_client.py` (automatisierter Python-Pull via Flex Web Service, `.env`-Credentials) + 2.11 `ko-flex-proxy` CF Worker (CORS-Bridge für Browser-Pull); Reihenfolge-Logik 2.10+2.11 parallel zu 2.8 ergänzt | (CSV-Deprecation-Strategie, `ko-flex.js`-Stub dokumentiert, Abhängigkeit für 2.9) + 2.9 Trade-Journal-Modul (Architektur-Entscheidung: Journal in Refundex, nicht UIQ; Spezifikation `docs/DATENMODELL_JOURNAL.md` v1.0); Reihenfolge-Logik 2.8→2.9 ergänzt |
| 1.4 | 03.07.2026 | 1.2 ✅ guide.html erstellt (Belegketten-Hero, Flex-Query-Setup, 5-Schritte-Bedienung, 4-Punkte-Haftungsblock, FAQ inkl. Lynx + QSt-Ausblick); kap.html v140 mit Leitfaden-Link im Banner |
