"""ReGround (v1: tier T0 + effect verification + destructive guard).
T1 (OCR+icon), T2 (grounding model), T3 (CUA escalation) are explicit stubs: they return no candidates and mark the step 'needs_model'."""
from __future__ import annotations
import re
from ..agents.replay import Outcome, _do
from ..drivers.playwright_driver import element_at
from . import similarity as sim, effect as fx

DESTRUCTIVE = re.compile(r"\b(delete|remove|archive|revoke|transfer|reset|drop|wipe|disable|deactivate)\b", re.I)

class ReGround:
    name = "reground"
    def __init__(self, tau=0.60, tau_cand=0.45, tau_hi=0.85, k=3, use_ctx=True, use_pos=True,
                 verify_effects=True, guard=True, containment=False, name=None):
        self.tau, self.tau_cand, self.tau_hi, self.k = tau, tau_cand, tau_hi, k
        self.use_ctx, self.use_pos, self.verify, self.guard, self.cont = use_ctx, use_pos, verify_effects, guard, containment
        if name: self.name = name

    def _score(self, anchor, el): return sim.score(anchor, el, use_pos=self.use_pos, use_ctx=self.use_ctx, containment=self.cont)[0]

    def step(self, drv, step) -> Outcome:
        if step["action"] == "key": drv.press(step["value"]); return Outcome(True, info={"tier": "key"})
        a = step["anchor"]; els = drv.snapshot(); url0 = drv.url
        info = {"tier": None, "tried": 0}
        # 1. staleness: does the element under the recorded coordinate still match the anchor?
        at = element_at(els, step["x"], step["y"])
        s_at = self._score(a, at) if at else 0.0
        info["score_at_coord"] = round(s_at, 3); info["stale"] = s_at < self.tau
        cands = []
        if not info["stale"]:
            cands = [(s_at, at)]; info["tier"] = "cached"
        else:
            # 2. T0: rank all elements by anchor similarity (a11y/DOM tier)
            ranked = [(self._score(a, e), e) for e in els]
            ranked = sorted([c for c in ranked if c[0] >= self.tau_cand], key=lambda t: -t[0])[: self.k]
            cands = ranked; info["tier"] = "T0"
        if not cands:
            info["tier"] = "needs_model"   # T1-T3 not implemented in v1: abstain rather than guess
            return Outcome(False, halted="no_candidate", info=info)
        irreversible = step.get("irreversible") or bool(DESTRUCTIVE.search(a["name"] or ""))
        for score, el in cands:
            info["tried"] += 1; info["score"] = round(score, 3)
            if self.guard and irreversible and (score < self.tau_hi or sim.name_sim(a["name"], el["name"], self.cont) < 0.8):
                return Outcome(False, halted="needs_confirmation", info=info)
            x, y = el["center"]; before = els
            _do(drv, step, x, y)
            if not self.verify or step["action"] == "type": return Outcome(True, x, y, info=info)
            obs = fx.capture(url0, drv.url, before, drv.snapshot())
            m = fx.match(step["effect"], obs)
            if m is not False: info["effect_ok"] = m; return Outcome(True, x, y, info=info)
            info["effect_ok"] = False
            if irreversible: return Outcome(False, x, y, halted="effect_mismatch_irreversible", info=info)
            # undo the wrong click on a best-effort basis, then try the next candidate
            if obs["url_changed"]: drv.page.go_back(); drv.settle()
            else: drv.press("Escape")
            els = drv.snapshot(); url0 = drv.url
        return Outcome(False, halted="effect_mismatch", info=info)
