#!/usr/bin/env python3
"""DepZero local web dashboard. Standard library only."""
from __future__ import annotations

import argparse
import json
import os
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import depzero

HOST = "127.0.0.1"
PORT = 8765

HTML = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>DepZero — Dependency Intelligence</title>
<style>
:root{--bg:#07110f;--panel:rgba(13,30,26,.72);--panel2:#0d1c19;--line:rgba(140,255,198,.14);--text:#ecfff7;--muted:#89a89c;--green:#76f7b7;--green2:#34d399;--red:#fb7185;--amber:#fbbf24;--blue:#60a5fa;--shadow:0 24px 80px rgba(0,0,0,.35)}
*{box-sizing:border-box}body{margin:0;font:14px/1.5 Inter,ui-sans-serif,system-ui,-apple-system,Segoe UI,sans-serif;background:radial-gradient(circle at 15% 0%,#123128 0,transparent 32%),radial-gradient(circle at 100% 30%,#10253a 0,transparent 32%),var(--bg);color:var(--text);min-height:100vh}.app{display:grid;grid-template-columns:250px 1fr;min-height:100vh}.sidebar{border-right:1px solid var(--line);padding:26px 18px;background:rgba(4,13,11,.72);backdrop-filter:blur(16px);position:sticky;top:0;height:100vh}.brand{display:flex;gap:12px;align-items:center;margin-bottom:34px}.logo{width:40px;height:40px;border-radius:12px;background:linear-gradient(145deg,#8affc6,#22c55e);display:grid;place-items:center;color:#062217;font-weight:900;box-shadow:0 0 35px rgba(52,211,153,.25)}.brand b{font-size:20px;letter-spacing:-.6px}.brand small{display:block;color:var(--muted);font-size:11px}.nav{display:grid;gap:7px}.nav button{appearance:none;border:0;background:transparent;color:var(--muted);padding:11px 12px;border-radius:10px;text-align:left;cursor:pointer;font-weight:650}.nav button:hover,.nav button.active{background:rgba(118,247,183,.09);color:var(--green)}.sidefoot{position:absolute;bottom:22px;left:18px;right:18px;border-top:1px solid var(--line);padding-top:16px;color:var(--muted);font-size:12px}.main{padding:28px clamp(20px,4vw,58px) 60px;max-width:1550px;width:100%}.top{display:flex;justify-content:space-between;align-items:flex-start;gap:20px;margin-bottom:28px}.kicker{color:var(--green);font-size:12px;letter-spacing:.16em;text-transform:uppercase;font-weight:800}.top h1{font-size:clamp(28px,3vw,42px);margin:4px 0 4px;letter-spacing:-1.5px}.top p{margin:0;color:var(--muted)}.badge{border:1px solid var(--line);border-radius:999px;padding:8px 12px;color:var(--green);background:rgba(118,247,183,.06);white-space:nowrap}.scanbar{display:flex;gap:10px;padding:10px;border:1px solid var(--line);background:var(--panel);border-radius:16px;box-shadow:var(--shadow);margin-bottom:20px}.scanbar input{flex:1;background:transparent;border:0;outline:0;color:var(--text);font-size:14px;padding:8px 10px}.scanbar input::placeholder{color:#60786f}.btn{border:0;border-radius:10px;padding:11px 16px;font-weight:800;cursor:pointer}.btn.primary{background:linear-gradient(135deg,var(--green),var(--green2));color:#062217}.btn.secondary{background:#163028;color:#c9fbe1;border:1px solid var(--line)}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:20px 0}.card{border:1px solid var(--line);background:var(--panel);backdrop-filter:blur(14px);border-radius:16px;padding:18px;box-shadow:0 10px 40px rgba(0,0,0,.16)}.metric span{display:block;color:var(--muted);font-size:12px;margin-bottom:8px}.metric strong{font-size:28px;letter-spacing:-1px}.metric i{font-style:normal;font-size:11px;margin-left:6px}.green{color:var(--green)}.red{color:var(--red)}.amber{color:var(--amber)}.blue{color:var(--blue)}.section{margin-top:16px}.section h2{font-size:15px;margin:0 0 14px}.split{display:grid;grid-template-columns:1.15fr .85fr;gap:14px}.table{width:100%;border-collapse:collapse}.table th{text-align:left;color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.08em;border-bottom:1px solid var(--line);padding:10px 8px}.table td{padding:12px 8px;border-bottom:1px solid rgba(140,255,198,.07);vertical-align:top}.pill{display:inline-flex;padding:3px 8px;border-radius:999px;font-size:10px;font-weight:900;text-transform:uppercase;letter-spacing:.05em}.pill.std{background:rgba(96,165,250,.12);color:#93c5fd}.pill.local{background:rgba(118,247,183,.12);color:var(--green)}.pill.ext{background:rgba(251,113,133,.12);color:#fda4af}.pill.unknown{background:rgba(251,191,36,.12);color:#fde68a}.resultbox{min-height:160px;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center}.ring{width:76px;height:76px;border-radius:50%;display:grid;place-items:center;margin-bottom:12px;background:rgba(118,247,183,.08);border:1px solid rgba(118,247,183,.32);font-size:30px}.ring.fail{background:rgba(251,113,133,.08);border-color:rgba(251,113,133,.35)}.resultbox h3{margin:0;font-size:20px}.resultbox p{color:var(--muted);margin:6px 0 0}.empty{color:var(--muted);padding:26px 8px;text-align:center}.mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}.error{display:none;margin-bottom:16px;border:1px solid rgba(251,113,133,.3);background:rgba(251,113,133,.08);color:#fecdd3;padding:12px 14px;border-radius:12px}.loading{opacity:.55;pointer-events:none}.toolbar{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 12px}.terminal{background:#050b0a;border:1px solid var(--line);border-radius:12px;padding:14px;white-space:pre-wrap;min-height:180px;color:#b7d8ca;overflow:auto;max-height:430px}.hidden{display:none}.depname{font-weight:800}.trade{color:var(--muted);font-size:12px;margin-top:3px}@media(max-width:1000px){.app{grid-template-columns:1fr}.sidebar{display:none}.grid{grid-template-columns:repeat(2,1fr)}.split{grid-template-columns:1fr}}@media(max-width:620px){.main{padding:20px 14px 40px}.grid{grid-template-columns:1fr 1fr}.scanbar{flex-wrap:wrap}.scanbar input{width:100%;flex-basis:100%}.top{display:block}.badge{display:inline-block;margin-top:12px}}
</style>
</head>
<body>
<div class="app">
<aside class="sidebar">
  <div class="brand"><div class="logo">D0</div><div><b>DepZero</b><small>Dependency Intelligence</small></div></div>
  <div class="nav">
    <button class="active" data-tab="dashboard">◫ &nbsp;Dashboard</button>
    <button data-tab="dependencies">⌘ &nbsp;Dependencies</button>
    <button data-tab="escape">↗ &nbsp;Escape Plan</button>
    <button data-tab="graph">⑂ &nbsp;Graph</button>
    <button data-tab="proof">✓ &nbsp;Proof</button>
  </div>
  <div class="sidefoot">Zero third-party runtime packages<br><span class="green">DepZero v1.0.0</span></div>
</aside>
<main class="main">
  <div class="top"><div><div class="kicker">Zero Dependency Audit</div><h1>Know what's inside your project.</h1><p>Scan source, classify imports, inspect manifests and plan your path to zero dependencies.</p></div><div class="badge">● Local · Private · Static</div></div>
  <div class="scanbar"><input id="path" value="." placeholder="Enter a local project path, e.g. C:\\projects\\my-app"/><button id="selfBtn" class="btn secondary">Use DepZero</button><button id="scanBtn" class="btn primary">Scan Project →</button></div>
  <div id="error" class="error"></div>

  <section id="dashboard" class="tab">
    <div class="grid">
      <div class="card metric"><span>FILES SCANNED</span><strong id="mFiles">—</strong></div>
      <div class="card metric"><span>STDLIB IMPORTS</span><strong class="blue" id="mStd">—</strong></div>
      <div class="card metric"><span>LOCAL IMPORTS</span><strong class="green" id="mLocal">—</strong></div>
      <div class="card metric"><span>EXTERNAL IMPORTS</span><strong class="red" id="mExt">—</strong></div>
    </div>
    <div class="split">
      <div class="card section"><h2>Detected dependencies</h2><div id="depPreview" class="empty">Run a scan to populate dependency intelligence.</div></div>
      <div class="card resultbox"><div id="resultRing" class="ring">?</div><h3 id="resultTitle">Awaiting scan</h3><p id="resultText">Choose a project path and start the audit.</p></div>
    </div>
    <div class="card section"><h2>Manifest findings</h2><div id="findings" class="empty">No scan data yet.</div></div>
  </section>

  <section id="dependencies" class="tab hidden"><div class="card"><h2>All observed imports</h2><div id="allDeps" class="empty">Run a scan first.</div></div></section>
  <section id="escape" class="tab hidden"><div class="card"><h2>Dependency Escape Plan</h2><div id="escapeContent" class="empty">Run a scan first.</div></div></section>
  <section id="graph" class="tab hidden"><div class="card"><h2>Dependency Graph</h2><div class="toolbar"><button id="asciiBtn" class="btn secondary">ASCII</button><button id="dotBtn" class="btn secondary">DOT</button></div><pre id="graphContent" class="terminal">Run a scan first.</pre></div></section>
  <section id="proof" class="tab hidden"><div class="card"><h2>Deterministic Dependency Proof</h2><div class="toolbar"><button id="copyProof" class="btn secondary">Copy proof</button></div><pre id="proofContent" class="terminal">Run a scan first.</pre></div></section>
</main>
</div>
<script>
let current=null;
const $=id=>document.getElementById(id);
function esc(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));}
function pill(cat){const m={standard_library:['std','STDLIB'],local:['local','LOCAL'],third_party:['ext','EXTERNAL'],unknown:['unknown','UNKNOWN']};const x=m[cat]||m.unknown;return `<span class="pill ${x[0]}">${x[1]}</span>`}
function setTab(id){document.querySelectorAll('.tab').forEach(x=>x.classList.add('hidden'));$(id).classList.remove('hidden');document.querySelectorAll('.nav button').forEach(b=>b.classList.toggle('active',b.dataset.tab===id));}
document.querySelectorAll('.nav button').forEach(b=>b.onclick=()=>setTab(b.dataset.tab));
async function api(path,body){const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const data=await r.json();if(!r.ok)throw new Error(data.error||'Request failed');return data;}
async function scan(){const btn=$('scanBtn'),err=$('error');err.style.display='none';document.body.classList.add('loading');btn.textContent='Scanning…';try{current=await api('/api/scan',{path:$('path').value.trim()||'.'});render(current);await loadExtras();}catch(e){err.textContent=e.message;err.style.display='block';}finally{document.body.classList.remove('loading');btn.textContent='Scan Project →';}}
function render(d){const s=d.summary;$('mFiles').textContent=s.files_scanned;$('mStd').textContent=s.stdlib;$('mLocal').textContent=s.local;$('mExt').textContent=s.external;const fail=s.external>0;$('resultRing').className='ring'+(fail?' fail':'');$('resultRing').textContent=fail?'!':'✓';$('resultTitle').textContent=fail?`${s.external} external import${s.external===1?'':'s'} detected`:'Zero external dependencies detected';$('resultTitle').className=fail?'red':'green';$('resultText').textContent=fail?'Review detected packages and generate an escape plan.':'Static audit passed for the scanned source.';
 const ext=d.dependencies.filter(x=>x.category==='third_party'); const unique=[...new Set(ext.map(x=>x.module))]; $('depPreview').innerHTML=unique.length?`<table class="table"><thead><tr><th>Dependency</th><th>References</th><th>Status</th></tr></thead><tbody>${unique.slice(0,8).map(name=>{const refs=ext.filter(x=>x.module===name);return `<tr><td class="depname">${esc(name)}</td><td class="mono">${esc(refs[0].file)}:${refs[0].line}${refs.length>1?` +${refs.length-1}`:''}</td><td>${pill('third_party')}</td></tr>`}).join('')}</tbody></table>`:'<div class="empty green">No third-party imports detected.</div>';
 $('findings').innerHTML=d.findings.length?`<table class="table"><thead><tr><th>Package</th><th>Finding</th></tr></thead><tbody>${d.findings.map(f=>`<tr><td class="depname">${esc(f.dependency)}</td><td>${esc(f.detail)}</td></tr>`).join('')}</tbody></table>`:'<div class="empty">No runtime manifest findings.</div>';
 $('allDeps').innerHTML=d.dependencies.length?`<table class="table"><thead><tr><th>Module</th><th>Category</th><th>Source</th><th>Type</th></tr></thead><tbody>${d.dependencies.map(x=>`<tr><td class="depname">${esc(x.module)}</td><td>${pill(x.category)}</td><td class="mono">${esc(x.file)}:${x.line}</td><td>${esc(x.import_type)}</td></tr>`).join('')}</tbody></table>`:'<div class="empty">No imports detected.</div>';
}
async function loadExtras(){const body={path:$('path').value.trim()||'.'};const [e,g,p]=await Promise.all([api('/api/escape',body),api('/api/graph',{...body,format:'ascii'}),api('/api/proof',body)]);$('escapeContent').innerHTML=e.items.length?e.items.map((x,i)=>`<div style="padding:14px 0;border-bottom:1px solid var(--line)"><div><b>${i+1}. ${esc(x.dependency)}</b> <span class="pill ${x.difficulty==='EASY'?'local':x.difficulty==='MEDIUM'?'unknown':'ext'}">${esc(x.difficulty)}</span></div><div style="margin-top:7px">Replacement: <span class="green">${esc(x.alternatives.join(', ')||'No general stdlib equivalent')}</span></div><div class="trade">${esc(x.tradeoffs)}</div></div>`).join(''):'<div class="empty green">No migration required.</div>';$('graphContent').textContent=g.text;$('proofContent').textContent=p.text;}
$('scanBtn').onclick=scan;$('selfBtn').onclick=()=>{$('path').value='.';scan();};$('path').addEventListener('keydown',e=>{if(e.key==='Enter')scan()});$('asciiBtn').onclick=async()=>{$('graphContent').textContent=(await api('/api/graph',{path:$('path').value||'.',format:'ascii'})).text};$('dotBtn').onclick=async()=>{$('graphContent').textContent=(await api('/api/graph',{path:$('path').value||'.',format:'dot'})).text};$('copyProof').onclick=()=>navigator.clipboard.writeText($('proofContent').textContent);
</script>
</body>
</html>'''


def json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(body)


def resolve_user_path(raw: str) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("Enter a project path to scan.")
    return str(Path(raw).expanduser().resolve())


def escape_payload(result: depzero.ScanResult) -> dict:
    rank = {"EASY": 0, "MEDIUM": 1, "HARD": 2}
    items = []
    for name in result.external_modules():
        suggestion = depzero.suggestion_for(name)
        if suggestion:
            purpose, alternatives, difficulty, tradeoffs = suggestion
        else:
            purpose, alternatives, difficulty, tradeoffs = "Unknown", [], "UNKNOWN", "No curated replacement entry. Review manually."
        items.append({"dependency": name, "purpose": purpose, "alternatives": alternatives, "difficulty": difficulty, "tradeoffs": tradeoffs})
    items.sort(key=lambda x: (rank.get(x["difficulty"], 99), x["dependency"]))
    return {"items": items}


class Handler(BaseHTTPRequestHandler):
    server_version = "DepZeroWeb/1.0"

    def log_message(self, fmt: str, *args) -> None:
        print(f"[web] {self.address_string()} - {fmt % args}")

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            body = HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/api/health":
            json_response(self, 200, {"status": "ok", "tool": "depzero", "version": depzero.VERSION})
            return
        self.send_error(404)

    def do_POST(self) -> None:
        route = urlparse(self.path).path
        if route not in {"/api/scan", "/api/graph", "/api/proof", "/api/escape"}:
            json_response(self, 404, {"error": "Unknown endpoint."})
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size > 64 * 1024:
                raise ValueError("Request too large.")
            payload = json.loads(self.rfile.read(size).decode("utf-8") or "{}")
            target = resolve_user_path(payload.get("path", "."))
            result = depzero.scan_project(target)
            if route == "/api/scan":
                json_response(self, 200, depzero.result_json(result))
            elif route == "/api/graph":
                fmt = payload.get("format", "ascii")
                if fmt not in {"ascii", "dot"}:
                    raise ValueError("Graph format must be ascii or dot.")
                json_response(self, 200, {"text": depzero.graph_text(result, fmt)})
            elif route == "/api/proof":
                json_response(self, 200, {"text": depzero.proof_text(result)})
            else:
                json_response(self, 200, escape_payload(result))
        except FileNotFoundError:
            json_response(self, 404, {"error": "Project path not found on this computer."})
        except (ValueError, json.JSONDecodeError) as exc:
            json_response(self, 400, {"error": str(exc)})
        except Exception as exc:
            json_response(self, 500, {"error": f"Analysis failed: {exc}"})


def main() -> int:
    p = argparse.ArgumentParser(description="Run DepZero's local zero-dependency web dashboard.")
    p.add_argument("--host", default=HOST)
    p.add_argument("--port", type=int, default=PORT)
    p.add_argument("--no-browser", action="store_true")
    args = p.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    url = f"http://{args.host}:{args.port}"
    print(f"DepZero Web Dashboard: {url}")
    print("Press Ctrl+C to stop.")
    if not args.no_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping DepZero Web Dashboard.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
