<p align="center"><img src=".github/assets/logo.png" width="110" alt="Highball logo"></p>
<h1 align="center">highball-db</h1>

The open, CC0 compatibility database behind [Highball](https://github.com/gauthierpiarrette/highball):
Windows games and launchers on Apple Silicon through Wine + DXMT / D3DMetal / DXVK,
**as data with provenance** — verified runs, upstream reports, community consensus, and the
kernel-anti-cheat blocklist.

- `recipes/` — declarative install/config recipes (launchers, games, tweaks) applied by Highball
- `db/games/` — one JSON per title: `status` ∈ `verified-local · reported-upstream · community · blocked-anticheat`, plus `provenance`
- `db/reports/` — append-only community reports, folded in from issues labeled `report-accepted`
- `Scripts/` — validator, report ingester, static-site generator (GitHub Pages)

**Contribute:** run something through Highball, then `highball report` — it opens a pre-filled
issue here. Or PR a recipe with the CLI output attached. Everything here is CC0: use it in your
own launcher, wiki, or even with CrossOver.
