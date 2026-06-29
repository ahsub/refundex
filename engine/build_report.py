#!/usr/bin/env python3
"""
build_report.py — Refundex Steuerreport-Generator v3.0
=======================================================
Erzeugt druckbaren HTML-Steuerreport (Anlage KAP) aus IBKR Flex Query XML.
Integriert: fifo_fx.py (FX-FIFO) + kapmassnm.py (Kapitalmaßnahmen)
"""
import sys, xml.etree.ElementTree as ET, json, os
from collections import defaultdict
from datetime import datetime
sys.path.insert(0, '/home/claude')
from fifo_fx import fx_fifo_from_lines
from kapmassnm import compute_kapmassnm
from verlusttoepfe import KapitaleinkunfteInput, berechne_verlusttoepfe, VerlustvortragState
from aktien_fifo import compute_aktien_fifo
from termingeschaefte import compute_termingeschaefte

# ── Konfiguration ─────────────────────────────────────────────────────────────
XMLS = [
    '/mnt/user-data/uploads/1782742593101_Steuerauswertung.xml',
    '/mnt/user-data/uploads/1782742593100_Steuerauswertung-2.xml',
    '/mnt/user-data/uploads/1782742593100_Steuerauswertung-3.xml',
]
STEUERJAHR = 2025
KONTO      = 'U12074449'
NOW        = datetime.now().strftime('%d.%m.%Y, %H:%M Uhr')

# ── Daten laden ───────────────────────────────────────────────────────────────
def load(path):
    root = ET.parse(path).getroot()
    s    = root.find('.//FlexStatement')
    return s.findall('.//StatementOfFundsLine'), s.findall('.//OpenPosition')

all_lines = []
pos24 = []; pos25 = []
for i, p in enumerate(XMLS):
    lns, pos = load(p)
    all_lines.extend(lns)
    if i == 1: pos24 = pos
    if i == 2: pos25 = pos

lines25 = [l for l in all_lines if l.get('date','').startswith('2025')]

# ── Hilfsfunktionen ───────────────────────────────────────────────────────────
def fmt(v):
    return f'{abs(v):,.2f}\u00a0EUR'.replace(',','X').replace('.',',').replace('X','.')
def numcell(v):
    if v >  0.005: return f'<span class="pos">+{fmt(v)}</span>'
    if v < -0.005: return f'<span class="neg">−{fmt(abs(v))}</span>'
    return '0,00\u00a0EUR'
CL  = {'US':'🇺🇸 USA','GB':'🇬🇧 Großbritannien','BR':'🇧🇷 Brasilien',
       'DK':'🇩🇰 Dänemark','SE':'🇸🇪 Schweden'}
DBA = {'US':0.15,'BR':0.15,'DK':0.15,'GB':0.0}

# ── 1. Optionen / Stillhalter ─────────────────────────────────────────────────
opt = defaultdict(lambda: {'p':0,'r':0,'desc':'','und':''})
for l in lines25:
    if l.get('assetCategory') != 'OPT' or l.get('currency') != 'EUR': continue
    c = l.get('activityCode',''); s = l.get('symbol','')
    opt[s]['desc'] = l.get('description','')
    opt[s]['und']  = l.get('underlyingSymbol','')
    if c == 'SELL': opt[s]['p'] += float(l.get('amount','0'))
    elif c == 'BUY': opt[s]['r'] += float(l.get('amount','0'))

opt_items = sorted(opt.items(), key=lambda x: (x[1]['und'], x[1]['desc']))
opt_g = sum(v['p']+v['r'] for v in opt.values() if v['p']+v['r'] >= 0)
opt_v = sum(v['p']+v['r'] for v in opt.values() if v['p']+v['r'] <  0)
opt_n = opt_g + opt_v

# ── 2. Dividenden ─────────────────────────────────────────────────────────────
divs = defaultdict(lambda: defaultdict(lambda: {'div':0,'tax':0,'desc':''}))
for l in lines25:
    if l.get('assetCategory') != 'STK' or l.get('currency') != 'EUR': continue
    c = l.get('activityCode',''); co = l.get('issuerCountryCode',''); s = l.get('symbol','')
    divs[co][s]['desc'] = l.get('description','')
    if c == 'DIV':   divs[co][s]['div'] += float(l.get('amount','0'))
    elif c == 'FRTAX': divs[co][s]['tax'] += -float(l.get('amount','0'))

div_total = sum(s['div'] for c in divs.values() for s in c.values())
tax_total = sum(s['tax'] for c in divs.values() for s in c.values())
tax_anr   = sum(min(s['tax'], s['div']*DBA.get(co,0))
                for co,syms in divs.items() for s in syms.values())

# ── 3. Zinsen & SYEP ──────────────────────────────────────────────────────────
zins = syep = sollzins = 0.0
for l in lines25:
    if l.get('currency') != 'EUR': continue
    c = l.get('activityCode',''); d = l.get('activityDescription','')
    a = float(l.get('amount','0'))
    if c == 'CINT':
        if 'SYEP' in d or 'Securities' in d: syep += a
        else: zins += a
    elif c == 'DINT': sollzins += a

