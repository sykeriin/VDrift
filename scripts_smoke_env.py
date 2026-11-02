import sys
from versiondrift.envs.gitea import GiteaEnv
for v in ["1.17.4", "1.22.3"]:
    e = GiteaEnv(v); e.init(); e.reset()
    print(v, e.api("GET", "/user").json().get("login"), e.api("GET", "/version").json())
    print(" seed:", e.seed_repo().status_code, e.seed_user("alice").status_code)
    e.stop()
