import sys, os, json, itertools
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

def main(vA, vB, agents, out):
    drv = Driver(); envA, envB = GiteaEnv(vA), GiteaEnv(vB)
    results = []
    for name in agents:
        agent = AGENTS[name]()
        for env_v, src_v in ((vA, vA), (vB, vA)):      # control: A on A (sanity), then A-memory replayed on B
            env = envA if env_v == vA else envB
            for t in TASKS:
                traj = tj.load(t.id, src_v); gt = tj.load(t.id, env_v)
                r = runner.run_one(env, drv, t, env_v, agent, traj, gt)
                r["source_version"] = src_v; results.append(r)
                print(f"{name:18} {src_v}->{env_v} {t.id:18} {'PASS' if r['success'] else 'FAIL'} {r['halted'] or ''}", flush=True)
    envA.stop(); envB.stop(); drv.close()
    Path(out).parent.mkdir(parents=True, exist_ok=True); Path(out).write_text(json.dumps(results, indent=1))

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3].split(","), sys.argv[4])
