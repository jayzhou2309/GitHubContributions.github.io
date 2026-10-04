#!/usr/bin/env bash
# Extract the headline, bug and fix of each PR from oss-grind's PR docs into
# notes/notes.json and push, so the next Pages build shows the explanations.
set -euo pipefail
cd "$(dirname "$0")/.."
git pull -q --rebase
python3 scripts/build_data.py --sync-notes
git add notes/notes.json
if git diff --cached --quiet; then
  echo "notes unchanged"
  exit 0
fi
git commit -q -m "notes: sync PR explanations $(date -u +%Y-%m-%dT%H:%MZ)"
git push -q
echo "notes synced and pushed"
