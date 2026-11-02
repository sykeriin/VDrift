"""Gitea tasks. Every task is solvable on both versions; checkers read server state via the REST API only.
A step target is {sel: CSS, text: exact visible text (optional), nth: int} or {label: str}; by_version overrides per release."""
from __future__ import annotations
from dataclasses import dataclass, field

def T(sel, text=None, nth=0): return {"sel": sel, "text": text, "nth": nth}
ACT = "a,button,.item,summary"

@dataclass
class Step:
    intent: str
    action: str            # click | type
    target: dict
    value: str | None = None
    by_version: dict = field(default_factory=dict)
    irreversible: bool = False

@dataclass
class Task:
    id: str
    instruction: str
    start: str
    steps: list
    check: callable
    setup: callable = lambda env: env.seed_repo("demo")
    viewport: tuple = (1280, 1200)   # tall where pages exceed the screen: v1 has no scroll actions (documented limitation)
    change_type: dict = field(default_factory=dict)   # {(vA, vB): label}; filled after labelling

def _desc(env): return env.api("GET", "/repos/vdadmin/demo").json().get("description") == "versiondrift description"
def _issue(env): return any(i["title"] == "Broken login" for i in env.api("GET", "/repos/vdadmin/demo/issues?state=all").json())
def _label(env): return any(l["name"] == "needs-triage" for l in env.api("GET", "/repos/vdadmin/demo/labels").json())
def _repo(env): return env.api("GET", "/repos/vdadmin/ledger").status_code == 200
def _collab(env): return env.api("GET", "/repos/vdadmin/demo/collaborators/alice").status_code == 204
def _fullname(env): return env.api("GET", "/user").json().get("full_name") == "Durva Test"
def _branch(env): return env.api("GET", "/repos/vdadmin/demo/branches/release-1").status_code == 200
def _star(env): return env.api("GET", "/user/starred/vdadmin/demo").status_code == 204
def _deleted(env): return env.api("GET", "/repos/vdadmin/demo").status_code == 404
def _seed_alice(env): env.seed_repo("demo"); env.seed_user("alice")

TASKS = [
    Task("star_repo", "Star the repository vdadmin/demo.", "/vdadmin/demo",
         [Step("click Star", "click", T(ACT, "Star"))], _star),
    Task("repo_description", "Set the description of vdadmin/demo to 'versiondrift description'.", "/vdadmin/demo",
         [Step("open repository settings", "click", T(ACT, "Settings")),
          Step("type description", "type", T("textarea#description, input#description"), "versiondrift description"),
          Step("save settings", "click", T("button", "Update Settings"))], _desc),
    Task("create_issue", "Create an issue titled 'Broken login' in vdadmin/demo.", "/vdadmin/demo",
         [Step("open issues", "click", T('a[href="/vdadmin/demo/issues"]', "Issues")),
          Step("new issue", "click", T("a,button", "New Issue")),
          Step("type title", "type", T("input[name=title]:visible"), "Broken login"),
          Step("submit issue", "click", T("button", "Create Issue"))], _issue),
    Task("create_label", "Create a label named 'needs-triage' in vdadmin/demo.", "/vdadmin/demo/issues",
         [Step("open labels", "click", T('a[href$="/labels"]', "Labels")),
          Step("new label", "click", T("div,a,button", "New Label")),
          Step("type label name", "type", T("input[name=title]:visible"), "needs-triage"),
          Step("create label", "click", T("div.button,button", "Create Label"))], _label),
    Task("create_repo", "Create a new repository named 'ledger'.", "/",
         [Step("open create menu", "click", T("[data-tooltip-content*=Create], .dropdown.item:has(.octicon-plus)")),
          Step("new repository", "click", T("a,.item", "New Repository")),
          Step("type repo name", "type", T("input#repo_name"), "ledger"),
          Step("create repository", "click", T("button", "Create Repository"))], _repo,
         setup=lambda env: None, viewport=(1280, 1800)),
    Task("add_collaborator", "Add user 'alice' as a collaborator of vdadmin/demo.", "/vdadmin/demo/settings",
         [Step("open collaborators", "click", T("a.item,a", "Collaborators")),
          Step("type collaborator", "type", T("input[name=collaborator]:visible"), "alice"),
          Step("pick suggestion", "click", T(".results .result, .menu.transition .item", "alice")),
          Step("add collaborator", "click", T("button", "Add Collaborator"))], _collab, setup=_seed_alice),
    Task("change_full_name", "Change your full name to 'Durva Test'.", "/",
         [Step("open profile menu", "click", T(".dropdown.item:has(img.avatar), .dropdown.item:has(.avatar)")),
          Step("open user settings", "click", T("a.item,a", "Settings")),
          Step("type full name", "type", T("input#full_name"), "Durva Test"),
          Step("update profile", "click", T("button", "Update Profile"))], _fullname, setup=lambda env: None),
    Task("create_branch", "Create a branch named 'release-1' from main in vdadmin/demo.", "/vdadmin/demo",
         [Step("open branch menu", "click", T(".choose.branch, .branch-dropdown-button, .ui.dropdown:has(.octicon-git-branch)")),
          Step("type branch name", "type", T("input[placeholder*=ilter], input[placeholder*=ranch]:visible"), "release-1"),
          Step("create branch", "click", T(".item, a, div", "Create branch"))], _branch),
    Task("delete_repo", "Delete the repository vdadmin/demo.", "/vdadmin/demo/settings",
         [Step("open delete dialog", "click", T("button", "Delete This Repository")),
          Step("type repo name", "type", T("#delete-repo-modal input[name=repo_name]:visible, .modal input[name=repo_name]:visible"), "demo"),
          Step("confirm delete", "click", T(".modal button, .modal .button", "Delete Repository"), irreversible=True)], _deleted, viewport=(1280, 4200)),
]
BY_ID = {t.id: t for t in TASKS}
