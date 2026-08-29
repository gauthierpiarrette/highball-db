#!/usr/bin/env python3
"""Render db/ + recipes/ into a single static page at site/index.html."""
import json, glob, html, os, datetime, shutil

games = [json.load(open(f)) for f in sorted(glob.glob("db/games/*.json"))]
recipes = {json.load(open(f))["id"]: json.load(open(f)) for f in glob.glob("recipes/*/*.json") if not f.endswith("LICENSE")}
reports = {}
for f in glob.glob("db/reports/*.jsonl"):
    slug = os.path.basename(f)[:-6]
    reports[slug] = [json.loads(l) for l in open(f) if l.strip()]
derived_count = 0
try:
    derived_count = len(json.load(open("db/derived/derived.json"))["games"])
except Exception:
    pass

STATUS = {
    "verified-local":    ("Verified", "good", "Tested by Highball on real Apple Silicon hardware."),
    "reported-upstream": ("Reported upstream", "info", "Named in DXMT release notes as working or fixed; not yet verified by Highball."),
    "community":         ("Community", "warn", "Community consensus (AppleGamingWiki, r/macgaming); unverified by Highball."),
    "blocked-anticheat": ("Blocked", "bad", "Kernel anti-cheat; structurally impossible under Wine. Don't waste the download."),
}
order = {"verified-local": 0, "reported-upstream": 1, "community": 2, "blocked-anticheat": 3}
games.sort(key=lambda g: (order.get(g["status"], 9), g["title"].lower()))
counts = {s: sum(1 for g in games if g["status"] == s) for s in STATUS}

def row(g):
    label, cls, _ = STATUS[g["status"]]
    r = g.get("renderer") or "—"
    appid = g.get("steam_appid")
    app = f'<a href="https://store.steampowered.com/app/{appid}/">{appid}</a>' if appid else "—"
    n = len(reports.get(g["id"], []))
    ac = g.get("anticheat")
    ac_chip = f'<span class="ac" title="{html.escape(ac.get("note") or "")}">⚠ {html.escape(", ".join(ac["names"]))}</span>' if ac and g["status"] != "blocked-anticheat" else ""
    return (f'<tr data-status="{g["status"]}"><td class="t">{html.escape(g["title"])}{ac_chip}</td>'
            f'<td><span class="pill {cls}">{label}</span></td>'
            f'<td class="mono">{r}</td><td class="mono num">{app}</td><td class="num">{n or "—"}</td>'
            f'<td class="notes">{html.escape(g.get("notes") or "")}<span class="prov">{html.escape(g.get("provenance") or "")}</span></td></tr>')

launchers = sorted((r for r in recipes.values() if r.get("kind") == "launcher"),
                   key=lambda r: (r.get("lastVerified") is None, r["title"]))
def lrow(r):
    v = r.get("lastVerified")
    state = (f'<span class="pill good">Verified</span> <span class="prov">{html.escape(v["result"])}</span>' if v
             else '<span class="pill warn">Untested</span> <span class="prov">recipe written — verification runs welcome</span>')
    return f'<tr><td class="t">{html.escape(r["title"])}</td><td class="mono">{r.get("renderer") or "—"}</td><td>{state}</td></tr>'

tiles = "".join(
    f'<button class="tile" data-f="{key}"><b>{counts[key]}</b><span>{STATUS[key][0]}</span><i class="bar {STATUS[key][1]}"></i></button>'
    for key in STATUS)

