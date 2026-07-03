# Refundex — RUNBOOK (Bus-Factor-Dokument)

**Version:** 1.2
**Stand:** 03.07.2026
**Ablage:** `ahsub/refundex/docs/RUNBOOK.md`
**Zweck:** Dieses Dokument versetzt eine technikaffine dritte Person in die Lage, Refundex zu verstehen, zu betreiben und im Notfall wiederherzustellen — ohne den Inhaber fragen zu können. Es adressiert Schwäche W1 (Bus-Faktor 1) aus `docs/STRATEGIE.md`.

> ⚠️ **Platzhalter:** Mit `[INHABER: …]` markierte Stellen kann nur der Inhaber füllen.

---

## 1. Was ist Refundex? (60 Sekunden)

Browserbasierter deutscher Steuerassistent für Kunden IBKR-basierter Broker (CapTrader, Lynx). Zwei Säulen: **(1) Anlage KAP** — aus einer IBKR Flex Query CSV werden zeilengenaue Werte für die Anlage KAP berechnet; **(2) Quellensteuer-Rückholung** (im Aufbau) — Rückholpotenzial ausländischer Quellensteuer je Land. Alles läuft lokal im Browser; es gibt keinen Server mit Nutzerdaten. Strategischer Rahmen: `docs/STRATEGIE.md`, Planung: `docs/ROADMAP.md`.

---

## 2. Systemlandkarte

```
┌──────────────────────────────────────────────────────────────┐
│  NUTZER-BROWSER (einzige Laufzeitumgebung mit Nutzerdaten)   │
│                                                              │
│  kap.html (Monolith, ~880 KB, v139)                          │
│   ├─ ko-flex.js        Flex-Query-CSV-Parser                 │
│   ├─ Berechnungslogik  KAP-Zeilen, Projektions-Schicht       │
│   │    calcKAP(d,year) → brutto                              │
│   │    projiziereErgebnis(brutto,kontoTyp) → 50%-Faktor      │
│   │    (EINZIGE Stelle des Gemeinschaftskonto-Faktors)       │
│   ├─ ETF-Vorabpauschale (§18 InvStG, BASISZINS-Konstante)    │
│   ├─ DOCX-Export, Checkliste, Hilfe-Modal                    │
│   └─ importEngineJSON() ← kap_data.json (Engine-Output)      │
│                                                              │
│  localStorage: ETF-Karten, UI-Zustand                        │
└──────────────────────────────────────────────────────────────┘
            ▲ statisches Hosting                ▲ Markdown lazy-load
┌───────────────────────────┐   ┌──────────────────────────────┐
│ Cloudflare Pages          │   │ ahsub/refundex-docs          │
│ (Direct Upload, Zip)      │   │ index.json + docs/*.md       │
│ Quelle: Deployment-Zip     │  │ (10 Hilfe-Module; Struktur   │
└───────────────────────────┘   │  wird mit UIQ geteilt)       │
                                └──────────────────────────────┘
┌──────────────────────────────────────────────────────────────┐
│  PYTHON-ENGINE (lokal beim Inhaber, kein Server)             │
│  build_report.py v4  →  kap_data.json + Steuerreport HTML    │
│   ├─ aktien_fifo.py        FIFO-Aktiengewinne (Topf 2)       │
│   ├─ termingeschaefte.py   Optionen/Futures/CFD (Topf 3)     │
│   ├─ verlusttoepfe.py      3-Töpfe, 20k-Cap, Verlustvortrag  │
│   ├─ vorabpauschale.py     §18 InvStG, BMF-Basiszins         │
│   └─ kapmassnm.py          Kapitalmaßnahmen SO/TO/TC/DW      │
│  Tests: pytest, 99/99 über 6 Testdateien                     │
└──────────────────────────────────────────────────────────────┘
```

**Zentrale Invariante (No-Hallucination):** Kein steuerlicher Wert entsteht durch Schätzung oder KI. Quellen sind ausschließlich: geparste Broker-Datenzeilen, amtliche Konstanten (BMF-Basiszins mit Geschäftszeichen), Gesetzesnormen. Ziel-Architektur (ROADMAP 2.1): die Python-Engine wird Single Source of Truth, der Browser rechnet nur noch Darstellung/Projektion.

---

## 3. Repos & Deploy-Wege

| Repo | Inhalt | Deploy |
|---|---|---|
| `ahsub/refundex` | Anwendungsdateien (index.html, kap.html, guide.html, formfiller.html, refundex-docs.html, `modules/`), Python-Engine, Tests, `docs/` | **Quellcode-Ablage — Push publiziert NICHT automatisch** |
| `ahsub/refundex-docs` | Hilfe-Module (Markdown) + `index.json` | Kein Build — kap.html lädt zur Laufzeit via raw/CDN |

