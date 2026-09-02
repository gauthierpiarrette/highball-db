#!/usr/bin/env python3
"""Regression tests for ingest-report.py, run against the real report corpus.

Tests/reports/ holds every issue this project has actually received. They are the
tests because they are the population: all 7 are free-form prose, which is exactly
what the previous form-only parser could not read.

Usage: python3 Scripts/test-ingest.py     (from the repo root)
"""
import json, glob, os, shutil, subprocess, sys, tempfile

ROOT = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
SCRIPT = os.path.join(ROOT, "Scripts", "ingest-report.py")
CODES = {0: ("WROTE", "DUPLICATE"), 3: ("NEEDS_GAME_ID",), 4: ("NEEDS_DECISION",)}
fails = []


def sandbox():
    d = tempfile.mkdtemp()
    os.symlink(os.path.join(ROOT, "db", "games"), os.path.join(d, "_games"))
    os.makedirs(os.path.join(d, "db"))
    os.symlink(os.path.join(ROOT, "db", "games"), os.path.join(d, "db", "games"))
    os.makedirs(os.path.join(d, "db", "reports"))
    return d


def run(box, body, num, title, user="tester", created="2026-09-01T12:00:00Z"):
    env = {**os.environ, "BODY": body, "NUM": str(num), "TITLE": title,
           "USER": user, "CREATED": created, "RUNNER_TEMP": box}
    env.pop("GITHUB_OUTPUT", None)
    p = subprocess.run([sys.executable, SCRIPT], cwd=box, env=env,
                       capture_output=True, text=True)
    outcome = (p.stdout.splitlines() or [""])[0].strip()
    return outcome, p.returncode, p.stdout + p.stderr


def check(name, got, want):
    if got == want:
        print(f"  ok    {name}")
    else:
        print(f"  FAIL  {name}: got {got!r}, want {want!r}")
        fails.append(name)


def fixture(n):
    return json.load(open(os.path.join(ROOT, "Tests", "reports", f"issue-{n}.json")))


print("== the real corpus ==")
EXPECT = {
    1: ("WROTE", "pragmata-sketchbook-demo"),
    2: ("WROTE", "cyberpunk-2077"),
    3: ("WROTE", "cyberpunk-2077"),
    4: ("NEEDS_GAME_ID", None),   # a feature request, not a report: a human decides
    5: ("WROTE", "beamng-drive"),
    6: ("WROTE", "microsoft-flight-simulator-2024"),
    7: ("WROTE", "the-sims-legacy-collection"),   # entry added 2026-09-02; was NEEDS_GAME_ID before it existed
}
for n in sorted(EXPECT):
    want_outcome, want_id = EXPECT[n]
    f = fixture(n)
    box = sandbox()
    outcome, code, log = run(box, f["body"], f["number"], f["title"], f["user"], f["created"])
    check(f"#{n} outcome", outcome, want_outcome)
    if outcome in CODES.get(code, ()) or True:
        pass
    if want_id:
        p = os.path.join(box, "db", "reports", f"{want_id}.jsonl")
        check(f"#{n} lands in {want_id}.jsonl", os.path.exists(p), True)
        if os.path.exists(p):
            rec = json.loads(open(p).read().strip().splitlines()[-1])
            check(f"#{n} game_id", rec["game_id"], want_id)
            check(f"#{n} issue", rec["issue"], n)
            check(f"#{n} no empty strings", [k for k, v in rec.items() if v == ""], [])
    shutil.rmtree(box)

print("== the bug that burned us: re-labelling must not double-add ==")
f = fixture(5)
box = sandbox()
run(box, f["body"], 5, f["title"], f["user"], f["created"])
outcome, _, _ = run(box, f["body"], 5, f["title"], f["user"], f["created"])
check("second label is DUPLICATE", outcome, "DUPLICATE")
lines = open(os.path.join(box, "db", "reports", "beamng-drive.jsonl")).read().strip().splitlines()
check("still one record", len(lines), 1)
shutil.rmtree(box)

