#!/usr/bin/env python3
"""Fold an accepted issue report into db/reports/<game_id>.jsonl.

Reports arrive as prose. Every report this project has ever received (7 of 7) was a
blank issue rather than the issue form, so the previous form-only parser matched none
of them and exited 1, which failed the run and ingested nothing.

Two rules shape everything here:

  A field is read from an explicit label or it is null. Nothing is inferred, defaulted,
  or backfilled from db/games. The database is the product; a wrong value costs more
  than a missing one.

  The filename is the db/games id, never a slug of the issue title. build-site.py joins
  reports to games by id, so a title-derived name produces a file the site never reads.
  Issue #6's title would have slugged to 109 characters and joined to nothing.

Outcomes and exit codes: WROTE 0, DUPLICATE 0, NEEDS_GAME_ID 3, NEEDS_DECISION 4,
hard error 1. Codes above 1 are questions for the maintainer, not breakage: the
workflow comments on the issue and stays green. Red means broken.

There is deliberately no "this is not a compatibility report" outcome. Separating a
report about a game we do not have yet from an issue that is not a report needs
knowledge the text does not contain, and both end the same way: a human decides.
Inventing the distinction would only make the bot sound more certain than it is.
"""
import glob, json, os, re, sys

REPORTS, GAMES = "db/reports", "db/games"
RENDERERS = {"d3dmetal", "dxmt", "dxvk", "wined3d"}
NON_ANSWERS = {"not reported", "not given", "unknown", "unspecified", "n/a", "na",
               "none", "-", "—", "?", ""}

AID = r"(?<![\d.])(\d{1,8})(?![\d.])"
LABEL_AID = re.compile(r"\b(?:steam\s*app\s*id|steam\s*id|app\s*id)\b[^0-9\n]{0,12}" + AID, re.I)
URL_AID = re.compile(r"store\.steampowered\.com/app/" + AID)
# Case-sensitive on purpose: lowercasing matches "mac16,12" inside log noise.
MODEL_ID = re.compile(r"(?<![A-Za-z0-9])"
                      r"(?:iMacPro|iMac|MacBookPro|MacBookAir|MacBook|Macmini|MacPro|MacStudio|Mac)"
                      r"\d{1,2},\d{1,2}(?![A-Za-z0-9.])")
CHIP = re.compile(r"^apple\s+m(\d{1,2})(\s+(pro|max|ultra))?$", re.I)
MACOS_INLINE = re.compile(r"(?i)\bmacos\s+v?(\d{2}(?:\.\d{1,2}){0,2})\b")
MACOS_OK = re.compile(r"^\d{2}(\.\d{1,2}){0,2}$")
GAME_ID_OVERRIDE = re.compile(r"^\s*game_id\s*:\s*([A-Za-z0-9._-]+)\s*$", re.M)


def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def strip_code(body):
    """Drop fenced and indented blocks. Mandatory: #6 pastes logs containing version
    numbers and 'Mac16,12' that would otherwise be read as reported values."""
    out, fenced = [], False
    for line in body.splitlines():
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if fenced or line.startswith("    ") or line.startswith("\t"):
            continue
        out.append(line)
    return "\n".join(out)


def clean(v):
    v = v.strip().strip("|").strip()
    v = re.sub(r"^[*_`]+|[*_`]+$", "", v).strip()
    return re.sub(r":$", "", v).strip()


def find_label(body, names):
    """First value for any of `names`, across the three shapes reporters actually use:
    a pipe-table row, a bullet or plain 'Label: value' line, and a '### Label' heading
    followed by its first non-empty line."""
    want = {norm(n) for n in names}
    lines = body.splitlines()
    for i, line in enumerate(lines):
        if line.count("|") >= 2:
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) >= 2 and norm(clean(cells[0])) in want:
                return clean(cells[1])
        m = re.match(r"^\s*(?:[-*+]\s*)?(.{1,40}?)\s*:\s*(.*)$", line)
        if m and norm(clean(m.group(1))) in want:
            return clean(m.group(2))
        # Only the issue form's own shape: '### Label' followed by a plain value.
        # A '## Game' prose section is a heading over a bullet list, not a field, and
        # treating it as one swallows a whole markdown line as the value.
        m = re.match(r"^#{3,6}\s+(.+?)\s*$", line)
        if m and norm(clean(m.group(1))) in want:
            for nxt in lines[i + 1:]:
                if not nxt.strip():
                    continue
                if nxt.lstrip()[0] in "#-*+|>" or len(nxt) > 120:
                    return None
                return clean(nxt)
    return None


