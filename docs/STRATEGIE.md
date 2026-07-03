# Refundex — Strategiedokument

**Version:** 1.1
**Stand:** 03.07.2026
**Ablage:** `ahsub/refundex/docs/STRATEGIE.md`
**Fortschreibung:** Claude versioniert dieses Dokument (v1.1, v1.2 …) bei jeder strategischen Weichenstellung und pusht es mit ins Repo — analog zu `ahsub/ko-aggregator/docs/STRATEGIE.md` (UnderlyingIQ).

---

## 1. Leitbild

**Refundex holt deutschen Privatanlegern ihr Geld zurück — auf zwei Säulen.**

**Säule 1 — Anlage KAP (IBKR-basierte Broker):** Ausländische Broker führen keine deutsche Abgeltungsteuer ab. Wer dort handelt, muss die Anlage KAP selbst befüllen — aus Rohdaten, die IBKR in einem Format liefert, das kein deutsches Steuerformular kennt. Refundex schließt diese Lücke:

> **Flex Query rein → geprüfte, zeilengenaue KAP-Werte raus.**

**Säule 2 — Ausländische Quellensteuer-Rückholung (broker-neutral):** Auf Auslandsdividenden wird oft mehr Quellensteuer einbehalten, als in Deutschland anrechenbar ist (z. B. CH 35 % einbehalten, 15 % anrechenbar). Der Überschuss ist im Quellenland rückforderbar — die meisten Anleger lassen ihn verfallen. Refundex macht das Rückholpotenzial sichtbar und den Weg dorthin gangbar:

> **Ertragsdaten rein → Rückholpotenzial je Land, Frist und Verfahrensweg raus.**

Säule 2 löst den Produktnamen ein — und sie ist bewusst **nicht auf IBKR beschränkt**: Über ein broker-neutrales Datenmodell (§2, Grundgesetz 6) erreicht sie perspektivisch jeden deutschen Anleger mit Auslandsdividenden, unabhängig von der Depotbank.

Beide Säulen folgen derselben Wertschöpfungskette in vier Stufen (analog zum UIQ-Strategie-Router):

| Stufe | Säule 1 (KAP) | Säule 2 (QSt-Rückholung) | UIQ-Pendant |
|---|---|---|---|
| 1 | **Datenextraktion** (Flex Query, deterministischer Parser) | **Daten-Adapter** (Flex Query / manuelle Erfassung / später PDF) | Regime-Erkennung |
| 2 | **Steuerliche Klassifikation** (Töpfe, §20 Abs. 6, §18 InvStG) | **Länder-Klassifikation** (Quellenland, DBA-Anrechnungssatz, Frist) | Strategie-Routing |
| 3 | **Berechnung** (FIFO, Verlustverrechnung, Vorabpauschale, Projektion) | **Rückholpotenzial** (einbehalten − anrechenbar = Überschuss) | Underlying-Auswahl |
| 4 | **Formular-Output** (zeilengenaue KAP-Werte, Checkliste, Report) | **Verfahrens-Output** (Cockpit, Verfahrenslink, später Formular-Vorbefüllung) | Instrumenten-Vorschlag |

Was Refundex bewusst **nicht** ist: keine Steuerberatung, keine ELSTER-Direktschnittstelle, keine Steueroptimierungs-Empfehlung. Refundex ist ein **Rechenwerk mit Belegkette** — jeder ausgewiesene Wert ist auf eine IBKR-Datenzeile oder eine dokumentierte Rechtsquelle (BMF-Schreiben, Gesetzesnorm) rückführbar.

### Kernversprechen

1. **Determinismus:** Gleiche Eingabe → gleiches Ergebnis. Der Rechenkern (Python-Engine v4, 99/99 Tests) arbeitet ohne jede KI-Schätzung.
2. **Belegkette:** Jede Zahl trägt ihre Quelle (Flex-Datenzeile, BMF-GZ, Paragraph).
3. **Datensouveränität:** Browser-first, keine Übertragung von Depotdaten an Server.
4. **Ehrliche Grenzen:** Was Refundex nicht abdeckt (Krypto, physische Edelmetalle, betriebliche Kapitalerträge), steht explizit im Disclaimer — nicht im Kleingedruckten.

---

## 2. Positionierung: Modul der Investment-Suite

Refundex und UnderlyingIQ sind **zwei Module einer gemeinsamen Investment-Suite** mit komplementären Rollen im Anlegerzyklus:

