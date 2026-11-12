# VersionDrift + ReGround

A benchmark of computer-use tasks replayed across **real consecutive releases** of the same app (VersionDrift), and a
semantic re-grounding layer that tries to keep a recorded workflow working after a UI update (ReGround).
Full plan, design decisions and rejected alternatives: [`PLAN.md`](PLAN.md). Raw reports: `runs/report_full.txt` (Gitea), `runs/report_nextcloud.txt`.

**Status: early research prototype, model-free.** No LLM/VLM agent has been run (no GPU or API key was available). Everything below is
*replay of a recording made on version A, executed on version B*, which is the setting where drift actually breaks deployed automation.

## Headline (read this before the tables)

1. **Real drift breaks recorded coordinates.** Coordinate replay (the RPA floor) falls from 100% on the same version to 12/36 across four Gitea release pairs (0/9 on the 1.17→1.22 jump) and 4/7 on Nextcloud 24→25.
2. **ReGround recovers most of that (31/36 on Gitea), but it does not beat a simple Similo-style locator (36/36)**, and removing all DOM attributes from that locator still gives 35/36. ReGround − Similo = −0.14, 95% CI [−0.25, −0.03], exact McNemar p = 0.062. On this benchmark the semantic-anchor design is not better than text + tag + position matching.
3. **The parts of ReGround that are supposed to add value did not show it here:** effect verification never changed an outcome; anchor context (ancestors/neighbours) did not help (`noctx` 33/36 vs 31/36); the destructive-action guard cost 3 successes and prevented nothing (zero wrong irreversible clicks occurred with it off). Gitea and Nextcloud are both DOM-rich, so the central claim ("works where there is no usable DOM") is **untested**.
4. **The benchmark is too small and too easy to rank methods:** 9 tasks (Gitea) and 7 (Nextcloud); the labeller found **no** `workflow_restructure` or `feature_removed` tasks, so abstention behaviour is untested.

## Results

### Gitea, 9 tasks, 4 version pairs (1.17.4→1.19.4, 1.19.4→1.21.11, 1.21.11→1.22.3, 1.17.4→1.22.3)
Same-version control (recording replayed on its own version): every agent 27/27 (a baseline below 100% there would measure the harness, not drift).

| agent | 17.4→19.4 | 19.4→21.11 | 21.11→22.3 | 17.4→22.3 | pooled (36) |
|---|---|---|---|---|---|
| coord_replay (RPA floor) | 6/9 | 1/9 | 5/9 | 0/9 | 12 |
| selector_replay (CSS/text, form- and dialog-scoped) | 6/9 | 7/9 | 8/9 | 5/9 | 26 |
| **reground** | 7/9 | 8/9 | 8/9 | 8/9 | **31** |
| reground, no effect check | 7/9 | 8/9 | 8/9 | 8/9 | 31 |
| reground, no context signals | 8/9 | 8/9 | 9/9 | 8/9 | 33 |
| reground, destructive guard off | 8/9 | 8/9 | 9/9 | 9/9 | 34 |
| reground + containment name match (post-hoc) | 8/9 | 8/9 | 8/9 | 8/9 | 32 |
| similo_noattr (Similo-style, DOM attributes removed) | 9/9 | 9/9 | 9/9 | 8/9 | 35 |
| similo_replay (Similo-style multi-attribute) | 9/9 | 9/9 | 9/9 | 9/9 | **36** |

- Task change types over all pair×task units: 11 cosmetic, 23 relocation, 2 rename, 0 workflow_restructure, 0 feature_removed. ReGround's pooled misses are 4 relocation + 1 rename; coordinate replay fails 23/23 relocation tasks.
- Staleness detector (ReGround, A→B steps): precision 0.98, recall 0.94 (48 TP, 1 FP, 3 FN, 60 TN) against ground truth derived from the recordings on both versions.
- ReGround's 5 misses: 3 destructive-guard halts on the *correct* `delete_repo` target (τ_hi too strict), 1 abstention (`no_candidate`), 1 effect mismatch.
- Paired comparisons (36 units): ReGround − coord +0.53 [+0.33, +0.69]; ReGround − selector +0.14 [−0.03, +0.31], p = 0.23; ReGround − guard-off −0.08 [−0.19, 0.00], p = 0.25.

**Post-hoc change, held-out check.** The containment name match was motivated by one observed miss ("Branch: main" → "main", pair 17.4→19.4, the tuning pair). It lifts that pair 7/9 → 8/9 and changes nothing on the three other pairs (24/27 vs 24/27). Treat it as a one-case fix, not an improvement. τ sweep on the tuning pair only: 0.5 → 7/9, 0.6 → 8/9, 0.7 → 8/9; default 0.6 kept.

