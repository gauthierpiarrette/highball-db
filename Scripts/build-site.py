#!/usr/bin/env python3
"""Render db/ + recipes/ into a single static page at site/index.html."""
import json, glob, html, os, datetime

games = [json.load(open(f)) for f in sorted(glob.glob("db/games/*.json"))]
recipes = {json.load(open(f))["id"]: json.load(open(f)) for f in glob.glob("recipes/*/*.json") if not f.endswith("LICENSE")}
reports = {}
for f in glob.glob("db/reports/*.jsonl"):
    slug = os.path.basename(f)[:-6]
    reports[slug] = [json.loads(l) for l in open(f) if l.strip()]

STATUS = {
    "verified-local":    ("Verified", "good", "Tested by Highball on real hardware; details in the entry."),
    "reported-upstream": ("Reported upstream", "info", "Named in DXMT release notes as working/fixed; not yet verified by Highball."),
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
    rep = f'{n}' if n else "—"
    return (f'<tr data-status="{g["status"]}"><td>{html.escape(g["title"])}</td>'
            f'<td><span class="pill {cls}">{label}</span></td>'
            f'<td class="mono">{r}</td><td class="mono num">{app}</td><td class="num">{rep}</td>'
            f'<td class="notes">{html.escape(g.get("notes") or "")}<span class="prov">{html.escape(g.get("provenance") or "")}</span></td></tr>')

launchers = [r for r in recipes.values() if r.get("kind") == "launcher"]
launchers.sort(key=lambda r: (r.get("lastVerified") is None, r["title"]))
def lrow(r):
    v = r.get("lastVerified")
    state = f'<span class="pill good">Verified</span> <span class="prov">{html.escape(v["result"])}</span>' if v else '<span class="pill warn">Untested</span> <span class="prov">recipe written, needs a verification run</span>'
    return f'<tr><td>{html.escape(r["title"])}</td><td class="mono">{r.get("renderer") or "—"}</td><td>{state}</td></tr>'

page = f"""<title>Highball Compatibility Database</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,700;12..96,800&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
:root {{ --ground:#F8F5EF; --surface:#EFEAE0; --line:#D8D0C0; --ink:#211D15; --ink2:#4A4436; --muted:#8A8171;
  --accent:#A5691C; --good:#2E6B4E; --info:#3B5F8A; --warn:#A5691C; --bad:#A23B3B; --code:#EFEBE2; }}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{ --ground:#16130E; --surface:#201B13; --line:#37301F;
  --ink:#EAE4D6; --ink2:#C2BAA6; --muted:#8F8672; --accent:#D79A45; --good:#74C29A; --info:#82A8D8; --warn:#D79A45; --bad:#E07A7A; --code:#1C1812; }} }}
:root[data-theme="dark"] {{ --ground:#16130E; --surface:#201B13; --line:#37301F; --ink:#EAE4D6; --ink2:#C2BAA6; --muted:#8F8672;
  --accent:#D79A45; --good:#74C29A; --info:#82A8D8; --warn:#D79A45; --bad:#E07A7A; --code:#1C1812; }}
* {{ box-sizing:border-box }}
body {{ margin:0; background:var(--ground); color:var(--ink); font:16px/1.55 "IBM Plex Sans",-apple-system,sans-serif; }}
.page {{ max-width:1100px; margin:0 auto; padding:2.5rem clamp(1rem,4vw,2.5rem) 4rem; }}
h1 {{ font-family:"Bricolage Grotesque",sans-serif; font-weight:800; font-size:clamp(2rem,5vw,3rem); margin:0; letter-spacing:-.02em; }}
.sub {{ color:var(--ink2); max-width:70ch; margin:.75rem 0 0; }}
.eyebrow {{ font-family:"IBM Plex Mono",monospace; font-size:.7rem; letter-spacing:.12em; text-transform:uppercase; color:var(--muted); }}
.counts {{ display:flex; flex-wrap:wrap; gap:.6rem; margin:1.5rem 0; }}
.chip {{ border:1px solid var(--line); background:var(--surface); padding:.35rem .8rem; font-size:.85rem; cursor:pointer; }}
.chip b {{ font-variant-numeric:tabular-nums; }}
.chip.on {{ border-color:var(--accent); color:var(--accent); }}
.scroll {{ overflow-x:auto; border:1px solid var(--line); margin:1rem 0 2rem; }}
table {{ border-collapse:collapse; width:100%; min-width:760px; font-size:.88rem; }}
th,td {{ text-align:left; vertical-align:top; padding:.55rem .7rem; border-bottom:1px solid var(--line); }}
th {{ background:var(--surface); font-size:.72rem; letter-spacing:.06em; text-transform:uppercase; color:var(--ink2); white-space:nowrap; }}
tr:last-child td {{ border-bottom:0 }}
.mono {{ font-family:"IBM Plex Mono",monospace; font-size:.8rem; }}
.num {{ font-variant-numeric:tabular-nums }}
.pill {{ display:inline-block; font-family:"IBM Plex Mono",monospace; font-size:.66rem; letter-spacing:.05em; text-transform:uppercase; padding:.14em .5em; border:1px solid currentColor; border-radius:2px; white-space:nowrap; }}
.pill.good {{ color:var(--good) }} .pill.info {{ color:var(--info) }} .pill.warn {{ color:var(--warn) }} .pill.bad {{ color:var(--bad) }}
.notes {{ max-width:44ch }} .prov {{ display:block; color:var(--muted); font-size:.76rem; margin-top:.15rem; }}
a {{ color:var(--accent) }}
h2 {{ font-family:"Bricolage Grotesque",sans-serif; font-weight:700; font-size:1.4rem; margin:2.5rem 0 .25rem; }}
.legend {{ font-size:.84rem; color:var(--ink2); margin:.5rem 0 0; }} .legend li {{ margin-bottom:.2rem }}
footer {{ color:var(--muted); font-family:"IBM Plex Mono",monospace; font-size:.75rem; margin-top:3rem; }}
input[type=search] {{ background:var(--surface); border:1px solid var(--line); color:var(--ink); padding:.5rem .8rem; font:inherit; width:min(340px,100%); margin:.25rem 0 0; }}
input[type=search]:focus {{ outline:2px solid var(--accent); }}
</style>
<div class="page">
<div class="eyebrow">Highball · open compatibility database · CC0</div>
<h1>What runs on Apple Silicon</h1>
<p class="sub">Windows games through Wine + DXMT / D3DMetal / DXVK, as data: what was actually verified, what upstream projects report, what the community says, and what kernel anti-cheat makes impossible. Every row carries its provenance.</p>

<div class="counts" id="filters">
<button class="chip on" data-f="all">All <b>{len(games)}</b></button>
<button class="chip" data-f="verified-local">Verified <b>{counts['verified-local']}</b></button>
<button class="chip" data-f="reported-upstream">Reported upstream <b>{counts['reported-upstream']}</b></button>
<button class="chip" data-f="community">Community <b>{counts['community']}</b></button>
<button class="chip" data-f="blocked-anticheat">Blocked <b>{counts['blocked-anticheat']}</b></button>
</div>
<input type="search" id="q" placeholder="Filter by title…" aria-label="Filter by title">

<div class="scroll"><table id="games">
<thead><tr><th>Title</th><th>Status</th><th>Renderer</th><th>Steam</th><th>Reports</th><th>Notes · provenance</th></tr></thead>
<tbody>
{chr(10).join(row(g) for g in games)}
</tbody></table></div>

<ul class="legend">
<li><span class="pill good">Verified</span> — {STATUS['verified-local'][2]}</li>
<li><span class="pill info">Reported upstream</span> — {STATUS['reported-upstream'][2]}</li>
<li><span class="pill warn">Community</span> — {STATUS['community'][2]}</li>
<li><span class="pill bad">Blocked</span> — {STATUS['blocked-anticheat'][2]}</li>
</ul>

<h2>Launchers</h2>
<div class="scroll"><table>
<thead><tr><th>Launcher</th><th>Renderer</th><th>Recipe status</th></tr></thead>
<tbody>{chr(10).join(lrow(r) for r in launchers)}</tbody>
</table></div>

<footer>generated {datetime.date.today().isoformat()} from db/ and recipes/ · contribute via `highball report` or a recipe PR</footer>
</div>
<script>
const rows=[...document.querySelectorAll('#games tbody tr')];
let f='all', q='';
function apply() {{ rows.forEach(r=>{{ const okF = f==='all'||r.dataset.status===f;
  const okQ = !q || r.cells[0].textContent.toLowerCase().includes(q); r.style.display = okF&&okQ?'':'none'; }}); }}
document.getElementById('filters').addEventListener('click',e=>{{ const b=e.target.closest('.chip'); if(!b)return;
  document.querySelectorAll('.chip').forEach(c=>c.classList.remove('on')); b.classList.add('on'); f=b.dataset.f; apply(); }});
document.getElementById('q').addEventListener('input',e=>{{ q=e.target.value.toLowerCase(); apply(); }});
</script>
"""
os.makedirs("site", exist_ok=True)
open("site/index.html", "w").write(page)
print(f"site/index.html: {len(page)//1024} KB, {len(games)} games, {len(launchers)} launchers")