# ── 4. FX-FIFO v1.1 ──────────────────────────────────────────────────────────
fx_res = fx_fifo_from_lines(all_lines, str(STEUERJAHR))
fx_g   = sum(r.gewinn_guthaben  for r in fx_res.values())
fx_v   = sum(r.verlust_guthaben for r in fx_res.values())
fx_n   = fx_g + fx_v

# ── 5. Kapitalmaßnahmen v1.0 ──────────────────────────────────────────────────
# CORP-Buchungen für kapmassnm-Symbole aus StmtFunds AUSSCHLIESSEN
# (AK-Anpassungen, keine KAP-Erträge)
km_report    = compute_kapmassnm(XMLS, str(STEUERJAHR))
km_sachausch = km_report.gesamt_sachausch
km_gl        = km_report.gesamt_gewinn + km_report.gesamt_verlust
km_symbols   = {e.symbol for e in km_report.ergebnisse}

# ── 6. KAP-Zeilen ─────────────────────────────────────────────────────────────
akt = compute_aktien_fifo(XMLS, str(STEUERJAHR))
ter = compute_termingeschaefte(XMLS, str(STEUERJAHR))
_inp = KapitaleinkunfteInput(
    steuerjahr=STEUERJAHR,
    stillhalter_praemien=opt_g, stillhalter_glatt=opt_v,
    dividenden=div_total, zinsen=zins, syep=syep,
    fx_gewinne=fx_g, fx_verluste=fx_v,
    km_sachausch=km_sachausch, km_gl=km_gl,
    aktien_gewinne=akt.gewinne, aktien_verluste=akt.verluste,
    termin_gewinne=ter.gewinne, termin_verluste=ter.verluste,
    quellensteuer_anr=tax_anr, sollzinsen=sollzins,
)
_vt     = berechne_verlusttoepfe(_inp)
kap19   = _vt.kap_z19;  kap20 = _vt.kap_z20
kap22   = _vt.kap_z22;  kap23 = _vt.kap_z23
kap41   = _vt.kap_z41;  SPARER = _vt.sparer_einzel
kap19_pos = _inp.topf1_brutto_positiv + max(0, km_sachausch)
kap19_neg = _inp.topf1_brutto_negativ + min(0, km_gl)

# ── 7. Positionen ─────────────────────────────────────────────────────────────
def plist(pos):
    r = []
    for p in pos:
        r.append({'cat':p.get('assetCategory',''), 'sym':p.get('symbol',''),
                  'desc':p.get('description',''),  'qty':float(p.get('position','0')),
                  'ak':float(p.get('costBasisMoney','0'))})
    return sorted(r, key=lambda x: (x['cat'], -abs(x['ak'])))

ps = plist(pos24); pe = plist(pos25)
ak_s = sum(abs(p['ak']) for p in ps)
ak_e = sum(abs(p['ak']) for p in pe)

# Ausgabe zur Verifikation
print(f'KAP-19 = {kap19:.2f}  KAP-22 = {kap22:.2f}  KAP-41 = {kap41:.2f}')
print(f'  Opt G/V: {opt_g:.2f} / {opt_v:.2f} / N={opt_n:.2f}')
print(f'  Div:     {div_total:.2f}  QST-anr: {tax_anr:.2f}')
print(f'  Zinsen:  {zins:.2f}  SYEP: {syep:.2f}')
print(f'  FX:      G={fx_g:.2f} V={fx_v:.2f} N={fx_n:.2f}')
print(f'  KM:      Sachausch={km_sachausch:.2f}  GL={km_gl:.2f}')
print(f'  Pos:     Start-AK={ak_s:.2f}  End-AK={ak_e:.2f}')

# ── 8. HTML-Helfer ────────────────────────────────────────────────────────────
def opt_rows():
    rows = []
    for sym, v in opt_items:
        n  = v['p'] + v['r']
        nc = 'pos' if n >= 0 else 'neg'
        rk = f'−{fmt(abs(v["r"]))}' if v['r'] < 0 else (f'+{fmt(v["r"])}' if v['r'] > 0 else '—')
        rows.append(f'<tr><td>{v["desc"]}</td>'
                    f'<td class="num pos">+{fmt(v["p"])}</td>'
                    f'<td class="num {"neg" if v["r"]<0 else ""}">{rk}</td>'
                    f'<td class="num {nc}">{numcell(n)}</td></tr>')
    return '\n'.join(rows)

def div_rows():
    rows = []
    for co in sorted(divs.keys()):
        syms = divs[co]; dba = DBA.get(co, 0)
        rows.append(f'<tr class="grp"><td colspan="5"><b>{CL.get(co,co)} — DBA {int(dba*100)} %</b></td></tr>')
        ct = cv = ca = 0
        for sym, d in sorted(syms.items()):
            anr = min(d['tax'], d['div'] * dba)
            ct += d['div']; cv += d['tax']; ca += anr
            rows.append(f'<tr><td>{sym}</td><td class="meta">{d["desc"]}</td>'
                        f'<td class="num">{fmt(d["div"])}</td>'
                        f'<td class="num neg">{"−"+fmt(d["tax"]) if d["tax"]>0 else "—"}</td>'
                        f'<td class="num pos">{"+" + fmt(anr) if anr>0 else "0,00\u00a0EUR"}</td></tr>')
        rows.append(f'<tr class="grp"><td colspan="2"><b>Zwischensumme</b></td>'
                    f'<td class="num"><b>{fmt(ct)}</b></td>'
                    f'<td class="num neg"><b>{"−"+fmt(cv) if cv>0 else "—"}</b></td>'
                    f'<td class="num pos"><b>{"+" + fmt(ca) if ca>0 else "0,00\u00a0EUR"}</b></td></tr>')
    return '\n'.join(rows)

