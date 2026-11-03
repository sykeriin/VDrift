"""Replay baselines. Each agent executes one recorded step on the live page and returns an Outcome."""
from __future__ import annotations
import math
from dataclasses import dataclass, field
from ..drivers.playwright_driver import element_at
from ..reground.similarity import toks, jaccard, role_sim

@dataclass
class Outcome:
    ok: bool                  # step executed (no error / no halt)
    x: float | None = None
    y: float | None = None
    halted: str | None = None  # reason when the agent stops the run (e.g. needs_confirmation, not_found)
    info: dict = field(default_factory=dict)

def _do(drv, step, x, y):
    if step["action"] == "key": drv.press(step["value"])
    elif step["action"] == "click": drv.click(x, y)
    else: drv.type_at(x, y, step["value"])

def _key(drv, step):
    drv.press(step["value"]); return Outcome(True)

class CoordReplay:
    """RPA floor: replay recorded pixel coordinates."""
    name = "coord_replay"
    def step(self, drv, step):
        if step["action"] == "key": return _key(drv, step)
        _do(drv, step, step["x"], step["y"]); return Outcome(True, step["x"], step["y"])

class SelectorReplay:
    """Classic test-automation floor: CSS selector from id/href/name, else role+name. Fails hard when nothing matches."""
    name = "selector_replay"
    def step(self, drv, step):
        if step["action"] == "key": return _key(drv, step)
        s = step["selector"]; p = drv.page
        loc = None
        if s["css"]:
            l = p.locator(s["css"]).locator("visible=true")
            if l.count() > 1:   # ambiguous selector: scope to an open dialog if any, then narrow by visible text
                import re
                modal = p.locator(".modal, [role=dialog]").locator("visible=true")
                if modal.count() >= 1:
                    lm = modal.last.locator(s["css"]).locator("visible=true")
                    if lm.count() >= 1: l = lm
                if l.count() > 1 and s["name"]:
                    pat = re.compile(r"^\s*" + r"\s+".join(re.escape(w) for w in s["name"].split()) + r"\s*$")
                    ln = l.filter(has_text=pat)
                    if ln.count() == 0: ln = l.filter(has_text=re.compile(r"\s+".join(re.escape(w) for w in s["name"].split()[:6]), re.I))
                    if ln.count() >= 1: l = ln
                    else:   # inputs carry their name in placeholder/aria-label rather than text
                        esc = s["name"].replace('"', '\\"')
                        la = p.locator(f'{s["css"]}[placeholder="{esc}"],{s["css"]}[aria-label="{esc}"]').locator("visible=true")
                        if la.count() >= 1: l = la
            if l.count() >= 1: loc = l.first
        if loc is None and s["name"]:
            import re
            nm = s["name"]
            # fallback 1: attribute carrying the accessible name (aria-label / title / tooltip / placeholder)
            esc = nm.replace('"', '\\"')
            l = p.locator(f'[aria-label="{esc}"],[title="{esc}"],[data-tooltip-content="{esc}"],[placeholder="{esc}"]').locator("visible=true")
            if l.count() >= 1: loc = l.first
            else:   # fallback 2: same tag + exact visible text, whitespace-insensitive (what a hand-written test script would do)
                pat = re.compile(r"^\s*" + r"\s+".join(re.escape(w) for w in nm.split()) + r"\s*$")
                l = p.locator(step["anchor"]["tag"]).filter(has_text=pat).locator("visible=true")
                if l.count() >= 1: loc = l.last if step["anchor"]["tag"] in ("button", "div") else l.first
        if loc is None: return Outcome(False, halted="selector_not_found")
        bb = loc.bounding_box(); x, y = bb["x"] + bb["width"] / 2, bb["y"] + bb["height"] / 2
        _do(drv, step, x, y); return Outcome(True, x, y)

# Similo-style: weighted multi-attribute similarity over DOM attributes, no semantic role/context, no effect check.
_SIMILO_W = dict(tag=1.5, id=1.5, name=1.5, type=0.5, href=1.5, cls=0.5, text=1.5, placeholder=1.0, xy=0.5)
def similo_score(a, e):
    aa, ea = a["attrs"], e["attrs"]
    f = {"tag": 1.0 if a["tag"] == e["tag"] else 0.0,
         "text": jaccard(toks(a["text"]), toks(e["text"]))}
    for k, src in (("id", "id"), ("name", "name"), ("type", "type"), ("href", "href"), ("placeholder", "placeholder")):
        if aa.get(src) or ea.get(src): f[k] = 1.0 if aa.get(src) == ea.get(src) else 0.0
    f["cls"] = jaccard(aa.get("class", "").split(), ea.get("class", "").split())
    f["xy"] = max(0.0, 1 - math.dist(a["center"], e["center"]) / 400)
    used = {k: v for k, v in f.items() if v is not None}
    return sum(_SIMILO_W[k] * v for k, v in used.items()) / sum(_SIMILO_W[k] for k in used)

class SimiloReplay:
    """Similo (Nass et al.) style locator: always re-locate the best-matching element, act without verification."""
    name = "similo_replay"
    def step(self, drv, step):
        if step["action"] == "key": return _key(drv, step)
        els = drv.snapshot()
        if not els: return Outcome(False, halted="empty_page")
        sc = sorted(((similo_score(step["anchor"], e), e) for e in els), key=lambda t: -t[0])
        best, e = sc[0]
        x, y = e["center"]; _do(drv, step, x, y); return Outcome(True, x, y, info={"score": best})
