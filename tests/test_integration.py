"""Run with:  pytest -m integration -q   (needs Gitea binaries in $VD_BIN_DIR and user `vd`; ~10 min)."""
import json, pytest
from versiondrift import apps
from versiondrift.harness import trajectory as tj

pytestmark = pytest.mark.integration
GITEA_VERSIONS = ["1.17.4", "1.19.4", "1.21.11", "1.22.3"]

@pytest.mark.parametrize("version", GITEA_VERSIONS)
def test_noop_fails_every_checker(version):
    """A checker that passes without any action is broken (it would credit agents for doing nothing)."""
    Env, TASKS = apps.get("gitea"); env = Env(version)
    try:
        for t in TASKS:
            env.reset(); t.setup(env)
            assert not t.check(env), f"{t.id} passes with no actions on {version}"
    finally: env.stop()

@pytest.mark.parametrize("version", GITEA_VERSIONS)
def test_reference_trajectories_pass_and_are_complete(version):
    """Recorded demonstrations: checker passed at recording time, every click/type step has an anchor with bbox, same steps on all versions."""
    Env, TASKS = apps.get("gitea")
    for t in TASKS:
        traj = tj.load(t.id, version)
        assert traj["check_passed"], f"{t.id}@{version}"
        assert len(traj["steps"]) == len(t.steps)
        for s in traj["steps"]:
            if s["action"] != "key": assert s["anchor"] and len(s["anchor"]["bbox"]) == 4

@pytest.mark.parametrize("version", GITEA_VERSIONS)
def test_replaying_a_trajectory_on_its_own_version_passes_for_coord_replay(version):
    """Control: with no drift the RPA floor must succeed on every task (otherwise 'drift failures' are really harness failures)."""
    from versiondrift.drivers.playwright_driver import Driver
    from versiondrift.agents.replay import CoordReplay
    from versiondrift.harness import runner
    Env, TASKS = apps.get("gitea"); env = Env(version, slot=9); drv = Driver()
    try:
        if not env.snapshot.exists(): env.init()
        bad = []
        for t in TASKS:
            traj = tj.load(t.id, version); r = runner.run_one(env, drv, t, version, CoordReplay(), traj, traj)
            if not r["success"]: bad.append(t.id)
        assert not bad, f"coord replay failed without drift on {version}: {bad}"
    finally: env.stop(); drv.close()

def test_reset_is_deterministic():
    Env, TASKS = apps.get("gitea"); env = Env("1.22.3", slot=9)
    try:
        sigs = []
        for _ in range(2):
            env.reset(); env.seed_repo("demo")
            sigs.append(sorted(r["name"] for r in env.api("GET", "/repos/search").json()["data"]))
        assert sigs[0] == sigs[1] == ["demo"]
    finally: env.stop()

def _docker_ok():
    import subprocess
    return subprocess.run(["docker", "info"], capture_output=True).returncode == 0

@pytest.mark.skipif(not _docker_ok(), reason="docker daemon not running (start dockerd)")
def test_noop_fails_every_checker_nextcloud():
    Env, TASKS = apps.get("nextcloud"); env = Env("24", slot=9)
    try:
        if not env.snapshot.exists(): env.init()
        for t in TASKS:
            env.reset(); t.setup(env)
            assert not t.check(env), f"{t.id} passes with no actions on nextcloud 24"
    finally: env.stop()

def test_nextcloud_reference_trajectories_recorded_and_passing():
    for v in ("24", "25"):
        _, TASKS = apps.get("nextcloud")
        for t in TASKS:
            traj = tj.load(t.id, v, "nextcloud")
            assert traj["check_passed"], f"{t.id}@{v}"