page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Highball Compatibility Database</title>
<meta property="og:title" content="Highball Compatibility Database">
<meta property="og:description" content="Windows games on Apple Silicon, as data with provenance: {counts['verified-local']} verified, {counts['reported-upstream']} reported upstream, {derived_count:,} predictions, anti-cheat blocklist.">
<meta property="og:url" content="https://gauthierpiarrette.github.io/highball-db/">
<link rel="icon" href="https://gauthierpiarrette.github.io/highball/logo-128.png">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,700;12..96,800&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
:root {{ --ground:#F8F5EF; --surface:#FFFFFF; --surface2:#F1EBDF; --line:#E2D9C6; --ink:#211D15; --ink2:#4A4436; --muted:#8A8171;
  --accent:#A5691C; --accent-ink:#FFF7EA; --good:#2E6B4E; --info:#3B5F8A; --warn:#A5691C; --bad:#A23B3B; --shadow:0 1px 2px rgba(33,29,21,.06),0 8px 24px rgba(33,29,21,.05); }}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{ --ground:#14100A; --surface:#1D1710; --surface2:#241D13; --line:#352C1C;
  --ink:#EAE4D6; --ink2:#C2BAA6; --muted:#8F8672; --accent:#D79A45; --accent-ink:#221503; --good:#74C29A; --info:#82A8D8; --warn:#D79A45; --bad:#E07A7A; --shadow:none; }} }}
:root[data-theme="dark"] {{ --ground:#14100A; --surface:#1D1710; --surface2:#241D13; --line:#352C1C; --ink:#EAE4D6; --ink2:#C2BAA6; --muted:#8F8672;
  --accent:#D79A45; --accent-ink:#221503; --good:#74C29A; --info:#82A8D8; --warn:#D79A45; --bad:#E07A7A; --shadow:none; }}
* {{ box-sizing:border-box }}
body {{ margin:0; background:var(--ground); color:var(--ink); font:15.5px/1.55 "IBM Plex Sans",-apple-system,sans-serif; }}
.page {{ max-width:1140px; margin:0 auto; padding:0 clamp(1rem,4vw,2.5rem) 4rem; }}
a {{ color:var(--accent) }}
.mono {{ font-family:"IBM Plex Mono",monospace; font-size:.8rem; }}
.num {{ font-variant-numeric:tabular-nums }}

.topbar {{ display:flex; justify-content:space-between; align-items:center; gap:1rem; padding:1.1rem 0; }}
.brand {{ display:flex; align-items:center; gap:.6rem; font-family:"Bricolage Grotesque",sans-serif; font-weight:700; font-size:1.05rem; }}
.brand img {{ width:30px; height:30px; }}
.brand span {{ color:var(--muted); font-family:"IBM Plex Mono",monospace; font-size:.68rem; letter-spacing:.1em; text-transform:uppercase; font-weight:400; }}
.get {{ background:var(--accent); color:var(--accent-ink); font-weight:600; font-size:.85rem; padding:.5rem 1rem; border-radius:7px; text-decoration:none; white-space:nowrap; }}
.get:hover {{ filter:brightness(1.07) }}

h1 {{ font-family:"Bricolage Grotesque",sans-serif; font-weight:800; font-size:clamp(1.9rem,4.5vw,2.9rem); margin:1.5rem 0 0; letter-spacing:-.02em; }}
.sub {{ color:var(--ink2); max-width:72ch; margin:.6rem 0 0; }}

.tiles {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(130px,1fr)); gap:.7rem; margin:1.75rem 0 .4rem; }}
.tile {{ position:relative; text-align:left; background:var(--surface); border:1px solid var(--line); border-radius:10px; padding:.85rem 1rem 1.05rem;
  cursor:pointer; font:inherit; color:var(--ink); box-shadow:var(--shadow); }}
.tile b {{ display:block; font-size:1.65rem; font-weight:700; font-variant-numeric:tabular-nums; line-height:1.1; }}
.tile span {{ font-size:.76rem; color:var(--muted); }}
.tile .bar {{ position:absolute; left:1rem; right:1rem; bottom:.55rem; height:3px; border-radius:2px; opacity:.85; }}
.bar.good {{ background:var(--good) }} .bar.info {{ background:var(--info) }} .bar.warn {{ background:var(--warn) }} .bar.bad {{ background:var(--bad) }}
.tile.on {{ border-color:var(--accent); outline:2px solid var(--accent); outline-offset:-1px; }}
.tile:focus-visible {{ outline:2px solid var(--accent); }}

.search {{ display:flex; align-items:center; gap:.5rem; background:var(--surface); border:1px solid var(--line); border-radius:9px;
  padding:.55rem .9rem; max-width:380px; margin:.9rem 0 1rem; box-shadow:var(--shadow); }}
.search svg {{ flex:none; opacity:.45 }}
.search input {{ border:0; outline:0; background:none; color:var(--ink); font:inherit; width:100%; }}

.tablecard {{ background:var(--surface); border:1px solid var(--line); border-radius:12px; overflow:hidden; box-shadow:var(--shadow); margin:0 0 2.5rem; }}
.scroll {{ overflow-x:auto; max-height:72vh; }}
table {{ border-collapse:collapse; width:100%; min-width:820px; font-size:.87rem; line-height:1.45; }}
th,td {{ text-align:left; vertical-align:top; padding:.6rem .85rem; border-bottom:1px solid var(--line); }}
thead th {{ position:sticky; top:0; background:var(--surface2); font-size:.7rem; letter-spacing:.07em; text-transform:uppercase; color:var(--ink2); white-space:nowrap; z-index:1; }}
tbody tr:nth-child(even) {{ background:var(--surface2); }}
tr:last-child td {{ border-bottom:0 }}
td.t {{ font-weight:600; max-width:26ch; }}
.ac {{ display:block; font-family:"IBM Plex Mono",monospace; font-size:.68rem; color:var(--warn); font-weight:400; margin-top:.15rem; }}
.pill {{ display:inline-block; font-family:"IBM Plex Mono",monospace; font-size:.64rem; letter-spacing:.05em; text-transform:uppercase; padding:.16em .55em; border:1px solid currentColor; border-radius:99px; white-space:nowrap; }}
.pill.good {{ color:var(--good) }} .pill.info {{ color:var(--info) }} .pill.warn {{ color:var(--warn) }} .pill.bad {{ color:var(--bad) }}
.notes {{ max-width:46ch }} .prov {{ display:block; color:var(--muted); font-size:.74rem; margin-top:.2rem; }}

h2 {{ font-family:"Bricolage Grotesque",sans-serif; font-weight:700; font-size:1.35rem; margin:0 0 .35rem; }}
.legend {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(230px,1fr)); gap:.7rem; margin:1rem 0 2.5rem; padding:0; list-style:none; }}
.legend li {{ background:var(--surface); border:1px solid var(--line); border-radius:10px; padding:.7rem .9rem; font-size:.82rem; color:var(--ink2); box-shadow:var(--shadow); }}
.legend .pill {{ margin-bottom:.3rem }}

