"""Full report over several result files: per pair, pooled, by change type, paired bootstrap CIs, safety."""
from __future__ import annotations
import json, random, sys
from collections import defaultdict
from ..harness import trajectory as tj
from .labels import label_task
from .metrics import mcnemar_exact, staleness_pr, tier_use, halts

from .. import apps as _apps
PAIRS = _apps.PAIRS["gitea"]   # rebound per app in main()
APP = "gitea"

def load_all(paths):
    """Later files override earlier ones for the same (agent, pair, task, run-version): lets re-runs replace stale results."""
    d = {}
    for p in paths:
        for r in json.load(open(p)): d[(r["agent"], r["source_version"], r["version"], r["task"])] = r
    for r in d.values(): r.setdefault("pair", f"{r['source_version']}->{r['version']}")
    return list(d.values())

def is_drift(r): return r["source_version"] != r["version"]

def table(results, rows):
    """{agent: (k, n)} for A->B rows in `rows` (list of results)."""
    t = defaultdict(lambda: [0, 0])
    for r in rows: t[r["agent"]][0] += r["success"]; t[r["agent"]][1] += 1
    return t

def paired_bootstrap(rows, a1, a2, iters=4000, seed=0):
    """95% CI of success(a1) - success(a2) over (pair, task) units, resampled with replacement."""
    by = defaultdict(dict)
    for r in rows: by[(r["pair"], r["task"])][r["agent"]] = r["success"]
    units = [u for u in by.values() if a1 in u and a2 in u]
    if not units: return None
    rng = random.Random(seed); n = len(units); ds = []
    for _ in range(iters):
        s = [units[rng.randrange(n)] for _ in range(n)]
        ds.append(sum(u[a1] - u[a2] for u in s) / n)
    ds.sort(); mean = sum(u[a1] - u[a2] for u in units) / n
    return mean, ds[int(0.025 * iters)], ds[int(0.975 * iters)], n

def wrong_destructive(rows):
    """Executed irreversible steps (click landed off the true target) per agent: the safety metric."""
    c = defaultdict(int)
    for r in rows:
        traj = tj.load(r["task"], r["source_version"], APP)
        for s in r["steps"]:
            if traj["steps"][s["idx"]].get("irreversible") and s.get("hit") is False and s.get("ok") is not False: c[r["agent"]] += 1
            elif traj["steps"][s["idx"]].get("irreversible") and s.get("hit") is False: c[r["agent"]] += 1
    return dict(c)

def main(paths, app="gitea"):
    global PAIRS, APP
    PAIRS, APP = _apps.PAIRS[app], app
    res = [r for r in load_all(paths) if r.get("app", "gitea") == app]; drift = [r for r in res if is_drift(r)]; same = [r for r in res if not is_drift(r)]
    agents = sorted({r["agent"] for r in res})
    print("== same-version sanity (trajectory replayed on its own version; baseline must be ~100%) ==")
    t = table(res, same)
    for a in agents:
        if a in t: print(f"  {a:20} {t[a][0]}/{t[a][1]}")
    print("\n== A-memory replayed on a newer version: success by pair ==")
    print(f"  {'agent':20}" + "".join(f"{a[-4:]}>{b[-5:]:8}" for a, b in PAIRS) + "  pooled")
    for a in agents:
        cells = []; K = N = 0
        for p in PAIRS:
            rows = [r for r in drift if r["agent"] == a and r["pair"] == f"{p[0]}->{p[1]}"]
            k = sum(r["success"] for r in rows); n = len(rows); K += k; N += n
            cells.append(f"{k}/{n}" if n else "-")
        print(f"  {a:20}" + "".join(f"{c:13}" for c in cells) + f"  {K}/{N}")
    labels = {}
    for p in PAIRS:
        for tk in _apps.get(app)[1]: labels[(f"{p[0]}->{p[1]}", tk.id)] = label_task(tj.load(tk.id, p[0], app), tj.load(tk.id, p[1], app))["label"]
    print("\n== pooled success by task change type (worst step in task) ==")
    for lab in ["cosmetic", "relocation", "rename", "workflow_restructure"]:
        rows = [r for r in drift if labels.get((r["pair"], r["task"])) == lab]
        if not rows: print(f"  {lab:22} (no tasks)"); continue
        tt = table(res, rows)
        print(f"  {lab:22}" + "  ".join(f"{a}:{tt[a][0]}/{tt[a][1]}" for a in agents if a in tt))
    print("\n== paired comparisons on pooled (pair,task) units: diff = first - second, 95% bootstrap CI, exact McNemar p ==")
    for a, b in [("reground", "similo_replay"), ("reground", "similo_noattr"), ("reground_noguard", "similo_replay"), ("reground", "coord_replay"), ("reground", "selector_replay"), ("similo_replay", "coord_replay"),
                 ("reground", "reground_noguard"), ("reground", "reground_noverify"), ("reground", "reground_noctx")]:
        if a in agents and b in agents:
            ci = paired_bootstrap(drift, a, b)
            by = defaultdict(dict)
            for r in drift: by[(r["pair"], r["task"])][r["agent"]] = r["success"]
            both = [u for u in by.values() if a in u and b in u]    # only units where BOTH agents ran
            x = sum(1 for u in both if u[a] and not u[b]); y = sum(1 for u in both if u[b] and not u[a])
            from math import comb
            n = x + y; p = 1.0 if n == 0 else min(1.0, 2 * sum(comb(n, i) for i in range(0, min(x, y) + 1)) / 2 ** n)
            print(f"  {a} - {b}: {ci[0]:+.3f} [{ci[1]:+.3f}, {ci[2]:+.3f}] n={ci[3]}  only-first={x} only-second={y} p={p:.3f}" if ci else f"  {a} - {b}: no data")
    print("\n== ReGround internals (A->B steps) ==")
    for a in agents:
        if a.startswith("reground"):
            print(f"  {a:20} tiers={tier_use(drift, a)} halts={halts(drift, a)} staleness={ {k: (round(v, 3) if isinstance(v, float) else v) for k, v in staleness_pr(drift, a).items()} }")
    print("\n== wrong irreversible clicks (executed off-target) ==", wrong_destructive(drift))

if __name__ == "__main__":
    a = sys.argv[1:]; app = "gitea"
    if a and a[0] == "--app": app = a[1]; a = a[2:]
    main(a, app)
