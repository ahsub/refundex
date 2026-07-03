# Refundex — Roadmap

**Version:** 1.0
**Stand:** 03.07.2026
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
| 1.1 | **Disclaimer-Verstärkung (4 Punkte)** — (a) No-Guarantee-Klausel, (b) Steuerberater-Klausel geschärft, (c) Basiszins-/Rechtsstand-Unsicherheit sichtbar, (d) explizite Nicht-Abdeckungsliste (Krypto, Edelmetalle, betriebliche Erträge) | Sichtbar in App + Report + guide.html | StBerG-Pflicht, vor allem anderen |
| 1.2 | **`guide.html`** — integrierter Leitfaden: Featureliste, Haftungshinweise, Schritt-für-Schritt Flex-Query-Einrichtung (197-Zeichen-Prompt), Bedienung, Grenzen | Ein Neuling kommt ohne Rückfragen vom leeren Depotauszug zum KAP-Ergebnis | 80/20: größter Hebel für Beta-Tauglichkeit |
| 1.3 | **Feedback-Kanal real** — Platzhalter `feedback@refundex.de` durch funktionierende Adresse oder GitHub-Issues-only ersetzen | Eingehende Meldung erreicht Axel nachweislich | Beta-Voraussetzung |
| 1.4 | **§23 EStG-Randfälle dokumentieren** — physische Edelmetalle (1-Jahres-Frist), Alt-Krypto (vor 2025): zunächst nur als Hilfe-Modul + Nicht-Abdeckungshinweis (Anlage SO, persönlicher Steuersatz) | Hilfe-Modul online; Berechnung erst Phase 3 | 80/20: dokumentieren jetzt, rechnen später |
| 1.5 | **`docs/RUNBOOK.md`** — Bus-Factor-Dokument analog UIQ: Systemlandkarte, Repo-/Deploy-Wege, Steuerjahr-Update-Prozess, Disaster Recovery | Ein technikaffiner Dritter kann das System betreiben | W1-Gegenmaßnahme |
| 1.6 | **Steuerjahr-Update-Checkliste** — jährlicher Prozess: Basiszins (BMF-Schreiben Januar), Sparer-Pauschbetrag, Rechtsänderungs-Review §20/§18/§23, Testlauf gegen Vorjahres-Referenzdaten | Checkliste in RUNBOOK.md, erstmals durchlaufen für Steuerjahr 2026 | W4-Gegenmaßnahme |
| 1.7 | **Beta-Testrunde** — Versand an 3–5 IBKR/CapTrader-Nutzer (Investmentclub), Feedback-Zyklus, Abgleich gegen deren Steuerbescheinigungen | ≥ 3 Fremd-Depots erfolgreich abgeglichen | Validierung jenseits des Eigen-Depots |

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

**Reihenfolge-Logik:** 2.1 vor 2.2 — erst die Wertequelle vereinheitlichen, dann die Fassade modularisieren. Sonst wird Doppel-Logik mitmigriert.

---

## Phase 3 — Erweiterung unter 80/20-Vorbehalt (2027)

**Ziel:** Nische verbreitern, ohne die Kernqualität zu verwässern. Jedes Item einzeln durch den Vier-Fragen-Filter; kein Item ist gesetzt.

| # | Kandidat | 80/20-Einschätzung |
|---|---|---|
| 3.1 | **§23-Berechnung (Anlage SO)** — Edelmetalle, Alt-Krypto, Devisengewinne konsolidiert | Mittlerer Aufwand, klar abgrenzbar; Devisen-Grundlage existiert bereits |
| 3.2 | **Steuerjahr 2026-Release** — Basiszins 3,20 % ist integriert; Pflichtdurchlauf der Update-Checkliste (1.6) | Geringer Aufwand, jährlicher Pflichttermin Q1 2027 |
| 3.3 | **Multi-Broker-Prüfung** — Lynx (baugleich IBKR: trivial), andere Broker nur bei nachgewiesener Nachfrage | Lynx ja; alles andere: erst Nachfrage, dann Code |
| 3.4 | **Suite-Cross-Verlinkung** — dezenter Verweis UIQ ↔ Refundex (identische Zielgruppe) | Minimaler Aufwand; Formulierung StBerG-/BaFin-sauber halten |
| 3.5 | **Monetarisierungs-Entscheidung** — frei / Spende / Freemium; erst nach Beta-Feedback (1.7) entscheiden | Entscheidung, kein Code; Impressums-/AGB-Fragen dann klären |
| 3.6 | **i18n-Vorbereitung** | ⚠️ Anders als bei UIQ vorerst **nein**: deutsches Steuerrecht ist das Produkt, EN-Version hätte kaum Zielgruppe. Nur String-Zentralisierung (2.2) als Option offen halten |

---

## Nicht-Ziele (bewusst verworfen)

Diese Liste ist Teil der Roadmap, damit sie nicht in jeder Session neu diskutiert wird:

1. **ELSTER-Direktschnittstelle (ERiC)** — Zertifizierungs- und Haftungsaufwand ohne Verhältnis zum Nutzen; der manuelle Übertrag per Checkliste ist der 80/20-Weg.
2. **Steueroptimierungs-Empfehlungen** (Tax-Loss-Harvesting-Vorschläge o. Ä.) — StBerG-Grenze, Filter-Frage 4 dauerhaft negativ.
3. **Server-seitige Depotdaten-Verarbeitung** — widerspricht Kernversprechen Datensouveränität (S4).
4. **KI-berechnete Steuerwerte** — No-Hallucination-Gebot; KI bleibt auf Erklären/Formulieren beschränkt.
5. **Vollständigkeit aller Exoten** (strukturierte Produkte, Wertlos-Ausbuchungs-Sonderfälle jenseits der Engine-Abdeckung) — dokumentierte Grenze + Steuerberater-Verweis statt Feature.

---

## Fortschreibungshistorie

| Version | Datum | Änderung |
|---|---|---|
| 1.0 | 03.07.2026 | Erstfassung: Ist-Stand, Phasen 1–3, Nicht-Ziele |