footer {{ color:var(--muted); font-family:"IBM Plex Mono",monospace; font-size:.72rem; margin-top:2rem; line-height:1.8; }}
</style>
</head>
<body>
<div class="page">

<div class="topbar">
  <div class="brand"><img src="https://gauthierpiarrette.github.io/highball/logo-128.png" alt="">Highball <span>· open database · CC0</span></div>
  <a class="get" href="https://gauthierpiarrette.github.io/highball/">Get Highball ↗</a>
</div>

<h1>What runs on Apple Silicon</h1>
<p class="sub">Windows games through Wine + DXMT / D3DMetal / DXVK, as data: what was actually verified, what upstream projects report, what the community says, and what kernel anti-cheat makes impossible. Every row carries its provenance.</p>

<div class="tiles" id="filters">
<button class="tile on" data-f="all"><b>{len(games)}</b><span>All curated</span><i class="bar" style="background:var(--accent)"></i></button>
{tiles}
</div>

<div class="search"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/></svg><input type="search" id="q" placeholder="Filter curated titles…" aria-label="Filter by title"></div>

<div class="tablecard"><div class="scroll"><table id="games">
<thead><tr><th>Title</th><th>Status</th><th>Renderer</th><th>Steam</th><th>Reports</th><th>Notes · provenance</th></tr></thead>
<tbody>
{chr(10).join(row(g) for g in games)}
</tbody></table></div></div>

<ul class="legend">
{chr(10).join(f'<li><span class="pill {STATUS[k][1]}">{STATUS[k][0]}</span><br>{STATUS[k][2]}</li>' for k in STATUS)}
</ul>

<h2>Predictions for everything else</h2>
<p class="sub" style="font-size:.9rem">{derived_count:,} more Steam games carry a <b>machine-derived prediction</b> — recent <a href="https://www.protondb.com">ProtonDB</a> verdicts (ODbL) crossed with <a href="https://areweanticheatyet.com">anti-cheat</a> knowledge. Proton describes Linux; treat these as odds, not verdicts.</p>
<div class="search"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/></svg><input type="search" id="dq" placeholder="Search {derived_count:,} predictions…" aria-label="Search predictions"></div>
<div id="dresults" style="margin:.5rem 0 2.5rem"></div>

