"""Run replay conditions for one version pair. Usage: run_cli [--app gitea] vA vB agents out.json [slot] [--aa]"""
import sys, json
from pathlib import Path
from .. import apps
from ..drivers.playwright_driver import Driver
from ..agents.replay import CoordReplay, SelectorReplay, SimiloReplay
from ..reground.middleware import ReGround
from . import trajectory as tj, runner

AGENTS = {"coord": CoordReplay, "selector": SelectorReplay, "similo": SimiloReplay, "similo_noattr": lambda: SimiloReplay(use_attrs=False, name="similo_noattr"),
          "reground": lambda: ReGround(name="reground"),
          "reground_noguard": lambda: ReGround(name="reground_noguard", guard=False),
          "reground_noverify": lambda: ReGround(name="reground_noverify", verify_effects=False),
          "reground_cont": lambda: ReGround(name="reground_cont", containment=True),
          "reground_cont_t50": lambda: ReGround(name="reground_cont_t50", containment=True, tau=0.50),
          "reground_cont_t70": lambda: ReGround(name="reground_cont_t70", containment=True, tau=0.70),
          "reground_off": lambda: ReGround(name="reground_off", offset=True),
          "reground_noguard_off": lambda: ReGround(name="reground_noguard_off", offset=True, guard=False),
          "reground_cont_off": lambda: ReGround(name="reground_cont_off", offset=True, containment=True),
          "similo_off": lambda: SimiloReplay(name="similo_off", offset=True),
          "similo_noattr_off": lambda: SimiloReplay(use_attrs=False, name="similo_noattr_off", offset=True),
          "reground_noctx": lambda: ReGround(name="reground_noctx", use_ctx=False)}

def main(vA, vB, agents, out, slot=0, aa=False, app="gitea"):
    Env, TASKS = apps.get(app)
    drv = Driver(); envs = {vA: Env(vA, slot=slot), vB: Env(vB, slot=slot)}
    results = []
    plan = ([(vA, vA)] if aa else []) + [(vB, vA)]       # (run-on, trajectory-from)
    for name in agents:
        agent = AGENTS[name]()
        for run_v, src_v in plan:
            env = envs[run_v]
            for t in TASKS:
                traj = tj.load(t.id, src_v, app); gt = tj.load(t.id, run_v, app)
                r = runner.run_one(env, drv, t, run_v, agent, traj, gt)
                r["source_version"] = src_v; r["pair"] = f"{src_v}->{run_v}"; r["app"] = app; results.append(r)
                print(f"{name:18} {src_v}->{run_v} {t.id:18} {'PASS' if r['success'] else 'FAIL'} {r['halted'] or ''}", flush=True)
        Path(out).parent.mkdir(parents=True, exist_ok=True); Path(out).write_text(json.dumps(results, indent=1))  # incremental save
    for e in envs.values(): e.stop()
    drv.close()

if __name__ == "__main__":
    argv = sys.argv[1:]; app = "gitea"
    if argv and argv[0] == "--app": app = argv[1]; argv = argv[2:]
    a = [x for x in argv if not x.startswith("--")]
    main(a[0], a[1], a[2].split(","), a[3], int(a[4]) if len(a) > 4 else 0, "--aa" in argv, app)
