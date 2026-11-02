"""Anchor <-> element similarity. Multi-signal, renormalised over the signals that are available."""
from __future__ import annotations
import re, math
from difflib import SequenceMatcher

# Hand-written synonym groups for UI vocabulary. Measured separately (how often needed) in analysis.
SYNONYMS = [
    {"settings", "preferences", "options", "configuration"}, {"new", "create", "add"},
    {"delete", "remove"}, {"save", "update", "apply"}, {"issues", "tickets"}, {"repository", "repo", "repositories"},
    {"profile", "account"}, {"sign", "log"}, {"collaborator", "collaborators", "member", "members"},
]
_CANON = {w: sorted(g)[0] for g in SYNONYMS for w in g}
WEIGHTS = dict(role=0.10, name=0.40, ancestors=0.15, neighbours=0.15, region=0.05, pos=0.05, icon=0.10)

def toks(s: str) -> list[str]:
    return [_CANON.get(t, t) for t in re.findall(r"[a-z0-9]+", (s or "").lower())]

def name_sim(a: str, b: str) -> float:
    ta, tb = toks(a), toks(b)
    if not ta or not tb: return 0.0
    sa, sb = set(ta), set(tb)
    jac = len(sa & sb) / len(sa | sb)
    ratio = SequenceMatcher(None, " ".join(ta), " ".join(tb)).ratio()
    return max(jac, ratio * 0.9)

def jaccard(a, b) -> float:
    a, b = set(a), set(b)
    if not a and not b: return None
    return len(a & b) / len(a | b)

_ROLE_GROUP = {"link": "act", "button": "act", "menuitem": "act", "tab": "act", "option": "act"}
def role_sim(a, b):
    if a == b: return 1.0
    if _ROLE_GROUP.get(a) and _ROLE_GROUP.get(a) == _ROLE_GROUP.get(b): return 0.6
    return 0.0

def region(bbox, vw=1280, vh=1200):
    x, y, w, h = bbox; cx, cy = x + w / 2, y + h / 2
    return ("top" if cy < vh * 0.2 else "mid" if cy < vh * 0.8 else "bottom") + "-" + ("left" if cx < vw / 3 else "center" if cx < 2 * vw / 3 else "right")

def anc_tokens(anc): return [t for a in anc for t in a.split("|") if t]
def neigh_tokens(n): return [t for x in n for t in toks(x)]

def score(anchor: dict, el: dict, use_pos=True, use_ctx=True) -> tuple[float, dict]:
    """anchor/el are snapshot-element-shaped dicts. Returns (score in [0,1], per-signal breakdown)."""
    f = {"role": role_sim(anchor["role"], el["role"]), "name": name_sim(anchor["name"], el["name"])}
    if use_ctx:
        f["ancestors"] = jaccard(anc_tokens(anchor["anc"]), anc_tokens(el["anc"]))
        f["neighbours"] = jaccard(neigh_tokens(anchor["neighbours"]), neigh_tokens(el["neighbours"]))
        f["region"] = 1.0 if region(anchor["bbox"]) == region(el["bbox"]) else 0.0
    if use_pos:
        d = math.dist(anchor["center"], el["center"]); f["pos"] = max(0.0, 1 - d / 400)
    used = {k: v for k, v in f.items() if v is not None}
    tw = sum(WEIGHTS[k] for k in used)
    return sum(WEIGHTS[k] * v for k, v in used.items()) / tw, f

def rank(anchor, els, **kw):
    sc = [(score(anchor, e, **kw)[0], e) for e in els]
    sc.sort(key=lambda t: -t[0]); return sc
