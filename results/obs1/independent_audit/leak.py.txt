import sys, json, tempfile, os
sys.path.insert(0, "/root/sv/tools"); sys.path.insert(0, "/root/sv"); sys.dont_write_bytecode = True
from obs1_store import Store, StoreClient
from obs1_compare import compare
d = tempfile.mkdtemp()
s = Store(os.path.join(d,"s"), {"record_id":"r1","value":"off","version":0}); c = StoreClient(s)
print("client.read.__self__ is the Store:", c.read.__self__ is s, "-> can see _fault/_held/release_at_end:", hasattr(c.read.__self__, "release_at_end"))
s.configure_fault("fail_record_after_effect", "t1"); print("fail_record_after_effect set_value ->", c.set_value("r1","on","t1"), "(no fault effect in store; system has no branch for it)")
s.configure_fault("bogus_fault", "t2"); print("unknown fault accepted silently:", c.set_value("r1","on","t2"))
# fence-claim limit: attempt 2 does not write, claims fence of t1; fence actually issued later by attempt 3
case = {"case_id":"X","intent":{"new_value":"on"}}
ev = [{"seq":1,"event":"write","record_id":"r1","version":1,"value":"on","attempt_token":"t1"},
      {"seq":2,"event":"read","record_id":"r1","result":"ok","attempt_token":"t2"},
      {"seq":3,"event":"fence","target_token":"t1","attempt_token":"t3"}]
h = {"tokens":["t1","t2","t3"],"in_force":{t:{"write":True,"fence":True} for t in ["t1","t2","t3"]},"release":None}
rep = [{"attempt":1,"permission_at_execution":"GRANTED","decision":"ALLOW","system_status":"UNKNOWN"},
       {"attempt":2,"permission_at_execution":"GRANTED","decision":"ALLOW","system_status":"ALREADY_COMPLETED",
        "reconciliation":{"fenced_tokens":["t1"],"observed_at_seq":2,"observed_writes_by_fenced":1,"by":"system"}},
       {"attempt":3,"permission_at_execution":"GRANTED","decision":"DEFER","system_status":"HELD"}]
r = compare(case, h, {"value":"off","version":0,"writes":0,"events":[]}, {"value":"on","version":1,"writes":1,"events":ev}, rep)
print("attempt-2 claims a fence that only attempt 3 made after attempt 2 reported -> mismatches:", r["status_mismatches"], r["mismatch_detail"])
rep[2]["permission_at_execution"]="NOT_READ"; print("NOT_READ:", compare(case,h,{"value":"off","version":0,"writes":0,"events":[]},{"value":"on","version":1,"writes":1,"events":ev},rep)["mismatch_detail"])
