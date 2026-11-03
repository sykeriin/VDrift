from versiondrift.reground import similarity as sim, effect as fx
from versiondrift.reground.middleware import DESTRUCTIVE

def el(name, role="link", bbox=(100, 100, 80, 30), anc=("||nav|",), nb=("Issues", "Pull Requests"), **attrs):
    x, y, w, h = bbox
    return {"name": name, "text": name, "role": role, "tag": "a", "attrs": attrs, "bbox": list(bbox),
            "center": (x + w / 2, y + h / 2), "anc": list(anc), "neighbours": list(nb)}

def test_synonyms_match_renames():
    assert sim.name_sim("Settings", "Preferences") == 1.0
    assert sim.name_sim("New Issue", "Create issue") == 1.0

def test_different_actions_do_not_match():
    assert sim.name_sim("Delete", "Archive") < 0.3

def test_moved_element_still_ranks_first():
    a = el("Settings", bbox=(1100, 140, 80, 30))
    moved = el("Settings", bbox=(1120, 110, 80, 30))             # shifted 30px: real drift
    decoy = el("Wiki", bbox=(1100, 140, 60, 30), nb=("Projects",))  # same coordinates, wrong element
    ranked = sim.rank(a, [decoy, moved])
    assert ranked[0][1] is moved

def test_stale_coordinate_scores_low():
    a = el("Settings", bbox=(1100, 140, 80, 30))
    under_coord = el("Packages", bbox=(1095, 140, 85, 30), nb=("Projects", "Wiki"))
    assert sim.score(a, under_coord)[0] < 0.6

def test_effect_url_match_is_approximate():
    stored = {"url_changed": True, "path": "/vdadmin/demo/settings", "appeared": [], "disappeared": []}
    assert fx.match(stored, {"url_changed": True, "path": "/vdadmin/demo/settings/", "appeared": [], "disappeared": []})
    assert fx.match(stored, {"url_changed": True, "path": "/vdadmin/demo/issues", "appeared": [], "disappeared": []}) is False
    assert fx.match(stored, {"url_changed": False, "path": "/x", "appeared": [], "disappeared": []}) is False

def test_effect_menu_open_match_and_unverifiable():
    stored = {"url_changed": False, "path": "/", "appeared": ["new repository", "new migration"], "disappeared": []}
    assert fx.match(stored, {"url_changed": False, "path": "/", "appeared": ["new repository"], "disappeared": []})
    assert fx.match(stored, {"url_changed": False, "path": "/", "appeared": [], "disappeared": []}) is False
    assert fx.match({"url_changed": False, "path": "/", "appeared": [], "disappeared": []}, {"url_changed": False, "path": "/", "appeared": [], "disappeared": []}) is None

def test_destructive_verbs():
    for w in ("Delete Repository", "Remove user", "Archive this repository", "Transfer ownership"):
        assert DESTRUCTIVE.search(w)
    assert not DESTRUCTIVE.search("Update Settings")

def test_containment_is_opt_in_and_capped():
    assert sim.name_sim("Branch: main", "main") < 0.85                      # baseline behaviour unchanged
    assert sim.name_sim("Branch: main", "main", containment=True) == 0.85
    assert sim.name_sim("main", "main", containment=True) == 1.0
    assert sim.name_sim("Delete", "Archive repository", containment=True) < 0.3   # unrelated verbs still get nothing
    assert sim.name_sim("Delete repository", "Archive repository", containment=True) < 0.85