def answered(v):
    return v is not None and v.strip().lower() not in NON_ANSWERS


def appid_of(body):
    hits = {m for m in LABEL_AID.findall(body)} | {m for m in URL_AID.findall(body)}
    return hits.pop() if len(hits) == 1 else None


def load_index():
    games, appid, key, titles = [], {}, {}, {}
    for f in sorted(glob.glob(f"{GAMES}/*.json")):
        g = json.load(open(f))
        games.append(g)
        gid = g["id"]
        titles[gid] = g.get("title", gid)
        if g.get("steam_appid"):
            a = str(g["steam_appid"])
            if a in appid and appid[a] != gid:
                sys.exit(f"duplicate steam_appid {a}: {appid[a]} and {gid}")
            appid[a] = gid
        for cand in [gid, g.get("title", "")] + list(g.get("aliases") or []):
            if not cand:
                continue
            k = norm(cand)
            if k in key and key[k] != gid:
                sys.exit(f"ambiguous key {k!r}: {key[k]} and {gid}")
            key[k] = gid
    # Keys that are a prefix of another key: a bare title match on these is ambiguous
    # ("Portal" vs "Portal 2"), so they need corroboration before we accept them.
    prefix = {k for k in key if any(o != k and o.startswith(k + " ") for o in key)}
    return games, appid, key, titles, prefix


def title_candidates(issue_title):
    """Whole title first, then trim one trailing segment at a time. Never shortest-first:
    19 catalogued titles contain ': ' (NieR: Automata, Alien: Isolation), and a
    segment-only walk resolves none of them."""
    cands, cur = [issue_title.strip()], issue_title.strip()
    while True:
        m = None
        for sep in (" — ", " – ", " - ", ": "):
            i = cur.rfind(sep)
            if i > 0 and (m is None or i > m[0]):
                m = (i, sep)
        if not m:
            break
        cur = cur[:m[0]].strip()
        cands.append(cur)
    return cands


def resolve(body, issue_title, appid, key, prefix):
    """Return (game_id, resolved_via, tried, appid_value). Tiers must agree."""
    m = GAME_ID_OVERRIDE.search(body)
    if m and norm(m.group(1)) in {norm(k) for k in key.values()}:
        return m.group(1), "maintainer", [], appid_of(body)
    a = appid_of(body)
    tried, by = [], {}
    if a and a in appid:
        by["appid"] = appid[a]
    for label in ("Game or launcher", "Game title", "Game", "Title"):
        v = find_label(body, [label])
        if answered(v):
            tried.append(v)
            if norm(v) in key:
                by["body-label"] = key[norm(v)]
            break
    for cand in title_candidates(issue_title):
        tried.append(cand)
        if norm(cand) in key:
            by.setdefault("title-prefix", key[norm(cand)])
            break
    ids = set(by.values())
    if len(ids) > 1:
        return None, "conflict:" + ", ".join(f"{k}={v}" for k, v in sorted(by.items())), tried, a
    if not ids:
        return None, None, tried, a
    gid = ids.pop()
    via = "+".join(k for k in ("appid", "body-label", "title-prefix", "maintainer") if k in by)
    if via == "title-prefix":
        matched = next(c for c in tried if norm(c) in key)
        if norm(matched) in prefix:
            return None, f"ambiguous:{matched!r} is a prefix of another title", tried, a
    return gid, via, tried, a