```
        ┌─────────────────────────────────────────────┐
        │              INVESTMENT-SUITE                │
        │                                             │
        │   UnderlyingIQ          Refundex            │
        │   (Vorne: Entscheiden)  (Hinten: Abrechnen) │
        │   Regime → Strategie →  Flex → Töpfe →      │
        │   Underlying → Instr.   FIFO → KAP          │
        │                                             │
        │   Gemeinsame Infrastruktur:                 │
        │   • ko-modules (CDN, ES6)                   │
        │   • Hilfe-System (refundex-docs/index.json) │
        │   • Cloudflare Workers/KV-Stack             │
        │   • Compliance-by-Design-Prinzip            │
        └─────────────────────────────────────────────┘
```

### Suite-Grundgesetze (für beide Module verbindlich)

1. **Streng-modularer Aufbau ist oberstes Prinzip.** Kein Modul kennt Interna des anderen; Austausch nur über definierte Schnittstellen (JSON-Kontrakte, CDN-Module). Der Rechenkern (Python) und die Präsentationsschicht (Browser) bleiben strikt getrennt.
2. **ES6-Konformität als Zielarchitektur.** Neue Frontend-Module ausschließlich ES6 (const/let, Arrow Functions, zentrale String-Objekte für i18n, keine Inline-Handler, JSDoc-Typen). Bestandscode (`kap.html`) wird schrittweise migriert, nicht big-bang.
3. **80/20-Vorbehalt für jedes neue Feature.** Ein Feature kommt nur, wenn 20 % Aufwand ≥ 80 % des Nutzerwerts liefern. Randfälle werden dokumentiert und an den Steuerberater verwiesen statt implementiert.
4. **No-Hallucination-Gebot auf allen Ebenen.** Steuerliche Werte entstehen nur deterministisch (Parser + Engine). KI darf erklären und formulieren, aber niemals rechnen, schätzen oder Rechtsquellen erfinden. Jeder Basiszins, jede Quote, jeder Paragraph mit dokumentierter Quelle (z. B. BMF 13.01.2026, GZ IV C 1 - S 1980/00230/012/001).
5. **Compliance by Design im Anwenderbereich** (Detail in §4).
6. **Broker-Neutralität über Datenmodell (Säule 2).** Die Quellensteuer-Logik setzt niemals direkt auf einem Broker-Format auf, sondern auf einem **Normalisierten Ertragsdatenmodell** (je Ertrag: ISIN, Quellenland, Datum, Brutto, einbehaltene QSt, Währung). Davor sitzen austauschbare Adapter: (1) Flex Query (IBKR/CapTrader/Lynx, automatisch), (2) manuelle Erfassung (jede Depotbank, ab Tag 1), (3) perspektivisch PDF-Extraktion — letztere ausschließlich im Strict-Extraction-Muster mit Fundstellen-Zitat und zeilenweiser Nutzer-Bestätigung (Review-Gate, Muster GuidelineIQ): KI schlägt vor, Mensch verifiziert, Engine rechnet. Niemals stille Übernahme.

---

## 3. SWOT-Analyse

### Stärken (intern)

| # | Stärke | Beleg |
|---|---|---|
| S1 | **Getesteter deterministischer Rechenkern** — Python-Engine v4 mit 99/99 pytest-Tests über sechs Testdateien (FIFO, Termingeschäfte, Verlusttöpfe, Vorabpauschale, Kapitalmaßnahmen) | `build_report.py` v4 |
| S2 | **Echte Nischenkompetenz** — Drei-Töpfe-Architektur inkl. 20.000-€-Cap, Verlustvortrag, Projektions-Schicht für Gemeinschaftskonten: Tiefe, die generische Steuersoftware für IBKR-Daten nicht bietet | `verlusttoepfe.py`, `projiziereErgebnis()` |
| S3 | **Validierung gegen Realität** — Drei Jahre echte Depotdaten (2023–2025) gegen CapTrader-Steuerbescheinigungen abgeglichen | Sessions 06/2026 |
| S4 | **Datenschutz als Architektur** — Browser-first, keine Depotdaten auf Servern; in der Zielgruppe ein hartes Kaufargument | kap.html |
| S5 | **Suite-Synergie** — Hilfe-System, CDN-Muster, Worker-Stack und Arbeitsprotokoll mit UIQ geteilt; Entwicklungskosten amortisieren sich doppelt | refundex-docs |
| S6 | **Domänen-Doppelkompetenz des Inhabers** — eigener Anwendungsfall (CapTrader, Gemeinschaftskonto, Wheel-Strategie) = eingebauter Realitätstest jedes Features | — |

