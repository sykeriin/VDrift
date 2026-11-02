import sys, os, traceback
from ..envs.gitea import GiteaEnv
from ..drivers.playwright_driver import Driver
from ..tasks_gitea import TASKS, BY_ID
from . import trajectory as tj

def main(versions, ids):
    drv = Driver()
    for v in versions:
        env = GiteaEnv(v)
        if not env.snapshot.exists(): env.init()
        for t in (BY_ID[i] for i in ids) if ids else TASKS:
            try:
                traj = tj.demonstrate(env, drv, t, v, shots_dir=os.environ.get('VD_SHOTS'))
                tj.save(traj)
                print(f"{v:7} {t.id:18} check={'PASS' if traj['check_passed'] else 'FAIL'} steps={len(traj['steps'])}")
            except Exception as e:
                print(f"{v:7} {t.id:18} ERROR {type(e).__name__}: {str(e)[:160]}")
        env.stop()
    drv.close()

if __name__ == "__main__":
    main(sys.argv[1].split(","), sys.argv[2].split(",") if len(sys.argv) > 2 else None)
