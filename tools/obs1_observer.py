#!/usr/bin/env python3
"""OBS-1 observer (docs/OBS1_INTERFACE.md, "The observer (read-only)").

A separate program. Standard library only; imports nothing from this repository and shares no memory with the
system under test. It opens the store's files read-only and has no call into the store, so it adds no events.

  python tools/obs1_observer.py STORE_DIR RECORD_ID   ->  one JSON object on stdout
"""
import json
import os
import sys


def observe(store_dir, record_id):
    with open(os.path.join(store_dir, "record.json"), "r", encoding="utf-8") as fh:
        record = json.load(fh)
    with open(os.path.join(store_dir, "log.jsonl"), "r", encoding="utf-8") as fh:
        events = [json.loads(line) for line in fh if line.strip()]
    events.sort(key=lambda e: e["seq"])
    writes = sum(1 for e in events if e.get("event") == "write" and e.get("record_id") == record_id)
    return {"value": record["value"], "version": record["version"], "writes": writes, "events": events}


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__.strip().splitlines()[-1])
        sys.exit(2)
    print(json.dumps(observe(sys.argv[1], sys.argv[2]), sort_keys=True))
