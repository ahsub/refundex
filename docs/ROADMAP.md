# Refundex — Roadmap

**Version:** 2.7
**Stand:** 10.08.2026
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
| 1.3 | ✅ **Feedback-Kanal real** *(erledigt 07.08.2026 — mailto:ahildebrand@me.com + GitHub Issues aktiv in kap.html)* — Platzhalter `feedback@refundex.de` durch funktionierende Adresse oder GitHub-Issues-only ersetzen | Eingehende Meldung erreicht Axel nachweislich | Beta-Voraussetzung |
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

| 2.8 | ✅ **XML-Migration (Flex Query CSV → XML, strategische Weichenstellung)** — IBKR/CapTrader plant mittelfristige Deprecation des CSV-Exports. XML ist das zukunftssichere Format: reicheres Schema, maschinenlesbar ohne Trennzeichen-Ambiguitäten, Versions-Fingerprint im Root-Tag. `ko-flex.js` erkennt `activity_xml` bereits und gibt `'coming soon'` zurück — das ist der Stub. Umfang: (a) `parseActivityXML()` in `ko-flex.js` implementieren (DOMParser, Namespace-aware), Feldmapping auf das normalisierte Datenmodell; (b) Python-Engine-Adapter in `build_report.py` (parallel zu CSV, kein Abriss); (c) `detectFormat` bleibt abwärtskompatibel (CSV-Pfade bleiben bis zur IBKR-Deprecation). Strategie: XML-first ab Implementierung, CSV als Legacy-Pfad — keine parallele Pflege neuer Features in CSV. Referenz-Schnittstelle: `docs/DATENMODELL_JOURNAL.md` (→ 2.9). | XML-Adapter liefert identische Engine-Ausgabe wie CSV-Pfad; verifiziert gegen CapTrader-Flex-XML-Exportbeispiel | R3 (Parser-Härtung), No-Hallucination; CSV-Deprecation-Risiko eliminiert |
| 2.9 | ✅ **Trade-Journal-Modul (Refundex, nicht UIQ)** — Architektur-Entscheidung 05.08.2026: Journal gehört in Refundex (Positions-Bewirtschaftung nach dem Trade, P&L-Auswertung), nicht in UIQ (Entscheidungs-Tool vor dem Trade). Datenbasis: Flex-XML (→ 2.8) liefert P&L, Fills, Laufzeit automatisch; manuelle Felder nur für subjektive Dimension (Setup-Typ, Regelkonformität, Lernnotiz). Datenstruktur: `docs/DATENMODELL_JOURNAL.md` (Spezifikation v1.0, 06.08.2026). Implementierung: neues Modul `modules/ko-journal.js` + Journal-Tab in `kap.html`; localStorage-first (Datensouveränität), optionaler DOCX-Export. Abhängigkeit: 2.8 vor 2.9 — XML-Adapter muss stehen, bevor Journal automatisch befüllt werden kann. | Journal-Einträge werden automatisch aus Flex-XML befüllt; manuelle Felder ergänzbar; P&L-Auswertung korrekt | Grundgesetz 3 (Datensouveränität), 80/20: automatische Befüllung aus Flex-Query eliminiert manuellen Overhead |

| 2.10 | ✅ **`flex_client.py` — Automatisierter Flex Web Service Pull (Python)** — Zwei-Schritt-API: (1) `SendRequest?t=TOKEN&q=QUERY_ID&v=3` → `ReferenceCode`; (2) `GetStatement?t=TOKEN&q=ReferenceCode&v=3` → XML. Token + QueryID aus `.env` (`IB_FLEX_TOKEN`, `IB_FLEX_QUERY_ID`), nie im Code. Retry-Logik (IBKR generiert Report asynchron, typisch 10–30s Wartezeit), XML-Fehlerresponse-Erkennung. Rückgabe: validiertes XML-String-Objekt, direkt an `parseActivityXML()` übergebar. Verwendung: `build_report.py` ruft `flex_client.py` auf statt CSV-Upload — vollautomatische Steuerberechnung ohne manuellen Download. Ablage: `engine/flex_client.py`. Credentials: `.env` + `.gitignore` (nie committen). | Liefert identisches XML wie manueller Download; verifiziert gegen CapTrader Flex Web Service | Datensouveränität, R3, Grundgesetz 1 |
| 2.11 | ✅ **`ko-flex-proxy` Cloudflare Worker — Browser-seitiger Flex Pull (CORS-Bridge)** — IBKR setzt keine CORS-Header → direkter Fetch aus `kap.html` schlägt fehl. Lösung: minimaler CF Worker als transparenter Proxy. Architektur: Browser sendet `{token, queryId}` → Worker ruft IBKR SendRequest + GetStatement auf → gibt XML zurück. Token verlässt Browser nur in Richtung eigener Worker-Infrastruktur. Worker-Route: `ko-flex-proxy.ahildebrand.workers.dev`. Token im Browser-`localStorage` (analog ko-sync-Token), kein Server-Logging. `kap.html` erhält „Direkt von CapTrader laden"-Button als Alternative zum Upload. Abhängigkeit: 2.8 (XML-Parser) muss stehen. | Browser-Pull liefert identisches XML wie Upload; Token nie im Klartext geloggt | Datensouveränität, UX: Upload-Schritt entfällt |

