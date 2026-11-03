"""Record reference trajectories (also the solvability check). Usage: demo_cli --app gitea 1.17.4,1.22.3 [task,task]"""
import sys, os
from .. import apps
from ..drivers.playwright_driver import Driver
from . import trajectory as tj

def main(app, versions, ids, slot=0):
    Env, TASKS = apps.get(app); by = {t.id: t for t in TASKS}
    drv = Driver(); fails = 0
    for v in versions:
        env = Env(v, slot=slot)
        if not env.snapshot.exists(): env.init()
        for t in ([by[i] for i in ids] if ids else TASKS):
            try:
                traj = tj.demonstrate(env, drv, t, v, shots_dir=os.environ.get("VD_SHOTS"))
                tj.save(traj, app); fails += not traj["check_passed"]
                print(f"{v:8} {t.id:20} check={'PASS' if traj['check_passed'] else 'FAIL'} steps={len(traj['steps'])}", flush=True)
            except Exception as e:
                fails += 1; print(f"{v:8} {t.id:20} ERROR {type(e).__name__}: {str(e)[:160]}", flush=True)
        env.stop()
    drv.close(); return fails

if __name__ == "__main__":
    a = sys.argv[1:]; app = "gitea"
    if a and a[0] == "--app": app = a[1]; a = a[2:]
    sys.exit(1 if main(app, a[0].split(","), a[1].split(",") if len(a) > 1 else None) else 0)