### Schwächen (intern)

| # | Schwäche | Konsequenz |
|---|---|---|
| W1 | **Bus-Faktor 1** — wie bei UIQ: eine Person mit Gesamtsystemwissen | RUNBOOK.md analog UIQ (Roadmap Phase 1) |
| W2 | **Zwei Rechenwelten** — Browser-Logik (kap.html) und Python-Engine (v4) existieren parallel; Drift-Risiko bei Gesetzesänderungen | Konsolidierung: Engine als Single Source of Truth (Roadmap Phase 2) |
| W3 | **Monolithisches Frontend** — kap.html (v138) ist gewachsen, nicht ES6-modular | Schrittweise Migration nach UIQ-v2.0-Muster |
| W4 | **Jährlicher Pflege-Zwang** — Basiszins, Freibeträge, Rechtsänderungen (z. B. §20 Abs. 6-Rechtsprechung) erfordern verlässlichen Update-Prozess | Steuerjahr-Update-Checkliste (Roadmap Phase 1) |
| W5 | **Beta-Infrastruktur unvollständig** — Feedback-Adresse Platzhalter, guide.html fehlt, Disclaimer in vier Punkten zu schwach | Roadmap Phase 1, höchste Priorität |

### Chancen (extern)

| # | Chance | Einordnung |
|---|---|---|
| O1 | **Wachsende Zielgruppe** — IBKR/CapTrader/Lynx-Nutzerbasis in DE wächst; jeder Neukunde hat das KAP-Problem ab Jahr 1 | Strukturell |
| O2 | **Schmerz ist jährlich wiederkehrend** — kein Einmal-Tool, sondern jährlicher Anlass zur Wiederkehr (Retention eingebaut) | Geschäftsmodell-relevant |
| O3 | **Kein direkter Wettbewerber in der Nische** — generische Steuersoftware kann Flex Queries nicht lesen; Steuerberater sind teuer und IBKR-fremd | Zeitfenster nutzen |
| O4 | **Suite-Cross-Selling** — UIQ-Nutzer sind qualifizierte Refundex-Interessenten und umgekehrt (identische Zielgruppe: aktive Selbstentscheider) | Phase 3 |
| O5 | **§23-Erweiterung** — Edelmetalle/Alt-Krypto (Anlage SO) als natürliche, klar abgrenzbare Erweiterung | Bereits als Next-Session-Item identifiziert |
| O6 | **Broker-neutrale Zielgruppe über Säule 2** — mit manuellem Erfassungs-Adapter adressiert das QSt-Cockpit jeden deutschen Anleger mit Auslandsdividenden bei beliebiger Bank; deutlich breiter als die IBKR-Nische der Säule 1 | Strategische Verbreiterung ohne Verwässerung des Kerns |

### Risiken (extern)

| # | Risiko | Gegenmaßnahme |
|---|---|---|
| R1 | **Rechtsberatungs-/Steuerberatungsgrenze (StBerG)** — individuelle Steuerempfehlungen wären unbefugte Hilfeleistung in Steuersachen | Compliance by Design: Rechenwerk + Belegkette, keine Gestaltungsempfehlung (§4) |
| R2 | **Haftung bei Rechenfehlern** — falsche KAP-Werte können Steuernachzahlungen/Zinsen auslösen | Testabdeckung, Abgleich-Pflichthinweis (Steuerbescheinigung), verstärkte Disclaimer |
| R3 | **IBKR ändert Flex-Query-Format** — Parser-Bruch ohne Vorwarnung | Parser-Versionierung, Format-Sanity-Checks, Fehlermeldung statt stiller Falschwerte (No-Hallucination auch hier) |
| R4 | **Gesetzesänderungen** — z. B. Verfassungsmäßigkeit der Verlustverrechnungsbeschränkung (§20 Abs. 6) ist umstritten; Änderung würde Kernlogik treffen | Modulare Töpfe-Architektur macht Regeländerung lokal; jährlicher Rechts-Review |
| R5 | **Kostenlose Konkurrenz durch Broker** — CapTrader könnte Steuerreporting selbst verbessern | Nische verbreitern (Multi-Broker, §23), Suite-Bindung |

---

