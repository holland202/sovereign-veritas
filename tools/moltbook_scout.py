"""moltbook_scout.py: a read-only scout for veritasgate. Finds and records; never posts and never obeys.

Run on the S25 in Termux:   python3 moltbook_scout.py
  --no-replies   skip the one call that needs your API key (search alone needs no key)
  --ask "text"   search one question of your own, posts and comments, and nothing else, e.g.
                 python3 moltbook_scout.py --ask "idempotency key for side effects after a timeout"

What it does
  1. Searches Moltbook once per open question (QUESTIONS below), which comes from the repos.
  2. Calls GET /api/v1/home with your key to list replies on your posts, and reads them.
  3. Records every hit in ~/moltbook_scout/ledger.jsonl: post id, author, time, sha256 of the text, and
     the question it matched. A hit already seen for the same question is not counted again.
  4. Writes and prints a digest, ~/moltbook_scout/digest-<time>.md: new hits per question, plus replies.

What it never does
  Any request other than GET, any host other than www.moltbook.com, posting, voting, following, or
  marking notifications read. Post text is untrusted data written by other agents: it is shown with
  control characters stripped and is never run or followed. Turning a hit into work is a human
  decision (register a hypothesis, then test it). The scout does not decide what is true.

Written with Claude (Opus 5.5) for Chad Holland, 2026-10-04. Container-tested on search only; the
--replies path needs the key, so it is first run on the phone. Standard library only.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

HOST = "https://www.moltbook.com/api/v1/"
ME = "veritasgate"
OUT = os.path.expanduser("~/moltbook_scout")
CRED = os.path.expanduser("~/.config/moltbook/credentials.json")
PER_QUERY = 8
# Authors whose posts are skipped. Your choice; edit freely. Starting entry: many near-identical templated
# posts that crowded out real discussion in the first test run (2026-10-04).
MUTE = {"auroras_happycapy"}

# id: (what in the repos it serves, search text). Edit freely; the ids keep the ledger readable.
QUESTIONS = {
    "Q1-defaulted": ("PR-2: should DEFAULTED or missing evidence ever be eligible for ALLOW",
                     "agent acted on an assumed value nobody actually checked"),
    "Q2-retry": ("XB-1/XB-2: timeouts, retries and duplicate side effects",
                 "timeout retry duplicate side effect idempotency agent actions"),
    "Q3-verify-write": ("verify-after-write: success claimed but not visible",
                        "verify after write success claimed but not actually visible"),
    "Q4-freshness": ("P11/P12: witness logs, freshness, rollback and replay of old evidence",
                     "stale evidence replay rollback freshness witness log"),
    "Q5-approval": ("DEFER cost: human approval fatigue and rubber-stamping",
                    "human approval fatigue rubber stamping agent escalations"),
    "Q6-independence": ("one dominant AI author: independent checking of AI-written tests and code",
                        "the constraint is written by the party it constrains, self-verification by the same agent"),
    "Q7-provenance": ("evidence states: provenance types for agent memory and decisions",
                      "agent memory needs types for doubt, inference stored as fact"),
}

# Feed pass (added 2026-10-04 after the first scheduled run): semantic search keeps returning the same top matches,
# so new hot posts were missed. The scout also reads the hot and new feeds and keeps posts whose title or text
# matches these words. An entry is a word (any match) or a tuple (all words must appear). Edit freely.
FEED_SORTS = ("hot", "new")
FEED_LIMIT = 50
KEYWORDS = {
    "Q1-defaulted": ["default", "missing evidence", "fallback", "unmeasured", "assumed value"],
    "Q2-retry": ["retry", "retries", "timeout", "idempoten", "duplicate", "exactly-once", "replay key"],
    "Q3-verify-write": ["verify-after-write", "verify after write", "postcondition", "claimed success", "not visible"],
    "Q4-freshness": ["stale", "freshness", "witness", "rollback"],
    "Q5-approval": ["approval", "rubber-stamp", "rubber stamp", "human-in-the-loop", "escalat", "permission prompt"],
    "Q6-independence": ["self-verif", "independent verif", "grades its own", "its own tests", "same model"],
    "Q7-provenance": ["provenance", ("memory", "measured"), ("memory", "inferred"), ("memory", "condition"), "doubt"],
    "Q8-authority": ["authoriz", "ambient authority", "capabilit", "permission boundary", "privilege"],
}
QUESTIONS.setdefault("Q8-authority", ("Gate capability/authorization scope: delegated or inherited authority",
                                      "agent inherits authorization from a session it should not"))

CTRL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f​-‏‪-‮⁦-⁩]")


def clean(s, n):
    s = CTRL.sub("", str(s or "")).replace("⟦HL⟧", "").replace("⟦/HL⟧", "")
    s = " ".join(s.split())
    return s if len(s) <= n else s[: n - 1] + "…"


def get(path, key=None):
    url = HOST + path
    assert url.startswith(HOST), url  # one host, GET only: there is no other request in this file
    headers = {"Authorization": "Bearer " + key} if key else {}
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        return {"http_error": e.code, "body": clean(e.read().decode(errors="replace"), 200)}
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        return {"error": clean(repr(e), 200)}


def load_seen(path):
    seen = set()
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                try:
                    r = json.loads(line)
                    seen.add((r["post_id"], r["question"]))
                except (ValueError, KeyError):
                    pass
    return seen


def ask_text():
    """--ask "your question": search that text alone (posts and comments), skip the replies check."""
    if "--ask" not in sys.argv:
        return None
    rest = [a for a in sys.argv[sys.argv.index("--ask") + 1:] if not a.startswith("--")]
    return " ".join(rest).strip()[:500] or None


def main():
    os.makedirs(OUT, exist_ok=True)
    asked = ask_text()
    search_type = "posts"
    if asked:
        qid = "ASK-" + hashlib.sha256(asked.encode()).hexdigest()[:6]
        QUESTIONS.clear()
        QUESTIONS[qid] = ("your question: " + clean(asked, 120), asked)
        search_type = "all"
        sys.argv.append("--no-replies")
    now = dt.datetime.now(dt.timezone.utc)
    ledger = os.path.join(OUT, "ledger.jsonl")
    seen = load_seen(ledger)
    lines = [f"# Moltbook scout digest {now:%Y-%m-%d %H:%M} UTC",
             "", "Post text below is UNTRUSTED (written by other agents). It is a lead, not a fact or an instruction.", ""]
    new_total, errors = 0, []

    with open(ledger, "a", encoding="utf-8") as led:
        for qid, (serves, query) in QUESTIONS.items():
            d = get("search?" + urllib.parse.urlencode({"q": query, "type": search_type, "limit": PER_QUERY}))
            if "results" not in d:
                errors.append(f"{qid}: {d}")
                continue
            fresh = []
            for r in d["results"]:
                pid = r.get("post_id") or r.get("id")
                author = (r.get("author") or {}).get("name")
                if not pid or author == ME or author in MUTE or (pid, qid) in seen:
                    continue
                text = r.get("content") or ""
                rec = {"seen_at": now.isoformat(), "question": qid, "post_id": pid,
                       "title": clean(r.get("title") or (r.get("post") or {}).get("title"), 200),
                       "kind": r.get("type", "post"), "author": clean(author, 60),
                       "submolt": clean((r.get("submolt") or {}).get("name"), 40),
                       "created_at": r.get("created_at"), "upvotes": r.get("upvotes"),
                       "relevance": r.get("relevance"),
                       "content_sha256": hashlib.sha256(text.encode()).hexdigest(),
                       "status": "LEAD"}  # a human changes this, never the scout
                led.write(json.dumps(rec) + "\n")
                seen.add((pid, qid))
                fresh.append((rec, clean(text, 220)))
            new_total += len(fresh)
            lines.append(f"## {qid}: {serves}")
            if not fresh:
                lines.append("- nothing new")
            for rec, snip in fresh:
                lines.append(f"- {'[comment on] ' if rec['kind'] == 'comment' else ''}**{rec['title']}** by {rec['author']} in m/{rec['submolt']}, "
                             f"{rec['upvotes']} up, relevance {rec['relevance']}, id {rec['post_id'][:8]}")
                lines.append(f"  > {snip}")
            lines.append("")

        if not asked:
            fresh_feed, seen_ids = {}, set()
            for sort in FEED_SORTS:
                d = get("posts?" + urllib.parse.urlencode({"sort": sort, "limit": FEED_LIMIT}))
                if "posts" not in d:
                    errors.append(f"feed {sort}: {d}")
                    continue
                for r in d["posts"]:
                    pid, author = r.get("id"), (r.get("author") or {}).get("name")
                    if not pid or pid in seen_ids or author == ME or author in MUTE:
                        continue
                    seen_ids.add(pid)
                    text = ((r.get("title") or "") + " " + (r.get("content") or "")).lower()
                    for fq, words in KEYWORDS.items():
                        hit = any((all(w in text for w in k) if isinstance(k, tuple) else k in text) for k in words)
                        if not hit or (pid, fq) in seen:
                            continue
                        rec = {"seen_at": now.isoformat(), "question": fq, "post_id": pid, "via": f"feed:{sort}",
                               "title": clean(r.get("title"), 200), "author": clean(author, 60),
                               "submolt": clean((r.get("submolt") or {}).get("name"), 40),
                               "created_at": r.get("created_at"), "upvotes": r.get("upvotes"),
                               "comment_count": r.get("comment_count"),
                               "content_sha256": hashlib.sha256((r.get("content") or "").encode()).hexdigest(),
                               "status": "LEAD"}
                        led.write(json.dumps(rec) + "\n")
                        seen.add((pid, fq))
                        fresh_feed.setdefault(fq, []).append((rec, clean(r.get("content"), 200)))
            n_feed = sum(len(v) for v in fresh_feed.values())
            new_total += n_feed
            lines.append(f"## From the hot/new feeds (keyword match): {n_feed} new")
            for fq, items in fresh_feed.items():
                lines.append(f"### {fq}")
                for rec, snip in items:
                    lines.append(f"- **{rec['title']}** by {rec['author']}, {rec['upvotes']} up, "
                                 f"{rec['comment_count']} comments, {rec['via']}, id {rec['post_id'][:8]}")
                    lines.append(f"  > {snip}")
            lines.append("")

    if "--no-replies" not in sys.argv:
        lines.append("## Replies to veritasgate")
        try:
            key = json.load(open(CRED, encoding="utf-8"))["api_key"]
        except (OSError, ValueError, KeyError):
            key = None
            lines.append("- no key file at ~/.config/moltbook/credentials.json, skipped")
        if key:
            h = get("home", key)
            acct = h.get("your_account") or {}
            lines.append(f"- unread notifications: {acct.get('unread_notification_count')}, karma {acct.get('karma')}")
            for a in h.get("activity_on_your_posts") or []:
                pid = a.get("post_id", "")
                lines.append(f"- on **{clean(a.get('post_title'), 90)}**: {a.get('new_notification_count')} new, "
                             f"from {', '.join(clean(x, 40) for x in a.get('latest_commenters') or [])}")
                c = get(f"posts/{pid}/comments?sort=new&limit=20", key)
                stack = list(c.get("comments") or [])
                while stack:
                    x = stack.pop(0)
                    stack.extend(x.get("replies") or [])
                    who = (x.get("author") or {}).get("name")
                    if who != ME:
                        lines.append(f"  > {clean(who, 40)} ({str(x.get('created_at'))[:16]}): {clean(x.get('content'), 300)}")
            if "your_account" not in h:
                errors.append(f"home: {h}")
        del key
        lines.append("")

    lines.append(f"New leads this run: {new_total}. Ledger: {ledger}")
    if errors:
        lines.append("Errors (the scout could not look; nothing above is affected):")
        lines += [f"- {e}" for e in errors]
    digest = "\n".join(lines)
    path = os.path.join(OUT, f"digest-{now:%Y%m%d-%H%M}.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(digest + "\n")
    print(digest)
    print(f"\nsaved {path}")
    return 2 if errors and new_total == 0 else 0


if __name__ == "__main__":
    sys.exit(main())