def fx_rows():
    rows = []
    for cur, r in sorted(fx_res.items()):
        n  = r.netto_guthaben; nc = 'pos' if n >= 0 else 'neg'
        vb = sum(1 for a in r.audit if a.typ == 'VB')
        rows.append(f'<tr><td>{cur}</td>'
                    f'<td class="num pos">+{fmt(r.gewinn_guthaben)}</td>'
                    f'<td class="num neg">−{fmt(abs(r.verlust_guthaben))}</td>'
                    f'<td class="num {nc}">{numcell(n)}</td>'
                    f'<td class="meta">{vb} Buchungen im Verbindlichkeitsbereich</td></tr>')
    return '\n'.join(rows)

def km_rows():
    rows = []
    typ_map = {'SO':'Spin-Off','TO':'Tender Offer','TC':'Tausch/Merger','DW':'Delisting'}
    for e in km_report.ergebnisse:
        gl = e.realis_gewinn + e.realis_verlust
        nc = 'pos' if gl > 0 else ('neg' if gl < 0 else '')
        sa_cell = f'<span class="pos">+{fmt(e.sachausch_eur)}</span>' if e.sachausch_eur > 0 else '—'
        gl_cell = numcell(gl) if abs(gl) > 0.01 else '—'
        rows.append(f'<tr><td>{e.date}</td>'
                    f'<td><b>[{e.type}]</b> {typ_map.get(e.type,e.type)}</td>'
                    f'<td>{e.symbol}</td>'
                    f'<td class="num">{e.quantity:+.4f}</td>'
                    f'<td class="num">{sa_cell}</td>'
                    f'<td class="num {nc}">{gl_cell}</td>'
                    f'<td class="meta" style="font-size:7.5pt">{e.rechtsgrundlage}</td></tr>')
    return '\n'.join(rows)

def pos_rows(pl):
    rows = []; cur = None
    lbl_map = {'STK':'Aktien','OPT':'Short-Optionen (Stillhalter)'}
    for p in pl:
        lbl = lbl_map.get(p['cat'], p['cat'])
        if lbl != cur:
            rows.append(f'<tr class="grp"><td colspan="4"><b>{lbl}</b></td></tr>')
            cur = lbl
        q = f'{abs(p["qty"]):,.4f}'.replace(',','X').replace('.',',').replace('X','.')
        rows.append(f'<tr><td>{p["sym"]}</td><td class="meta">{p["desc"]}</td>'
                    f'<td class="num">{q}</td><td class="num">{fmt(abs(p["ak"]))}</td></tr>')
    return '\n'.join(rows)

print('\nGeneriere HTML...')

