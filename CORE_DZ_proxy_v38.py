#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CORE-DZ Proxy v38 — ActiveGPS Algeofleet
URLs 100% confirmées par inspection réseau (05/03/2026)

ENDPOINTS RÉELS :
  GET  /rest/dashboard/live
  GET  /rest/mapview/events
  POST /rest/dashboard/history   (Form Data: days=[timestamps_ms])
  GET  /rest/mapview/vehiculesId
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from urllib.parse import urlencode
import json
import threading
import time
import gzip

# ─────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────
BASE_URL = "https://activegps.algeofleet.com"
import os
PORT     = int(os.environ.get('PORT', 5000))

# Headers de base (sans cookie — la session est gérée côté serveur)
COOKIE = (
    "_ga=GA1.1.1847861242.1768304216;"
    "JSESSIONID=F316EB0C802FE3B32607CA160E0EED79.node1;"
    "SERVER_USED=s2|aajK+|aajFq;"
    "_ga_2NJFDN7DHN=GS2.1.s1772668333$o32$g1$t1772669685$j60$l0$h0"
)

HEADERS_GET = {
    "Accept":           "application/json, text/javascript, */*; q=0.01",
    "Accept-Encoding":  "identity",
    "Accept-Language":  "fr-DZ,fr-FR;q=0.9,fr;q=0.8",
    "Connection":       "keep-alive",
    "Cookie":           COOKIE,
    "Host":             "activegps.algeofleet.com",
    "Referer":          "https://activegps.algeofleet.com/dashbord.xhtml",
    "X-Requested-With": "XMLHttpRequest",
    "User-Agent":       "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/145.0.0.0 Safari/537.36",
}

HEADERS_POST = {**HEADERS_GET, "Content-Type": "application/x-www-form-urlencoded"}

