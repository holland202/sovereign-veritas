"""EO-2 P9: property tests for sovereign_veritas/effect_observation.py, written from the verdict rules in
docs/EO2_PREREG.md (and Amendment 1), on seeded random states, actions and decisions. No answer key."""
import random

from sovereign_veritas import effect_observation as eo

KEYS = ["V1", "V2", "V3"]
VALUES = ["open", "closed", "half"]
SEEDS = range(400)


def rand_state(rng):
    return {k: rng.choice(VALUES) for k in KEYS if rng.random() < 0.8}


def case(seed):
    rng = random.Random(seed)
    action = {"capability": "valve", "requested": rng.choice(["open_valve", "close_valve", "x"]),
              "parameters": {"target": rng.choice(KEYS)}}
    decision = rng.choice(["ALLOW", "REFUSE", "DEFER"])
    status = rng.choice(["SUCCEEDED", "FAILED", "UNKNOWN"]) if decision == "ALLOW" else None
    record = {"record_id": f"r{seed}", "action": action, "decision": decision,
              "metadata": {} if status is None else {"execution_status": status}}
    before = rand_state(rng)
    expected = {rng.choice(KEYS): rng.choice(VALUES)} if rng.random() < 0.9 else None
    u = rng.random()
    if u < 0.3:
        after = dict(before)
    elif u < 0.6 and expected:  # the expected effect and nothing else (first draft never generated this: no OK case)
        after = dict(before, **expected)
    else:
        after = rand_state(rng)
    return rng, record, before, after, expected


def test_missing_observation_is_never_ok():
    for s in SEEDS:
        _, rec, _, _, exp = case(s)
        assert eo.check_observed_effect(rec, None, exp) == eo.NO_OBSERVATION


def test_binding_mismatch_whatever_the_states():
    for s in SEEDS:
        rng, rec, b, a, exp = case(s)
        obs = eo.make_observation(rec["record_id"] + "x", rec["action"], b, a)
        assert eo.check_observed_effect(rec, obs, exp) == eo.BINDING_MISMATCH
        other = dict(rec["action"], requested=rec["action"]["requested"] + "!")
        obs = eo.make_observation(rec["record_id"], other, b, a)
        assert eo.check_observed_effect(rec, obs, exp) == eo.BINDING_MISMATCH
        # unbound: the same observation is judged on its states, never as a binding mismatch
        assert eo.check_observed_effect(rec, obs, exp, bind=False) != eo.BINDING_MISMATCH


def test_not_allowed_means_no_change():
    for s in SEEDS:
        _, rec, b, a, exp = case(s)
        if rec["decision"] == "ALLOW":
            continue
        v = eo.check_observed_effect(rec, eo.make_observation(rec["record_id"], rec["action"], b, a), exp)
        assert v == (eo.OK if b == a else eo.UNAUTHORIZED_EFFECT)


def test_allow_not_succeeded():
    for s in SEEDS:
        _, rec, b, a, exp = case(s)
        if rec["decision"] != "ALLOW" or rec["metadata"]["execution_status"] == "SUCCEEDED":
            continue
        v = eo.check_observed_effect(rec, eo.make_observation(rec["record_id"], rec["action"], b, a), exp)
        assert v == (eo.OK if b == a else eo.EFFECT_DESPITE_FAILURE)


def test_allow_succeeded_rules():
    seen = set()
    for s in SEEDS:
        _, rec, b, a, exp = case(s)
        if rec["decision"] != "ALLOW" or rec["metadata"]["execution_status"] != "SUCCEEDED":
            continue
        obs = eo.make_observation(rec["record_id"], rec["action"], b, a)
        strict = eo.check_observed_effect(rec, obs, exp)
        loose = eo.check_observed_effect(rec, obs, exp, strict=False)
        changed = {k for k in set(b) | set(a) if b.get(k, None) != a.get(k, None) or (k in b) != (k in a)}
        if not exp:
            want = eo.WRONG_EFFECT if changed else eo.NO_EFFECT
            assert strict == loose == want
        elif all(k in b and b[k] == v for k, v in exp.items()):
            assert loose == eo.UNOBSERVABLE
            assert strict == (eo.WRONG_EFFECT if changed else eo.UNOBSERVABLE)
        elif not changed:
            assert strict == loose == eo.NO_EFFECT
        elif all(k in a and a[k] == v for k, v in exp.items()) and changed <= set(exp):
            assert strict == loose == eo.OK
        else:
            assert strict == loose == eo.WRONG_EFFECT
        seen.add(strict)
    # coverage: every ALLOW/SUCCEEDED verdict was reached by some seed
    assert {eo.OK, eo.NO_EFFECT, eo.WRONG_EFFECT, eo.UNOBSERVABLE} <= seen


def test_digest_is_canonical():
    a = {"capability": "c", "requested": "r", "parameters": {"x": 1, "y": 2}}
    b = {"parameters": {"y": 2, "x": 1}, "requested": "r", "capability": "c"}
    assert eo.action_digest(a) == eo.action_digest(b)
    assert eo.action_digest(a) != eo.action_digest(dict(a, requested="s"))
