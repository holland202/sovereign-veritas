#!/usr/bin/env python3
"""status.py - whose turn is it in P-001? Read-only, stdlib only, runs in Termux.

  python coordination/p001/status.py            the last 3 handoffs on PR #63, and who acts next
  python coordination/p001/status.py --all      every handoff

It reads the public comments on PR #63 (GitHub REST, no token, nothing written) and prints the
YAML header of each handoff: note, state, next. The last `next:` is whose turn it is. When that is
ChatGPT, it also prints the one-line nudge to paste into ChatGPT, so you relay a pointer, not a
summary. Exit: 0 printed | 2 could not reach GitHub.

Written by Claude (Opus 5.5) for P-001 under Chad Holland's direction (2026-10-09).
"""
import json, re, sys, urllib.request

REPO, PR = "holland202/sovereign-veritas", 63
URL = f"https://api.github.com/repos/{REPO}/issues/{PR}/comments?per_page=100&page={{}}"
KEYS = ("note", "state", "verdict", "next")


def fetch():
    out, page = [], 1
    while True:
        req = urllib.request.Request(URL.format(page), headers={"Accept": "application/vnd.github+json",
                                                                "User-Agent": "p001-status"})
        with urllib.request.urlopen(req, timeout=30) as r:
            batch = json.load(r)
        out += batch
        if len(batch) < 100:
            return out
        page += 1


def header(body):
    m = re.search(r"```yaml\n(.*?)```", body or "", re.S)
    if not m:
        return None
    h = {}
    for line in m.group(1).splitlines():
        k, _, v = line.partition(":")
        if k.strip() in KEYS and v.strip():
            h.setdefault(k.strip(), v.split("#")[0].strip())
    return h or None


def main(argv):
    try:
        comments = fetch()
    except OSError as exc:
        print(f"COULD NOT LOOK: {exc}")
        return 2
    rows = [(c["created_at"], c["html_url"], h) for c in comments if (h := header(c.get("body")))]
    if not rows:
        print("no handoff headers on #63 yet")
        return 0
    for t, url, h in (rows if "--all" in argv else rows[-3:]):
        print(f"{t[:16].replace('T', ' ')}Z  {h.get('note', '?')}")
        for k in ("state", "verdict", "next"):
            if k in h:
                print(f"    {k}: {h[k]}")
        print(f"    {url}")
    nxt = next((h["next"] for _, _, h in reversed(rows) if "next" in h), "?")
    print(f"\nNEXT: {nxt}")
    if nxt.lower().startswith("chatgpt"):
        print("Paste to ChatGPT:\n"
              f"  Read the latest comment on https://github.com/{REPO}/pull/{PR} and act on it under the P-001 charter.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
