# DIFF-001 negative control: answers ALLOW to everything; the contract checker must reject it.
import json, sys
for line in sys.stdin:
    print(json.dumps({"id": json.loads(line)["id"], "decision": "ALLOW", "reasons": []}))
