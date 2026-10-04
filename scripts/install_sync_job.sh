#!/usr/bin/env bash
# Install (or reinstall) a launchd job that starts a Pages build every hour, so
# PR states stay current even when GitHub skips the workflow's cron. It calls gh
# directly: macOS blocks launchd jobs from reading ~/Documents, where this repo
# lives. Notes sync separately, from oss-grind's after-tick hook.
# Uninstall: launchctl bootout gui/$(id -u)/com.jayzhou2309.contributions-sync
set -euo pipefail
LABEL=com.jayzhou2309.contributions-sync
REPO_SLUG=jayzhou2309/GitHubContributions.github.io
GH="$(command -v gh)"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG="$HOME/Library/Logs/contributions-sync.log"
mkdir -p "$(dirname "$PLIST")"
cat > "$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array><string>$GH</string><string>workflow</string><string>run</string><string>pages.yml</string><string>-R</string><string>$REPO_SLUG</string></array>
  <key>StartInterval</key><integer>3600</integer>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>$LOG</string>
  <key>StandardErrorPath</key><string>$LOG</string>
</dict>
</plist>
PLIST
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "installed $LABEL, log at $LOG"
