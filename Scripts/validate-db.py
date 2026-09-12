#!/usr/bin/env python3
"""Validate every db/games entry and recipes/*.json against the schema rules CI enforces."""
import re, json, sys, glob

STATUSES = {"verified-local", "reported-upstream", "community", "blocked-anticheat"}
RENDERERS = {"wined3d", "dxmt", "d3dmetal", "dxvk", "vkd3d", None}
errors = []

for f in glob.glob("db/games/*.json"):
    d = json.load(open(f))
    for key in ("id", "title", "status", "provenance", "notes"):
        if key not in d: errors.append(f"{f}: missing {key}")
    if d.get("status") not in STATUSES: errors.append(f"{f}: bad status {d.get('status')}")
    if d.get("renderer") not in RENDERERS: errors.append(f"{f}: bad renderer {d.get('renderer')}")
    if d.get("status") == "verified-local" and not d.get("lastVerified"):
        errors.append(f"{f}: verified-local requires lastVerified")
    # The app decodes these with fixed types; a wrong shape drops the row silently (2026-09-08:
    # a lastVerified block instead of a date string hid Five Nights at Freddy's from the app).
    if d.get("lastVerified") is not None and not isinstance(d["lastVerified"], str):
        errors.append(f"{f}: lastVerified must be a date string (YYYY-MM-DD) or null; details go under \"verified\"")
    if d.get("verified") is not None and not (isinstance(d["verified"], dict) and all(isinstance(v, str) for v in d["verified"].values())):
        errors.append(f"{f}: verified must be an object of strings (chip, macos, engine, fps)")
    # The app reads this field as "<figure> where it was read" and puts "frames per second" after
    # the figure, one sentence. A figure first, or a short status with no figure at all.
    fps = d["verified"].get("fps") if isinstance(d.get("verified"), dict) else None
    if fps is not None and not (re.match(r"^(about )?[0-9]", fps, re.I) or len(fps) <= 64):
        errors.append(f"{f}: verified.fps must start with the figure ('about 34 in the prologue ride at 1280x720') or be a short status; details go in notes")
    if "nativeVulkan" in d and not isinstance(d["nativeVulkan"], bool):
        errors.append(f"{f}: nativeVulkan must be true or false")
    if "epic_app_name" in d and not isinstance(d["epic_app_name"], str):
        errors.append(f"{f}: epic_app_name must be a string")
    if d.get("status") == "blocked-anticheat" and d.get("renderer") is not None:
        errors.append(f"{f}: blocked entries must not recommend a renderer")

recipe_engines = {}
for f in glob.glob("recipes/*/*.json"):
    if f.endswith("LICENSE"): continue
    d = json.load(open(f))
    if d.get("kind") not in ("launcher", "game", "tweak"): errors.append(f"{f}: bad kind")
    if not isinstance(d.get("steps"), list) or not d["steps"]: errors.append(f"{f}: steps missing")
    recipe_engines[d.get("id")] = d.get("engine")
    # The CLI decodes a recipe's lastVerified as an object of five strings (date, engine, macos,
    # chip, result), unlike a row's, which is a date string. A bare date here fails every CI run
    # that validates recipes against the CLI (2026-09-12, the Metaphor recipe).
    lv = d.get("lastVerified")
    if lv is not None:
        if not isinstance(lv, dict) or not all(isinstance(lv.get(k), str) and lv.get(k) for k in ("date", "engine", "macos", "chip", "result")):
            errors.append(f"{f}: recipe lastVerified must be null or an object with string date, engine, macos, chip, result")

# A fix that lives in an engine only reaches people if a recipe names that engine: Highball offers
# a required engine at Play time, and otherwise the owner has to find "Update engine" in Settings.
# The reporter on highball#63 could not find it, so a published fix never reached them
# (2026-09-09). If a row says an issue is fixedIn some engine, the recipe must ask for that engine.
for f in glob.glob("db/games/*.json"):
    d = json.load(open(f))
    for issue in d.get("knownIssues") or []:
        want = issue.get("fixedIn")
        if not want: continue
        have = recipe_engines.get(d["id"], "MISSING")
        if have == "MISSING":
            errors.append(f'{f}: an issue is fixedIn "{want}" but there is no recipe for this game, '
                          f'so Play cannot offer that engine and the fix will not reach anyone')
        elif have != want:
            errors.append(f'{f}: an issue is fixedIn "{want}" but recipes/games/{d["id"]}.json asks for '
                          f'"{have}", so Play offers the wrong engine')

if errors:
    print("\n".join(errors)); sys.exit(1)
print(f"ok: {len(glob.glob('db/games/*.json'))} games, {len(glob.glob('recipes/*/*.json'))} recipes")