| 2.13 | ~~**FIFO-Positions-Tracker**~~ **ENTFÄLLT** — Steuerrechtliche Klarstellung 08.08.2026: §20 Abs.1 Nr.11 EStG = Cash-Basis, kein FIFO-Matching nötig. Z.21 = SELL-netCash, Z.24 = BUY-netCash. Validiert vs. PWC 2024: Δ=0,01 EUR. Implementiert in ko-flex.js v1.2/v1.3 + kap.html. — Matching von SELL+BUY-Paaren über Jahresgrenzen hinweg. Eine Option die am 15.11.2024 verkauft und am 03.01.2025 zurückgekauft wird, darf NICHT im 2024-Report auftauchen (offene Position). Implementierung: `ko-fifo-options.js` — Stack-basiertes FIFO analog zu `aktien_fifo.py`, aber für Options-Legs. Ausgabe: `{closedPositions[], openPositions[]}` je Steuerjahr. **Voraussetzung für Z.21/Z.24-Korrektheit.** | Geschlossene Positionen korrekt abgegrenzt, Gegenprüfung mit PWC 2024 ± 5 EUR | Kern-Rechenwerk, Belegkette-relevant |
| 2.14 | ✅ **Buchungs-Datums-Filter (Jahresüberschreiter)** *(erledigt 09.08.2026)* — WHT-Stornos und Dividenden-Reversals die als Korrekturbuchung im Folgejahr erscheinen, werden ausgeschlossen. Erkennungsmuster: negative WHT-Buchung ohne zugehörige Dividende im gleichen Jahr, `description` enthält "REVERSAL"/"CORRECTION"/"STORNO"/"ADJUSTMENT". Implementiert in `ko-flex.js` (`correctionBookings`-Array für Audit-Trail). **Systematisch gegen Axels vollständige 2023-2025-Daten geprüft: 0 Treffer** — Filter ist defensiv aktiv, greift aber aktuell bei keiner Buchung. **Wichtigerer Nebenfund bei der Implementierung:** Der CashTransaction-Filter nutzte `activityCode`, ein Attribut, das im echten Flex-XML-Schema nicht existiert (0/250 Elemente betroffen) — echtes Schema nutzt `type` ("Dividends"/"Withholding Tax"/"Payment In Lieu Of Dividends"). Das `dividends`-Array war dadurch bei echten Daten **immer leer**, betraf die komplette Divi/WHT-Pipeline (Säule 2/QSt-Cockpit), nicht nur diesen Punkt. Gefixt im selben Commit. | Quellensteuer-Summe ± 5 EUR gegen PWC | Filter-Regel — Bug-Fix hatte höhere Priorität als ursprünglicher Punkt |
| 2.15 | **Gains/Losses-Auftrennung für Z.21/Z.24** — Nicht nur Netto-P&L sondern getrennte Gewinntöpfe (Z.21: income from trading in derivatives) und Verlusttöpfe (Z.24: losses, mit 20k-Cap §20 Abs.6). Basis: abgeschlossene Positionen aus 2.13. Verluste mit `isRestrictedLoss`-Flag wenn Disposal-Proceeds = 0 (wertlose Option = §20 Abs.6 Satz 2). | Z.21 und Z.24 getrennt ausgewiesen, 20k-Cap korrekt angewendet | Steuerrechtlich kritisch (20k-Cap) |
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
| 1.7 | 07.08.2026 |
| 2.3 | 09.08.2026 | Gegenprüfung alle 3 Jahre (2023/2024/2025 XML vs. PWC-PDF): 2023 ✅ (0 Trades/0 EUR), 2024 ✅ (Δ=0,01/0,00 EUR), 2025 ✅ (Δ=0,06/0,11 EUR gegen Transaktionsliste). PWC-Summary-Bug 2025 entdeckt: Line 21 fehlt komplett, Line 24 unter falscher Zeile (Line 22). Dual-Mode-Gate bereinigt: FIFO raus, Cash-Basis rein, Gegenprüfungen bestätigt. Beta-Anforderung: PDF-Upload neben XML nötig. Neuer ROADMAP-Punkt Phase F. |
| 2.7 | 10.08.2026 | 2.17 Governance geklärt: als Bugfix eingestuft (jederzeit erlaubt, keine §4-Ausnahme nötig). Klärungsplan vereinbart (4 Schritte: Diskrepanz aufklären → Methodik prüfen → PWC-Gegenprüfung → Fix). Axel prüft eigenständig Herkunft/Datenstand des ursprünglichen DOCX. |
| 2.6 | 10.08.2026 | **🔴 KRITISCHER OFFENER BEFUND (Punkt 2.17):** Z.8/Z.9-Formel (Aktienveräußerungsgewinne/-verluste, `ko-flex.js` Zeile ~1016 `stkGainEur`/`stkLossEur`) nutzt Vorzeichen von `netCashEur` — bei Optionen (Z.21/Z.24) korrekt (Cash-Basis-Prinzip, gegen PWC validiert), bei Aktien aber konzeptionell fragwürdig: ein Aktienkauf hat negativen Cashflow und würde fälschlich als "Verlust" gezählt, obwohl ein Kauf steuerlich nie ein Verlust ist (Gewinn/Verlust entsteht erst beim Verkauf). Gegen Axels echte 2025-Daten verifiziert: alle 46 Aktien-Trades 2025 sind Käufe (0 Verkäufe) — würden nach aktueller Formel alle als Verlust gezählt. Eigene Nachrechnung (-40.057,62 €) stimmt NICHT mit dem von Axel hochgeladenen DOCX überein (-68.868,46 € bei 50%-Anteil) — Diskrepanz ungeklärt, evtl. anderer Datenstand/Zwischenversion. **Anders als Z.21/Z.24 wurde Z.8/Z.9 nie gegen einen PWC-Report validiert.** Axel-Entscheidung 10.08.2026: als eigenständiger, priorisierter Punkt behandeln, NICHT im laufenden Trade-Detail-Report-Sprint nebenbei fixen. **Bis zur Klärung: aktuelle Z.8/Z.9-Werte vor Abgabe manuell gegen die offizielle CapTrader-Jahressteuerbescheinigung prüfen.** Nebenbefund: `_xmlConvertEAE` STK-Assignment setzte bei JEDEM Assignment qty positiv/BUY (falsch bei Call-Assignment, Aktien fließen ab) — gefixt (Commit `1e4dc47d`), betrifft aber laut Datenlage nicht Axels 2025-Konto (0 Call-Assignments dort). Trade-Detail-Report (2.16) selbst: Options-Engine grundlegend überarbeitet (zustandsbasierte Open/Close-Erkennung statt unzuverlässigem `openCloseIndicator`-Feld, s. `ko-tradedetail.js` v1.1.0/Commit `8f85bed5`), gegen echte Daten validiert (Summen matchen SWOT-Referenzkennzahl). |
| 2.5 | 10.08.2026 | **SUITE.md-Ausnahme (Axel-Entscheidung, bewusst):** Maintenance-Mode-Regel (§4 SUITE.md, nur Bugfixes/<1h) für dieses eine Feature durchbrochen. Kontext: Live-Browser-Test kap.html (erstmals seit PDF-Upload-Bau) deckte zwei blockierende SyntaxErrors auf (siehe kap.html-Commits `2c10f5d2`, `2ccff146` — `profile-btn`-Quoting-Fehler seit 08.08./Commit `23678830`, `BASISZINS`-Doppeldeklaration seit 07.08./Commit `ccf79f33`; beide bestanden vor dieser Session, blockierten komplette Skriptausführung). Nach Fix: Axel-Anforderung neues Feature 2.15 — vollständige Trade-Auflistung mit tagesaktuellem EZB-Kurs im Steuerreport, Vorbild BubbleTax-Wettbewerbsprodukt (Anhang A.1–A.5: Einzeltransaktionen inkl. FIFO-Zuordnung, Referenz-IDs, Fremdwährungs-FIFO-Pools je Währung). Kein <1h-Bugfix, echtes Ausbau-Feature — Axel hat Ausnahme bewusst bestätigt. |
| 2.4 | 09.08.2026 | Phase F umgesetzt: kap.html PDF-Upload deterministisch (PDF.js-Textparser statt Claude-API — kein API-Key, kein Drittanbieter-Datenfluss, Bestätigungs-Dialog vor Engine-Übernahme lt. Nicht-Ziel 4). Fallback auf Transaktionsliste bei PWC-Summary-Bug automatisiert. Getestet gegen echte 2023/2024/2025-PDFs, alle Werte exakt. **2.14 erledigt** (Buchungs-Datums-Filter, defensiv, 0 Treffer in Axels Daten) — dabei kritischerer Bug gefunden+gefixt: CashTransaction-Filter nutzte nicht-existentes `activityCode`-Attribut statt `type`, `dividends`-Array war bei echten Daten immer leer (betraf komplette Divi/WHT-Pipeline). |
| 2.2 | 08.08.2026 | Steuerrechtliche Klarstellung: Z.21/Z.24 Cash-Basis §20 EStG (kein FIFO); ko-flex.js v1.3 + kap.html CDN+Badge; 2.13 ENTFÄLLT |
| 2.1 | 08.08.2026 | Vollständige Diskrepanz-Analyse ergänzt: D1a Assignment-Prämien, D1b REIT/Teilfills; Fazit: vollständig aus XML lösbar |
| 2.0 | 08.08.2026 | Dual-Mode-Strategie: Modus A (Cash-Flow/Ergänzung) + Modus B (Eigenberechnung mit Gate-Kriterien) |
| 1.9 | 08.08.2026 | Validierungsbefund 08.08.2026 dokumentiert (D1 Jahresabgrenzung, D2 Split, D3 Korrekturbuchungen); ROADMAP 2.13–2.15 ergänzt |
| 1.8 | 08.08.2026 | 2.8–2.11 als ✅ markiert; 1.3 Feedback-Kanal als ✅ markiert (ahildebrand@me.com + GitHub Issues bereits aktiv) | 2.12 OptionsCoach + OptionsDoktor (SUITE.md №37): KI-Coaching auf Basis Flex-XML + UIQ-Kontext, Lernmuster-Engine, Trigger 01.10.2026 | `flex_client.py` (automatisierter Python-Pull via Flex Web Service, `.env`-Credentials) + 2.11 `ko-flex-proxy` CF Worker (CORS-Bridge für Browser-Pull); Reihenfolge-Logik 2.10+2.11 parallel zu 2.8 ergänzt | (CSV-Deprecation-Strategie, `ko-flex.js`-Stub dokumentiert, Abhängigkeit für 2.9) + 2.9 Trade-Journal-Modul (Architektur-Entscheidung: Journal in Refundex, nicht UIQ; Spezifikation `docs/DATENMODELL_JOURNAL.md` v1.0); Reihenfolge-Logik 2.8→2.9 ergänzt |
| 1.4 | 03.07.2026 | 1.2 ✅ guide.html erstellt (Belegketten-Hero, Flex-Query-Setup, 5-Schritte-Bedienung, 4-Punkte-Haftungsblock, FAQ inkl. Lynx + QSt-Ausblick); kap.html v140 mit Leitfaden-Link im Banner |

