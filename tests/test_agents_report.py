import json
from versiondrift.agents.replay import similo_score
from versiondrift.analysis import report

def el(**kw):
    base = {"tag": "a", "text": "Settings", "attrs": {"id": "x", "href": "/o/r/settings", "class": "item"}, "center": (100.0, 100.0)}
    base.update(kw); return base

def test_similo_attr_ablation_ignores_dom_attributes():
    a = el()
    same_text_other_attrs = el(attrs={"id": "y", "href": "/zzz", "class": "other"})
    assert similo_score(a, same_text_other_attrs, use_attrs=True) < similo_score(a, a, use_attrs=True)
    assert similo_score(a, same_text_other_attrs, use_attrs=False) == similo_score(a, a, use_attrs=False)

def test_report_later_files_override_earlier(tmp_path):
    r1 = {"agent": "selector_replay", "source_version": "A", "version": "B", "task": "t", "success": False, "steps": []}
    r2 = dict(r1, success=True)
    f1, f2 = tmp_path / "a.json", tmp_path / "b.json"
    f1.write_text(json.dumps([r1])); f2.write_text(json.dumps([r2]))
    out = report.load_all([str(f1), str(f2)])
    assert len(out) == 1 and out[0]["success"] is True and out[0]["pair"] == "A->B"

def test_paired_bootstrap_only_uses_units_with_both_agents():
    rows = [{"pair": "p", "task": "t1", "agent": "a", "success": True}, {"pair": "p", "task": "t1", "agent": "b", "success": False},
            {"pair": "p", "task": "t2", "agent": "a", "success": True}]   # t2 has no b: must be ignored
    mean, lo, hi, n = report.paired_bootstrap(rows, "a", "b", iters=200)
    assert n == 1 and mean == 1.0