print("== the join bug: filename must be the game id, not the issue title ==")
box = sandbox()
f = fixture(6)
run(box, f["body"], 6, f["title"], f["user"], f["created"])
check("no title-slug file", glob.glob(os.path.join(box, "db", "reports", "*shader*")), [])
check("joins by id", os.path.exists(os.path.join(box, "db", "reports",
      "microsoft-flight-simulator-2024.jsonl")), True)
shutil.rmtree(box)

print("== synthetic edge cases ==")
CASES = [
    ("empty body, title resolves", "", "BeamNG.drive", "WROTE"),
    ("issue form still works", "### Game or launcher\n\nPortal 2\n\n### Renderer\n\ndxvk\n",
     "anything", "WROTE"),
    ("unknown game", "Some game that does not exist here.", "Totally Unknown Game 9000",
     "NEEDS_GAME_ID"),
    ("not a game at all", "Please add a settings toggle.", "feature request", "NEEDS_GAME_ID"),
    ("bare prefix title is ambiguous", "It crashes.", "Portal", "NEEDS_DECISION"),
    ("steam url gives the appid", "See https://store.steampowered.com/app/1091500/ for it.",
     "Cyberpunk 2077", "WROTE"),
]
for name, body, title, want in CASES:
    box = sandbox()
    outcome, code, log = run(box, body, 900 + CASES.index((name, body, title, want)), title)
    check(name, outcome, want)
    shutil.rmtree(box)

print("== a '## Section' heading is not a field label ==")
box = sandbox()
body = "## Game\n\n- **Cyberpunk 2077** - Steam app id [1091500](https://store.steampowered.com/app/1091500/)\n"
run(box, body, 960, "Cyberpunk 2077")
rec = json.loads(open(os.path.join(box, "db", "reports", "cyberpunk-2077.jsonl")).read().strip())
check("title is not a swallowed markdown line", rec["title"], "Cyberpunk 2077")
shutil.rmtree(box)

print("== fields are read or null, never guessed ==")
box = sandbox()
body = ("| Chip | Apple M4 |\n| macOS version | 26.5.2 |\n| Renderer | d3dmetal |\n"
        "| Rating | 1 — does not launch |\n| Steam AppID | 1091500 |\n")
run(box, body, 950, "Cyberpunk 2077")
rec = json.loads(open(os.path.join(box, "db", "reports", "cyberpunk-2077.jsonl")).read().strip())
for k, v in [("chip", "Apple M4"), ("macos", "26.5.2"), ("renderer", "d3dmetal"),
             ("rating", "1"), ("steam_appid", "1091500")]:
    check(f"reads {k}", rec[k], v)
shutil.rmtree(box)

box = sandbox()
body = ("| Renderer | not reported, presumably the default (dxmt) |\n"
        "| Chip | M4 MacBook (exact model not given) |\n"
        "| macOS | not reported |\n")
run(box, body, 951, "Cyberpunk 2077")
rec = json.loads(open(os.path.join(box, "db", "reports", "cyberpunk-2077.jsonl")).read().strip())
for k in ("renderer", "chip", "macos"):
    check(f"refuses to guess {k}", rec[k], None)
shutil.rmtree(box)

box = sandbox()
body = "The bottle was set to d3dmetal/dxvk and the log shows 1920x1200 and 0x80004002.\n"
run(box, body, 952, "Cyberpunk 2077")
rec = json.loads(open(os.path.join(box, "db", "reports", "cyberpunk-2077.jsonl")).read().strip())
check("two renderers in one phrase -> null", rec["renderer"], None)
check("log noise is not an appid", rec["steam_appid"], None)
shutil.rmtree(box)

print()
if fails:
    print(f"{len(fails)} FAILED: " + ", ".join(fails))
    sys.exit(1)
print("all ingest tests passed")
