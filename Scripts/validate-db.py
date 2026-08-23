#!/usr/bin/env python3
"""Validate every db/games entry and recipes/*.json against the schema rules CI enforces."""
import json, sys, glob

STATUSES = {"verified-local", "reported-upstream", "community", "blocked-anticheat"}
RENDERERS = {"wined3d", "dxmt", "d3dmetal", "dxvk", None}
errors = []

for f in glob.glob("db/games/*.json"):
    d = json.load(open(f))
    for key in ("id", "title", "status", "provenance", "notes"):
        if key not in d: errors.append(f"{f}: missing {key}")
    if d.get("status") not in STATUSES: errors.append(f"{f}: bad status {d.get('status')}")
    if d.get("renderer") not in RENDERERS: errors.append(f"{f}: bad renderer {d.get('renderer')}")
    if d.get("status") == "verified-local" and not d.get("lastVerified"):
        errors.append(f"{f}: verified-local requires lastVerified")
    if d.get("status") == "blocked-anticheat" and d.get("renderer") is not None:
        errors.append(f"{f}: blocked entries must not recommend a renderer")

for f in glob.glob("recipes/*/*.json"):
    if f.endswith("LICENSE"): continue
    d = json.load(open(f))
    if d.get("kind") not in ("launcher", "game", "tweak"): errors.append(f"{f}: bad kind")
    if not isinstance(d.get("steps"), list) or not d["steps"]: errors.append(f"{f}: steps missing")

if errors:
    print("\n".join(errors)); sys.exit(1)
print(f"ok: {len(glob.glob('db/games/*.json'))} games, {len(glob.glob('recipes/*/*.json'))} recipes")
