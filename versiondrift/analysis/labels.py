"""Automatic change-type labels from two reference trajectories (same task recorded on versions A and B).
Per step: cosmetic < relocation < rename < workflow_restructure. Task label = worst step.
feature_removed cannot be derived this way (the task would not be solvable on B): such tasks are labelled by hand when found."""
from __future__ import annotations
import math
from ..reground.similarity import name_sim

ORDER = ["cosmetic", "relocation", "rename", "workflow_restructure"]
MOVE_PX = 24.0   # centre shift above this = relocation (below = same place)

def _dest(path: str) -> str:
    segs = [s for s in path.split("/") if s]
    return segs[-1] if segs else ""

def label_step(a: dict, b: dict) -> str:
    if a["anchor"] is None or b["anchor"] is None: return "cosmetic"   # key presses have no element to drift
    ea, eb = a["effect"], b["effect"]
    # the action no longer leads to the same kind of place: a different workflow, not a different look
    if ea["url_changed"] != eb["url_changed"]: return "workflow_restructure"
    if ea["url_changed"] and name_sim(_dest(ea["path"]).replace("-", " "), _dest(eb["path"]).replace("-", " ")) < 0.7 \
            and _dest(ea["path"]) != _dest(eb["path"]):
        return "workflow_restructure"
    if name_sim(a["anchor"]["name"], b["anchor"]["name"]) < 0.8 and a["anchor"]["name"] != b["anchor"]["name"]:
        return "rename"
    if math.dist(a["anchor"]["center"], b["anchor"]["center"]) > MOVE_PX: return "relocation"
    return "cosmetic"

def label_task(traj_a: dict, traj_b: dict) -> dict:
    if len(traj_a["steps"]) != len(traj_b["steps"]):
        return {"label": "workflow_restructure", "steps": [], "reason": "different number of steps"}
    steps = [label_step(a, b) for a, b in zip(traj_a["steps"], traj_b["steps"])]
    return {"label": max(steps, key=ORDER.index), "steps": steps}