**Zwei getrennte Vorgänge — beide nötig:**

1. **Quellcode nach GitHub** (Versionshistorie, Zusammenarbeit mit Claude): Push über GitHub Contents API (`PUT /repos/ahsub/refundex/contents/{pfad}`), Muster SHA-first (bestehende Datei: erst GET für SHA, dann PUT mit SHA). Auth: klassischer PAT mit `repo`-Scope, **7 Tage Laufzeit, nach jeder Session löschen**.
2. **Publikation über Cloudflare Pages** (macht die App live): Deployment-Zip mit allen Anwendungsdateien in korrekter Struktur (Root-HTMLs + `modules/`-Ordner; NICHT `engine/`, NICHT `docs/`) im Cloudflare-Dashboard unter Workers & Pages als Direct Upload hochladen. Claude baut das Zip am Sessionende (`refundex-deploy-vNNN.zip`); der Upload selbst erfolgt durch den Inhaber im Dashboard. **Merksatz: GitHub-Commit ≠ live — erst der Pages-Upload publiziert.**

**Pages-Projekt:** `refundex-app` → erreichbar unter `refundex-app.pages.dev` (kostenlose CF-Subdomain inkl. HTTPS; Muster identisch zu UIQ: Projekt `underlyingiq-app` → underlyingiq-app.pages.dev + Custom Domain underlyingiq.com). Eine Custom Domain (Kandidat: refundex.de, ggf. refundex.com) ist optional und für die Beta nicht erforderlich — Entscheidung offen, siehe ROADMAP 3.5 (Monetarisierung/Außenauftritt). UIQ liegt getrennt in `ahsub/axel-scanner` (dort index.html + help.html) mit eigenem Pages-Projekt.

**Versionierung:** kap.html trägt die Version im `<title>` (aktuell v139) — bei jeder Änderung hochzählen. Strategiedokumente tragen eigene Versionen mit Fortschreibungshistorie am Dokumentende.

---

## 4. Steuerjahr-Update-Checkliste (jährlich, Januar/Februar)

Der wichtigste wiederkehrende Betriebsprozess (Roadmap-Item 1.6). Reihenfolge einhalten:

1. **BMF-Basiszins besorgen:** Das BMF veröffentlicht den Basiszins nach §18 Abs. 4 InvStG jeweils Anfang Januar per BMF-Schreiben (Referenzen: 2025 = 2,53 %, BMF 10.01.2025, GZ IV C 1 - S 1980/00230/009/002; 2026 = 3,20 %, BMF 13.01.2026, GZ IV C 1 - S 1980/00230/012/001). **Nur amtliche Quelle verwenden, GZ dokumentieren.**
2. **Wert eintragen in BEIDEN Rechenwelten** (bis Konsolidierung ROADMAP 2.1): `BASISZINS`-Konstante in kap.html **und** `vorabpauschale.py`. Drift zwischen beiden ist ein bekanntes Risiko (STRATEGIE W2).
3. **Freibeträge prüfen:** Sparer-Pauschbetrag (Stand 2026: 1.000 € / 2.000 € zusammenveranlagt), 20.000-€-Cap Termingeschäfte (§20 Abs. 6 — Rechtsprechung beobachten, Verfassungsmäßigkeit umstritten).
4. **Rechtsänderungs-Review:** §20, §18 InvStG, §23 EStG, Anlage-KAP-Formularänderungen des neuen Jahres (Zeilennummern können sich verschieben!).
5. **Regressionstest:** `pytest` (Soll: 99/99 grün) + ein Vorjahres-Referenzdatensatz durch kap.html laufen lassen und gegen bekannte Steuerbescheinigungs-Werte abgleichen.
6. **Hilfe-Module aktualisieren** (refundex-docs), insbesondere `etf.md` (Basiszins) und `faq.md`.
7. **Version hochzählen, deployen, ROADMAP.md-Item 3.2 abhaken.**

---

## 5. Störungs-Runbook