# ── CSS ───────────────────────────────────────────────────────────────────────
CSS = """
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Segoe UI',Arial,sans-serif;font-size:10pt;color:#1a1a1a;background:#fff;line-height:1.5}
@page{size:A4;margin:20mm 15mm 18mm 15mm}
@media print{
  .no-print{display:none!important}
  .page-break{page-break-before:always}
  body{font-size:9pt}
  .ph{display:block!important;font-size:8pt;color:#555;text-align:right;
      border-bottom:1px solid #ccc;padding-bottom:3px;margin-bottom:6px}}
.ph{display:none}
h1{font-size:18pt;color:#fff}
h2{font-size:13pt;color:#1a3a5c;margin:22px 0 8px;padding-bottom:4px;border-bottom:2.5px solid #1a3a5c}
h3{font-size:10.5pt;color:#2c5282;margin:14px 0 5px}
.cover{background:linear-gradient(135deg,#1a3a5c,#2c5282);color:#fff;padding:20px 24px;border-radius:5px;margin-bottom:18px}
.cover .sub{font-size:9pt;opacity:.85;margin-top:3px}
.badge{display:inline-block;margin-top:10px;padding:4px 12px;background:rgba(255,255,255,.2);border-radius:3px;font-size:9pt;font-weight:600}
.kap-box{background:#f0f7ff;border:2px solid #1a3a5c;border-radius:5px;padding:16px 20px;margin-bottom:16px}
.kap-row{display:flex;align-items:baseline;margin:5px 0;flex-wrap:wrap;gap:4px}
.kap-zl{color:#555;font-size:9pt;width:65px;flex-shrink:0}
.kap-desc{flex:1;font-size:9pt;min-width:200px}
.kap-amt{font-weight:700;font-size:13pt;color:#1a3a5c;white-space:nowrap;margin-left:12px}
.kap-split{font-size:11pt;color:#2c5282;display:none}
.pers-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:10px 0}
.pers-grid input,.pers-grid select{width:100%;border:1px solid #b0bec5;border-radius:3px;padding:5px 8px;font-size:9.5pt;font-family:inherit}
.pers-grid label{font-size:8.5pt;color:#555;display:block;margin-bottom:2px}
.toggle-bar{display:flex;margin:10px 0;border:1.5px solid #1a3a5c;border-radius:4px;overflow:hidden;width:fit-content}
.toggle-bar button{padding:6px 18px;border:none;background:#fff;cursor:pointer;font-size:9.5pt;font-family:inherit}
.toggle-bar button.active{background:#1a3a5c;color:#fff;font-weight:600}
.warn{background:#fffbeb;border:1.5px solid #d97706;padding:10px 14px;border-radius:4px;font-size:9pt;margin:8px 0}
.danger{background:#fef2f2;border:1.5px solid #dc2626;padding:10px 14px;border-radius:4px;font-size:9pt;margin:8px 0}
.info{background:#f0fdf4;border:1.5px solid #16a34a;padding:10px 14px;border-radius:4px;font-size:9pt;margin:8px 0}
.neutral{background:#f8fafc;border:1.5px solid #94a3b8;padding:10px 14px;border-radius:4px;font-size:9pt;margin:8px 0}
.meta{font-size:8.5pt;color:#666;margin:4px 0}
table.data{width:100%;border-collapse:collapse;margin:6px 0 10px;font-size:9pt}
table.data th{background:#1a3a5c;color:#fff;padding:5px 8px;text-align:left;font-weight:600}
table.data td{padding:4px 8px;border-bottom:1px solid #e2e8f0;vertical-align:top}
table.data tr.grp td{background:#e8f0fe;font-weight:600;padding:5px 8px}
table.data tr:last-child td{border-bottom:2px solid #1a3a5c}
table.data .num{text-align:right;font-family:monospace;white-space:nowrap}
table.data .pos{color:#166534}
table.data .neg{color:#991b1b}
table.data .meta{color:#666;font-size:8.5pt}
.manual-input{background:#fffbeb;border:1px dashed #d97706;border-radius:3px;
  padding:2px 6px;font-family:inherit;font-size:9.5pt;width:150px;text-align:right}
.toc ol{padding-left:20px;columns:2;gap:30px}
.toc li{margin:3px 0;font-size:9.5pt}
.toc a{color:#1a3a5c;text-decoration:none}
.disclaimer{font-size:8pt;color:#666;border-top:1px solid #ddd;padding-top:10px;margin-top:24px}
.footer{text-align:center;font-size:8pt;color:#999;margin-top:8px}
@media print{.pers-grid input{border:none;border-bottom:1px solid #ccc;border-radius:0}}
"""

HTML = f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<title>Steuerreport {STEUERJAHR} · {KONTO}</title>
<style>{CSS}</style>
</head>
<body>

<!-- Druckkopf (nur beim Drucken sichtbar) -->
<div class="ph">Steuerreport {STEUERJAHR} · IBKR {KONTO} · {NOW}
  <span id="ph-name" style="margin-left:16px;font-weight:600"></span>
</div>

<!-- TITELSEITE -->
<div class="cover">
  <h1>Steuerreport Kapitalerträge {STEUERJAHR}</h1>
  <div class="sub">Nachweis der steuerlichen Berechnungen · Interactive Brokers Depot</div>
  <div class="sub">Basis: IBKR Flex Query XML (3 Dateien 2023–2025) · FIFO · EZB-Kurse</div>
  <span class="badge">Broker: Interactive Brokers &nbsp;·&nbsp; Konto: {KONTO}</span>
  <span class="badge" style="margin-left:8px">Erstellt: {NOW}</span>
</div>

<!-- TOGGLE -->
<div class="no-print">
  <h3 style="margin-top:0">Kontoart</h3>
  <div class="toggle-bar">
    <button class="active" onclick="setMode('einzel',this)">Einzelkonto</button>
    <button onclick="setMode('gemein',this)">Gemeinschaftskonto (50/50)</button>
  </div>
</div>

<!-- PERSÖNLICHE ANGABEN -->
<h2>Persönliche Angaben</h2>
<div class="pers-grid">
  <div><label>Steuerpflichtiger 1</label>
    <input id="name1" type="text" placeholder="Hildebrand, Axel" oninput="updateNames()"></div>
  <div id="blk2" style="display:none"><label>Steuerpflichtiger 2</label>
    <input id="name2" type="text" placeholder="Hildebrand, …" oninput="updateNames()"></div>
  <div><label>Steuernummer</label>
    <input id="steuernr" type="text" placeholder="213/567/89012"></div>
  <div><label>Zuständiges Finanzamt</label>
    <input id="finanzamt" type="text" placeholder="Finanzamt Krefeld"></div>
  <div><label>Veranlagungsjahr</label>
    <input type="text" value="{STEUERJAHR}" readonly style="background:#f0f4f8"></div>
  <div><label>Depot-ID</label>
    <input type="text" value="{KONTO}" readonly style="background:#f0f4f8"></div>
</div>

