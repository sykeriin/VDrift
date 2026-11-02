# VersionDrift + ReGround (v0.1, Gitea only)

Benchmark of tasks replayed across real app releases (Gitea 1.17.4 -> 1.22.3) plus ReGround, a semantic grounding layer
(anchor store, staleness detector, T0 re-grounding, effect verification, destructive-action guard). Full plan: `PLAN.md`.

## Run
    # needs Gitea binaries in $VD_BIN_DIR (gitea-1.17.4, gitea-1.22.3) and an unprivileged user `vd`
    python -m versiondrift.harness.demo_cli 1.17.4,1.22.3          # record reference trajectories (also checks solvability)
    python -m versiondrift.harness.run_cli 1.17.4 1.22.3 coord,similo,reground runs/x.json
    python -m versiondrift.analysis.metrics runs/x.json

## First results (9 tasks, 1 app pair, replay of A-trajectories; NOT a benchmark yet)
| agent | A->A | A->B |
|---|---|---|
| coord_replay (RPA floor) | 9/9 | 0/9 |
| similo_replay (prior-art style) | 9/9 | 8/9 |
| reground | 9/9 | 7/9 |
| reground, guard off | 9/9 | 8/9 |
| reground, no context signals | 9/9 | 6/9 |
| selector_replay | 4/9 | 3/9 |  <- INVALID: fails on the same version, baseline bug, unfixed

Staleness detector (ReGround, A->B steps): precision 0.95, recall 1.0 (20 TP, 1 FP, 5 TN).
Paired exact McNemar: ReGround vs Similo (1 vs 2 discordant tasks) p=1.0. **No evidence ReGround beats the Similo-style baseline.**

## What the data does and does not show
- Real drift breaks coordinate replay completely (0/9), so the problem exists on these releases.
- Cheap re-matching recovers most of it, but a simple multi-attribute DOM locator (Similo-style) does as well. ReGround's claimed edges
  (effect verification, safety, non-DOM apps) are not demonstrated: verification never changed an outcome here, and Gitea is all-DOM.
- Failures: `create_branch` (name changed "Branch: main" -> "main": false stale flag and no T0 candidate, run abstained);
  `delete_repo` (guard halted for confirmation on the correct target; with guard off it succeeds). No wrong destructive click occurred in any condition.
- 9 tasks, one version pair, one app: 1-task differences are noise. Thresholds (tau) were NOT tuned on this data; tune on a different app before comparing.

## Known limitations
selector baseline broken; no scroll actions (tall viewports); T1-T3 not implemented; no model-based agents (no GPU/API key here);
change-type labels not yet assigned; GitHub push blocked (invalid GH_TOKEN).