def extract(body):
    """Labelled values only. Everything else is null, with a reason recorded."""
    b = strip_code(body)
    rec, asks = {}, []

    a = appid_of(b)
    rec["steam_appid"] = a
    if not a:
        asks.append("steam_appid: no labelled AppID or store.steampowered.com link")

    r = find_label(b, ["Rating", "Score"])
    rec["rating"] = r[0] if answered(r) and r[0] in "12345" else None
    if rec["rating"] is None:
        asks.append("rating: no labelled 1-5 Rating (prose verdicts are never mapped)")

    v = find_label(b, ["Renderer", "Graphics backend", "Backend"])
    val = re.sub(r"\s*\([^)]*\)$", "", v).strip().lower() if answered(v) else None
    rec["renderer"] = val if val in RENDERERS else None
    if rec["renderer"] is None:
        asks.append("renderer: no labelled value matching exactly one of " + ", ".join(sorted(RENDERERS)))

    c = find_label(b, ["Chip", "CPU", "SoC"])
    rec["chip"] = None
    if answered(c) and CHIP.match(c):
        g = CHIP.match(c)
        rec["chip"] = "Apple M" + g.group(1) + (" " + g.group(3).capitalize() if g.group(3) else "")
    if rec["chip"] is None:
        asks.append("chip: no labelled 'Apple M<n> [Pro|Max|Ultra]'")

    mv = find_label(b, ["macOS version", "macOS", "macOS ver", "OS version"])
    rec["macos"] = None
    if answered(mv) and MACOS_OK.match(mv) and 10 <= int(mv.split(".")[0]) <= 30:
        rec["macos"] = mv
    elif mv is None:
        hits = {h for h in MACOS_INLINE.findall(b)}
        if len(hits) == 1:
            h = hits.pop()
            if MACOS_OK.match(h) and 10 <= int(h.split(".")[0]) <= 30:
                rec["macos"] = h
    if rec["macos"] is None and answered(mv):
        asks.append(f"macos: value present but unparseable: {mv!r}")
    elif rec["macos"] is None:
        asks.append("macos: not reported")

    ids = list(dict.fromkeys(MODEL_ID.findall(b)))
    rec["model_identifier"] = ids[0] if len(ids) == 1 else None
    if len(ids) > 1:
        asks.append("model_identifier: multiple found: " + ", ".join(ids))

    e = find_label(b, ["Engine id", "Engine"])
    rec["engine"] = e if answered(e) else None
    if rec["engine"] is None:
        asks.append("engine: no labelled Engine id")

    n = find_label(b, ["Notes", "Test notes"])
    rec["notes"] = n if answered(n) else None
    return rec, asks


def already_ingested(num):
    """Dedupe on the issue number, before extraction. Re-labelling must be a no-op:
    the maintainer hand-entered #5 and #6, and a second add would double-count them."""
    for f in sorted(glob.glob(f"{REPORTS}/*.jsonl")):
        for i, line in enumerate(open(f), 1):
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError as e:
                sys.exit(f"{f}:{i} is not valid JSON ({e}); refusing to append")
            if rec.get("issue") is not None and int(rec["issue"]) == num:
                return f
    return None


def append(path, rec):
    """Never let a missing trailing newline glue two records together."""
    if os.path.exists(path) and os.path.getsize(path):
        with open(path, "rb") as f:
            f.seek(-1, os.SEEK_END)
            lead = "" if f.read(1) == b"\n" else "\n"
    else:
        lead = ""
    with open(path, "a", encoding="utf-8") as f:
        f.write(lead + json.dumps(rec, ensure_ascii=False) + "\n")


def suggestions(tried, key, titles):
    import difflib
    scored = []
    for cand in tried:
        for k, gid in key.items():
            s = difflib.SequenceMatcher(None, norm(cand), k).ratio()
            if s >= 0.75:
                scored.append((s, gid))
    best, seen = [], set()
    for s, gid in sorted(scored, key=lambda x: (-x[0], x[1])):
        if gid not in seen:
            seen.add(gid)
            best.append(f"- `{gid}` ({titles[gid]})")
        if len(best) == 3:
            break
    return best


