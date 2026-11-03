from versiondrift.tasks_gitea import TASKS

def test_tasks_on_the_demo_repo_get_it_seeded():
    for t in TASKS:
        if t.start.startswith("/vdadmin/demo"):
            assert t.setup.__name__ in ("_seed_demo", "_seed_alice"), t.id

def test_irreversible_step_is_last_and_only_on_delete():
    for t in TASKS:
        flags = [s.irreversible for s in t.steps]
        assert flags.count(True) == (1 if t.id == "delete_repo" else 0)
