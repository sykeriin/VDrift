"""Metrics over run results (list of dicts from run_cli)."""
from __future__ import annotations
import json, sys
from collections import defaultdict

def load(path): return json.loads(open(path).read())

def success_table(results):
    """{agent: {'A->A': (k, n), 'A->B': (k, n)}} keyed by source->target version type."""
    t = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for r in results:
        key = "A->A" if r["source_version"] == r["version"] else "A->B"
        t[r["agent"]][key][0] += r["success"]; t[r["agent"]][key][1] += 1
    return t

def staleness_pr(results, agent):
    """Detector flags (stale) vs ground truth (coordinate no longer on target). Only A->B steps that were reached."""
    tp = fp = fn = tn = 0
    for r in results:
        if r["agent"] != agent or r["source_version"] == r["version"]: continue
        for s in r["steps"]:
            if "stale" not in s or "truly_stale" not in s: continue
            if s["stale"] and s["truly_stale"]: tp += 1
            elif s["stale"]: fp += 1
            elif s["truly_stale"]: fn += 1
            else: tn += 1
    p = tp / (tp + fp) if tp + fp else float("nan"); rc = tp / (tp + fn) if tp + fn else float("nan")
    return dict(tp=tp, fp=fp, fn=fn, tn=tn, precision=p, recall=rc)

def step_accuracy(results, agent):
    """Fraction of executed A->B steps whose click landed on the true target on B."""
    k = n = 0
    for r in results:
        if r["agent"] != agent or r["source_version"] == r["version"]: continue
        for s in r["steps"]:
            if "hit" in s: n += 1; k += s["hit"]
    return k, n

def tier_use(results, agent):
    c = defaultdict(int)
    for r in results:
        if r["agent"] != agent or r["source_version"] == r["version"]: continue
        for s in r["steps"]:
            if s.get("tier"): c[s["tier"]] += 1
    return dict(c)

def halts(results, agent):
    c = defaultdict(int)
    for r in results:
        if r["agent"] == agent and r["source_version"] != r["version"] and r["halted"]: c[r["halted"]] += 1
    return dict(c)

def mcnemar_exact(results, a1, a2):
    """Exact two-sided McNemar p-value on paired A->B task outcomes (b = a1 only, c = a2 only)."""
    from math import comb
    by = defaultdict(dict)
    for r in results:
        if r["source_version"] != r["version"]: by[r["task"]][r["agent"]] = r["success"]
    b = sum(1 for t in by.values() if t.get(a1) and not t.get(a2)); c = sum(1 for t in by.values() if t.get(a2) and not t.get(a1))
    n = b + c
    if n == 0: return b, c, 1.0
    p = min(1.0, 2 * sum(comb(n, i) for i in range(0, min(b, c) + 1)) / 2 ** n)
    return b, c, p

def report(results):
    t = success_table(results); out = []
    out.append(f"{'agent':20} {'A->A':>7} {'A->B':>7}  step-hit(A->B)  tiers  halts")
    for a in t:
        k1, n1 = t[a]["A->A"]; k2, n2 = t[a]["A->B"]; sk, sn = step_accuracy(results, a)
        out.append(f"{a:20} {k1:>3}/{n1:<3} {k2:>3}/{n2:<3}  {sk:>3}/{sn:<3}         {tier_use(results, a)}  {halts(results, a)}")
    return "\n".join(out)

if __name__ == "__main__":
    res = load(sys.argv[1]); print(report(res))
    for a in {r["agent"] for r in res}:
        if a.startswith("reground"): print(a, "staleness P/R:", staleness_pr(res, a))
