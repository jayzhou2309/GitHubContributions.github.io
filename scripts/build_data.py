#!/usr/bin/env python3
"""Build data.json: every public PR the author opened on repos they don't own.

Runs in the Pages workflow (GITHUB_TOKEN) or locally (falls back to `gh auth token`).
Plain-language headline, bug and fix come from notes/notes.json (see --sync-notes) when a PR has them,
else from the PR body's Why section.
"""
import json
import os
import re
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AUTHOR = os.environ.get("PORTFOLIO_AUTHOR", "jayzhou2309")

QUERY = """
query($q: String!, $after: String) {
  search(query: $q, type: ISSUE, first: 50, after: $after) {
    pageInfo { hasNextPage endCursor }
    nodes {
      ... on PullRequest {
        number title url state merged mergedAt createdAt closedAt updatedAt isDraft
        additions deletions changedFiles body
        reviewDecision
        reviews { totalCount }
        comments { totalCount }
        labels(first: 10) { nodes { name } }
        closingIssuesReferences(first: 5) { nodes { number title url state } }
        repository {
          nameWithOwner url description stargazerCount
          primaryLanguage { name color }
          owner { avatarUrl }
        }
      }
    }
  }
}
"""


def token():
    if os.environ.get("GITHUB_TOKEN"):
        return os.environ["GITHUB_TOKEN"]
    return subprocess.check_output(["gh", "auth", "token"], text=True).strip()


def graphql(variables, tok):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {tok}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as r:
        out = json.load(r)
    if out.get("errors"):
        sys.exit(f"graphql errors: {out['errors']}")
    return out["data"]["search"]


def fetch_prs():
    tok = token()
    q = f"author:{AUTHOR} is:pr is:public -user:{AUTHOR} sort:updated-desc"
    prs, after = [], None
    while True:
        page = graphql({"q": q, "after": after}, tok)
        prs += [n for n in page["nodes"] if n]
        if not page["pageInfo"]["hasNextPage"]:
            return prs
        after = page["pageInfo"]["endCursor"]


PR_URL = re.compile(r"https://github\.com/[\w.-]+/[\w.-]+/pull/\d+")


def labelled(section, label):
    """Text after `- Label:` or under a `**The label**` heading, up to the next label."""
    m = re.search(rf"^- {label}: (.+)$", section, re.M | re.I)
    if m:
        return m.group(1).strip()
    m = re.search(rf"^\*\*(?:The )?{label}\*\*\s*\n(.*?)(?=^\*\*|^#|\Z)", section, re.M | re.S | re.I)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""


NOTES = ROOT / "notes" / "notes.json"


def extract_notes(oss_dir):
    """Map PR URL -> {headline, bug, fix} from oss-grind's <name>-prs.md docs.

    Only these three plain-language fields leave the machine; status, blockers
    and next steps in the docs stay private.
    """
    notes = {}
    for doc in sorted(Path(oss_dir).glob("*-prs.md")):
        for section in re.split(r"^## ", doc.read_text(), flags=re.M)[1:]:
            url = PR_URL.search(section)
            if not url:
                continue
            title = section.split("\n", 1)[0]
            entry = {
                "headline": re.sub(r"^#\d+\s*", "", title).strip(),
                "bug": labelled(section, "bug"),
                "fix": labelled(section, "fix"),
            }
            notes[url.group(0)] = {k: v for k, v in entry.items() if v}
    return notes


def load_notes():
    return json.loads(NOTES.read_text()) if NOTES.exists() else {}


AGENT_FOOTER = re.compile(r"\n---\s*\n<!-- oss-agent -->.*", re.S)


def section(body, names):
    """Return the first markdown section whose heading matches one of names."""
    for name in names:
        m = re.search(rf"^#+\s*{name}\b[^\n]*\n(.*?)(?=^#+\s|\Z)", body, re.M | re.S | re.I)
        if m and m.group(1).strip():
            return m.group(1).strip()
    return ""


def first_paragraph(text, limit=700):
    para = text.strip().split("\n\n")[0].strip()
    return para if len(para) <= limit else para[:limit].rsplit(" ", 1)[0] + "…"


def status(pr):
    if pr["merged"]:
        return "merged"
    if pr["state"] == "CLOSED":
        return "closed"
    return "draft" if pr["isDraft"] else "open"


def shape(pr, notes):
    body = AGENT_FOOTER.sub("", pr.get("body") or "")
    note = notes.get(pr["url"].rstrip("/"), {})
    why = section(body, ["What Problem This Solves", "Why", "Summary", "What does this PR do", "Description"])
    what = section(body, ["Why This Change Was Made", "Scope", "Changes Made", "Changes", "Description of change"])
    verification = section(body, ["Verification", "Evidence", "How to Test", "Testing"])
    repo = pr["repository"]
    return {
        "number": pr["number"],
        "title": pr["title"],
        "url": pr["url"],
        "status": status(pr),
        "createdAt": pr["createdAt"],
        "mergedAt": pr["mergedAt"],
        "closedAt": pr["closedAt"],
        "updatedAt": pr["updatedAt"],
        "additions": pr["additions"],
        "deletions": pr["deletions"],
        "changedFiles": pr["changedFiles"],
        "reviews": pr["reviews"]["totalCount"],
        "comments": pr["comments"]["totalCount"],
        "reviewDecision": pr["reviewDecision"],
        "labels": [l["name"] for l in pr["labels"]["nodes"]],
        "issues": pr["closingIssuesReferences"]["nodes"],
        "headline": note.get("headline", ""),
        "bug": note.get("bug") or first_paragraph(why),
        "fix": note.get("fix") or first_paragraph(what),
        "why": why,
        "changes": what,
        "verification": verification,
        "repo": repo["nameWithOwner"],
    }


def main():
    if sys.argv[1:2] == ["--sync-notes"]:
        oss = os.environ.get("OSS_ROOT", str(Path.home() / "Documents/GitHub/oss"))
        NOTES.parent.mkdir(exist_ok=True)
        NOTES.write_text(json.dumps(extract_notes(oss), indent=1, sort_keys=True) + "\n")
        print(f"wrote {NOTES.relative_to(ROOT)}")
        return
    notes = load_notes()
    raw = fetch_prs()
    repos = {}
    for pr in raw:
        r = pr["repository"]
        repos.setdefault(r["nameWithOwner"], {
            "name": r["nameWithOwner"],
            "url": r["url"],
            "description": r["description"],
            "stars": r["stargazerCount"],
            "language": (r["primaryLanguage"] or {}).get("name"),
            "languageColor": (r["primaryLanguage"] or {}).get("color"),
            "avatar": r["owner"]["avatarUrl"],
        })
    data = {
        "author": AUTHOR,
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "repos": list(repos.values()),
        "prs": [shape(pr, notes) for pr in raw],
    }
    out = ROOT / "site" / "data.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(data, indent=1))
    counts = {}
    for p in data["prs"]:
        counts[p["status"]] = counts.get(p["status"], 0) + 1
    print(f"wrote {out.relative_to(ROOT)}: {len(data['prs'])} PRs across {len(repos)} repos {counts}")


if __name__ == "__main__":
    main()
