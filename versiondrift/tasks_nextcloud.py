"""Nextcloud tasks (24 -> 25, the 'Hub 3' redesign). Checkers read server state via WebDAV/OCS only.
Selectors are validated by the demonstrator (every task must pass on both versions) -- see harness/demo_cli."""
from __future__ import annotations
import re
from .taskdef import T, Step, Task

FILES = "/index.php/apps/files/"
ROW = "tr[data-file='{}']"

def _fav(env):
    body = '<?xml version="1.0"?><d:propfind xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns"><d:prop><oc:favorite/></d:prop></d:propfind>'
    r = env.dav("PROPFIND", "notes.txt", data=body, headers={"Depth": "0", "Content-Type": "application/xml"})
    return r.status_code == 207 and "<oc:favorite>1</oc:favorite>" in r.text

def _user(env): return env.ocs("GET", "/cloud/users/carol").status_code == 200
def _group(env): return any(g == "qa-team" for g in env.ocs("GET", "/cloud/groups").json()["ocs"]["data"]["groups"])
def _dispname(env):
    d = env.ocs("GET", "/cloud/user").json()["ocs"]["data"]
    return (d.get("display-name") or d.get("displayname")) == "Durva Test"
def _seed_notes(env): env.put_file("notes.txt")

def row_action(intent, menu_text, irreversible=False):
    """open the row's '...' menu on notes.txt, then pick `menu_text`"""
    return [Step("open file actions", "click", T(f"{ROW.format('notes.txt')} a.action-menu, {ROW.format('notes.txt')} .action-menu, {ROW.format('notes.txt')} a[data-action=menu]")),
            Step(intent, "click", T("a.menuitem, .menuitem, li a, button", menu_text), irreversible=irreversible)]

TASKS = [
    Task("create_folder", "Create a folder named 'Projects' in your files.", FILES,
         [Step("open new menu", "click", T("a.button.new, .button.new, button", "New")),
          Step("new folder", "click", T("a, button, .menuitem", "New folder")),
          Step("type folder name", "type", T("input[type=text]:visible"), "Projects"),
          Step("confirm", "key", None, "Enter")],
         lambda env: env.exists("Projects")),
    Task("rename_file", "Rename notes.txt to meeting-notes.txt.", FILES,
         [*row_action("rename", "Rename"),
          Step("type new name", "type", T("input.filename:visible, .renameform input:visible, input[type=text]:visible"), "meeting-notes.txt"),
          Step("confirm", "key", None, "Enter")],
         lambda env: env.exists("meeting-notes.txt"), setup=_seed_notes),
    Task("favorite_file", "Mark notes.txt as a favorite.", FILES,
         [*row_action("add to favorites", "Add to favorites")], _fav, setup=_seed_notes),
    Task("delete_file", "Delete notes.txt.", FILES,
         [*row_action("delete", "Delete file", irreversible=True)], lambda env: not env.exists("notes.txt"), setup=_seed_notes),
    Task("add_user", "Create a user named carol with password 'Carol-pass-123!'.", "/index.php/settings/users",
         [Step("new user", "click", T("button, a, #new-user-button", "New user")),
          Step("type user name", "type", T("input[name=username]:visible, input[placeholder*=sername]:visible"), "carol"),
          Step("type password", "type", T("input[type=password]:visible"), "Carol-pass-123!"),
          Step("add user", "click", T("form input[type=submit]:visible, form button[type=submit]:visible"))], _user),
    Task("create_group", "Create a group named 'qa-team'.", "/index.php/settings/users",
         [Step("add group", "click", T("#new-group-button, a, button, li", "Add group")),
          Step("type group name", "type", T("input[type=text]:visible#new-group-name, input.new-group-name, #newgroup-entry input:visible, input[placeholder*=roup]:visible"), "qa-team"),
          Step("confirm", "key", None, "Enter")], _group),
    Task("change_display_name", "Change your full name to 'Durva Test'.", "/index.php/settings/user",
         [Step("type full name", "type", T("input#displayname, input[name=displayname]"), "Durva Test",
               by_version={"25": T("input#account-property-displayname")}),
          Step("confirm", "key", None, "Enter")], _dispname),
]
