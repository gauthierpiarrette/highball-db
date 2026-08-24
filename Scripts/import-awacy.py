#!/usr/bin/env python3
"""Import Are We Anti-Cheat Yet? (MIT, github.com/AreWeAntiCheatYet) into the database.

Mac-aware mapping — AWACY statuses describe Linux/Proton, which does NOT transfer:
- HARD kernel vendors that cannot run under Wine on macOS at all -> new/updated
  entries with status blocked-anticheat.
- EAC / BattlEye / others -> `anticheat` warning metadata only (some titles run the
  userspace path under Wine on macOS; the Linux opt-in does not extend to macOS).
Writes db/anticheat.json (full mapping) and annotates/creates db/games entries.
"""
import json, re, sys, urllib.request, os

HARD = {"Riot Vanguard", "Vanguard", "Ricochet", "EA anticheat", "Denuvo Anticheat", "Denuvo Anti-Cheat"}
def slugify(n): return re.sub(r"[^a-z0-9]+", "-", n.lower()).strip("-")

src = sys.argv[1] if len(sys.argv) > 1 else "https://raw.githubusercontent.com/AreWeAntiCheatYet/AreWeAntiCheatYet/master/games.json"
data = json.load(open(src)) if os.path.exists(src) else json.load(urllib.request.urlopen(src))

mapping, created, annotated = {}, 0, 0
existing = {}
for f in os.listdir("db/games"):
    e = json.load(open(f"db/games/{f}"))
    existing[e["id"]] = f
    if e.get("steam_appid"): existing[f'appid:{e["steam_appid"]}'] = f

for g in data:
    slug = g.get("slug") or slugify(g["name"])
    acs = g.get("anticheats") or []
    if not acs: continue
    hard = [a for a in acs if a in HARD]
    steam_appid = None
    for sid in (g.get("storeIds") or {}).values() if isinstance(g.get("storeIds"), dict) else []:
        pass
    sid = g.get("storeIds") or {}
    if isinstance(sid, dict) and sid.get("steam"): 
        try: steam_appid = int(sid["steam"])
        except (ValueError, TypeError): pass
    verdict = "blocked" if hard else "warning"
    mapping[slug] = {"title": g["name"], "anticheats": acs, "linuxStatus": g.get("status"),
                     "steam_appid": steam_appid, "macVerdict": verdict}
    key = existing.get(f"appid:{steam_appid}") or existing.get(slug)
    ac_field = {"names": acs, "macVerdict": verdict,
                "note": "kernel anti-cheat; cannot work under Wine on macOS" if hard else
                        "anti-cheat present; Linux/Proton support does not extend to macOS — userspace path works for some titles"}
    if key:
        path = f"db/games/{key}"; e = json.load(open(path))
        if e.get("anticheat") != ac_field:
            e["anticheat"] = ac_field
            json.dump(e, open(path, "w"), indent=2, ensure_ascii=False); annotated += 1
    elif hard:
        e = {"id": slug, "title": g["name"], "steam_appid": steam_appid, "status": "blocked-anticheat",
             "renderer": None, "provenance": "Are We Anti-Cheat Yet? (MIT) — kernel anti-cheat vendor; structurally impossible under Wine on macOS",
             "notes": f"Anti-cheat: {', '.join(acs)}. Linux/Proton status '{g.get('status')}' does not apply to macOS.",
             "anticheat": ac_field, "lastVerified": None}
        json.dump(e, open(f"db/games/{slug}.json", "w"), indent=2, ensure_ascii=False); created += 1

json.dump({"source": "https://github.com/AreWeAntiCheatYet/AreWeAntiCheatYet", "license": "MIT",
           "macNote": "verdicts are Highball's macOS interpretation, not AWACY's Linux statuses",
           "games": mapping}, open("db/anticheat.json", "w"), indent=2, ensure_ascii=False)
print(f"anticheat.json: {len(mapping)} titles · new blocked entries: {created} · annotated existing: {annotated}")