---

## Validierungsbefund 08.08.2026 — XML-Parser vs. PWC German Tax Report

**Quelle:** Vergleich 2024_Complete.xml gegen U12074449_2024_PWC_DE_2.pdf (Ground Truth)

### Drei strukturelle Diskrepanzen identifiziert

**D1 — Jahresabgrenzung (gravierendste):**
Der XML-Parser erfasst alle netCash-Flows des Kalenderjahres.
PWC meldet nur **abgeschlossene Positionen** (FIFO-gematchte SELL+BUY-Paare
die beide im selben Steuerjahr liegen).
Positionen die am 31.12. noch offen sind → kommen NICHT in den PWC-Report,
tauchen aber vollständig im XML auf.

Beispiel 2024: XML Optionen-Netto 8.689 EUR vs. PWC Gains 6.094 - Losses 1.749 = 4.344 EUR.
Die 4.345 EUR Differenz erklärt sich durch Positionen die 2025 geschlossen wurden
(z.B. NVO 21MAR25 95P, AMSC 21FEB25 26P, AMSC 21FEB25 32C, VST 17JAN25 160C).

**D2 — Gemeinschaftskonto-Split:**
PWC erstellt getrennte Reports pro Inhaber (Axel / Christa F. Hildebrand) mit
je 50% der gemeinsamen Kapitalerträge. Der XML-Parser liefert 100% (Gesamtkonto).
Refundex muss den 50%-Anteil NACH der Berechnung anwenden (Projektions-Schicht
`projiziereErgebnis()` tut das bereits — aber nur für Z.18/Z.19, nicht für Z.21/Z.24).

