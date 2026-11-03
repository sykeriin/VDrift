"""Gitea environment: one binary + SQLite per version, isolated work dir and port."""
from __future__ import annotations
import os, shutil, subprocess, time, signal
from dataclasses import dataclass
from pathlib import Path
import requests

BIN_DIR = Path(os.environ.get("VD_BIN_DIR", "/home/user/vd-bins"))
DATA_DIR = Path(os.environ.get("VD_DATA_DIR", "/home/user/versiondrift/data"))
RUN_AS = ["setpriv", "--reuid=vd", "--regid=vd", "--clear-groups"]
ADMIN = ("vdadmin", "vdadmin-pass-1", "admin@example.com")
PORTS = {"1.17.4": 3017, "1.19.4": 3019, "1.21.11": 3021, "1.22.3": 3022}

APP_INI = """APP_NAME = Gitea
RUN_MODE = prod
RUN_USER = vd
WORK_PATH = {work}
[database]
DB_TYPE = sqlite3
PATH = {work}/gitea.db
[server]
HTTP_PORT = {port}
ROOT_URL = http://127.0.0.1:{port}/
DOMAIN = 127.0.0.1
DISABLE_SSH = true
OFFLINE_MODE = true
LFS_START_SERVER = false
[repository]
ROOT = {work}/repos
[security]
INSTALL_LOCK = true
SECRET_KEY = versiondrift-fixed-secret
INTERNAL_TOKEN =
[service]
DISABLE_REGISTRATION = true
REQUIRE_SIGNIN_VIEW = false
ENABLE_NOTIFY_MAIL = false
[log]
MODE = console
LEVEL = Warn
[session]
PROVIDER = file
[picture]
DISABLE_GRAVATAR = true
ENABLE_FEDERATED_AVATAR = false
[other]
SHOW_FOOTER_VERSION = false
SHOW_FOOTER_TEMPLATE_LOAD_TIME = false
"""

@dataclass
class GiteaEnv:
    version: str
    proc: subprocess.Popen | None = None
    slot: int = 0    # parallel workers: own port (+100*slot) and work dir; the snapshot is shared read-only

    @property
    def port(self): return PORTS[self.version] + 100 * self.slot
    @property
    def url(self): return f"http://127.0.0.1:{self.port}"
    @property
    def work(self): return DATA_DIR / (f"gitea-{self.version}" if self.slot == 0 else f"gitea-{self.version}-s{self.slot}")
    @property
    def snapshot(self): return DATA_DIR / f"gitea-{self.version}.snapshot"
    @property
    def binary(self): return str(BIN_DIR / f"gitea-{self.version}")
    @property
    def auth(self): return (ADMIN[0], ADMIN[1])

    @staticmethod
    def _chown(path):
        subprocess.run(["chown", "-R", "vd:vd", str(path)], check=True)

    def _cli(self, *args):
        return subprocess.run([*RUN_AS, self.binary, "--config", str(self.work/"app.ini"), "--work-path", str(self.work), *args],
                              capture_output=True, text=True, cwd=self.work, env=dict(os.environ, HOME="/home/vd"))

    def init(self):
        """Create a fresh instance with admin user and take a snapshot."""
        self.stop()
        shutil.rmtree(self.work, ignore_errors=True)
        (self.work/"repos").mkdir(parents=True)
        (self.work/"app.ini").write_text(APP_INI.format(work=self.work, port=self.port))
        self._chown(self.work)
        r = self._cli("migrate")
        if r.returncode: raise RuntimeError(r.stderr or r.stdout)
        r = self._cli("admin", "user", "create", "--admin", "--username", ADMIN[0], "--password", ADMIN[1],
                      "--email", ADMIN[2], "--must-change-password=false")
        if r.returncode: raise RuntimeError(r.stderr or r.stdout)
        shutil.rmtree(self.snapshot, ignore_errors=True)
        shutil.copytree(self.work, self.snapshot)
        self._chown(self.snapshot)

    def reset(self):
        """Restore snapshot -> deterministic state."""
        self.stop()
        shutil.rmtree(self.work, ignore_errors=True)
        shutil.copytree(self.snapshot, self.work)
        (self.work/"app.ini").write_text(APP_INI.format(work=self.work, port=self.port))   # slot-specific paths/port
        self._chown(self.work)
        self.start()

    def start(self, timeout=60):
        if self.proc: return
        env = dict(os.environ, GITEA_WORK_DIR=str(self.work), HOME="/home/vd")
        self.proc = subprocess.Popen([*RUN_AS, self.binary, "web", "--config", str(self.work/"app.ini"), "--work-path", str(self.work)],
                                     cwd=self.work, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                     start_new_session=True)
        t0 = time.time()
        while time.time() - t0 < timeout:
            try:
                if requests.get(self.url + "/api/healthz", timeout=1).status_code == 200: return
            except requests.RequestException: pass
            time.sleep(0.3)
        raise TimeoutError(f"gitea {self.version} did not start")

    def stop(self):
        if self.proc:
            try: os.killpg(self.proc.pid, signal.SIGTERM); self.proc.wait(10)
            except Exception: pass
            self.proc = None

    # --- API helpers (used by seeds and checkers) ---
    def api(self, method, path, **kw):
        return requests.request(method, f"{self.url}/api/v1{path}", auth=self.auth, timeout=15, **kw)
    def seed_repo(self, name="demo", **kw):
        return self.api("POST", "/user/repos", json={"name": name, "auto_init": True, "default_branch": "main", **kw})
    def seed_user(self, name):
        return self.api("POST", "/admin/users", json={"username": name, "email": f"{name}@example.com",
                                                      "password": "pw-12345-abc", "must_change_password": False})