<!-- PFLICHTVERANLAGUNG -->
<div class="danger">
  <b>⚠️ Pflichtveranlagung (§ 32d Abs. 3 EStG)</b><br>
  Interactive Brokers ist ein <b>ausländisches Kreditinstitut</b> und führt <b>keine deutsche
  Kapitalertragsteuer (Abgeltungsteuer) ab</b>. Für Erträge aus diesem Depot besteht
  <b>gesetzliche Pflicht zur Abgabe der Anlage KAP</b> — unabhängig von der Ertragshöhe.
</div>

<!-- ══ 1. STEUERZUSAMMENFASSUNG ══ -->
<h2 id="s1">1. Steuerzusammenfassung — Anlage KAP {STEUERJAHR}</h2>
<div class="kap-box">
  <div class="kap-row">
    <span class="kap-zl"><b>Zeile 19</b></span>
    <span class="kap-desc">Ausländische Kapitalerträge (ohne Zeilen 26a und 52)</span>
    <span class="kap-amt" id="kap19-e">{fmt(kap19)}</span>
    <span class="kap-split kap-amt" id="kap19-g">je&nbsp;{fmt(kap19/2)}</span>
  </div>
  {'''<div class="kap-row" style="margin-top:8px">
    <span class="kap-zl"><b>Zeile 20</b></span>
    <span class="kap-desc">Aktiengewinne (§ 20 Abs. 2 Nr. 1 EStG)</span>
    <span class="kap-amt">''' + fmt(kap20) + '''</span></div>''' if kap20 > 0.005 else ''}
  <div class="kap-row" style="margin-top:8px">
    <span class="kap-zl"><b>Zeile 22</b></span>
    <span class="kap-desc">In Zeile 19 enthaltene Verluste (ohne Aktienverluste)</span>
    <span class="kap-amt" id="kap22-e">{fmt(kap22)}</span>
    <span class="kap-split kap-amt" id="kap22-g">je&nbsp;{fmt(kap22/2)}</span>
  </div>
  {'''<div class="kap-row" style="margin-top:8px">
    <span class="kap-zl"><b>Zeile 23</b></span>
    <span class="kap-desc">Aktienverluste (§ 20 Abs. 6 Satz 4 EStG — nur mit Aktiengewinnen)</span>
    <span class="kap-amt">''' + fmt(kap23) + '''</span></div>''' if kap23 > 0.005 else ''}
  <div class="kap-row" style="margin-top:8px">
    <span class="kap-zl"><b>Zeile 41</b></span>
    <span class="kap-desc">Anrechenbare ausländische Quellensteuer (DBA-begrenzt)</span>
    <span class="kap-amt" id="kap41-e">{fmt(kap41)}</span>
    <span class="kap-split kap-amt" id="kap41-g">je&nbsp;{fmt(kap41/2)}</span>
  </div>
</div>

<div class="warn">
<b>Methodenhinweis:</b> Die Berechnung basiert auf IBKR-integrierten FX-Kursen (fxRateToBase).
BubbleTax verwendet EZB-Referenzkurse. Über ~300 Optionsprämien-Transaktionen summieren sich
Kursdifferenzen zu ca. +{fmt(kap19 - 6450)}.
Für die endgültige Steuererklärung empfiehlt sich Abstimmung mit einem Steuerberater.
</div>

<!-- Sparer-Pauschbetrag -->
<h3>1.1 Sparer-Pauschbetrag (§ 20 Abs. 9 EStG)</h3>
<div class="warn">Interactive Brokers berücksichtigt den Sparer-Pauschbetrag <b>nicht automatisch</b>.
Er ist in der Anlage KAP (Zeile 16) geltend zu machen.</div>
<table class="data">
<thead><tr><th>Position</th><th class="num">Einzelkonto</th>
  <th class="num" id="th-gem" style="display:none">Gemeinschaftskonto (je Person)</th></tr></thead>
<tbody>
<tr><td>Kapitalerträge (Zeile 19)</td>
    <td class="num">{fmt(kap19)}</td>
    <td class="num" id="p-gem1" style="display:none">{fmt(kap19/2)}</td></tr>
<tr><td>Sparer-Pauschbetrag</td>
    <td class="num neg">−1.000,00 EUR</td>
    <td class="num neg" id="p-gem2" style="display:none">−1.000,00 EUR</td></tr>
<tr><td><b>Zu versteuernde Kapitalerträge</b></td>
    <td class="num pos"><b>{fmt(max(0,kap19-1000))}</b></td>
    <td class="num pos" id="p-gem3" style="display:none"><b>{fmt(max(0,kap19/2-1000))}</b></td></tr>
</tbody></table>

<!-- Verlustvortrag -->
<h3>1.2 Verlustvortrag Vorjahre (§ 20 Abs. 6 EStG)</h3>
<div class="neutral">IBKR weist keine deutschen Verlustvorträge aus — manuell eintragen.</div>
<table class="data"><tbody>
<tr><td>Allgemeiner Verlustverrechnungstopf (§ 20 Abs. 6 Satz 3)</td>
    <td class="num"><input class="manual-input" type="text" placeholder="0,00 EUR"></td></tr>
<tr><td>Termingeschäfte (§ 20 Abs. 6 Satz 5)</td>
    <td class="num"><input class="manual-input" type="text" placeholder="0,00 EUR"></td></tr>