def emit(outcome, comment, code):
    tmp = os.environ.get("RUNNER_TEMP", ".")
    open(os.path.join(tmp, "outcome"), "w").write(outcome)
    open(os.path.join(tmp, "comment.md"), "w").write(comment)
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"outcome={outcome}\n")
    print(f"{outcome}\n\n{comment}")
    sys.exit(code)


def main():
    body = os.environ.get("BODY", "")
    raw_num = os.environ.get("NUM", "")
    user = os.environ.get("USER", "")
    created = os.environ.get("CREATED", "")
    issue_title = os.environ.get("TITLE", "")

    if not raw_num.isdigit():
        sys.exit(f"NUM is not an issue number: {raw_num!r}")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", created):
        # "" would type-check and then sort the newest report to the oldest.
        sys.exit(f"CREATED is not an ISO timestamp: {created!r}")
    if not user:
        sys.exit("USER is empty")
    num = int(raw_num)

    dup = already_ingested(num)
    if dup:
        emit("DUPLICATE", f"Already ingested into `{dup}`. Nothing was written.", 0)

    _, appid, key, titles, prefix = load_index()
    gid, via, tried, a = resolve(body, issue_title, appid, key, prefix)

    if gid is None:
        cands = "\n".join(f"- {c!r}" for c in dict.fromkeys(tried)) or "- (none)"
        if via and via.startswith("conflict:"):
            emit("NEEDS_DECISION",
                 f"Two ways of identifying this game disagree, so nothing was written.\n\n"
                 f"{via[len('conflict:'):]}\n\nResolve by adding a line to the issue body:\n"
                 f"```\ngame_id: <the correct id>\n```\nthen re-apply `report-accepted`.", 4)
        if via and via.startswith("ambiguous:"):
            emit("NEEDS_DECISION",
                 f"{via[len('ambiguous:'):]}, so this could match more than one entry and "
                 f"nothing was written.\n\nAdd `game_id: <id>` to the issue body and re-apply "
                 f"`report-accepted`.", 4)
        near = suggestions(tried, key, titles)
        appid_note = (f"\nSteam AppID `{a}` is not in `db/games` either.\n" if a else "")
        emit("NEEDS_GAME_ID",
             "Could not match this to an entry in `db/games`, so nothing was written.\n\n"
             f"Tried:\n{cands}\n{appid_note}"
             + ("\nDid you mean:\n" + "\n".join(near) + "\n" if near else "")
             + "\nThree ways forward:\n"
               "- it is an existing game under another name: add `game_id: <id>` to the issue body\n"
               "- it is a new game: create `db/games/<id>.json` first\n"
               "- it is not a compatibility report: remove the `report-accepted` label\n\n"
               "Then re-apply `report-accepted` if you want it ingested.", 3)

    if not os.path.exists(f"{GAMES}/{gid}.json"):
        sys.exit(f"resolved {gid} but {GAMES}/{gid}.json does not exist")

    fields, asks = extract(body)
    name = find_label(strip_code(body), ["Game or launcher", "Game title", "Game", "Title"])
    rec = {"issue": num, "user": user, "date": created,
           "title": name if answered(name) else next((c for c in tried if norm(c) in key), titles[gid]),
           "game_id": gid, "resolved_via": via, **fields, "ingested_by": "workflow"}

    assert rec["renderer"] in RENDERERS or rec["renderer"] is None
    assert rec["rating"] in {"1", "2", "3", "4", "5", None}
    for k, v in rec.items():
        assert v != "", f"{k} is empty string; use null"

    os.makedirs(REPORTS, exist_ok=True)
    path = f"{REPORTS}/{gid}.jsonl"
    append(path, rec)
    gaps = ("\n\nLeft null, because nothing in the issue stated them:\n"
            + "\n".join(f"- {x}" for x in asks)) if asks else ""
    emit("WROTE",
         f"Ingested into `{path}` as `{gid}` (matched via {via}).{gaps}\n\n"
         f"```json\n{json.dumps(rec, ensure_ascii=False, indent=2)}\n```", 0)


if __name__ == "__main__":
    main()