# ─────────────────────────────────────────────
#  UTILITAIRES
# ─────────────────────────────────────────────
def last_7_days_timestamps():
    """Timestamps minuit heure algérienne (UTC+1 = 23h00 UTC la veille)"""
    import time as _t
    now = _t.time()
    tz_offset = 3600  # UTC+1 Algérie
    today_midnight_local = (int(now + tz_offset) // 86400) * 86400 - tz_offset
    return [str((today_midnight_local - i * 86400) * 1000) for i in range(6, -1, -1)]


def fetch_get(path):
    url = BASE_URL + path
    req = Request(url, headers=HEADERS_GET)
    with urlopen(req, timeout=15) as r:
        return r.read(), r.status


def fetch_post(path, form_data):
    url  = BASE_URL + path
    body = urlencode(form_data, doseq=True).encode('utf-8')
    req  = Request(url, data=body, headers=HEADERS_POST, method='POST')
    with urlopen(req, timeout=15) as r:
        return r.read(), r.status


# ─────────────────────────────────────────────
#  DASHBOARD HTML
# ─────────────────────────────────────────────
DASHBOARD = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>CORE-DZ v38 | Gestion de Flotte</title>
<style>
:root{--bg:#0a0e1a;--card:#111827;--border:#1e293b;
      --accent:#00e5ff;--green:#00e676;--yellow:#ffea00;--red:#ff1744;--orange:#ff9800}
*{margin:0;padding:0;box-sizing:border-box}
body{background:var(--bg);color:#e2e8f0;font-family:'Segoe UI',sans-serif;min-height:100vh}

/* HEADER */
header{background:linear-gradient(135deg,#0d1b4b,#1a237e);
       padding:14px 24px;display:flex;align-items:center;
       justify-content:space-between;border-bottom:2px solid var(--accent)}
header h1{font-size:1.4rem;color:var(--accent);letter-spacing:2px}
.btn{padding:7px 16px;border:none;border-radius:8px;cursor:pointer;
     font-weight:700;font-size:.82rem;transition:opacity .2s}
.btn:hover{opacity:.8}
.btn-primary{background:var(--accent);color:#000}
.btn-dark{background:#1e293b;color:#e2e8f0}

/* STATUS BAR */
.sbar{background:#0d1117;padding:6px 24px;font-size:.8rem;
      display:flex;gap:20px;align-items:center;border-bottom:1px solid var(--border)}
.dot{width:8px;height:8px;border-radius:50%;display:inline-block;margin-right:5px}
.dot.g{background:var(--green);box-shadow:0 0 6px var(--green)}
.dot.r{background:var(--red);box-shadow:0 0 6px var(--red)}
.dot.y{background:var(--yellow);box-shadow:0 0 6px var(--yellow)}

/* TABS */
.tabs{display:flex;gap:4px;padding:16px 24px 0}
.tab{padding:8px 20px;border-radius:8px 8px 0 0;cursor:pointer;
     font-size:.85rem;font-weight:600;background:#1e293b;color:#64748b;border:1px solid var(--border)}
.tab.active{background:var(--card);color:var(--accent);border-bottom-color:var(--card)}

/* PANELS */
.panel{display:none;padding:16px 24px 24px}
.panel.active{display:block}

/* KPI GRID */
.kpi-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:14px;margin-bottom:20px}
.kpi{background:var(--card);border:1px solid var(--border);border-radius:12px;
     padding:16px;text-align:center;transition:transform .2s}
.kpi:hover{transform:translateY(-2px);border-color:var(--accent)}
.kpi .val{font-size:2rem;font-weight:700;color:var(--accent)}
.kpi .lbl{font-size:.78rem;color:#94a3b8;margin-top:4px}
.kpi .sub{font-size:.72rem;color:#475569;margin-top:2px}

/* TABLES */
.tbl-wrap{overflow-x:auto;border-radius:8px;border:1px solid var(--border)}
table{width:100%;border-collapse:collapse;font-size:.83rem}
th{background:#1e293b;color:var(--accent);padding:10px 12px;text-align:left;font-weight:600}
td{padding:8px 12px;border-bottom:1px solid var(--border)}
tr:last-child td{border-bottom:none}
tr:hover td{background:#1e293b55}

/* TAGS */
.tag{display:inline-block;padding:2px 9px;border-radius:10px;font-size:.73rem;font-weight:700}
.tag-on  {background:#00e67622;color:var(--green);border:1px solid var(--green)}
.tag-off {background:#ff174422;color:var(--red);border:1px solid var(--red)}
.tag-idle{background:#ffea0022;color:var(--yellow);border:1px solid var(--yellow)}
.tag-evt {background:#ff980022;color:var(--orange);border:1px solid var(--orange)}

/* SECTION TITLE */
h2{font-size:.95rem;color:var(--accent);margin-bottom:12px;
   padding-bottom:6px;border-bottom:1px solid var(--border)}

/* HISTORY CHART */
.chart-bar-wrap{display:flex;align-items:flex-end;gap:6px;height:140px;margin-top:8px}
.bar-col{display:flex;flex-direction:column;align-items:center;flex:1}
.bar{background:var(--accent);border-radius:4px 4px 0 0;width:100%;
     min-height:4px;transition:height .5s}
.bar-lbl{font-size:.68rem;color:#64748b;margin-top:4px;text-align:center}
.bar-val{font-size:.7rem;color:var(--accent);margin-bottom:2px}

/* RAW */
#raw{background:#0d1117;border:1px solid var(--border);border-radius:8px;
     padding:12px;font-family:monospace;font-size:.75rem;color:#94a3b8;
     max-height:260px;overflow-y:auto;margin-top:12px}

footer{text-align:center;padding:12px;font-size:.72rem;color:#334155}
</style>
</head>
<body>

<header>
  <h1>⚡ CORE-DZ <span style="color:#fff;font-weight:300">v38</span></h1>
  <div style="display:flex;gap:8px;align-items:center">
    <span id="clock" style="color:#94a3b8;font-size:.83rem"></span>
    <span id="mode-badge" class="tag tag-idle" style="font-size:.8rem">INIT</span>
    <button class="btn btn-primary" onclick="loadAll()">↻ Actualiser</button>
    <button class="btn btn-dark"    onclick="showRaw()">JSON brut</button>
  </div>
</header>

<div class="sbar">
  <span><span class="dot y" id="dot"></span><span id="stext">Connexion...</span></span>
  <span>MAJ : <span id="last-upd">—</span></span>
  <span>activegps.algeofleet.com | 197.140.18.9:443</span>
</div>

<!-- TABS -->
<div class="tabs">
  <div class="tab active" onclick="switchTab('live')">🚛 Flotte Live</div>
  <div class="tab"        onclick="switchTab('events')">🔔 Événements</div>
  <div class="tab"        onclick="switchTab('history')">📊 Activité events</div>
  <div class="tab"        onclick="switchTab('raw')">🔧 JSON brut</div>
</div>

<!-- PANEL LIVE -->
<div class="panel active" id="tab-live">
  <div class="kpi-grid">
    <div class="kpi"><div class="val" id="k-total">—</div><div class="lbl">Total véhicules</div></div>
    <div class="kpi"><div class="val" id="k-on" style="color:var(--green)">—</div><div class="lbl">En ligne</div><div class="sub" id="k-mov">—</div></div>
    <div class="kpi"><div class="val" id="k-idle" style="color:var(--yellow)">—</div><div class="lbl">Au ralenti</div></div>
    <div class="kpi"><div class="val" id="k-off" style="color:var(--red)">—</div><div class="lbl">Hors ligne</div></div>
  </div>
  <h2>Positions en temps réel</h2>
  <div class="tbl-wrap">
    <table>
      <thead><tr><th>Véhicule</th><th>Statut</th><th>Vitesse</th><th>Localisation</th><th>Dernière MAJ</th></tr></thead>
      <tbody id="tb-live"><tr><td colspan="5" style="text-align:center;color:#475569">Chargement...</td></tr></tbody>
    </table>
  </div>
</div>

<!-- PANEL EVENTS -->
<div class="panel" id="tab-events">
  <div class="kpi-grid">
    <div class="kpi"><div class="val" id="k-evtotal" style="color:var(--orange)">—</div><div class="lbl">Événements aujourd'hui</div></div>
  </div>
  <h2>Événements récents</h2>
  <div class="tbl-wrap">
    <table>
      <thead><tr><th>Heure</th><th>Véhicule</th><th>Type</th><th>Détails</th></tr></thead>
      <tbody id="tb-events"><tr><td colspan="4" style="text-align:center;color:#475569">Chargement...</td></tr></tbody>
    </table>
  </div>
</div>

<!-- PANEL HISTORY — calculé depuis events -->
<div class="panel" id="tab-history">
  <h2>📊 Activité des 7 derniers jours — calculée depuis les événements</h2>
  <div class="chart-bar-wrap" id="chart-bars" style="height:160px;margin-bottom:16px"></div>
  <div class="tbl-wrap">
    <table>
      <thead><tr><th>Date</th><th>Événements</th><th>Véhicules distincts</th><th>Type dominant</th></tr></thead>
      <tbody id="tb-history"><tr><td colspan="4" style="text-align:center;color:#475569">Chargement events...</td></tr></tbody>
    </table>
  </div>
</div>

<!-- PANEL RAW -->
<div class="panel" id="tab-raw">
  <h2>Données JSON brutes reçues de ActiveGPS</h2>
  <div id="raw">En attente de données...</div>
</div>

<footer>CORE-DZ v38 — Proxy ActiveGPS Algeofleet — Données réelles 🟢</footer>

<script>
let allRaw = {};

// ── TABS ──
function switchTab(name) {
  document.querySelectorAll('.tab').forEach((t,i)=>{
    t.classList.toggle('active', ['live','events','history','raw'][i]===name);
  });
  document.querySelectorAll('.panel').forEach(p=>p.classList.remove('active'));
  document.getElementById('tab-'+name).classList.add('active');
}

function showRaw() { switchTab('raw'); }

// ── CLOCK ──
function updateClock() {
  document.getElementById('clock').textContent = new Date().toLocaleTimeString('fr-FR');
}

// ── STATUS ──
function setStatus(ok, msg) {
  const d = document.getElementById('dot');
  d.className = 'dot ' + (ok?'g':'r');
  document.getElementById('stext').textContent = msg;
  const b = document.getElementById('mode-badge');
  b.textContent = ok ? '🟢 RÉEL' : '🔴 ERREUR';
  b.className   = ok ? 'tag tag-on' : 'tag tag-off';
}

// ── HELPERS ──
function f(v, u='') { return (v===null||v===undefined||v==='')?'—':v+(u?' '+u:''); }

function statusTag(s) {
  if(!s) return '<span class="tag tag-off">—</span>';
  const u = s.toString().toUpperCase();
  if(u.includes('ONLINE')||u.includes('MOVING')||u==='1'||u==='ON')
    return '<span class="tag tag-on">EN LIGNE</span>';
  if(u.includes('IDLE')||u.includes('STOP')||u==='0')
    return '<span class="tag tag-idle">ARRÊTÉ</span>';
  return '<span class="tag tag-off">HORS LIGNE</span>';
}

// ── RENDER LIVE ──
function renderLive(data) {
  const arr = Array.isArray(data)?data:(data.vehicles||data.data||data.list||data.result||[]);
  let on=0,idle=0,off=0,mov=0, rows='';

  arr.forEach(v=>{
    const name  = v.name||v.vehicleName||v.plate||v.immatriculation||v.id||'—';
    const speed = v.speed!==undefined?v.speed:(v.vitesse??'—');
    const stat  = (v.status||v.state||v.etat||'').toString();
    const loc   = v.address||v.location||v.localisation||(v.lat&&v.lng?`${v.lat}, ${v.lng}`:'—');
    const upd   = v.lastUpdate||v.last_update||v.date||v.time||'—';
    const su    = stat.toUpperCase();
    if(su.includes('ONLINE')||su.includes('MOVING')||su==='1'||su==='ON'){on++;if(parseFloat(speed)>0)mov++;}
    else if(su.includes('IDLE')||su.includes('STOP')||su==='0') idle++;
    else off++;
    rows+=`<tr>
      <td><strong>${name}</strong></td>
      <td>${statusTag(stat)}</td>
      <td>${f(speed,'km/h')}</td>
      <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${loc}</td>
      <td style="color:#64748b;font-size:.78rem">${upd}</td>
    </tr>`;
  });

  document.getElementById('tb-live').innerHTML = rows||'<tr><td colspan="5" style="text-align:center;color:#ffea00">Aucun véhicule</td></tr>';
  document.getElementById('k-total').textContent = arr.length;
  document.getElementById('k-on').textContent    = on;
  document.getElementById('k-idle').textContent  = idle;
  document.getElementById('k-off').textContent   = off;
  document.getElementById('k-mov').textContent   = mov+' en mouvement';
}

// ── RENDER EVENTS ──
function renderEvents(data) {
  const arr = Array.isArray(data)?data:(data.events||data.data||data.list||data.result||[]);
  document.getElementById('k-evtotal').textContent = arr.length;
  if(!arr.length){
    document.getElementById('tb-events').innerHTML='<tr><td colspan="4" style="text-align:center;color:#475569">Aucun événement</td></tr>';
    return;
  }
  document.getElementById('tb-events').innerHTML = arr.slice(0,50).map(e=>{
    const h = e.date||e.time||e.timestamp||e.dateEvent||'—';
    const v = e.vehicleName||e.name||e.plate||e.vehicleId||'—';
    const t = e.type||e.eventType||e.typeEvent||'—';
    const d = e.description||e.details||e.message||e.address||'—';
    return `<tr>
      <td style="color:#94a3b8;font-size:.78rem;white-space:nowrap">${h}</td>
      <td><strong>${v}</strong></td>
      <td><span class="tag tag-evt">${t}</span></td>
      <td style="color:#64748b;font-size:.8rem">${d}</td>
    </tr>`;
  }).join('');
}

// ── RENDER HISTORY — calculé depuis events ──
function renderHistoryFromEvents(eventsData) {
  const arr = Array.isArray(eventsData)?eventsData:(eventsData.events||eventsData.data||eventsData.list||eventsData.result||[]);
  
  // Grouper par jour
  const days = {};
  arr.forEach(e => {
    const raw = e.date||e.time||e.timestamp||e.dateEvent||'';
    if(!raw) return;
    // Extraire la date YYYY-MM-DD ou DD/MM/YYYY
    let day = raw.toString().substring(0,10);
    if(!days[day]) days[day] = {count:0, vehicles:new Set(), types:{}};
    days[day].count++;
    const veh = e.vehicleName||e.name||e.plate||e.vehicleId||'';
    if(veh) days[day].vehicles.add(veh);
    const type = e.type||e.eventType||e.typeEvent||'Autre';
    days[day].types[type] = (days[day].types[type]||0)+1;
  });

  const sorted = Object.keys(days).sort();
  if(!sorted.length){
    document.getElementById('tb-history').innerHTML='<tr><td colspan="4" style="text-align:center;color:#475569">Aucun événement à analyser</td></tr>';
    document.getElementById('chart-bars').innerHTML='';
    return;
  }

  const maxV = Math.max(...sorted.map(d=>days[d].count), 1);

  document.getElementById('chart-bars').innerHTML = sorted.map(day=>{
    const d   = days[day];
    const pct = Math.round((d.count/maxV)*100);
    return `<div class="bar-col">
      <div class="bar-val" style="font-size:.68rem">${d.count}</div>
      <div class="bar" style="height:${Math.max(pct,3)}%"></div>
      <div class="bar-lbl">${day.substring(5)}</div>
    </div>`;
  }).join('');

  document.getElementById('tb-history').innerHTML = sorted.map(day=>{
    const d = days[day];
    const dominant = Object.entries(d.types).sort((a,b)=>b[1]-a[1])[0];
    return `<tr>
      <td>${day}</td>
      <td><strong style="color:var(--orange)">${d.count}</strong></td>
      <td>${d.vehicles.size}</td>
      <td><span class="tag tag-evt">${dominant?dominant[0]:'—'}</span></td>
    </tr>`;
  }).join('');
}

// ── FETCH API ──
async function api(path) {
  const r = await fetch(path);
  if(!r.ok) throw new Error('HTTP '+r.status);
  return r.json();
}

// ── LOAD ALL ──
async function loadAll() {
  document.getElementById('last-upd').textContent = 'Chargement...';
  allRaw = {};
  let ok = false;

  // LIVE
  try {
    const d = await api('/api/live');
    renderLive(d); allRaw.live=d; ok=true;
  } catch(e) {
    document.getElementById('tb-live').innerHTML=
      `<tr><td colspan="5" style="color:var(--red);text-align:center">❌ live : ${e.message}</td></tr>`;
  }

  // EVENTS
  try {
    const d = await api('/api/events');
    renderEvents(d); allRaw.events=d; ok=true;
  } catch(e) {
    document.getElementById('tb-events').innerHTML=
      `<tr><td colspan="4" style="color:var(--red);text-align:center">❌ events : ${e.message}</td></tr>`;
  }

  // HISTORY — calculé depuis les events déjà chargés
  if(allRaw.events) {
    try { renderHistoryFromEvents(allRaw.events); } catch(e) { console.error(e); }
  }

  // VEHICULES ID (utilisé en interne)
  try {
    const d = await api('/api/vehiculesId');
    allRaw.vehiculesId=d;
  } catch(e) { /* silencieux */ }

  setStatus(ok, ok?'Connecté — données réelles ActiveGPS':'Erreur de connexion');
  document.getElementById('last-upd').textContent = new Date().toLocaleTimeString('fr-FR');
  document.getElementById('raw').textContent = JSON.stringify(allRaw, null, 2);
}

// ── INIT ──
setInterval(updateClock, 1000);
updateClock();
loadAll();
setInterval(loadAll, 30000);
</script>
</body>
</html>"""

# ─────────────────────────────────────────────
#  HANDLER
# ─────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        print(f"  [{time.strftime('%H:%M:%S')}] {fmt % args}")

    def send_json(self, data, status=200):
        body = data if isinstance(data, bytes) else json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_page(self, html):
        body = html.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def proxy_get(self, remote):
        url = BASE_URL + remote
        print(f"  → GET {url}")
        try:
            req = Request(url, headers=HEADERS_GET)
            with urlopen(req, timeout=15) as r:
                data = r.read()
                print(f"  ✅ {r.status} — {len(data)} bytes")
                self.send_json(data)
        except HTTPError as e:
            print(f"  ❌ HTTP {e.code}")
            self.send_json({"error": f"HTTP {e.code}", "url": url}, e.code)
        except Exception as e:
            print(f"  ❌ {e}")
            self.send_json({"error": str(e)}, 503)

    def do_GET(self):
        path = self.path.split('?')[0]

        if path in ('/', '/index.html'):
            self.send_page(DASHBOARD)
        elif path == '/ping':
            self.send_json({"status": "ok", "version": "v38"})
        elif path == '/api/live':
            self.proxy_get('/rest/dashboard/live')
        elif path == '/api/events':
            self.proxy_get('/rest/mapview/events')
        elif path == '/api/vehiculesId':
            self.proxy_get('/rest/mapview/vehiculesId')
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'Not found')

# ─────────────────────────────────────────────
#  KEEPALIVE
# ─────────────────────────────────────────────
def keepalive():
    from urllib.request import urlopen as ul
    while True:
        time.sleep(120)
        try:
            ul(f"http://localhost:{PORT}/ping", timeout=5)
            print(f"  [{time.strftime('%H:%M:%S')}] keepalive ✅")
        except:
            pass

# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 55)
    print("  CORE-DZ Proxy v38 — ActiveGPS Algeofleet")
    print("  URLs réelles confirmées 05/03/2026")
    print("=" * 55)
    print(f"  Dashboard   : http://localhost:{PORT}")
    print(f"  /api/live        → GET  /rest/dashboard/live")
    print(f"  /api/events      → GET  /rest/mapview/events")
    print(f"  /api/history     → POST /rest/dashboard/history")
    print(f"  /api/vehiculesId → GET  /rest/mapview/vehiculesId")
    print("  [Ctrl+C pour arrêter]")
    print("=" * 55)

    threading.Thread(target=keepalive, daemon=True).start()
    server = HTTPServer(('0.0.0.0', PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Arrêt propre.")
        server.server_close()
