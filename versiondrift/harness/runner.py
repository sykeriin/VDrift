from __future__ import annotations
import json, time
from pathlib import Path
from . import trajectory as tj

def point_in(bbox, x, y):
    bx, by, bw, bh = bbox; return bx <= x <= bx + bw and by <= y <= by + bh

def run_one(env, drv, task, version, agent, traj, gt=None, max_steps=None):
    """Replay `traj` (recorded on another version) on `version` with `agent`. gt = demonstration recorded ON `version` (for step-level truth)."""
    env.reset(); task.setup(env)
    drv.new_session(task.viewport); drv.login(env); drv.goto(env.url + task.start)
    t0 = time.time(); rows = []; halted = None
    for st in traj["steps"]:
        try: out = agent.step(drv, st)
        except Exception as e: rows.append({"idx": st["idx"], "error": f"{type(e).__name__}: {str(e)[:100]}"}); halted = "exception"; break
        row = {"idx": st["idx"], "ok": out.ok, "halted": out.halted, **out.info}
        if gt and out.x is not None and gt["steps"][st["idx"]]["anchor"]: row["hit"] = point_in(gt["steps"][st["idx"]]["anchor"]["bbox"], out.x, out.y)
        if gt and gt["steps"][st["idx"]]["anchor"] and st["x"] is not None:   # ground truth staleness: recorded coordinate no longer lands on the target element
            row["truly_stale"] = not point_in(gt["steps"][st["idx"]]["anchor"]["bbox"], st["x"], st["y"])
        rows.append(row)
        if not out.ok: halted = out.halted; break
    success = bool(task.check(env)) if halted is None else False
    # a run that halted but whose check still passes (e.g. nothing was needed) counts as the check says
    if halted is not None: success = bool(task.check(env))
    return {"task": task.id, "version": version, "agent": agent.name, "success": success, "halted": halted,
            "seconds": round(time.time() - t0, 2), "steps": rows}
