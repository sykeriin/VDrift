"""Demonstration: execute a task's reference script on one version and record what a CUA would have seen."""
from __future__ import annotations
import json, re, time
from pathlib import Path
from ..drivers.playwright_driver import element_at
from ..reground import effect as fx

TRAJ_DIR = Path("/home/user/versiondrift/data/trajectories")

def resolve(page, tgt):
    if "label" in tgt: loc = page.get_by_label(tgt["label"])
    else:
        loc = page.locator(tgt["sel"])
        if tgt.get("text"): loc = loc.filter(has_text=re.compile(rf"^\s*{re.escape(tgt['text'])}", re.I))
    loc = loc.locator("visible=true")
    n = loc.count()
    if n == 0: raise LookupError(f"no visible element for {tgt}")
    return loc.nth(min(tgt.get("nth", 0), n - 1))

def make_selector(el):
    a = el["attrs"]
    if a.get("id"): css = "#" + a["id"]
    elif a.get("href") and el["tag"] == "a": css = f'a[href="{a["href"]}"]'
    elif a.get("name") and el["tag"] in ("input", "textarea", "select"): css = f'{el["tag"]}[name="{a["name"]}"]'
    else: css = None
    return {"css": css, "role": el["role"], "name": el["name"]}

def demonstrate(env, drv, task, version, shots_dir=None):
    env.reset(); task.setup(env)
    drv.new_session(task.viewport); drv.login(env); drv.goto(env.url + task.start)
    steps = []
    for i, st in enumerate(task.steps):
        if st.action == "key":   # keyboard press on the focused element: no pixel target, no anchor
            els = drv.snapshot(); url0 = drv.url; drv.press(st.value)
            steps.append({"idx": i, "intent": st.intent, "action": "key", "value": st.value, "x": None, "y": None,
                          "irreversible": st.irreversible, "anchor": None, "selector": None,
                          "effect": fx.capture(url0, drv.url, els, drv.snapshot())})
            continue
        tgt = st.by_version.get(version, st.target)
        loc = resolve(drv.page, tgt)
        bb = loc.bounding_box()
        cx, cy = bb["x"] + bb["width"] / 2, bb["y"] + bb["height"] / 2
        els = drv.snapshot(); url0 = drv.url
        if shots_dir == "debug": drv.screenshot(f"/tmp/claude-0/-home-user/38af1ac1-3fc8-52d3-a00e-a6d303e17e7d/scratchpad/dbg_{version}_{task.id}_{i}.png")
        el = element_at(els, cx, cy)
        if el is None: raise LookupError(f"step {i} ({st.intent}): no snapshot element at ({cx:.0f},{cy:.0f})")
        if shots_dir: drv.screenshot(str(Path(shots_dir) / f"{task.id}_{i}.png"))
        (drv.click(cx, cy) if st.action == "click" else drv.type_at(cx, cy, st.value))
        els1 = drv.snapshot()
        steps.append({"idx": i, "intent": st.intent, "action": st.action, "value": st.value, "x": cx, "y": cy,
                      "irreversible": st.irreversible, "anchor": el, "selector": make_selector(el),
                      "effect": fx.capture(url0, drv.url, els, els1)})
    ok = bool(task.check(env))
    return {"task": task.id, "version": version, "check_passed": ok, "steps": steps}

def save(traj, app="gitea"):
    d = TRAJ_DIR / app / traj["version"]; d.mkdir(parents=True, exist_ok=True)
    (d / f"{traj['task']}.json").write_text(json.dumps(traj, indent=1))

def load(task_id, version, app="gitea"):
    return json.loads((TRAJ_DIR / app / version / f"{task_id}.json").read_text())