**D3 — Jahresübergreifende Korrekturbuchungen:**
Das 2024-XML enthält WHT-Stornobuchungen aus 2023/2025 (z.B. O-Dividenden
mit dateTime aus 2024 aber settlement aus 2023). PWC schneidet hart am 01.01./31.12.
ab. XML-Parser muss diese identifizieren und ausschließen.

### Vollständige Diskrepanz-Analyse (08.08.2026, Python-Test)

**Algorithmus:** FIFO-Stack mit OptionEAE-Integration gegen PWC 2024:

| Schließungstyp | Anzahl | Gains EUR | Losses EUR | PWC-Behandlung |
|---|---|---|---|---|
| Trade (BUY) | 46 | +6.649 | −1.850 | Z.21 / Z.24 ✅ |
| Expiration (wertlos) | 1 | +129 | 0 | Z.21 ✅ |
| Assignment (Zuteilung) | 5 | +683 | 0 | ⚠️ NICHT Z.21! |
| **Summe** | **52** | **+7.461** | **−1.850** | |
| **PWC** | | **+6.094** | **−1.749** | |
| **Differenz** | | **+1.367** | **−101** | |

**D1a — Assignment-Prämien (größte Einzelursache):**
PWC-Note p.31: *"Premiums received on the grant of an option are reported separately
to any purchase or sale that takes place as a result of the option being exercised."*
→ Bei CSP-Assignment: die Prämie (683 EUR in 2024) reduziert die Anschaffungskosten
der zugeteilten Aktien und erscheint in Z.20 (Aktiengewinne), NICHT in Z.21.
→ Fix: `isAssignmentPremium`-Flag auf SELL-Legs die via Assignment geschlossen werden.

