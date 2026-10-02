"""Output parsers for the evidence bench — hardened (fail-closed) and legacy.

Defect found 2026-10-02 (container, before any S25 run): the v0/A2 parsers matched label
words as substrings, so they FAILED OPEN:

    legacy parse("UNSUPPORTED")       -> "SUPPORTED"      (a refusal read as an acceptance)
    legacy parse_stance("UNTRUE")     -> "TRUE"
    legacy parse_stance("NOT TRUE")   -> "TRUE"

None of the 608 outputs recorded in v0/A1/A2 contained such a string (every output was a
single clean label word), so no published number changes; tests/test_parsers.py proves
hardened == legacy on every recorded output. The hardened parsers are used for every run
from H1 on.

Hardened rules:
  * labels are matched as whole words only (UNSUPPORTED, UNTRUE match nothing);
  * a label preceded by a negation (NOT, NO, NEVER, DOES NOT ...) makes the output INVALID,
    except the dedicated phrase NOT SUPPORTED, which is the label NOT_SUPPORTED;
  * zero labels, or more than one distinct label, -> INVALID.
INVALID is never SUPPORTED/TRUE: in the direct arm it scores as wrong, in the gate it counts
as NEITHER. Both fail toward denial.
"""
import re

VERDICTS = ("SUPPORTED", "REFUTED", "NOT_SUPPORTED")
STANCES = ("TRUE", "FALSE", "NEITHER")

_NEG = r"(?:NOT|NO|NEVER|ISN'T|ISNT|DOESN'T|DOESNT|CANNOT|CAN'T)"


def _norm(text):
    t = (text or "").upper()
    t = t.replace("’", "'")
    # the one negated phrase that IS a label
    t = re.sub(r"\bNOT[\s\-_]+SUPPORTED\b", "NOT_SUPPORTED", t)
    return t


def _labels(t, vocab):
    found = set()
    for lab in vocab:
        for m in re.finditer(r"(?<![A-Z_])" + re.escape(lab) + r"(?![A-Z_])", t):
            before = t[:m.start()].rstrip()
            # negation immediately before the label (up to 2 words back) -> ambiguous
            if re.search(r"\b" + _NEG + r"(?:\s+\w+)?$", before):
                return None
            found.add(lab)
    return found


def parse(text):
    """Direct-arm verdict parser (hardened)."""
    found = _labels(_norm(text), VERDICTS)
    if not found or len(found) != 1:
        return "INVALID"
    return found.pop()


A3_MAP = {"CONFIRMS": "TRUE", "CONFIRM": "TRUE", "CONTRADICTS": "FALSE", "CONTRADICT": "FALSE",
          "NEITHER": "NEITHER"}


def parse_stance(text, vocab="a2"):
    """Decomposed-arm stance parser (hardened). vocab a2: TRUE/FALSE/NEITHER;
    vocab a3: CONFIRMS/CONTRADICTS/NEITHER, mapped to TRUE/FALSE/NEITHER for the gate."""
    t = _norm(text)
    if vocab == "a2":
        found = _labels(t, STANCES)
        if not found or len(found) != 1:
            return "INVALID"
        return found.pop()
    if vocab == "a3":
        found = _labels(t, tuple(A3_MAP))
        if not found:
            return "INVALID"
        mapped = {A3_MAP[f] for f in found}
        return mapped.pop() if len(mapped) == 1 else "INVALID"
    raise ValueError(vocab)


# ---- legacy parsers, verbatim behaviour of v0/A1/A2 (kept to reproduce recorded runs) ----

def parse_legacy(text):
    t = text.upper().replace("NOT SUPPORTED", "NOT_SUPPORTED").replace("NOT-SUPPORTED", "NOT_SUPPORTED")
    found = set()
    if "NOT_SUPPORTED" in t:
        found.add("NOT_SUPPORTED")
        t = t.replace("NOT_SUPPORTED", " ")
    for lab in ("SUPPORTED", "REFUTED"):
        if lab in t:
            found.add(lab)
    return found.pop() if len(found) == 1 else "INVALID"


def parse_stance_legacy(text):
    t = text.upper()
    found = {w for w in ("TRUE", "FALSE", "NEITHER") if w in t}
    return found.pop() if len(found) == 1 else "INVALID"
