"""Nextcloud environment: official Docker image + SQLite, whole /var/www/html bind-mounted so a directory copy is a full snapshot."""
from __future__ import annotations
import os, shutil, subprocess, time
from dataclasses import dataclass
from pathlib import Path
import requests

DATA_DIR = Path(os.environ.get("VD_DATA_DIR", "/home/user/versiondrift/data"))
ADMIN = ("vdadmin", "vdadmin-pass-1")
IMAGES = {"24": "nextcloud:24.0.12-apache", "25": "nextcloud:25.0.13-apache"}   # pin digests in the release; tags are fine for development
PORTS = {"24": 8024, "25": 8025}
OCS = {"OCS-APIRequest": "true", "Accept": "application/json"}

def sh(*args, check=True, **kw):
    r = subprocess.run(args, capture_output=True, text=True, **kw)
    if check and r.returncode: raise RuntimeError(f"{' '.join(args)[:120]}: {r.stderr or r.stdout}")
    return r

@dataclass
class NextcloudEnv:
    version: str
    slot: int = 0

    @property
    def port(self): return PORTS[self.version] + 100 * self.slot
    @property
    def url(self): return f"http://127.0.0.1:{self.port}"
    @property
    def work(self): return DATA_DIR / f"nc-{self.version}" / f"s{self.slot}"
    @property
    def snapshot(self): return DATA_DIR / f"nc-{self.version}" / "snapshot"
    @property
    def cname(self): return f"vd-nc-{self.version}-s{self.slot}"
    @property
    def auth(self): return ADMIN

    def _run(self, install: bool):
        env = ["-e", "SQLITE_DATABASE=nextcloud", "-e", f"NEXTCLOUD_ADMIN_USER={ADMIN[0]}",
               "-e", f"NEXTCLOUD_ADMIN_PASSWORD={ADMIN[1]}", "-e", "NEXTCLOUD_TRUSTED_DOMAINS=127.0.0.1"] if install else []
        sh("docker", "run", "-d", "--name", self.cname, "-p", f"{self.port}:80", "-v", f"{self.work}:/var/www/html", *env, IMAGES[self.version])

    def stop(self): sh("docker", "rm", "-f", self.cname, check=False)

    def _wait_ready(self, timeout=420):
        t0 = time.time()
        while time.time() - t0 < timeout:
            try:
                j = requests.get(self.url + "/status.php", timeout=3).json()
                if j.get("installed") and not j.get("maintenance"): return
            except Exception: pass
            time.sleep(2)
        raise TimeoutError(f"nextcloud {self.version} not ready: {sh('docker', 'logs', '--tail', '15', self.cname, check=False).stdout}")

    def occ(self, *args): return sh("docker", "exec", "-u", "www-data", self.cname, "php", "occ", *args)

    def init(self):
        """Fresh install, switch off first-run popups, snapshot the directory."""
        self.stop(); shutil.rmtree(self.work.parent, ignore_errors=True); self.work.mkdir(parents=True)
        self._run(install=True); self._wait_ready()
        for app in ("firstrunwizard", "recommendedapps", "survey_client", "updatenotification"):
            sh("docker", "exec", "-u", "www-data", self.cname, "php", "occ", "app:disable", app, check=False)
        self.stop()
        shutil.rmtree(self.snapshot, ignore_errors=True)
        sh("cp", "-a", str(self.work), str(self.snapshot))

    def reset(self):
        self.stop(); shutil.rmtree(self.work, ignore_errors=True)
        sh("cp", "-a", str(self.snapshot), str(self.work))
        self._run(install=False); self._wait_ready()

    def start(self): pass   # reset() starts the container

    def login(self, drv):
        p = drv.page
        p.goto(self.url + "/login")
        p.fill("input[name=user]", ADMIN[0]); p.fill("input[name=password]", ADMIN[1])
        p.locator("button[type=submit], input[type=submit]").first.click()
        p.wait_for_url(lambda u: "/login" not in u, timeout=20000)
        drv.settle(800)

    # --- API helpers (seeds and checkers) ---
    def ocs(self, method, path, **kw):
        return requests.request(method, f"{self.url}/ocs/v2.php{path}", auth=self.auth, headers=OCS, timeout=20, **kw)
    def dav(self, method, path, **kw):
        return requests.request(method, f"{self.url}/remote.php/dav/files/{ADMIN[0]}/{path.lstrip('/')}", auth=self.auth, timeout=20, **kw)
    def put_file(self, path, data=b"versiondrift"): return self.dav("PUT", path, data=data)
    def mkdir(self, path): return self.dav("MKCOL", path)
    def exists(self, path): return self.dav("PROPFIND", path, headers={"Depth": "0"}).status_code == 207
    def seed_user(self, uid): return self.ocs("POST", "/cloud/users", data={"userid": uid, "password": "pw-12345-abcXYZ!"})