### Nextcloud 24 → 25 (the "Hub 3" redesign), 7 tasks, Docker + SQLite
| agent | same version | after drift |
|---|---|---|
| coord_replay | 7/7 | 4/7 |
| reground (centre-click) | 5/7 | 6/7 |
| reground, offset click policy | 7/7 | 6/7 |
| similo_replay / noattr / offset variants | 6/7 | 6/7 |
| selector_replay | 3/7 (**invalid baseline**) | 3/7 |

All 14 reference demonstrations (7 tasks × 2 versions) pass their state-based checkers. With n = 7 no agent ranking is supported. This app exposed a harness flaw: clicking the *centre of the matched element* misses the target when the smallest element under the recorded point is a wrapper (Vue components). Replaying the recorded point when not stale, and the same relative offset when re-grounding, fixed ReGround's same-version control (5/7 → 7/7); it is an opt-in variant (`*_off`), and the **Gitea numbers above were run with centre-click**. One Similo task still fails without drift, so the Nextcloud controls are not fully clean.

## How it works
- `envs/`: Gitea (single binary + SQLite, run as an unprivileged user, snapshot-reset, parallel "slots" with their own port/dir) and Nextcloud (official Docker image, bind-mounted dir snapshot).
- `tasks_*.py`: tasks with **state-based** checkers (REST/OCS/WebDAV), never UI-based. Reference demonstrations are recorded on every version (this doubles as the solvability check) and store, per step, the click point, the target element's role/name/ancestors/neighbours/bbox, a CSS selector and the observed effect.
- `agents/replay.py`: coordinate, selector and Similo-style baselines. `reground/`: staleness detector, tier-0 (DOM/a11y-attribute) re-grounding, effect verification, destructive guard. Tiers T1 (OCR + icon embeddings), T2 (small grounding model), T3 (full CUA) are **not implemented**; ReGround abstains instead.
- `analysis/`: automatic change-type labels, per-pair/pooled tables, paired bootstrap CIs, exact McNemar, safety counts.
- Bugs found by testing along the way (all fixed): snapshot included elements hidden behind dialogs (corrupted anchors); effect check accepted `/issues` for `/settings` because the shared repo path dominated; my first selector baseline failed on the *same* version (so it was excluded until it passed 27/27).

## Reproduce
Needs Linux, Python ≥ 3.11, Playwright Chromium, a user named `vd` (Gitea refuses root), Gitea binaries `gitea-{1.17.4,1.19.4,1.21.11,1.22.3}` from dl.gitea.com in `$VD_BIN_DIR`, and Docker for Nextcloud.
```bash
pip install -e .
python -m versiondrift.harness.demo_cli --app gitea 1.17.4,1.19.4,1.21.11,1.22.3     # record + solvability check
python -m versiondrift.harness.run_cli 1.17.4 1.19.4 coord,selector,similo,reground runs/x.json 0 --aa
python -m versiondrift.analysis.report runs/x.json                                    # --app nextcloud for the other app
pytest -q                       # unit tests
pytest -m integration -q        # needs the apps running (~25 min)
```

## Limitations
No model-based agents or T1–T3 tiers; no GPU/API key was available. Tasks are simple CRUD with stable flows. No scroll actions (tall viewports are used for long pages). Single seed (replay is deterministic, but stochastic agents will need ≥ 3). Image tags are not yet pinned to digests. The brief's 2026 arXiv citations were not verified.

## Next steps (priority order)
1. **Make the benchmark able to discriminate:** 20–30 tasks per app, including flows that genuinely changed between releases (branch protection, webhooks, project boards, sharing) so `workflow_restructure`/`feature_removed` exist and abstention can be scored.
2. **Test the central claim:** add an app with a weak or absent DOM (canvas/Electron/desktop via VNC; GIMP 2.10→3.0, LibreOffice) and a third web app (WordPress admin). Compare ReGround to Similo restricted to the information a pixel-only agent has.
3. **Fix the remaining Nextcloud control failure**, re-run Gitea with the offset click policy, then add 3 seeds.
4. **Rework the destructive guard:** the fixed threshold halted correct clicks. Use effect-prediction and a confirmation hook, and evaluate on tasks where an off-target destructive click is actually possible (otherwise its benefit is unmeasurable).
5. **Model-based agents (needs GPU / API key):** Claude computer use, UI-TARS-1.5-7B, OpenCUA-7B; implement T1 (OCR + icon embeddings), T2 (grounding model), T3 (CUA escalation); report cost per recovered step.
6. Synthetic-vs-real correlation at the *grounder* level (6–10 grounders), not the agent level.
7. Pin image digests, add CI, verify the cited papers, then release.
