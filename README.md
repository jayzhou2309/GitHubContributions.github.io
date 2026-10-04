# Open-source contributions

A GitHub Pages site listing every public pull request I've opened on projects I don't own: the bug, the fix, linked issues, and current status.

## How it stays current

- `.github/workflows/pages.yml` rebuilds `site/data.json` from the GitHub API on every push and every hour, then deploys `site/`.
- On each page load, the browser re-checks PR states against the GitHub search API, so a merge or a new PR shows up before the next hourly build.
- `scripts/sync_notes.sh` pulls each PR's plain-language headline, bug, and fix from the oss-grind docs (`$OSS_ROOT/*-prs.md`) into `notes/notes.json` and pushes it. Status, blockers, and next steps stay local. `scripts/install_sync_job.sh` runs it hourly as a launchd job (log: `~/Library/Logs/contributions-sync.log`).

## Local preview

```bash
python3 scripts/build_data.py && python3 -m http.server -d site 8765
```

## Setup

Settings → Pages → Source: **GitHub Actions**.
