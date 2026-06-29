#!/usr/bin/env python3
"""Refundex Steuerreport v2 — vollständig mit allen KAP-Feldern"""
import xml.etree.ElementTree as ET
from collections import defaultdict, deque
from datetime import datetime

XMLS = [
    '/mnt/user-data/uploads/1782742593101_Steuerauswertung.xml',
    '/mnt/user-data/uploads/1782742593100_Steuerauswertung-2.xml',
    '/mnt/user-data/uploads/1782742593100_Steuerauswertung-3.xml',
]
STEUERJAHR = 2025; KONTO = 'U12074449'
NOW = datetime.now().strftime('%d.%m.%Y, %H:%M Uhr')

def load(path):
    root = ET.parse(path).getroot()
    s = root.find('.//FlexStatement')
    return s.findall('.//StatementOfFundsLine'), s.findall('.//OpenPosition')

all_lines=[]; lines25=[]
pos24=[]; pos25=[]
for i,p in enumerate(XMLS):
    lns,pos=load(p)
    all_lines.extend(lns)
    if i==1: pos24=pos
    if i==2: pos25=pos; lines25=lns

# ── Formatter ──
def fmt(v): return f'{abs(v):,.2f}\u00a0EUR'.replace(',','X').replace('.',',').replace('X','.')
def numcell(v):
    if v>0: return f'<span class="pos">+{fmt(v)}</span>'
    elif v<0: return f'<span class="neg">−{fmt(abs(v))}</span>'
    return fmt(0)
CL={'US':'🇺🇸&nbsp;USA','GB':'🇬🇧&nbsp;Großbritannien','BR':'🇧🇷&nbsp;Brasilien','DK':'🇩🇰&nbsp;Dänemark','SE':'🇸🇪&nbsp;Schweden'}
DBA={'US':0.15,'BR':0.15,'DK':0.15,'GB':0.0}

# ── Optionen ──
opt=defaultdict(lambda:{'prae':0,'rk':0,'desc':'','und':''})
for l in lines25:
    if l.get('assetCategory')!='OPT' or l.get('currency')!='EUR': continue
    c=l.get('activityCode',''); s=l.get('symbol','')
    opt[s]['desc']=l.get('description',''); opt[s]['und']=l.get('underlyingSymbol','')
    if c=='SELL': opt[s]['prae']+=float(l.get('amount','0'))
    elif c=='BUY': opt[s]['rk']+=float(l.get('amount','0'))

opt_items=sorted(opt.items(),key=lambda x:(x[1]['und'],x[1]['desc']))
opt_g=sum(v['prae']+v['rk'] for v in opt.values() if v['prae']+v['rk']>=0)
opt_v=sum(v['prae']+v['rk'] for v in opt.values() if v['prae']+v['rk']<0)
opt_n=opt_g+opt_v
# Verluste aus Stillhalter (alle sind §20 Abs. 1 Nr. 11 — kein Termingeschäft-Cap)
opt_v_stillh=abs(opt_v)  # Netto-Verluste bei Stillhalter-Kontrakten

# ── Dividenden ──
divs=defaultdict(lambda:defaultdict(lambda:{'div':0,'tax':0,'desc':''}))
for l in lines25:
    if l.get('assetCategory')!='STK' or l.get('currency')!='EUR': continue
    c=l.get('activityCode','')
    if c not in ('DIV','FRTAX'): continue
    sym=l.get('symbol',''); co=l.get('issuerCountryCode','')
    divs[co][sym]['desc']=l.get('description','')
    if c=='DIV': divs[co][sym]['div']+=float(l.get('amount','0'))
    elif c=='FRTAX': divs[co][sym]['tax']+=-float(l.get('amount','0'))

div_total=sum(s['div'] for c in divs.values() for s in c.values())
tax_total=sum(s['tax'] for c in divs.values() for s in c.values())
tax_anr=sum(min(s['tax'],s['div']*DBA.get(co,0)) for co,syms in divs.items() for s in syms.values())

# ── Zinsen ──
zins=0.; syep=0.; sollzins=0.
for l in lines25:
    if l.get('currency')!='EUR': continue
    c=l.get('activityCode',''); d=l.get('activityDescription',''); a=float(l.get('amount','0'))
    if c=='CINT':
        if 'SYEP' in d or 'Securities' in d: syep+=a
        else: zins+=a
    elif c=='DINT': sollzins+=a

# ── FX-FIFO ──
import sys as _sys; _sys.path.insert(0, '/home/claude')
from fifo_fx import fx_fifo_from_lines as _fx_engine

fx_res_raw=_fx_engine(all_lines,'2025')
fx_g=sum(r.gewinn_guthaben for r in fx_res_raw.values())
fx_v=sum(r.verlust_guthaben for r in fx_res_raw.values())
fx_n=fx_g+fx_v
# Für FX-Tabelle im Report
fx_res={cur:{'g':r.gewinn_guthaben,'v':r.verlust_guthaben,'vb':sum(1 for a in r.audit if a.typ=="VB")}
        for cur,r in fx_res_raw.items()}

# ── ENVXW ──
envxw_n=sum(float(l.get('amount','0')) for l in lines25
            if 'ENVXW' in l.get('symbol','') and l.get('currency')=='EUR')

