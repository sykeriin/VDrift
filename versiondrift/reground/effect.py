"""Post-action effect signature and approximate matching."""
from __future__ import annotations
from urllib.parse import urlparse
from .similarity import name_sim

def _names(els): return {e["name"].strip().lower() for e in els if e["name"].strip() and not e["name"].strip().isdigit()}

def capture(url_before, url_after, els_before, els_after) -> dict:
    pb, pa = urlparse(url_before).path, urlparse(url_after).path
    nb, na = _names(els_before), _names(els_after)
    return {"url_changed": pb != pa, "path": pa, "appeared": sorted(na - nb)[:10], "disappeared": sorted(nb - na)[:10]}

def _seg_overlap(a, b):
    sa, sb = set(filter(None, a.split("/"))), set(filter(None, b.split("/")))
    return len(sa & sb) / len(sa | sb) if sa | sb else 1.0

def match(stored: dict, observed: dict):
    """True / False / None (None = stored effect carries no checkable signal)."""
    if stored["url_changed"]:
        return observed["url_changed"] and _seg_overlap(stored["path"], observed["path"]) >= 0.5
    if stored["appeared"]:
        hits = sum(1 for s in stored["appeared"] if any(name_sim(s, o) >= 0.7 for o in observed["appeared"]))
        return hits / len(stored["appeared"]) >= 0.4
    return None