**D1b — Verbleibende Differenz (684 EUR Gains, 101 EUR Losses):**
Wahrscheinlich AMSC 250117P00031000 (doppelter FIFO-Eintrag wegen Teilfills)
und Realty Income/O (REIT → KAP-INV Z.8, nicht Z.21).
Erfordert weiteren Test-Zyklus nach D1a-Fix.

**Steuerrechtliche Klarstellung (08.08.2026, nach Python-Test):**
§20 Abs.1 Nr.11 EStG: Stillhalterprämie = sofort Z.21 im Jahr der Einnahme (Cash-Basis).
§20 Abs.2 S.1 Nr.3 EStG: Schließungskosten = Z.24 im Jahr der Zahlung (Cash-Basis).
→ Kein FIFO-Matching nötig. Z.21 = SELL-netCashEur, Z.24 = BUY-netCashEur.
→ Validiert vs. PWC 2024: Δ = 0,01 EUR (Rundung).
→ ROADMAP 2.13 (FIFO-Tracker) entfällt. 2.14/2.15 parken bis Bedarf klar.
Implementiert: ko-flex.js v1.3 + kap.html (CDN-Hash, Modus-A-Badge).

**Zwischenfazit: Die Lösung ist vollständig aus XML-Daten umsetzbar.**
BubbleTax macht dasselbe — kein Datenzugriff den wir nicht haben.
Implementierungsaufwand: 3–4 Sessions für Modus-B-Gate.

### Auswirkung auf die aktuelle Engine

| Posten | XML-Parser 2024 | PWC 2024 (je Inhaber) | Faktor |
|---|---|---|---|
| Opt-Gewinne (Z.21) | 8.689 EUR netto | 6.094 EUR | D1 |
| Opt-Verluste (Z.24) | (in Netto enthalten) | 1.749 EUR | D1 |
| Dividenden (Z.7+Z.19) | 2.046 EUR | 860 EUR (50%) | D2+D3 |
| Quellensteuer (Z.41) | 246 EUR | 59 EUR (50%) | D2+D3 |
| Aktiengewinne (Z.20) | ✅ korrekt | 4.099 EUR | — |

### Lösungsarchitektur (→ ROADMAP 2.14–2.15)

~~**Stufe 1 (2.13) — FIFO-Positions-Tracker:**~~ **ENTFÄLLT** — steuerrechtliche
Klarstellung 08.08.2026: §20 Abs.1 Nr.11 EStG = Cash-Basis, kein FIFO-Matching
nötig. Validiert gegen PWC 2024 (Δ=0,01 EUR), bestätigt über alle drei Jahre
(Gegenprüfung 09.08.2026, Details unten).

**Stufe 2 (2.14) — Buchungs-Datums-Filter:** Korrekturbuchungen erkennen
(negative WHT im Folgejahr, Revenue-Storno), aus dem Abrechnungsjahr ausschließen.
**Status: weiterhin offen, noch nicht implementiert.**

**Stufe 3 (2.15) — Gains/Losses-Auftrennung:** Im Kern durch Cash-Basis-Formel
(Z.21 = SELL-netCash, Z.24 = BUY-netCash) bereits miterledigt — Trennung
ergibt sich direkt aus der Formel. 20k-Cap-Logik (§20 Abs.6 Satz 5)
muss noch als Anzeige in kap.html ergänzt werden, wenn Z.24 > 20.000 EUR.

## Architekturentscheidung 08.08.2026 — Dual-Mode-Strategie

**Kontext:** Validierungsbefund 08.08.2026 zeigt drei strukturelle Diskrepanzen
zwischen XML-Parser und PWC German Tax Report (D1 Jahresabgrenzung,
D2 Gemeinschaftskonto-Split, D3 Korrekturbuchungen).

**Entscheidung (Axel, 08.08.2026):** Beide Modi parallel entwickeln.

### Modus A — Ergänzungs-Modus (sofort nutzbar, immer verfügbar)