# ── KAP-Zeilen ──
kap19_pos=opt_g+div_total+zins+syep+fx_g
kap19_neg=opt_v+fx_v+envxw_n
kap19=kap19_pos+kap19_neg
kap22=opt_v_stillh+abs(fx_v)  # nur negative Nettopositionen Stillhalter + FX-Verluste
kap41=tax_anr
SPARER=1000.0  # pro Person
kap19_nach_pausch=max(0, kap19-SPARER)

# ── Positionen ──
def plist(pos):
    r=[]
    for p in pos:
        r.append({'cat':p.get('assetCategory',''),'sym':p.get('symbol',''),
                  'desc':p.get('description',''),'qty':float(p.get('position','0')),
                  'ak':float(p.get('costBasisMoney','0'))})
    return sorted(r,key=lambda x:(x['cat'],-abs(x['ak'])))

ps=plist(pos24); pe=plist(pos25)
ak_s=sum(abs(p['ak']) for p in ps); ak_e=sum(abs(p['ak']) for p in pe)

def pos_rows(pl):
    rows=[]; cur=None
    for p in pl:
        lbl={'STK':'Aktien','OPT':'Short-Optionen (Stillhalter)'}.get(p['cat'],p['cat'])
        if lbl!=cur:
            rows.append(f'<tr class="grp"><td colspan="4"><b>{lbl}</b></td></tr>'); cur=lbl
        q=f'{abs(p["qty"]):,.4f}'.replace(',','X').replace('.',',').replace('X','.')
        rows.append(f'<tr><td>{p["sym"]}</td><td class="meta">{p["desc"]}</td>'
                    f'<td class="num">{q}</td><td class="num">{fmt(abs(p["ak"]))}</td></tr>')
    return '\n'.join(rows)

def opt_rows():
    rows=[]
    for sym,v in opt_items:
        n=v['prae']+v['rk']; nc='pos' if n>=0 else 'neg'
        rows.append(f'<tr><td>{v["desc"]}</td>'
                    f'<td class="num pos">+{fmt(v["prae"])}</td>'
                    f'<td class="num {"neg" if v["rk"]<0 else ""}">{"−"+fmt(abs(v["rk"])) if v["rk"]<0 else "+"+fmt(v["rk"])}</td>'
                    f'<td class="num {nc}">{numcell(n)}</td></tr>')
    return '\n'.join(rows)

def div_rows():
    rows=[]
    for co in sorted(divs.keys()):
        syms=divs[co]; dba=DBA.get(co,0)
        rows.append(f'<tr class="grp"><td colspan="5"><b>{CL.get(co,co)} — DBA-Quellensteuer-Höchstsatz: {int(dba*100)}\u00a0%</b></td></tr>')
        ct=cv=ca=0
        for sym,d in sorted(syms.items()):
            anr=min(d['tax'],d['div']*dba); ct+=d['div']; cv+=d['tax']; ca+=anr
            rows.append(f'<tr><td>{sym}</td><td class="meta">{d["desc"]}</td>'
                        f'<td class="num">{fmt(d["div"])}</td>'
                        f'<td class="num neg">{"−"+fmt(d["tax"]) if d["tax"]>0 else "—"}</td>'
                        f'<td class="num pos">{"+" + fmt(anr) if anr>0 else "0,00\u00a0EUR"}</td></tr>')
        rows.append(f'<tr class="grp"><td colspan="2"><b>Zwischensumme {CL.get(co,co)}</b></td>'
                    f'<td class="num"><b>{fmt(ct)}</b></td>'
                    f'<td class="num neg"><b>{"−"+fmt(cv) if cv>0 else "—"}</b></td>'
                    f'<td class="num pos"><b>{"+" + fmt(ca) if ca>0 else "0,00\u00a0EUR"}</b></td></tr>')
    return '\n'.join(rows)

print(f'KAP-19={kap19:.2f}  KAP-22={kap22:.2f}  KAP-41={kap41:.2f}')
print(f'opt_g={opt_g:.2f}  opt_v={opt_v:.2f}  opt_n={opt_n:.2f}')
print(f'div={div_total:.2f}  qst_anr={tax_anr:.2f}  zins={zins:.2f}  syep={syep:.2f}')
print(f'fx_g={fx_g:.2f}  fx_v={fx_v:.2f}  envxw={envxw_n:.2f}')
print('Daten OK — schreibe HTML...')

# ══════════════════════════════════════════════════════════════════════════════
# HTML
# ══════════════════════════════════════════════════════════════════════════════
HTML = f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<title>Steuerreport {STEUERJAHR} · {KONTO}</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'Segoe UI',Arial,sans-serif;font-size:10pt;color:#1a1a1a;background:#fff;line-height:1.5}}

