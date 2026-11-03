from versiondrift.analysis.labels import label_step, label_task

def step(name, center, url_changed=False, path="/x/settings"):
    return {"anchor": {"name": name, "center": center}, "effect": {"url_changed": url_changed, "path": path}}

def test_same_place_same_name_is_cosmetic():
    assert label_step(step("Star", (100, 80)), step("Star", (108, 84))) == "cosmetic"

def test_moved_is_relocation():
    assert label_step(step("Settings", (1100, 140)), step("Settings", (1180, 120))) == "relocation"

def test_renamed_is_rename_but_synonym_is_not():
    assert label_step(step("Wiki", (10, 10)), step("Projects", (10, 10))) == "rename"
    assert label_step(step("Settings", (10, 10)), step("Preferences", (10, 10))) == "cosmetic"

def test_destination_change_is_workflow_restructure():
    a = step("Settings", (1, 1), True, "/o/r/settings")
    b = step("Settings", (1, 1), True, "/o/r/admin")
    assert label_step(a, b) == "workflow_restructure"
    assert label_step(step("x", (1, 1), True), step("x", (1, 1), False)) == "workflow_restructure"

def test_task_label_is_worst_step_and_length_mismatch():
    A = {"steps": [step("a", (0, 0)), step("b", (0, 0))]}
    B = {"steps": [step("a", (1, 1)), step("b", (300, 0))]}
    assert label_task(A, B)["label"] == "relocation"
    assert label_task(A, {"steps": B["steps"][:1]})["label"] == "workflow_restructure"