XML-Parser liefert **Rohdaten und Plausibilitätsprüfung** neben dem PWC-Report.
PWC bleibt Goldstandard für die Steuererklärung — **aber:** Gegenprüfung
09.08.2026 hat gezeigt, dass PWC selbst Darstellungsfehler enthalten kann
(s. „PWC-Summary-Bug 2025" unten). Modus A dient damit auch als
Qualitätskontrolle des PWC-Reports.

Nutzen: Schnelle Jahresübersicht, Plausibilitätsprüfung PWC, Journal-Befüllung,
QSt-Cockpit, OptionsDoktor-Datenbasis. Keine FIFO-Jahresabgrenzung nötig —
explizit als "laufende Cash-Flows" deklariert.

**UI-Signal:** Badge "📊 Cash-Flow-Ansicht — für Steuererklärung PWC-Report verwenden"

**Beta-User-Anforderung (ergänzt 09.08.2026):** Nutzer müssen **zwei Dateien**
hochladen: (1) Flex-XML-Export und (2) PWC German Tax Report als PDF.
Begründung: Nur so ist die Cross-Validierung beider Quellen möglich, und der
PWC-Summary-Bug (s. u.) zeigt, dass weder XML allein noch PDF allein ausreicht.
kap.html benötigt daher einen zweiten Upload-Button für PDF mit automatischem
Line-21/24-Extraktor (Layout-Text-Parsing aus dem Summary-Block, Dateiformat-
Erkennung PDF/XML getrennt). Die PDF wird nur clientseitig geparst (kein Upload
auf Server, Datensouveränität).

### Modus B — Eigenberechnungs-Modus (Entwicklungsziel, schrittweise)

Refundex berechnet Z.21/Z.24 eigenständig auf PWC-Niveau.
Freischaltung erst wenn Gegenprüfung ≤ 5 EUR Abweichung über 3 Steuerjahre.

**Gate-Kriterien für Modus-B-Aktivierung (bereinigt 09.08.2026):**

| Kriterium | Schwelle | Status |
|---|---|---|
| ~~D1 FIFO-Jahresabgrenzung (2.13)~~ | ~~implementiert + getestet~~ | ~~ENTFÄLLT~~ (Cash-Basis, kein FIFO) |
| Cash-Basis-Formel Z.21/Z.24 | Δ ≤ 1 EUR gegen PWC | ✅ implementiert (ko-flex.js v1.3) |
| D2 Split korrekt auf Z.21/Z.24 | implementiert | ⏳ offen |
| D3 Korrekturbuchungen gefiltert (2.14) | implementiert | ⏳ offen |
| Gegenprüfung 2023 | ≤ 5 EUR Abweichung | ✅ bestätigt (0 Opt-Trades, PWC = 0,00 €) |
| Gegenprüfung 2024 | ≤ 5 EUR Abweichung | ✅ bestätigt (Z.21 Δ=0,01 €, Z.24 Δ=0,00 €) |
| Gegenprüfung 2025 | ≤ 5 EUR Abweichung | ✅ bestätigt (Z.21 Δ=0,06 €, Z.24 Δ=0,11 €) — Achtung: PWC-Summary fehlerhaft (s. u.), Validierung gegen Transaktionsliste |

**Disclaimer Modus B (StBerG-konform):**
"Refundex-Eigenberechnung — nicht geprüft durch Steuerberater.
Vergleich mit CapTrader-Steuerbescheinigung empfohlen."

### Implementierungsreihenfolge (bereinigt 09.08.2026)

```
Phase A (sofort): Modus A explizit deklarieren + UI-Badge            ✅ erledigt
Phase B (2.13):   ENTFÄLLT — Cash-Basis statt FIFO                   ✅ erledigt
Phase C (2.14):   Buchungs-Datums-Filter — WHT-Korrekturen           ⏳ offen
Phase D (2.15):   20k-Cap-Anzeige in kap.html (bei Z.24 > 20k)      ⏳ offen
Phase E:          Gegenprüfung 3 Jahre → Modus-B-Gate                ✅ bestätigt
Phase F (neu):    PDF-Upload + Cross-Validierung (s. Beta-Anforderung)  ⏳ offen
```


## Gegenprüfung 09.08.2026 — XML Cash-Basis vs. PWC alle 3 Steuerjahre

**Methodik:** Cash-Basis-Formel (Z.21 = SELL-netCash × fxRateToBase,
Z.24 = BUY-netCash × fxRateToBase) aus ko-flex.js v1.3 angewendet auf
`2023_Complete.xml`, `2024_Complete.xml`, `2025_Complete.xml`. Verglichen gegen
PWC German Tax Reports (`U12074449.YYYY.PWC_DE.pdf`).

Voraussetzung bestätigt: **Alle Options-Trades in allen drei Jahren sind
ausschließlich Stillhaltergeschäfte** (SELL mit qty<0 = Short-Open,
BUY mit qty>0 = Close/Rückkauf). Keine einzige Long-Options-Position
(BUY+Open) in 2023–2025. Die Cash-Basis-Formel ist damit strukturell
korrekt für den tatsächlichen Trading-Stil, nicht nur zufällig.

### Ergebnisse

| Jahr | Trades | XML Z.21 (je Inh.) | PWC Line 21 | Δ Z.21 | XML Z.24 (je Inh.) | PWC Line 24 | Δ Z.24 |
|---|---|---|---|---|---|---|---|
| 2023 | 0 | 0,00 € | 0,00 € | 0,00 € | 0,00 € | 0,00 € | 0,00 € |
| 2024 | 109 | 6.093,84 € | 6.093,85 € | **0,01 €** | 1.749,37 € | 1.749,37 € | **0,00 €** |
| 2025 | 284 | 21.909,53 € | ⚠️ *fehlt* | 0,06 €* | 20.272,54 € | ⚠️ *falsche Zeile* | 0,11 €* |

*\*2025-Deltas gegen Transaktionsliste im PWC-PDF (nicht gegen Summary, s. Bug unten).*

### PWC-Summary-Bug 2025

Der PWC German Tax Report für 2025 (`U12074449.2025.PWC_DE 3.pdf`, 102 Seiten,
51 Seiten je Inhaber) weist im Summary-Block auf Seite 1 einen **Darstellungsfehler** auf:

1. **Line 21 („income from trading in derivatives") fehlt komplett** — nicht
   als 0,00 € aufgeführt wie bei echten Nullwerten, sondern die Zeile selbst
   wird nicht generiert. Die ~21.910 € Prämieneinnahmen (je Inhaber) sind
   nur in der Transaktionsliste (ca. 2.300 Zeilen, „Sell to Open" / „Buy to Close")
   weiter hinten im Dokument auffindbar.

2. **Line 22 zeigt 20.273,83 €** als „losses from the disposal of non-share capital"
   — das ist fast exakt der Rückkaufkosten-Wert (XML: 20.272,54 € je Inhaber,
   Δ=1,29 €), gehört aber auf **Line 24** („losses from trading in derivatives"),
   nicht auf Line 22 (die betrifft Nicht-Aktien-Kapitalanlagen, z. B. Anleihen).

**Gegenprüfung:** Manuelle Summierung aller 144 „Sell to Open" + 135 „Buy to Close"
Zeilen im Transaktionsblock des PDF ergibt:

| | PDF-Transaktionsliste | XML (je Inhaber) | Δ |
|---|---|---|---|
| Prämien (Sell to Open) | 21.909,59 € | 21.909,53 € | 0,06 € |
| Rückkauf (Buy to Close) | 20.272,65 € | 20.272,54 € | 0,11 € |

**→ XML-Berechnung ist korrekt; der Bug liegt im PWC-Report-Generator.**

**Konsequenz für Refundex:**
- Modus A (Plausibilitätsprüfung) hat damit seinen Wert konkret bewiesen:
  ein echter PWC-Fehler wäre ohne XML-Gegenprüfung unentdeckt geblieben.
- **Beta-User müssen neben der Flex-XML auch den PWC German Tax Report als
  PDF hochladen.** kap.html benötigt einen zweiten Upload-Button mit
  automatischem Line-21/24-Extraktor (clientseitiges PDF-Text-Parsing).
  Nur so kann die Cross-Validierung „XML gegen PDF" stattfinden, die bei
  diesem Bug-Typ den Nutzer vor falschen Steuererklärungswerten schützt.
  Die PDF wird nur clientseitig geparst (Datensouveränität, kein Server-Upload).

### Performance-Auffälligkeit 2025

Rückkauf/Prämien-Verhältnis 2025: **92,5 %** (40.545/43.819 EUR Gesamtkonto)
vs. 2024: **28,7 %** (3.499/12.188 EUR). D. h. 2025 wurden verhältnismäßig
deutlich mehr Positionen mit Verlust zurückgekauft — Axel-Einordnung:
„zu viele schlechte Options-Trades, das war der Beweggrund für dieses Projekt."
Dieser Befund ist ein konkreter Datenpunkt für die OptionsDoktor-Lernmuster-
Engine (ROADMAP 2.12 / SUITE.md №37, Trigger 01.10.2026).

## 🔴 KRITISCHER BEFUND 10.08.2026 — Z.8/Z.9-Formel Aktien unvalidiert (2.17)

**Status: OFFEN, ungeklärt. Axel-Entscheidung: eigenständig behandeln, nicht
im Trade-Detail-Report-Sprint nebenbei fixen.**

### Befund

`ko-flex.js` (Zeile ~1016, `stkGainEur`/`stkLossEur` innerhalb der
`yearlyResults`-Konstruktion in `parseActivityXML`) bestimmt Z.8/Z.9
(Aktienveräußerungsgewinne/-verluste) über das **Vorzeichen von
`netCashEur`** — dasselbe Cash-Basis-Prinzip, das bei Optionen (Z.21/Z.24)
steuerlich korrekt ist (Stillhalterprämie ist im Zuflussjahr sofort
Einkommen, § 20 Abs. 1 Nr. 11 EStG).

Bei **Aktien** ist dieses Prinzip aber konzeptionell fragwürdig: Ein
Aktienkauf hat einen negativen Cashflow (Geld fließt ab) — die aktuelle
Formel würde das als "Verlust" zählen, obwohl ein Kauf steuerlich niemals
ein Verlust ist. Der Gewinn/Verlust entsteht erst beim späteren Verkauf,
als Differenz aus Veräußerungserlös und Anschaffungskosten (FIFO), nicht
aus der Kauf-Cashflow-Richtung.

Ein Code-Kommentar eine Zeile über der Formel behauptet "IBKR
FifoPnlRealized × FXRateToBase" — tatsächlich verwendet wird aber
`netCashEur`, nicht `fifoPnlEur`. Kommentar und Code stimmen nicht überein.

### Verifikation gegen echte Daten (10.08.2026, Node+jsdom, Axels
2023-2025-XML-Dateien)

- Alle **46 Aktien-Trades im Steuerjahr 2025 sind Käufe** — 0 Verkäufe.
- Nach der aktuellen Formel würden **alle 46** als Verlust gezählt
  (negativer Cashflow bei jedem Kauf).
- Eigene Nachrechnung der Summe: **-40.057,62 €**.
- **Stimmt NICHT** mit dem von Axel hochgeladenen DOCX-Begleitdokument
  überein (Z.9 = -68.868,46 € bei 50%-Anteil, entspräche ~-137.736,92 €
  Vollkonto). Diskrepanz **ungeklärt** — möglicherweise wurde das DOCX mit
  einem anderen Datenstand oder einer Zwischenversion aus der laufenden
  Session erzeugt. Muss vor jeder Korrektur der Formel selbst geklärt
  werden, sonst besteht Gefahr einer Verschlimmbesserung.

### Wichtige Abgrenzung

**Anders als Z.21/Z.24 (Optionen) wurde Z.8/Z.9 (Aktien) nie gegen einen
PWC German Tax Report validiert.** Die in ROADMAP 2.3/2.4 dokumentierte
Gegenprüfung (Δ=0,01–0,11 €) bezog sich ausschließlich auf die
Options-Formel. Für Aktien fehlt diese Validierung komplett — dieser Fund
entstand zufällig beim Debuggen des Trade-Detail-Reports (2.16), nicht
durch gezielte Prüfung.

### Bis zur Klärung

**Axel: aktuelle Z.8/Z.9-Werte vor Abgabe der Steuererklärung 2025 manuell
gegen die offizielle CapTrader-Jahressteuerbescheinigung abgleichen.**

### Governance-Einordnung (Axel-Entscheidung, 10.08.2026)

Als **Bugfix an bestehender, bereits ausgelieferter Berechnung** eingestuft
— fällt unter die im Refundex-Maintenance-Modus (SUITE.md §4) jederzeit
erlaubten "Bugfixes und Kleinstaufgaben", die §4-Wirbelsäulen-Regel (nur
Recherche/Doku, kein Bau vor UIQ Phase 1) greift hier NICHT. Damit
unterscheidet sich dieser Punkt bewusst von 2.15/2.16 (Trade-Detail-Report),
die als echte Ausbauarbeit eine explizite Ausnahme brauchten.

### Nächste Schritte (nicht in dieser Session begonnen)

1. Diskrepanz zwischen eigener Nachrechnung und DOCX-Wert aufklären
   (welcher Datenstand erzeugte das hochgeladene DOCX?).
2. Klären, ob eine echte FIFO-Gewinn/Verlust-Berechnung für Aktien nötig
   ist (ggf. Wiederaufnahme von `ko-fifo.js`, s. dortige Dormant-Notiz vom
   25.06.2026) oder ob IBKRs `FifoPnlRealized`-Feld direkt nutzbar ist
   (das Feld existiert pro Trade, wird aber aktuell für die
   `yearlyResults`-Aggregation nicht verwendet).
3. Gegenprüfung gegen PWC German Tax Report 2023/2024/2025 für Z.8/Z.9,
   analog zur bereits erfolgten Z.21/Z.24-Gegenprüfung.

### Nebenbefund (bereits behoben)

`_xmlConvertEAE` (STK-Assignment-Events aus der OptionEAE-Sektion) setzte
bei **jedem** Assignment `qty` positiv und `buySell:'BUY'` — korrekt für
Put-Assignment (Aktien fließen zu), aber falsch für Call-Assignment (Aktien
fließen ab, wäre ein Verkauf). Gefixt in Commit `1e4dc47d`. Betrifft laut
Datenlage NICHT Axels 2025-Konto (0 Call-Assignments dort, nur 5
Put-Assignments) — daher auch nicht die Ursache der obigen Diskrepanz,
aber ein reeller, unabhängig sinnvoller Fix für andere Jahre/Konten.