<tr><td>Aktien (§ 20 Abs. 6 Satz 4)</td>
    <td class="num"><input class="manual-input" type="text" placeholder="0,00 EUR"></td></tr>
</tbody></table>

<!-- §20 Abs. 6 Satz 5 -->
<h3>1.3 Termingeschäft-Verlustverrechnungsgrenze (§ 20 Abs. 6 Satz 5 EStG)</h3>
<div class="info">
<b>Ergebnis 2025: Kein Cap anwendbar.</b>
Alle {len(opt)} Optionskontrakte sind Stillhaltergeschäfte (§ 20 Abs. 1 Nr. 11 EStG),
<b>keine Termingeschäfte i.S.v. § 20 Abs. 6 Satz 5</b>.
Long-Optionskäufe (§ 20 Abs. 2 Nr. 3) mit Verlusten wurden in 2025 nicht identifiziert.
→ Verluste aus Stillhaltergeschäften sind vollständig im allgemeinen Verlustverrechnungstopf verrechenbar.
</div>

<!-- ══ 2. HERLEITUNG ══ -->
<div class="page-break"></div>
<h2 id="s2">2. Steuerliche Herleitung</h2>
<table class="data">
<thead><tr><th>Kategorie</th><th>Rechtsgrundlage</th>
  <th class="num">Erträge</th><th class="num">Verluste</th><th class="num">Netto</th></tr></thead>
<tbody>
<tr><td>Dividenden (ausländisch)</td><td>§ 20 Abs. 1 Nr. 1 EStG</td>
    <td class="num pos">+{fmt(div_total)}</td><td class="num">—</td>
    <td class="num pos">+{fmt(div_total)}</td></tr>
<tr><td>Stillhaltergeschäfte ({len(opt)} Kontrakte)</td><td>§ 20 Abs. 1 Nr. 11 EStG</td>
    <td class="num pos">+{fmt(opt_g)}</td><td class="num neg">−{fmt(abs(opt_v))}</td>
    <td class="num pos">+{fmt(opt_n)}</td></tr>
<tr><td>Guthabenzinsen</td><td>§ 20 Abs. 1 Nr. 7 EStG</td>
    <td class="num pos">+{fmt(zins)}</td><td class="num">—</td>
    <td class="num pos">+{fmt(zins)}</td></tr>
<tr><td>Wertpapierleihe (SYEP)</td><td>§ 20 Abs. 1 Nr. 7 EStG</td>
    <td class="num pos">+{fmt(syep)}</td><td class="num">—</td>
    <td class="num pos">+{fmt(syep)}</td></tr>
<tr><td>Kapitalmaßnahmen: SO Sachausschüttung (ENVXW)</td><td>§ 20 Abs. 4a Satz 7 EStG</td>
    <td class="num pos">+{fmt(km_sachausch)}</td><td class="num">—</td>
    <td class="num pos">+{fmt(km_sachausch)}</td></tr>
<tr><td>Kapitalmaßnahmen: Realisierte G/V (ENVXW DW)</td><td>§ 20 Abs. 2 Satz 1 Nr. 1 EStG</td>
    <td class="num">—</td><td class="num neg">−{fmt(abs(km_gl))}</td>
    <td class="num neg">{numcell(km_gl)}</td></tr>
<tr><td>Devisenergebnisse <sup>*</sup></td><td>§ 20 Abs. 2 Nr. 7 EStG; Rn. 131 BMF</td>
    <td class="num pos">+{fmt(fx_g)}</td><td class="num neg">−{fmt(abs(fx_v))}</td>
    <td class="num neg">{numcell(fx_n)}</td></tr>
<tr><td>Sollzinsen (nicht abzugsfähig)</td><td>§ 20 Abs. 9 EStG</td>
    <td colspan="3" class="meta">−{fmt(abs(sollzins))} · <b>kein Werbungskostenabzug</b></td></tr>
<tr class="grp"><td><b>Summe Anlage KAP Zeile 19</b></td><td></td>
    <td class="num pos"><b>+{fmt(kap19_pos)}</b></td>
    <td class="num neg"><b>−{fmt(abs(kap19_neg))}</b></td>
    <td class="num pos"><b>+{fmt(kap19)}</b></td></tr>
</tbody></table>
<p class="meta"><sup>*</sup> FX-FIFO v1.1: Guthaben/Verbindlichkeits-Trennung, Zufluss-First-Prinzip (BubbleTax-Methodik).
IBKR-Kurse (fxRateToBase) statt EZB-Referenzkurse → geringe Abweichungen möglich.</p>

<!-- ══ 3. STILLHALTER ══ -->
<div class="page-break"></div>
<h2 id="s3">3. Stillhaltergeschäfte (§ 20 Abs. 1 Nr. 11 EStG)</h2>
<div class="info">Prämieneinnahme beim Zufluss steuerpflichtig. Rückkauf/Glattstellung = negative Einnahme (BMF Rn. 25).
Verfall wertlos = kein zusätzlicher Steuertatbestand. Alle Kontrakte sind Stillhalter — kein Termingeschäft-Cap.</div>
<table class="data">
<thead><tr><th>Kontrakt</th><th class="num">Prämie</th>
  <th class="num">Rückkauf / Glattst.</th><th class="num">Nettoresultat</th></tr></thead>
