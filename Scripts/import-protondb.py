#!/usr/bin/env python3
"""Aggregate a ProtonDB data dump (bdefore/protondb-data, ODbL) into db/derived/derived.json.

The output is a *prediction* layer for macOS: Proton results describe Linux, so each row
carries a macPrediction derived from (recent Proton verdicts x anti-cheat knowledge), never
a claim of Mac verification. Licensed ODbL (share-alike) separately from the CC0 core DB.

Usage: import-protondb.py /path/to/reports_piiremoved.json
"""
import json, sys, time, os

POS = {"yes", "platinum", "gold"}
MID = {"silver"}
NEG = {"no", "bronze", "borked"}
CUTOFF = time.time() - 3 * 365 * 86400

src = sys.argv[1]
print("loading dump (this takes a minute)…", flush=True)
reports = json.load(open(src))
print(f"{len(reports)} reports", flush=True)

agg = {}
for r in reports:
    try:
        app = r["app"]; appid = int(app["steam"]["appId"]); title = app.get("title") or ""
        verdict = (r.get("responses") or {}).get("verdict") or ""
        ts = r.get("timestamp") or 0
    except (KeyError, TypeError, ValueError):
        continue
    a = agg.setdefault(appid, {"title": title, "pos": 0, "mid": 0, "neg": 0, "recent": 0, "total": 0})
    if title and not a["title"]: a["title"] = title
    a["total"] += 1
    if ts < CUTOFF: continue
    a["recent"] += 1
    v = verdict.lower()
    if v in POS: a["pos"] += 1
    elif v in MID: a["mid"] += 1
    elif v in NEG: a["neg"] += 1

anticheat = json.load(open("db/anticheat.json"))["games"]
ac_by_appid = {v["steam_appid"]: v for v in anticheat.values() if v.get("steam_appid")}

out = {}
for appid, a in agg.items():
    rated = a["pos"] + a["mid"] + a["neg"]
    if rated < 2: continue                       # too little recent signal
    ratio = a["pos"] / rated
    tier = "gold" if ratio >= 0.75 else ("silver" if ratio >= 0.45 else "poor")
    ac = ac_by_appid.get(appid)
    if ac and ac["macVerdict"] == "blocked": continue   # already a real blocked row
    if tier == "gold": pred = "likely"
    elif tier == "silver": pred = "maybe"
    else: pred = "unlikely"
    row = {"title": a["title"], "protonTier": tier, "recentReports": rated, "macPrediction": pred}
    if ac: row["anticheat"] = ac["anticheats"]; row["macPrediction"] = "maybe" if pred == "likely" else pred
    out[appid] = row

os.makedirs("db/derived", exist_ok=True)
json.dump({"source": "bdefore/protondb-data (ODbL); predictions computed by Highball",
           "license": "ODbL-1.0", "generated": time.strftime("%Y-%m-%d"),
           "note": "Proton describes Linux. macPrediction = recent Proton verdicts x anti-cheat knowledge; NOT a macOS verification.",
           "games": out}, open("db/derived/derived.json", "w"), ensure_ascii=False)
counts = {}
for r in out.values(): counts[r["macPrediction"]] = counts.get(r["macPrediction"], 0) + 1
print(f"derived: {len(out)} games -> {counts}")
