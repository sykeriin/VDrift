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
    """Classic test-automation floor: CSS selector from id/href/name, else attribute/text lookup; scoped to the form last acted in
    (what a page-object script does) and to an open dialog. Fails hard when nothing matches."""
    name = "selector_replay"
    MARK = "data-vd-lastform"

    @staticmethod
    def _pat(name, exact=True):
        import re
        body = r"\s+".join(re.escape(w) for w in name.split()[:None if exact else 3])
        return re.compile((r"^\s*" + body + r"\s*$") if exact else body, 0 if exact else re.I)

    def _find(self, root, step):
        s = step["selector"]; nm = s["name"]; tag = step["anchor"]["tag"]
        if s["css"]:
            l = root.locator(s["css"]).locator("visible=true")
            if l.count() > 1 and nm:
                ln = l.filter(has_text=self._pat(nm))
                if ln.count() == 0: ln = l.filter(has_text=self._pat(nm, exact=False))
                if ln.count() == 0:
                    esc = nm.replace('"', '\\"')
                    ln = root.locator(f'{s["css"]}[placeholder="{esc}"],{s["css"]}[aria-label="{esc}"]').locator("visible=true")
                if ln.count() >= 1: l = ln
            if l.count() >= 1: return l.first
        if nm:
            esc = nm.replace('"', '\\"')   # attribute carrying the accessible name
            l = root.locator(f'[aria-label="{esc}"],[title="{esc}"],[data-tooltip-content="{esc}"],[placeholder="{esc}"]').locator("visible=true")
            if l.count() >= 1: return l.first
            l = root.locator(tag).filter(has_text=self._pat(nm)).locator("visible=true")   # same tag + exact visible text
            if l.count() >= 1: return l.last if tag in ("button", "div") else l.first
        return None

    def step(self, drv, step):
        if step["action"] == "key": return _key(drv, step)
        p = drv.page
        if step["idx"] == 0: p.evaluate(f"document.querySelectorAll('[{self.MARK}]').forEach(e => e.removeAttribute('{self.MARK}'))")
        roots = []
        modal = p.locator(".modal, [role=dialog]").locator("visible=true")
        if modal.count() >= 1: roots.append(modal.last)
        if p.locator(f"[{self.MARK}]").count() >= 1: roots.append(p.locator(f"[{self.MARK}]").first)
        roots.append(p)
        loc = None
        for root in roots:
            loc = self._find(root, step)
            if loc is not None: break
        if loc is None: return Outcome(False, halted="selector_not_found")
        bb = loc.bounding_box(); x, y = bb["x"] + bb["width"] / 2, bb["y"] + bb["height"] / 2
        p.evaluate(f"""([x, y]) => {{ document.querySelectorAll('[{self.MARK}]').forEach(e => e.removeAttribute('{self.MARK}'));
            const f = document.elementFromPoint(x, y)?.closest('form'); if (f) f.setAttribute('{self.MARK}', '1'); }}""", [x, y])
        _do(drv, step, x, y); return Outcome(True, x, y)

# Similo-style: weighted multi-attribute similarity over DOM attributes, no semantic role/context, no effect check.
_SIMILO_W = dict(tag=1.5, id=1.5, name=1.5, type=0.5, href=1.5, cls=0.5, text=1.5, placeholder=1.0, xy=0.5)
_ATTR_KEYS = ("id", "name", "type", "href", "cls", "placeholder")
def similo_score(a, e, use_attrs=True):
    aa, ea = a["attrs"], e["attrs"]
    f = {"tag": 1.0 if a["tag"] == e["tag"] else 0.0,
         "text": jaccard(toks(a["text"]), toks(e["text"]))}
    for k, src in (("id", "id"), ("name", "name"), ("type", "type"), ("href", "href"), ("placeholder", "placeholder")):
        if aa.get(src) or ea.get(src): f[k] = 1.0 if aa.get(src) == ea.get(src) else 0.0
    f["cls"] = jaccard(aa.get("class", "").split(), ea.get("class", "").split())
    f["xy"] = max(0.0, 1 - math.dist(a["center"], e["center"]) / 400)
    used = {k: v for k, v in f.items() if v is not None and (use_attrs or k not in _ATTR_KEYS)}
    return sum(_SIMILO_W[k] * v for k, v in used.items()) / sum(_SIMILO_W[k] for k in used)

class SimiloReplay:
    """Similo (Nass et al.) style locator: always re-locate the best-matching element, act without verification."""
    name = "similo_replay"
    def __init__(self, use_attrs=True, name=None):
        self.use_attrs = use_attrs
        if name: self.name = name
    def step(self, drv, step):
        if step["action"] == "key": return _key(drv, step)
        els = drv.snapshot()
        if not els: return Outcome(False, halted="empty_page")
        sc = sorted(((similo_score(step["anchor"], e, self.use_attrs), e) for e in els), key=lambda t: -t[0])
        best, e = sc[0]
        x, y = e["center"]; _do(drv, step, x, y); return Outcome(True, x, y, info={"score": best})
