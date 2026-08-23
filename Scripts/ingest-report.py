#!/usr/bin/env python3
"""Fold an accepted GitHub issue report (issue-form markdown in $BODY) into db/reports/<slug>.jsonl."""
import json, os, re, sys

body, num, user, created = (os.environ.get(k, "") for k in ("BODY", "NUM", "USER", "CREATED"))
def field(name):
    m = re.search(rf"### {name}\s*\n+\s*(.+?)(?:\n{{2,}}|$)", body, re.S)
    return m.group(1).strip() if m else None

title = field("Game or launcher")
if not title: sys.exit("no title in body")
slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
report = {
    "issue": int(num) if num else None, "user": user, "date": created,
    "title": title, "steam_appid": field(r"Steam AppID \(if a Steam game\)"),
    "rating": (field("Rating") or "")[:1], "renderer": field("Renderer"),
    "chip": field("Chip"), "macos": field("macOS version"), "engine": field("Engine id"),
    "notes": field("Notes"),
}
os.makedirs("db/reports", exist_ok=True)
with open(f"db/reports/{slug}.jsonl", "a") as f:
    f.write(json.dumps(report, ensure_ascii=False) + "\n")
print(f"appended db/reports/{slug}.jsonl")