<tbody>
{opt_rows()}
<tr class="grp">
  <td><b>Summe ({len(opt)} Kontrakte)</b></td>
  <td class="num pos"><b>+{fmt(opt_g)}</b></td>
  <td class="num neg"><b>−{fmt(abs(opt_v))}</b></td>
  <td class="num pos"><b>+{fmt(opt_n)}</b></td>
</tr>
</tbody></table>

<!-- ══ 4. DIVIDENDEN ══ -->
<div class="page-break"></div>
<h2 id="s4">4. Dividenden und Quellensteuer</h2>
<table class="data">
<thead><tr><th>Symbol</th><th>Wertpapier</th><th class="num">Brutto-Div.</th>
  <th class="num">Einbeh. QST</th><th class="num">Anrechenbar (DBA)</th></tr></thead>
<tbody>
{div_rows()}
<tr class="grp"><td colspan="2"><b>Gesamt (50 Transaktionen, 4 Länder)</b></td>
  <td class="num pos"><b>+{fmt(div_total)}</b></td>
  <td class="num neg"><b>−{fmt(tax_total)}</b></td>
  <td class="num pos"><b>+{fmt(tax_anr)}</b></td></tr>
</tbody></table>

<!-- ══ 5. ZINSEN ══ -->
<h2 id="s5">5. Zinsen und Wertpapierleihe</h2>
<table class="data">
<thead><tr><th>Kategorie</th><th>Rechtsgrundlage</th><th class="num">Betrag</th><th>Steuerlich</th></tr></thead>
<tbody>
<tr><td>Guthabenzinsen (EUR + USD)</td><td>§ 20 Abs. 1 Nr. 7 EStG</td>
    <td class="num pos">+{fmt(zins)}</td><td>Steuerpflichtig → Zeile 19</td></tr>
<tr><td>Wertpapierleihe (IBKR SYEP)</td><td>§ 20 Abs. 1 Nr. 7 EStG</td>
    <td class="num pos">+{fmt(syep)}</td><td>Steuerpflichtig → Zeile 19</td></tr>
<tr><td>Sollzinsen / Debit Interest</td><td>§ 20 Abs. 9 EStG</td>
    <td class="num neg">−{fmt(abs(sollzins))}</td>
    <td><b>NICHT abzugsfähig</b> (Abgeltungsteuer)</td></tr>
<tr class="grp"><td colspan="2"><b>Steuerlich wirksam</b></td>
    <td class="num pos"><b>+{fmt(zins+syep)}</b></td><td></td></tr>
</tbody></table>
<p class="meta">Zinsen nach Fälligkeitsprinzip (§ 11 EStG, Rn. 242 BMF): IBKR bucht am 3. Geschäftstag
des Folgemonats — Januar-Buchungen für Dezember zählen zum laufenden Steuerjahr.</p>

<!-- ══ 6. FX ══ -->
<h2 id="s6">6. Fremdwährungsgewinne und -verluste</h2>
<table class="data">
<thead><tr><th>Währung</th><th class="num">Gewinne §20 EStG</th>
  <th class="num">Verluste §20 EStG</th><th class="num">Netto</th><th>Hinweis</th></tr></thead>
<tbody>
{fx_rows()}
<tr class="grp"><td><b>Gesamt</b></td>
  <td class="num pos"><b>+{fmt(fx_g)}</b></td>
  <td class="num neg"><b>−{fmt(abs(fx_v))}</b></td>
  <td class="num neg"><b>{numcell(fx_n)}</b></td><td></td></tr>
</tbody></table>
<div class="warn"><b>FX-Methodik:</b> FIFO v1.1 — Guthaben/Verbindlichkeits-Trennung (§20 EStG),
Zufluss-First innerhalb eines Tages (BubbleTax-kompatibel). Kurse: IBKR fxRateToBase.
SEK und GBP: BubbleTax-Abgleich ±1 EUR ✓. USD: VB-Randeffekte ±70 EUR.</div>

<!-- ══ 7. KAPITALMAASSNAHMEN ══ -->
<div class="page-break"></div>
<h2 id="s7">7. Kapitalmaßnahmen</h2>
<p class="meta">Verarbeitung aller Corporate Actions aus IBKR Flex Query.
Marktwert-Hierarchie: 1. IBKR value-Feld · 2. Yahoo Finance Eröffnungskurs · 3. 0,00 EUR Fallback</p>
<table class="data">
<thead><tr><th>Datum</th><th>Typ / Vorgang</th><th>Symbol</th><th class="num">Menge</th>
  <th class="num">Sachausch.</th><th class="num">Realis. G/V</th><th>Rechtsgrundlage</th></tr></thead>
<tbody>
{km_rows()}
<tr class="grp">
  <td colspan="4"><b>Summe Kapitalmaßnahmen {STEUERJAHR}</b></td>
  <td class="num pos"><b>+{fmt(km_sachausch)}</b></td>
  <td class="num neg"><b>{numcell(km_gl)}</b></td><td></td>