| Symptom | Wahrscheinliche Ursache | Behebung |
|---|---|---|
| Upload wird nicht erkannt / 0 Werte | IBKR hat Flex-Query-Format geändert (Risiko R3) | Spaltenköpfe der CSV mit ko-flex.js-Erwartung abgleichen; Parser anpassen; NIEMALS stillschweigend raten — lieber Fehlermeldung |
| Werte weichen von Steuerbescheinigung ab | (a) EZB-Näherung (~-Werte) statt Flex Cash, (b) unvollständige Flex Query (Sections fehlen), (c) echter Bug | Flex-Query-Konfiguration gegen Hilfe-Modul `flex-query.md` prüfen; Abweichung >1 % → GitHub Issue |
| Hilfe-Modal leer | refundex-docs nicht erreichbar / index.json-Bruch | index.json-Syntax prüfen; CDN-Cache (purge.jsdelivr.net) |
| Vorabpauschale offensichtlich falsch | Basiszins des Jahres fehlt/veraltet in einer der beiden Rechenwelten | Checkliste §4 Schritt 1–2 |
| ETF-Karten verschwunden | localStorage geleert (Browserwechsel, Private Mode) | Erwartetes Verhalten — Daten sind bewusst nur lokal; Kurse neu eintragen |
| Live-Seite zeigt alten Stand | Pages-Upload vergessen (GitHub-Commit allein publiziert nicht!) oder Browser-Cache | Aktuelles Deployment-Zip im CF-Dashboard hochladen; Hard-Reload |

---

## 6. Disaster Recovery

**Was kann überhaupt verloren gehen?** Bewusst wenig — das ist Architekturprinzip:

| Asset | Verlustszenario | Wiederherstellung |
|---|---|---|
| Code + Docs | Repo-Verlust | Git-Klone lokal beim Inhaber; GitHub-Historie; zur Not letzte Outputs aus Claude-Sessions |
| Nutzerdaten | — | Existieren serverseitig nicht (localStorage nur beim Nutzer). Nichts wiederherzustellen, nichts kompromittierbar |
| Steuerliche Referenzwerte | Verlust der GZ-Dokumentation | In diesem RUNBOOK (§4) und in vorabpauschale.py dokumentiert |
| GitHub-Account `ahsub` | Sperrung/Verlust | [INHABER: Recovery-Codes / Backup-Zugang dokumentieren — Ablageort angeben] |
| Domain/Erreichbarkeit | Cloudflare Pages down | Statisches HTML — jede Kopie von kap.html funktioniert lokal per Doppelklick vollständig offline |

**Minimal-Wiederaufbau ohne alles:** kap.html (eine Datei!) auf beliebigem statischem Host + refundex-docs-Repo = voll funktionsfähige App. Die Python-Engine ist für Endnutzer nicht erforderlich.

---

## 7. Kontakte & Zugänge

| Was | Wo | Hinweis |
|---|---|---|
| Feedback-Eingang | ahildebrand@me.com (Betreff REFUNDEX) + GitHub Issues | Beide in kap.html verlinkt |
| GitHub-Account | ahsub | [INHABER: 2FA-Recovery-Ablageort] |
| PAT-Tokens | — | Nie persistent; 7-Tage-Laufzeit, nach Session löschen |
| Steuerfachliche Rückfragen | [INHABER: Steuerberater-Kontakt eintragen] | Für §20 Abs. 6-Entwicklung und Formularänderungen |

---

## 8. Wo weiterlesen

1. `docs/STRATEGIE.md` — Leitbild, Suite-Grundgesetze, SWOT, Entscheidungsfilter (4 Fragen)
2. `docs/ROADMAP.md` — Phasenplan, Gate-Protokoll Quellensteuer, Nicht-Ziele
3. `docs/DATENMODELL_ERTRAEGE.md` — JSON-Kontrakt Säule 2 (broker-neutral)
4. UIQ-Pendants in `ahsub/ko-aggregator/docs/` — gleiche Governance, gleiches Arbeitsprotokoll

---

## Fortschreibungshistorie

| Version | Datum | Änderung |
|---|---|---|
| 1.0 | 03.07.2026 | Erstfassung: Systemlandkarte, Deploy-Wege, Steuerjahr-Update-Checkliste (= Roadmap-Item 1.6), Störungs-Runbook, Disaster Recovery; 3 Inhaber-Platzhalter offen |
| 1.1 | 03.07.2026 | KORREKTUR §3: Hosting läuft über Cloudflare Pages (Direct Upload als Zip), nicht GitHub Pages; Zwei-Vorgänge-Prinzip (GitHub = Quellcode, CF Pages = Publikation) dokumentiert; Deployment-Zip-Inhalt definiert |
| 1.2 | 03.07.2026 | Pages-Projekt `refundex-app` → refundex-app.pages.dev dokumentiert (Muster UIQ); Custom Domain optional, Kandidat refundex.de — Entscheidung offen; Abgrenzung zu UIQ (axel-scanner, help.html) präzisiert |