## 4. Compliance-Rahmen (Compliance by Design)

**Wichtige Abgrenzung zur UIQ-Welt:** Für UnderlyingIQ ist die maßgebliche Schranke das Aufsichtsrecht (BaFin: §34b WpHG a.F. / Art. 20 MAR, §1 WpHG — daher dort „Statistische Kontext-Analyse" statt „Handlungsempfehlung"). Für Refundex ist die maßgebliche Schranke das **Steuerberatungsgesetz (StBerG)**: Unbefugte geschäftsmäßige Hilfeleistung in Steuersachen (§§ 2–5 StBerG) ist untersagt. Das Suite-Prinzip dahinter ist identisch — **im normalen Anwenderbereich ist regulatorische Konformität oberste Pflicht** — nur die Rechtsquelle unterscheidet sich je Modul.

Konkrete Leitplanken für Refundex:

1. **Rechenwerk, nicht Beratung.** Refundex berechnet aus vom Nutzer gelieferten Daten nach dokumentierten, allgemeinen Regeln. Keine individuellen Gestaltungsempfehlungen („verkaufe X vor Jahresende, um…"), keine Einzelfall-Würdigung.
2. **Formulierungsdisziplin.** Ausgaben heißen „Berechnungsergebnis", „Richtwert", „Übertragungshilfe" — nie „Steuerempfehlung". Checklisten beschreiben den mechanischen Übertrag in ELSTER/WISO, nicht steuerliche Wahlrechte.
3. **Pflicht-Disclaimer sichtbar, nicht versteckt:** (a) keine Gewähr für Richtigkeit, (b) ersetzt keinen Steuerberater, (c) Basiszins-/Rechtsstand-Unsicherheit, (d) explizite Nicht-Abdeckungsliste (Krypto, Edelmetalle, betriebliche Kapitalerträge). — Die vier bereits identifizierten Verstärkungspunkte sind Phase-1-Pflicht.
4. **Abgleich-Gebot:** Jeder Report fordert aktiv zum Abgleich mit der offiziellen Jahressteuerbescheinigung auf.
5. **No-Hallucination als Compliance-Instrument:** Erfundene Paragraphen oder geschätzte Werte wären nicht nur Qualitätsmängel, sondern Haftungsrisiken. Deshalb: Strict-Source-Prinzip — jede Rechtsangabe mit BMF-GZ/Normzitat, jeder Wert mit Datenzeilen-Herkunft; bei fehlender Quelle wird der Wert nicht ausgegeben, sondern als Lücke ausgewiesen.

---

## 5. Entscheidungsfilter (vier Fragen vor jedem neuen Feature)

Analog zum UIQ-Filter (STRATEGIE.md §6 dort), angepasst auf Refundex. Ein Feature wird nur gebaut, wenn alle vier Fragen positiv beantwortet sind:

1. **Belegketten-Frage:** Ist jeder neue Ausgabewert deterministisch berechenbar und auf Datenzeile + Rechtsquelle rückführbar? *(Wenn nein: nicht bauen — No-Hallucination.)*
2. **80/20-Frage:** Liefert das Feature mit ≤ 20 % Aufwand ≥ 80 % Nutzerwert — oder ist es ein Randfall, der besser als dokumentierte Grenze an den Steuerberater verwiesen wird?
3. **ES6/Modularitäts-Frage:** Lässt sich das Feature als sauberes Modul (ES6, zentrale Strings, JSON-Kontrakt zur Engine) bauen, ohne den Monolithen zu vergrößern?
4. **StBerG-Frage:** Bleibt das Feature ein Rechenwerk mit allgemeinen Regeln — oder rutscht es in individuelle Steuerberatung? *(Im Zweifel: Formulierung entschärfen oder nicht bauen.)*

---

## 6. Fortschreibungshistorie

| Version | Datum | Änderung |
|---|---|---|
| 1.0 | 03.07.2026 | Erstfassung: Leitbild, Suite-Positionierung, SWOT, Compliance-Rahmen (StBerG-Abgrenzung), Entscheidungsfilter |
| 1.1 | 03.07.2026 | Leitbild auf zwei Säulen verbreitert (KAP + QSt-Rückholung); Grundgesetz 6 Broker-Neutralität über Normalisiertes Ertragsdatenmodell mit Adapter-Architektur inkl. Extraction-Review-Gate; SWOT-Chance O6 (broker-neutrale Zielgruppe) |