</tr>
</tbody></table>
<div class="info">
<b>ENVXW Sachausschüttung:</b> IBKR-Marktwert (value-Feld) = 181,20 USD × 0,86227 EUR/USD = 156,24 EUR.
BubbleTax-Referenz: +15*,** EUR ✓. Tender Offer steuerneutral (§ 20 Abs. 4a Satz 1 EStG).
Delisting-Verlust = AK der 0,5714 Restanteile (5,4685 EUR/Stück).
</div>

<!-- ══ 8. WEITERE HINWEISE ══ -->
<h2 id="s8">8. Weitere steuerliche Hinweise</h2>

<h3>8.1 Günstigerprüfung (§ 32d Abs. 6 EStG)</h3>
<div class="neutral">Bei persönlichem Einkommensteuersatz unter 25 % (z.B. Rentenphase):
Antrag auf Günstigerprüfung in Anlage KAP Zeile 4. Das Finanzamt versteuert dann
mit dem individuellen Steuersatz. Nur sinnvoll bei nachweislich niedrigerem Satz.</div>

<h3>8.2 Kirchensteuer</h3>
<div class="info">Kirchensteuer auf Kapitalerträge aus ausländischen Depots wird <b>nicht automatisch
einbehalten</b>. ELSTER berechnet sie automatisch bei der Veranlagung (5,5 % Soli auf KapESt).
<b>Kein gesonderter Eintrag in Anlage KAP erforderlich.</b></div>

<h3>8.3 Aufbewahrungspflicht</h3>
<div class="neutral">IBKR Flex Query XML-Exporte und dieser Report: <b>10 Jahre aufzubewahren</b>
(§ 147 AO). IBKR stellt Daten erfahrungsgemäß nur 7 Jahre bereit → frühzeitig sichern!</div>

<!-- ══ 9. POSITIONEN ══ -->
<div class="page-break"></div>
<h2 id="s9">9. Offene Positionen</h2>

<h3>9.1 Jahresbeginn 01.01.{STEUERJAHR} ({len(ps)} Positionen · AK gesamt: {fmt(ak_s)})</h3>
<table class="data">
<thead><tr><th>Symbol</th><th>Beschreibung</th><th class="num">Bestand</th>
  <th class="num">Anschaffungskosten</th></tr></thead>
<tbody>
{pos_rows(ps)}
<tr class="grp"><td colspan="2"><b>Gesamt 01.01.{STEUERJAHR}</b></td>
  <td></td><td class="num"><b>{fmt(ak_s)}</b></td></tr>
</tbody></table>

<h3>9.2 Jahresende 31.12.{STEUERJAHR} ({len(pe)} Positionen · AK gesamt: {fmt(ak_e)})</h3>
<table class="data">
<thead><tr><th>Symbol</th><th>Beschreibung</th><th class="num">Bestand</th>
  <th class="num">Anschaffungskosten</th></tr></thead>
<tbody>
{pos_rows(pe)}
<tr class="grp"><td colspan="2"><b>Gesamt 31.12.{STEUERJAHR}</b></td>
  <td></td><td class="num"><b>{fmt(ak_e)}</b></td></tr>
</tbody></table>
<p class="meta">Diese Positionen sind steuerlich nicht realisiert.
Gewinne/Verluste entstehen erst bei späterer Veräußerung (§ 20 Abs. 2 EStG).</p>

<div class="disclaimer">
<b>Rechtlicher Hinweis:</b> Dieser Bericht dient der strukturierten Aufbereitung von Transaktionsdaten
und stellt keine steuerliche Beratung dar. Die Verantwortung für die Steuererklärung liegt beim
Steuerpflichtigen. Für komplexe Sachverhalte (FX, Kapitalmaßnahmen, Verlustvorträge) wird die
Hinzuziehung eines Steuerberaters empfohlen.
</div>
<div class="footer">Erstellt mit <b>Refundex Engine v4.0</b> · fifo_fx v1.1 · kapmassnm v1.0 · {NOW}</div>

<script>
var MODE='einzel';
function setMode(m,btn){{
  MODE=m;
  document.querySelectorAll('.toggle-bar button').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active');
  var g=(m==='gemein');
  document.querySelectorAll('.kap-split').forEach(el=>el.style.display=g?'inline':'none');
  ['th-gem','p-gem1','p-gem2','p-gem3'].forEach(id=>{{
    var el=document.getElementById(id);if(el)el.style.display=g?'':'none';
  }});
  document.getElementById('blk2').style.display=g?'':'none';
  updateNames();
}}
function updateNames(){{
  var n1=document.getElementById('name1').value;
  var n2=document.getElementById('name2').value;
  var ph=document.getElementById('ph-name');
  if(ph) ph.textContent=n1+(MODE==='gemein'&&n2?' / '+n2:'');
}}
</script>
</body></html>"""

OUT = '/mnt/user-data/outputs/Steuerreport_2025_U12074449_v4.html'
with open(OUT,'w',encoding='utf-8') as f:
    f.write(HTML)
print(f'\n✅ Report gespeichert: {OUT}')
print(f'   Größe: {len(HTML):,} Bytes')