<h2>Launchers</h2>
<div class="tablecard"><div class="scroll"><table>
<thead><tr><th>Launcher</th><th>Renderer</th><th>Recipe status</th></tr></thead>
<tbody>{chr(10).join(lrow(r) for r in launchers)}</tbody>
</table></div></div>

<footer>generated {datetime.date.today().isoformat()} from db/ and recipes/ · contribute via `highball report` or a recipe PR<br>
anti-cheat data © Are We Anti-Cheat Yet? (MIT) · predictions derive from ProtonDB data exports (ODbL) · everything else CC0</footer>
</div>
<script>
const rows=[...document.querySelectorAll('#games tbody tr')];
let f='all', q='';
function apply() {{ rows.forEach(r=>{{ const okF = f==='all'||r.dataset.status===f;
  const okQ = !q || r.cells[0].textContent.toLowerCase().includes(q); r.style.display = okF&&okQ?'':'none'; }}); }}
document.getElementById('filters').addEventListener('click',e=>{{ const b=e.target.closest('.tile'); if(!b)return;
  document.querySelectorAll('.tile').forEach(c=>c.classList.remove('on')); b.classList.add('on'); f=b.dataset.f; apply(); }});
document.getElementById('q').addEventListener('input',e=>{{ q=e.target.value.toLowerCase(); apply(); }});
let derived=null;
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));
const PRED={{likely:['Likely works','good'],maybe:['Maybe','warn'],unlikely:['Unlikely','bad']}};
document.getElementById('dq').addEventListener('input',async e=>{{
  const term=e.target.value.toLowerCase(); const box=document.getElementById('dresults');
  if(term.length<2){{box.innerHTML='';return;}}
  if(!derived){{box.textContent='Loading predictions…'; derived=(await (await fetch('derived.json')).json()).games;}}
  const hits=Object.entries(derived).filter(([id,g])=>g.title.toLowerCase().includes(term)).slice(0,30);
  box.innerHTML=hits.length? '<div class="tablecard"><div class="scroll"><table><thead><tr><th>Title</th><th>Prediction</th><th>Proton (recent)</th><th>Anti-cheat</th></tr></thead><tbody>'+hits.map(([id,g])=>{{
    const [label,cls]=PRED[g.macPrediction]||['?',''];
    const appid=String(id).replace(/[^0-9]/g,'');
    return `<tr><td class="t"><a href="https://store.steampowered.com/app/${{appid}}/">${{esc(g.title)}}</a></td><td><span class="pill ${{cls}}">${{label}}</span></td><td class="mono">${{esc(g.protonTier)}} · ${{Number(g.recentReports)||0}} reports</td><td class="mono">${{g.anticheat?esc(g.anticheat.join(', ')):'—'}}</td></tr>`;
  }}).join('')+'</tbody></table></div></div>' : 'No match.';
}});
</script>
</html>"""
os.makedirs("site", exist_ok=True)
open("site/index.html", "w").write(page)
# The public database moved to gethighball.com/database/ (built by the highball-website repo).
# This site now redirects so the old URL keeps working and search consolidates on one host.
REDIRECT = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>The Highball database has moved</title>
<link rel="canonical" href="https://gethighball.com/database/">
<meta http-equiv="refresh" content="0; url=https://gethighball.com/database/">
<meta name="robots" content="noindex, follow">
<style>body{margin:0;min-height:100vh;display:grid;place-items:center;text-align:center;background:#16110A;
color:#EFE7D6;font:17px/1.6 -apple-system,BlinkMacSystemFont,sans-serif;padding:2rem}a{color:#D79A45}</style>
</head><body><div>
<h1>The compatibility database has moved</h1>
<p>It now lives at <a href="https://gethighball.com/database/">gethighball.com/database</a>,
with a page for every game.</p>
<p>The data itself is still here:
<a href="https://github.com/gauthierpiarrette/highball-db">github.com/gauthierpiarrette/highball-db</a>.</p>
</div><script>location.replace("https://gethighball.com/database/");</script></body></html>
"""
open("site/index.html", "w").write(REDIRECT)

try:
    shutil.copy("db/derived/derived.json", "site/derived.json")
except Exception:
    pass
print(f"site/index.html: {len(page)//1024} KB, {len(games)} games, {len(launchers)} launchers, {derived_count} predictions")