/* Print */
@page{{size:A4;margin:20mm 15mm 18mm 15mm}}
@media print{{
  .no-print{{display:none!important}}
  .page-break{{page-break-before:always}}
  body{{font-size:9pt}}
  .print-header{{display:block!important;position:running(header)}}
}}
.print-header{{display:none;font-size:8pt;color:#555;text-align:right;
  border-bottom:1px solid #ccc;padding-bottom:3px;margin-bottom:6px}}

/* Layout */
h1{{font-size:18pt;color:#fff}}
h2{{font-size:13pt;color:#1a3a5c;margin:22px 0 8px;padding-bottom:4px;border-bottom:2.5px solid #1a3a5c}}
h3{{font-size:10.5pt;color:#2c5282;margin:14px 0 5px}}
.cover{{background:linear-gradient(135deg,#1a3a5c,#2c5282);color:#fff;padding:20px 24px;
  border-radius:5px;margin-bottom:18px}}
.cover .sub{{font-size:9pt;opacity:.85;margin-top:3px}}
.badge{{display:inline-block;margin-top:10px;padding:4px 12px;background:rgba(255,255,255,.2);
  border-radius:3px;font-size:9pt;font-weight:600}}

/* Karten */
.kap-box{{background:#f0f7ff;border:2px solid #1a3a5c;border-radius:5px;padding:16px 20px;margin-bottom:16px}}
.kap-row{{display:flex;align-items:baseline;margin:5px 0}}
.kap-zl{{color:#555;font-size:9pt;width:65px;flex-shrink:0}}
.kap-desc{{flex:1;font-size:9pt}}
.kap-amt{{font-weight:700;font-size:13pt;color:#1a3a5c;white-space:nowrap;margin-left:12px}}
.kap-amt.split{{font-size:11pt;color:#2c5282}}

/* Persönliche Daten */
.pers-grid{{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:10px 0}}
.pers-grid input,.pers-grid select{{width:100%;border:1px solid #b0bec5;border-radius:3px;
  padding:5px 8px;font-size:9.5pt;font-family:inherit}}
.pers-grid label{{font-size:8.5pt;color:#555;display:block;margin-bottom:2px}}
@media print{{.pers-grid input{{border:none;border-bottom:1px solid #ccc;border-radius:0}}}}

/* Toggle */
.toggle-bar{{display:flex;gap:0;margin:10px 0;border:1.5px solid #1a3a5c;border-radius:4px;overflow:hidden;width:fit-content}}
.toggle-bar button{{padding:6px 18px;border:none;background:#fff;cursor:pointer;font-size:9.5pt;font-family:inherit}}
.toggle-bar button.active{{background:#1a3a5c;color:#fff;font-weight:600}}

/* Alerts */
.warn{{background:#fffbeb;border:1.5px solid #d97706;padding:10px 14px;border-radius:4px;font-size:9pt;margin:8px 0}}
.danger{{background:#fef2f2;border:1.5px solid #dc2626;padding:10px 14px;border-radius:4px;font-size:9pt;margin:8px 0}}
.info{{background:#f0fdf4;border:1.5px solid #16a34a;padding:10px 14px;border-radius:4px;font-size:9pt;margin:8px 0}}
.neutral{{background:#f8fafc;border:1.5px solid #94a3b8;padding:10px 14px;border-radius:4px;font-size:9pt;margin:8px 0}}
.meta{{font-size:8.5pt;color:#666;margin:4px 0}}

/* Tabellen */
table.data{{width:100%;border-collapse:collapse;margin:6px 0 10px;font-size:9pt}}
table.data th{{background:#1a3a5c;color:#fff;padding:5px 8px;text-align:left;font-weight:600}}
table.data td{{padding:4px 8px;border-bottom:1px solid #e2e8f0;vertical-align:top}}
table.data tr.grp td{{background:#e8f0fe;font-weight:600;padding:5px 8px}}
table.data tr:last-child td{{border-bottom:2px solid #1a3a5c}}
table.data .num{{text-align:right;font-family:monospace;white-space:nowrap}}
table.data .pos{{color:#166534}}
table.data .neg{{color:#991b1b}}
table.data .meta{{color:#666;font-size:8.5pt}}

/* Input-Felder im Report */
.manual-input{{background:#fffbeb;border:1px dashed #d97706;border-radius:3px;
  padding:2px 6px;font-family:inherit;font-size:9.5pt;width:140px;text-align:right}}
@media print{{.manual-input{{border:none;border-bottom:1px solid #999;border-radius:0;background:transparent}}}}

.toc ol{{padding-left:20px;columns:2;gap:30px}}
.toc li{{margin:3px 0;font-size:9.5pt}}
.toc a{{color:#1a3a5c;text-decoration:none}}
.disclaimer{{font-size:8pt;color:#666;border-top:1px solid #ddd;padding-top:10px;margin-top:24px}}
.refundex-footer{{text-align:center;font-size:8pt;color:#999;margin-top:8px}}
</style>
</head>
<body>

<div class="print-header">
  Steuerreport {STEUERJAHR} · IBKR-Konto {KONTO} · Erstellt: {NOW}
  <span id="ph-name" style="margin-left:20px;font-weight:600"></span>
</div>

<!-- ══ TITELBEREICH ══ -->
<div class="cover">
  <h1>Steuerreport Kapitalerträge {STEUERJAHR}</h1>
  <div class="sub">Nachweis der steuerlichen Berechnungen · Interactive Brokers Depot</div>
  <div class="sub">Basis: IBKR Flex Query XML-Export (3 Dateien, 2023–2025) · FIFO-Bewertung</div>
  <span class="badge">Broker: Interactive Brokers &nbsp;·&nbsp; Konto-ID: {KONTO}</span>
  <span class="badge" style="margin-left:8px">Erstellt: {NOW}</span>
</div>

<!-- ══ KONTOART-TOGGLE ══ -->
<div class="no-print">
  <h3 style="margin-top:0">Kontoart</h3>
  <div class="toggle-bar">
    <button class="active" onclick="setMode('einzel')">Einzelkonto</button>
    <button onclick="setMode('gemein')">Gemeinschaftskonto (50/50)</button>
  </div>
</div>

<!-- ══ PERSÖNLICHE ANGABEN ══ -->
<h2>Persönliche Angaben</h2>
<div class="pers-grid">
  <div id="block-p1">
    <label>Steuerpflichtiger 1 — Name, Vorname</label>
    <input id="name1" type="text" placeholder="z. B. Hildebrand, Axel" oninput="updateNames()">
  </div>
  <div id="block-p2" style="display:none">
    <label>Steuerpflichtiger 2 — Name, Vorname</label>
    <input id="name2" type="text" placeholder="z. B. Hildebrand, Maria" oninput="updateNames()">
  </div>
  <div>
    <label>Steuernummer</label>
    <input id="steuernum" type="text" placeholder="z. B. 213/567/89012">
  </div>
  <div>
    <label>Zuständiges Finanzamt</label>
    <input id="finanzamt" type="text" placeholder="z. B. Finanzamt Krefeld">
  </div>
  <div>
    <label>Veranlagungsjahr</label>
    <input type="text" value="{STEUERJAHR}" readonly style="background:#f0f4f8">
  </div>
  <div>
    <label>IBKR-Konto</label>
    <input type="text" value="{KONTO}" readonly style="background:#f0f4f8">
  </div>
</div>

<!-- ══ PFLICHTVERANLAGUNG ══ -->
<div class="danger">
  <b>⚠️ Pflichtveranlagung (§ 32d Abs. 3 EStG)</b><br>
  Interactive Brokers ist ein <b>ausländisches Kreditinstitut</b> und führt <b>keine deutsche
  Kapitalertragsteuer (Abgeltungsteuer) ab</b>. Für Erträge aus diesem Depot besteht daher
  <b>gesetzliche Pflicht zur Abgabe der Anlage KAP</b> im Rahmen der Einkommensteuererklärung —
  unabhängig von der Höhe der Erträge und unabhängig davon, ob ein Steuerbetrag anfällt.
  Die Nichtabgabe stellt eine Steuerhinterziehung dar.
</div>

<!-- ══ 1. STEUERZUSAMMENFASSUNG ══ -->
<h2 id="s1">1. Steuerzusammenfassung — Anlage KAP {STEUERJAHR}</h2>

<div class="kap-box">
  <div class="kap-row">
    <span class="kap-zl"><b>Zeile 19</b></span>
    <span class="kap-desc">Ausländische Kapitalerträge (ohne Zeilen 26a und 52)</span>
    <span class="kap-amt" id="kap19">{fmt(kap19)}</span>
    <span class="kap-amt split" id="kap19s" style="display:none">&nbsp;(je {fmt(kap19/2)})</span>
  </div>
  <div class="kap-row" style="margin-top:8px">
    <span class="kap-zl"><b>Zeile 22</b></span>
    <span class="kap-desc">In Zeilen 18 und 19 enthaltene Verluste (ohne Aktienverluste)</span>
    <span class="kap-amt" id="kap22">{fmt(kap22)}</span>
    <span class="kap-amt split" id="kap22s" style="display:none">&nbsp;(je {fmt(kap22/2)})</span>
  </div>
  <div class="kap-row" style="margin-top:8px">
    <span class="kap-zl"><b>Zeile 41</b></span>
    <span class="kap-desc">Anrechenbare noch nicht angerechnete ausländische Steuern (Quellensteuer)</span>
    <span class="kap-amt" id="kap41">{fmt(kap41)}</span>
    <span class="kap-amt split" id="kap41s" style="display:none">&nbsp;(je {fmt(kap41/2)})</span>
  </div>
</div>

<!-- Sparer-Pauschbetrag -->
<h3>1.1 Sparer-Pauschbetrag (§ 20 Abs. 9 EStG)</h3>
<div class="warn">
  <b>Hinweis:</b> Interactive Brokers / CapTrader als ausländischer Broker berücksichtigt den
  Sparer-Pauschbetrag <b>nicht automatisch</b>. Der Pauschbetrag muss im Rahmen der
  Einkommensteuererklärung geltend gemacht werden (Anlage KAP, Zeile 16).
</div>
<table class="data">
<thead><tr><th>Position</th><th>Einzelkonto</th><th id="th-gem" style="display:none">Gemeinschaftskonto (je Person)</th></tr></thead>
<tbody>
<tr><td>Kapitalerträge (Zeile 19)</td>
    <td class="num">{fmt(kap19)}</td>
    <td class="num" id="td-gem1" style="display:none">{fmt(kap19/2)}</td></tr>
<tr><td>Sparer-Pauschbetrag (§ 20 Abs. 9 EStG)</td>
    <td class="num neg">−1.000,00&nbsp;EUR</td>
    <td class="num neg" id="td-gem2" style="display:none">−1.000,00&nbsp;EUR</td></tr>
<tr><td><b>Zu versteuernde Kapitalerträge (nach Pauschbetrag)</b></td>
    <td class="num pos"><b>{fmt(max(0,kap19-1000))}</b></td>
    <td class="num pos" id="td-gem3" style="display:none"><b>{fmt(max(0,kap19/2-1000))}</b></td></tr>
</tbody>
</table>

<!-- Verlustvortrag -->
<h3>1.2 Verlustvortrag Vorjahre (§ 20 Abs. 6 Satz 3 EStG)</h3>
<div class="neutral">
  IBKR / CapTrader weist keine deutschen Verlustvorträge aus. Falls aus Vorjahren (Anlage KAP)
  ein Verlustvortrag besteht, ist dieser manuell einzutragen und zu berücksichtigen.
</div>
<table class="data">
<tbody>
<tr><td>Verlustvortrag allgemeiner Topf (§ 20 Abs. 6 Satz 3)</td>
    <td class="num"><input class="manual-input" type="text" placeholder="0,00 EUR" id="vv1"></td></tr>
<tr><td>Verlustvortrag Termingeschäfte (§ 20 Abs. 6 Satz 5)</td>
    <td class="num"><input class="manual-input" type="text" placeholder="0,00 EUR" id="vv2"></td></tr>
<tr><td>Verlustvortrag Aktien (§ 20 Abs. 6 Satz 4)</td>
    <td class="num"><input class="manual-input" type="text" placeholder="0,00 EUR" id="vv3"></td></tr>
</tbody>
</table>

<!-- §20 Abs. 6 Satz 5 -->
<h3>1.3 Termingeschäft-Verlustverrechnungsgrenze (§ 20 Abs. 6 Satz 5 EStG)</h3>
<table class="data">
<thead><tr><th>Kategorie</th><th>Rechtsgrundlage</th><th class="num">Verluste 2025</th><th>20.000-EUR-Cap</th></tr></thead>
<tbody>
<tr>
  <td><b>Stillhaltergeschäfte</b> (Short Puts/Calls)</td>
  <td>§ 20 Abs. 1 Nr. 11 EStG</td>
  <td class="num neg">−{fmt(opt_v_stillh)}</td>
  <td class="info" style="padding:2px 6px;font-size:8.5pt"><b>Nicht betroffen</b> — allgemeiner Verlustverrechnungstopf</td>
</tr>
<tr>
  <td>Long-Optionskäufe (§ 20 Abs. 2 Nr. 3)</td>
  <td>§ 20 Abs. 6 Satz 5 EStG</td>
  <td class="num">0,00&nbsp;EUR</td>
  <td class="meta">Keine Long-Positionen in 2025 identifiziert</td>
</tr>
<tr class="grp">
  <td colspan="2"><b>Fazit: Termingeschäft-Cap greift in 2025 nicht</b></td>
  <td class="num pos"><b>0,00&nbsp;EUR</b> Sperrung</td>
  <td><b>Alle Verluste vollständig verrechenbar</b></td>
</tr>
</tbody>
</table>
<div class="info">
  <b>Erläuterung §&nbsp;20 Abs.&nbsp;6 Satz 5 EStG:</b> Verluste aus Termingeschäften
  (z.&nbsp;B. Long-Optionskäufe, §&nbsp;20 Abs.&nbsp;2 Nr.&nbsp;3) können nur mit Gewinnen aus
  Termingeschäften und mit Einkünften aus Stillhalterprämien verrechnet werden, maximal
  20.000&nbsp;EUR pro Jahr (übersteigende Beträge werden vorgetragen). <b>Stillhaltergeschäfte
  (§&nbsp;20 Abs.&nbsp;1 Nr.&nbsp;11) sind keine Termingeschäfte i.&nbsp;S. dieser Vorschrift</b>
  und fallen in den allgemeinen Verlustverrechnungstopf ohne Betragsbegrenzung.
  In 2025 wurden ausschließlich Stillhaltergeschäfte betrieben — der Cap ist nicht anwendbar.
</div>

<!-- ══ 2. HERLEITUNG ══ -->
<div class="page-break"></div>
<h2 id="s2">2. Steuerliche Herleitung</h2>
<table class="data">
<thead><tr><th>Kategorie</th><th>Rechtsgrundlage</th><th class="num">Erträge</th><th class="num">Verluste</th><th class="num">Netto</th></tr></thead>
<tbody>
<tr><td>Dividenden (ausländisch)</td><td>§ 20 Abs. 1 Nr. 1 EStG</td>
    <td class="num pos">+{fmt(div_total)}</td><td class="num">—</td><td class="num pos">+{fmt(div_total)}</td></tr>
<tr><td>Stillhaltergeschäfte</td><td>§ 20 Abs. 1 Nr. 11 EStG</td>
    <td class="num pos">+{fmt(opt_g)}</td><td class="num neg">−{fmt(abs(opt_v))}</td>
    <td class="num pos">+{fmt(opt_n)}</td></tr>
<tr><td>Guthabenzinsen</td><td>§ 20 Abs. 1 Nr. 7 EStG</td>
    <td class="num pos">+{fmt(zins)}</td><td class="num">—</td><td class="num pos">+{fmt(zins)}</td></tr>
<tr><td>Wertpapierleihe (SYEP)</td><td>§ 20 Abs. 1 Nr. 7 EStG</td>
    <td class="num pos">+{fmt(syep)}</td><td class="num">—</td><td class="num pos">+{fmt(syep)}</td></tr>
<tr><td>Devisenergebnisse <sup>*</sup></td><td>§ 20 Abs. 2 Satz 1 Nr. 7 i.V.m. Rn. 131 BMF</td>
    <td class="num pos">+{fmt(fx_g)}</td><td class="num neg">−{fmt(abs(fx_v))}</td>
    <td class="num neg">{numcell(fx_n)}</td></tr>
<tr><td>Kapitalmaßnahmen (ENVXW Tender/Delisting)</td><td>§ 20 Abs. 4a EStG</td>
    <td class="num">—</td><td class="num neg">−{fmt(abs(envxw_n))}</td>
    <td class="num neg">{numcell(envxw_n)}</td></tr>
<tr><td>Sollzinsen (nicht abzugsfähig)</td><td>§ 20 Abs. 9 EStG</td>
    <td class="num meta" colspan="3">−{fmt(abs(sollzins))} · <b>Kein Werbungskostenabzug bei Abgeltungsteuer</b></td></tr>
<tr class="grp"><td><b>Summe Anlage KAP (Zeile 19)</b></td><td></td>
    <td class="num pos"><b>+{fmt(kap19_pos)}</b></td><td class="num neg"><b>−{fmt(abs(kap19_neg))}</b></td>
    <td class="num pos"><b>+{fmt(kap19)}</b></td></tr>
</tbody>
</table>
<p class="meta"><sup>*</sup> FX-FIFO-Näherungsberechnung. Guthaben/Verbindlichkeits-Trennung teilweise vereinfacht — zur Präzisierung Abgleich mit Steuerberater empfohlen.</p>

<!-- ══ 3. STILLHALTER ══ -->
<div class="page-break"></div>
<h2 id="s3">3. Stillhaltergeschäfte (§ 20 Abs. 1 Nr. 11 EStG)</h2>
<div class="info"><b>Methodik:</b> Prämieneinnahme (Short Open) sofort steuerpflichtig beim Zufluss.
Rückkauf / Glattstellung mindert als negative Einnahme. Verfall wertlos: keine zusätzliche Erfassung.
Alle Kontrakte sind Stillhalter — keine Termingeschäfte i.&nbsp;S.&nbsp;v. §&nbsp;20 Abs.&nbsp;6 Satz&nbsp;5.</div>
<table class="data">
<thead><tr><th>Kontrakt</th><th class="num">Prämie eingenommen</th><th class="num">Rückkauf/Glattst.</th><th class="num">Nettoresultat</th></tr></thead>
<tbody>
{opt_rows()}
<tr class="grp">
  <td><b>Summe ({len(opt)} Kontrakte: {len([v for v in opt.values() if v["prae"]+v["rk"]>=0])} Gewinn / {len([v for v in opt.values() if v["prae"]+v["rk"]<0])} Verlust)</b></td>
  <td class="num pos"><b>+{fmt(opt_g)}</b></td>
  <td class="num neg"><b>−{fmt(abs(opt_v))}</b></td>
  <td class="num pos"><b>+{fmt(opt_n)}</b></td>
</tr>
</tbody>
</table>

<!-- ══ 4. DIVIDENDEN ══ -->
<div class="page-break"></div>
<h2 id="s4">4. Dividenden und Quellensteuer</h2>
<div class="meta" style="margin-bottom:8px">§ 20 Abs. 1 Nr. 1 EStG · Anrechenbare QST begrenzt auf DBA-Höchstsatz (§ 32d Abs. 5 EStG).
UK: keine Quellensteuer auf Dividenden an Ausländer. Dänemark (NVO-ADR): DBA 15%, aber einbehaltene QST übersteigt Limit → Differenz im Quellenstaat rückforderbar.</div>
<table class="data">
<thead><tr><th>Symbol</th><th>Wertpapier</th><th class="num">Brutto-Div.</th><th class="num">Einbeh. QST</th><th class="num">Anrechenbar (DBA)</th></tr></thead>
<tbody>
{div_rows()}
<tr class="grp"><td colspan="2"><b>Gesamt (50 Transaktionen, 4 Länder)</b></td>
  <td class="num pos"><b>+{fmt(div_total)}</b></td>
  <td class="num neg"><b>−{fmt(tax_total)}</b></td>
  <td class="num pos"><b>+{fmt(tax_anr)}</b></td></tr>
</tbody>
</table>

<!-- ══ 5. ZINSEN ══ -->
<h2 id="s5">5. Zinsen, Wertpapierleihe und Gebühren</h2>
<table class="data">
<thead><tr><th>Kategorie</th><th>Rechtsgrundlage</th><th class="num">Betrag</th><th>Steuerliche Behandlung</th></tr></thead>
<tbody>
<tr><td>Guthabenzinsen (EUR + USD)</td><td>§ 20 Abs. 1 Nr. 7 EStG</td>
    <td class="num pos">+{fmt(zins)}</td><td>Steuerpflichtig → Anlage KAP Zeile 19</td></tr>
<tr><td>Wertpapierleihe-Erträge (IBKR SYEP)</td><td>§ 20 Abs. 1 Nr. 7 EStG</td>
    <td class="num pos">+{fmt(syep)}</td><td>Steuerpflichtig → Anlage KAP Zeile 19</td></tr>
<tr><td>Sollzinsen / Debit Interest</td><td>§ 20 Abs. 9 EStG</td>
    <td class="num neg">−{fmt(abs(sollzins))}</td><td><b>NICHT abzugsfähig</b> (Abgeltungsteuer)</td></tr>
<tr class="grp"><td colspan="2"><b>Steuerlich wirksam</b></td>
    <td class="num pos"><b>+{fmt(zins+syep)}</b></td><td></td></tr>
</tbody>
</table>
<p class="meta">Zinsen nach Fälligkeitsprinzip (§ 11 EStG, Rn. 242 BMF): IBKR bucht Guthabenzinsen am 3. Geschäftstag des Folgemonats
→ Januar-Buchung für Dezember-Zeitraum zählt zum aktuellen Steuerjahr. Keine Rückverlagerung ins Vorjahr.</p>

<!-- ══ 6. FX ══ -->
<h2 id="s6">6. Fremdwährungsgewinne und -verluste</h2>
<div class="meta" style="margin-bottom:8px">
Rechtsgrundlage: § 20 Abs. 2 Satz 1 Nr. 7 i.V.m. Abs. 4 EStG, Rn. 131 BMF (BStBl I 2025).
FIFO-Zuordnung: § 23 Abs. 1 Nr. 2 Satz 3 EStG. Kursumrechnung: IBKR-integrierte Referenzkurse (fxRateToBase).
Alle Bestände konservativ als verzinsliche § 20-Sachverhalte (Rn. 131 BMF).
</div>
<table class="data">
<thead><tr><th>Währung</th><th class="num">Gewinne (§ 20 EStG)</th><th class="num">Verluste (§ 20 EStG)</th><th class="num">Netto</th></tr></thead>
<tbody>
{"".join(f'<tr><td>{cur}</td><td class="num pos">+{fmt(v["g"])}</td><td class="num neg">−{fmt(abs(v["v"]))}</td><td class="num {"pos" if v["g"]+v["v"]>=0 else "neg"}">{numcell(v["g"]+v["v"])}</td></tr>' for cur,v in sorted(fx_res.items()))}
<tr class="grp"><td><b>Gesamt</b></td><td class="num pos"><b>+{fmt(fx_g)}</b></td>
  <td class="num neg"><b>−{fmt(abs(fx_v))}</b></td>
  <td class="num neg"><b>{numcell(fx_n)}</b></td></tr>
</tbody>
</table>
<div class="warn"><b>Hinweis FX:</b> Verbindlichkeitsdifferenzen (negativer Saldo / Margin-Kredit) sind nach BubbleTax-Methodik
separat auszuweisen und nicht nach § 20 EStG steuerpflichtig. Die vereinfachte FIFO-Berechnung
kann diese Abgrenzung nicht vollständig leisten → Differenz zu anderen Berechnungsmethoden möglich.
Empfehlung: Für die endgültige Steuererklärung Abstimmung mit Steuerberater.</div>

<!-- ══ 7. KAPITALMAASSNAHMEN ══ -->
<h2 id="s7">7. Kapitalmaßnahmen (ENVXW)</h2>
<table class="data">
<thead><tr><th>Datum</th><th>Vorgang</th><th class="num">EUR</th><th>Rechtsgrundlage</th></tr></thead>
<tbody>
<tr><td>16.07.2025</td><td>Spin-Off ENVX → ENVXW (1:7) — Sachausschüttung</td>
    <td class="num">0,00&nbsp;EUR</td><td>§ 20 Abs. 4a Satz 7 EStG — steuerneutral; AK anteilig übertragen</td></tr>
<tr><td>22.08.2025</td><td>Tender Offer: 28 Stück ENVXW → ENVX, Barausgleich −8,75 USD/Stück</td>
    <td class="num neg">−209,03&nbsp;EUR</td><td>§ 20 Abs. 4a EStG — Tausch steuerpflichtig (CORP-Buchung)</td></tr>
<tr><td>26.09.2025</td><td>Delisting — 0,5714 Stück ENVXW Totalverlust</td>
    <td class="num neg">ca.&nbsp;−4,00&nbsp;EUR</td><td>§ 20 Abs. 2 Satz 1 Nr. 1 EStG — Totalverlust (AK anteilig)</td></tr>
<tr class="grp"><td colspan="2"><b>Nettoresultat ENVXW</b></td>
    <td class="num neg"><b>−{fmt(abs(envxw_n))}</b></td><td></td></tr>
</tbody>
</table>

<!-- ══ 8. HINWEISE ══ -->
<h2 id="s8">8. Weitere steuerliche Hinweise</h2>

<h3>8.1 Günstigerprüfung (§ 32d Abs. 6 EStG)</h3>
<div class="neutral">
Liegt der persönliche Einkommensteuersatz unter 25&nbsp;% (z.&nbsp;B. bei niedrigem Gesamteinkommen oder
in der Rentenphase), kann auf Antrag die <b>Günstigerprüfung</b> beantragt werden.
Das Finanzamt versteuert die Kapitalerträge dann mit dem individuellen Steuersatz statt der
Abgeltungsteuer. Antrag in der Steuererklärung (Zeile 4 Anlage KAP). Der Antrag ist freiwillig
und lohnt sich nur bei nachweislich niedrigerem persönlichen Steuersatz.
</div>

<h3>8.2 Kirchensteuer</h3>
<div class="info">
Die Kirchensteuer auf Kapitalerträge aus ausländischen Depots wird <b>nicht automatisch einbehalten</b>.
Sie wird von ELSTER bei der Veranlagung automatisch auf Basis der Abgeltungsteuer berechnet
(Kirchensteuersatz × Abgeltungsteuer, nach Abzug des Soli). <b>Kein gesonderter Eintrag
in der Anlage KAP erforderlich</b> — ELSTER ermittelt die Kirchensteuer automatisch,
sofern die Kirchensteuerpflicht im Einkommensteuerbescheid hinterlegt ist.
</div>

<h3>8.3 Solidaritätszuschlag</h3>
<div class="neutral">
Der Solidaritätszuschlag auf Kapitalerträge entfällt seit 2021 für die meisten Steuerpflichtigen
(Einkommensteuer unter ca. 17.543&nbsp;EUR). Bei Kapitalerträgen, die der Abgeltungsteuer unterliegen,
gilt weiterhin 5,5&nbsp;% Soli auf die Abgeltungsteuer — wird automatisch von ELSTER berechnet.
</div>

<h3>8.4 Aufbewahrungspflicht</h3>
<div class="neutral">
Die IBKR Flex Query XML-Exporte und dieser Report sind <b>10 Jahre aufzubewahren</b>
(§ 147 AO). Empfehlung: Originalfiles + diesen Report als PDF archivieren.
IBKR stellt Kontodaten erfahrungsgemäß nur für die letzten 7 Jahre zur Verfügung.
</div>

<!-- ══ 9. POSITIONEN ══ -->
<div class="page-break"></div>
<h2 id="s9">9. Offene Positionen</h2>

<h3>9.1 Jahresbeginn 01.01.{STEUERJAHR} ({len(ps)} Positionen)</h3>
<table class="data">
<thead><tr><th>Symbol</th><th>Beschreibung</th><th class="num">Bestand</th><th class="num">Anschaffungskosten</th></tr></thead>
<tbody>
{pos_rows(ps)}
<tr class="grp"><td colspan="2"><b>Gesamt 01.01.{STEUERJAHR}</b></td><td></td><td class="num"><b>{fmt(ak_s)}</b></td></tr>
</tbody>
</table>

<h3>9.2 Jahresende 31.12.{STEUERJAHR} ({len(pe)} Positionen)</h3>
<table class="data">
<thead><tr><th>Symbol</th><th>Beschreibung</th><th class="num">Bestand</th><th class="num">Anschaffungskosten</th></tr></thead>
<tbody>
{pos_rows(pe)}
<tr class="grp"><td colspan="2"><b>Gesamt 31.12.{STEUERJAHR}</b></td><td></td><td class="num"><b>{fmt(ak_e)}</b></td></tr>
</tbody>
</table>
<p class="meta">Diese Positionen sind steuerlich nicht realisiert. Gewinne oder Verluste entstehen erst bei späterer Veräußerung (§ 20 Abs. 2 EStG).</p>

<!-- Footer -->
<div class="disclaimer">
<b>Rechtlicher Hinweis:</b> Dieser Bericht dient der strukturierten Aufbereitung von Transaktionsdaten und stellt
keine steuerliche Beratung dar. Die steuerliche Verantwortung liegt beim Steuerpflichtigen.
Für die finale Würdigung — insbesondere bei komplexen FX-Sachverhalten, Kapitalmaßnahmen und
Verlustvorträgen — wird die Hinzuziehung eines Steuerberaters empfohlen.
</div>
<div class="refundex-footer">Erstellt mit <b>Refundex</b> · ahsub/refundex · {NOW}</div>

<!-- JavaScript -->
<script>
var MODE='einzel';
function setMode(m){{
  MODE=m;
  document.querySelectorAll('.toggle-bar button').forEach(b=>b.classList.remove('active'));
  event.target.classList.add('active');
  var isG=(m==='gemein');
  ['kap19s','kap22s','kap41s'].forEach(id=>document.getElementById(id).style.display=isG?'':'none');
  ['th-gem','td-gem1','td-gem2','td-gem3'].forEach(id=>{{var el=document.getElementById(id);if(el)el.style.display=isG?'':'none';}});
  document.getElementById('block-p2').style.display=isG?'':'none';
  updateNames();
}}
function updateNames(){{
  var n1=document.getElementById('name1').value;
  var n2=document.getElementById('name2').value;
  var ph=document.getElementById('ph-name');
  if(ph)ph.textContent=n1+(MODE==='gemein'&&n2?' / '+n2:'');
}}
</script>
</body>
</html>"""

out='/mnt/user-data/outputs/Steuerreport_2025_U12074449_v2.html'
with open(out,'w',encoding='utf-8') as f:
    f.write(HTML)
print(f'Gespeichert: {out}  ({len(HTML):,} Bytes)')
