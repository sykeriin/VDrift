"""Run replay conditions for one version pair. Usage: run_cli vA vB agents out.json [slot] [--aa]"""
import sys, json
from pathlib import Path
from ..envs.gitea import GiteaEnv
from ..drivers.playwright_driver import Driver
from ..tasks_gitea import TASKS
from ..agents.replay import CoordReplay, SelectorReplay, SimiloReplay
from ..reground.middleware import ReGround
from . import trajectory as tj, runner

AGENTS = {"coord": CoordReplay, "selector": SelectorReplay, "similo": SimiloReplay,
          "reground": lambda: ReGround(name="reground"),
          "reground_noguard": lambda: ReGround(name="reground_noguard", guard=False),
          "reground_noverify": lambda: ReGround(name="reground_noverify", verify_effects=False),
          "reground_noctx": lambda: ReGround(name="reground_noctx", use_ctx=False)}

def main(vA, vB, agents, out, slot=0, aa=False):
    drv = Driver(); envs = {vA: GiteaEnv(vA, slot=slot), vB: GiteaEnv(vB, slot=slot)}
    results = []
    plan = ([(vA, vA)] if aa else []) + [(vB, vA)]       # (run-on, trajectory-from)
    for name in agents:
        agent = AGENTS[name]()
        for run_v, src_v in plan:
            env = envs[run_v]
            for t in TASKS:
                traj = tj.load(t.id, src_v); gt = tj.load(t.id, run_v)
                r = runner.run_one(env, drv, t, run_v, agent, traj, gt)
                r["source_version"] = src_v; r["pair"] = f"{src_v}->{run_v}"; results.append(r)
                print(f"{name:18} {src_v}->{run_v} {t.id:18} {'PASS' if r['success'] else 'FAIL'} {r['halted'] or ''}", flush=True)
        Path(out).parent.mkdir(parents=True, exist_ok=True); Path(out).write_text(json.dumps(results, indent=1))  # incremental save
    for e in envs.values(): e.stop()
    drv.close()

if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    main(a[0], a[1], a[2].split(","), a[3], int(a[4]) if len(a) > 4 else 0, "--aa" in sys.argv)
