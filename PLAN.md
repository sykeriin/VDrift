# Project 8 — VersionDrift + ReGround: full plan

Date: 2026-11-02. Source brief: `Project_8___UI-drift_robustness_for_computer-use_agents.md` (@DK, dated today).

---

## 0. Context — why this exists

Computer-use agents (CUAs) are being sold as the replacement for RPA scripts. RPA's oldest cost is maintenance: every vendor UI release breaks recorded workflows. Benchmarks published in 2025–26 show CUAs are also brittle to UI change, but every one of them uses **synthetic** perturbations (theme, zoom, language, pop-ups, tablet mode). Two things are missing:

1. A benchmark of **real** UI drift: the same task, run on consecutive real releases of the same app.
2. A **deployment-time** fix that needs no retraining: remember *what* an element is, not *where* it is, notice when that memory is stale, and re-ground cheaply.

Intended outcome: a reproducible benchmark (VersionDrift), a library (ReGround), and a write-up with one clear number per agent — the drift gap and how much of it ReGround closes, at what cost.

---

## 1. Honest assessment before building (read this first)

These are the problems with the brief as written. Some change the design.

**1.1 The headline metric may be near zero for live agents.** A live CUA re-perceives the screen on every step. It never stored coordinates from version A, so "stale-coordinate stuck" mostly cannot happen to it on a fresh run of B. For zero-shot agents, Success(A) − Success(B) will be small and noisy, because these agents were not tuned to version A. Where drift *really* hurts is when something was **learned on A and reused on B**: recorded RPA scripts, cached trajectories, workflow memory (Agent Workflow Memory style), few-shot exemplars. So the primary experiment is the **"deployed agent with A-memory"** setting, and the zero-shot drift gap is a secondary measurement. The brief half-acknowledges this ("gap *with* trajectories or cache from A"); I am promoting it to the main result.

**1.2 ReGround has strong prior art the brief does not cite.** Self-healing locators in web test automation have done "remember attributes, not positions, then re-locate" for 15 years:
- WATER (Choudhary et al., 2011) — repair of broken web tests across versions.
- Leotta et al. (2014–16) — robust XPath/locator generation; ROBULA+.
- Similo / VON Similo (Nass, Alégroth, Feldt et al., 2022–23) — multi-attribute similarity locator; directly comparable to anchor matching.
- Healenium (open source), Testim, mabl — commercial self-healing selectors.
- UiPath "Healing Agent" (2025) — self-healing for RPA, i.e. the same business pitch.
Novelty must be argued against these: (a) vision + accessibility fusion so it works on canvas/Electron apps with no DOM, (b) **effect verification** (checking that the post-click change happened), (c) a cost-tiered cascade ending in a grounding model, (d) evaluation on real version drift against modern CUAs. Similo is the baseline to beat on the a11y tier; if we skip it, a reviewer will ask.

**1.3 Sample sizes in the brief are too small for the claims.** 20 tasks/app × 4 apps = 80 task pairs. A 10-point change in success rate on 80 paired items is within noise for stochastic agents. Fixes: paired tests (McNemar per task), 3 seeds per (agent, task, version), and step-level metrics (re-grounding accuracy per step) which give thousands of data points instead of 80.

**1.4 10 weeks part-time is optimistic.** Environment building (Dockerising versions, seeding data, writing checkers that work on both versions) is ~60% of the effort. Desktop apps will likely slip. Plan treats desktop as a stretch.

**1.5 Citations.** Several arXiv IDs in the brief (2604.*, 2605.*, 2608.*) are after or near my knowledge cutoff; I have not verified them. They must be read and checked in Week 1 before being cited. The "Berkeley RDI gamed 8 leaderboards" and "gentic.news" claims are secondary sources; cite the primary paper or drop them.

**1.6 What can and cannot run in this cloud session.** Checked today: 4 CPUs, 15 GB RAM, **no GPU**, Docker CLI installed but daemon not running (starting `dockerd` may or may not work in this container), Playwright + Chromium available, PyPI and `dl.gitea.com` reachable, no Anthropic/OpenAI API key exposed to user code. Consequences:
- UI-TARS-1.5-7B / OpenCUA-7B cannot be run here at usable speed. They need a GPU box (a single 24 GB GPU, or a hosted endpoint).
- An API CUA needs a key set as an environment secret.
- Everything that needs no model — environments, checkers, recorder, coordinate-replay control, ReGround tiers 0–2 (a11y, OCR, small icon embeddings on CPU), effect verification, the metrics — **can** be built and tested here.

---

## 2. Scope

### In scope (v1)
- **VersionDrift-Web**: 4 web apps × 2–4 real versions each, 20–30 tasks per app, programmatic checkers, change-type labels.
- **ReGround** library: anchor store, staleness detector, tiered re-grounder, effect verifier, destructive-action guard. Agent-agnostic (wraps any agent that emits clicks/types).
- **Harness**: run agent on version A, record; run on version B under conditions {fresh, coord-replay, ReGround-replay, agent+ReGround}.
- **Baselines**: coordinate replay (RPA floor), selector replay (CSS/XPath), Similo-style multi-attribute locator, full-CUA re-plan.
- **Agents**: 1 API CUA (Claude computer use), 1–2 open models (UI-TARS-1.5-7B, OpenCUA-7B) on a GPU box, 1 small-grounder agent.
- **Analysis**: drift gap by change type, recovery rate, staleness P/R, cost per recovered step, synthetic-vs-real correlation.

### Stretch
- 2 desktop apps over VNC (LibreOffice, GIMP 2.10 → 3.0).
- Android across APK versions.
- "Pre-release CI" product demo.

### Out of scope
- Training or fine-tuning any agent or grounding model.
- Tasks that require live third-party services (email delivery, payments).
- Any attempt to top a leaderboard.

---

## 3. App and version selection

Criteria: open source, long release history, visible UI redesign between pairs, runnable offline with seeded data, an API or DB for checkers, permissive licence.

| App | Why | Candidate version pairs (verify in Week 1 changelogs) | Run method | Checker source |
|---|---|---|---|---|
| **Gitea** (first) | Single Go binary + SQLite, no Docker needed; frequent UI reworks (Fomantic → custom CSS/Vue, repo header & settings reorganised across 1.17→1.22) | 1.17 → 1.19 → 1.21 → 1.22+ | binary from dl.gitea.com | REST API + SQLite |
| **Nextcloud** | Big redesign in 25 ("Nextcloud Hub 3"), Files app rewrite in 28 | 24 → 25, 27 → 28 | Docker (official image) | OCS API / DB |
| **WordPress admin** | Classic editor/Customizer → block editor / Site Editor; menus moved | 5.8 → 6.x | Docker + WP-CLI | WP-CLI / DB |
| **Mattermost** or **Odoo** | Mattermost: channel sidebar/settings redesigns; Odoo: big UI change 16 → 17 | pick one in Week 1 based on Docker reproducibility | Docker | API / Postgres |
| (stretch) LibreOffice, GIMP | Desktop, canvas-heavy, weak a11y — tests the vision tiers | GIMP 2.10 → 3.0; LO 7.x → 24.x | Docker + Xvfb + VNC | output files |

**Why Gitea first:** it is the only candidate that runs from a single binary with no Docker, so the whole pipeline can be built and debugged end-to-end in this session before any infra exists.

**Alternative considered: open-source web apps "by git tag" built from source.** Rejected for v1 — builds of old tags rot (dead npm deps), which costs days per version. Use published binaries/images, pin digests.

---

## 4. Task design

- 20–30 tasks per app, each valid in **both** versions of a pair. Mix: navigation (find a setting), CRUD (create repo/issue/label), configuration (toggle a setting), multi-step (create repo → add collaborator → protect branch).
- Each task: `id`, `instruction`, `setup` (seed script), `checker` (pure function over API/DB state → pass/fail), `irreversible_steps` flag.
- **Change-type label per (task, version-pair)**: `cosmetic`, `relocation`, `rename`, `workflow_restructure`, `feature_removed`. Labelled by diffing the human reference trajectories on A and B (same steps & same labels → cosmetic; same labels different place → relocation; etc.).
- **Solvability check**: a human (or a scripted reference trajectory) completes each task once on each version; the run is recorded (screens + actions). Tasks that cannot be done on B are labelled `feature_removed` and kept — the correct agent behaviour there is to *stop and report*, not thrash.
- **Checker robustness**: checkers read state, never the UI, so they do not drift.

---

## 5. System design

```
                 ┌──────────────────────────── VersionDrift harness ─────────────────────────────┐
 tasks/*.yaml ──►│ EnvManager ── start app@version (binary/Docker, pinned) ── seed ── reset       │
                 │      │                                                                        │
                 │      ▼                                                                        │
                 │ Browser/VNC driver (Playwright / xdotool)  ◄── Observation: screenshot,        │
                 │      ▲                                       a11y tree, DOM (if web), URL      │
                 │      │ actions                                                                │
                 │ ┌────┴─────────────── Agent adapter ───────────────┐                          │
                 │ │ ClaudeCUA | UITARS | OpenCUA | SmallGrounder |    │                          │
                 │ │ CoordReplay | SelectorReplay | SimiloReplay       │                          │
                 │ └────┬─────────────────────────────────────────────┘                          │
                 │      │ proposed action (click x,y / type / key)                               │
                 │      ▼                                                                        │
                 │ ┌──────────────────────── ReGround middleware ─────────────────────────────┐  │
                 │ │ 1. lookup anchor for (task, step) or by intent text                       │  │
                 │ │ 2. StalenessDetector: does element under (x,y) match anchor? (score<τ)    │  │
                 │ │ 3. Re-ground cascade:                                                     │  │
                 │ │    T0 a11y match (role,name,ancestors,neighbours) + synonym table         │  │
                 │ │    T1 OCR text + icon-embedding search on screenshot                      │  │
                 │ │    T2 small grounding model prompted with anchor description              │  │
                 │ │    T3 escalate to full CUA ("the element you used to click was X; find it")│  │
                 │ │ 4. DestructiveGuard: irreversible verb / low effect confidence → stop     │  │
                 │ │ 5. execute → EffectVerifier: compare post-state to stored effect;          │  │
                 │ │    fail → next candidate (bounded k), never retry irreversible            │  │
                 │ │ 6. on success: write/refresh anchor (versioned)                           │  │
                 │ └──────────────────────────────────────────────────────────────────────────┘  │
                 │      ▼                                                                        │
                 │ Recorder → runs/<run_id>/{steps.jsonl, screens/, a11y/}  → Checker → results  │
                 └───────────────────────────────────────────────────────────────────────────────┘
                                         ▼
                              analysis/ (drift gap, recovery, P/R, cost, correlation)
```

### 5.1 Anchor (what gets stored per successful action)
```
Anchor {
  task_id, step_idx, app, version, intent_text      # "open repository settings"
  action: click|type|select, value?
  role, accessible_name, visible_text, tag/attrs (web only, not used for matching by default)
  ancestor_path: [role:name, ...]  (a11y tree)
  neighbours: k nearest labelled elements (text, relative direction, distance)
  bbox_norm, screen_region (header/sidebar/main/dialog)
  icon_crop (PNG) + embedding (small CLIP / SigLIP on CPU)
  effect: {url_delta, a11y_tree_delta_summary, new_dialog?, toast_text?, screenshot_phash_delta}
  irreversible: bool
}
```

### 5.2 Staleness detection
Score the element at the proposed coordinate against the anchor with a weighted similarity (role, name, text, ancestors, neighbours, icon). Stale if score < τ, **or** if after execution the observed effect does not match the stored effect. τ tuned on a held-out app. Ground truth for P/R: annotate per step whether the coordinate target changed between A and B (derived automatically from reference trajectories, spot-checked by hand).

### 5.3 Re-grounding cascade (cheap first)
| Tier | Method | Cost | Fails on |
|---|---|---|---|
| T0 | a11y-tree match: multi-attribute similarity (Similo-style) + synonym table + optional LLM rename | ms, no model | canvas/Electron apps with empty a11y trees; heavy renames |
| T1 | OCR (RapidOCR, CPU) text match + icon embedding nearest-neighbour over UI crops | ~0.3–1 s CPU | icon-only redesigns, text in images |
| T2 | small grounding model (UI-TARS-1.5-7B / OS-Atlas / UGround) with anchor description as query | 1 GPU call | ambiguous duplicates |
| T3 | full CUA re-plan with anchor as hint | expensive | workflow restructures (expected) |

Every tier returns ranked candidates with a confidence; EffectVerifier is the final judge.

### 5.4 Safety
- Destructive-verb list (delete, remove, archive, revoke, transfer, reset, drop…) plus task-level `irreversible` flags.
- A re-grounded click on an irreversible action needs confidence ≥ τ_hi **and** text/role agreement; else halt with reason `needs_confirmation`.
- Never auto-retry an irreversible action after a failed effect check.
- Report the number of wrong destructive clicks per condition (target: 0 for ReGround).

### 5.5 Code layout (new repo `versiondrift/`, Python 3.11+)
```
versiondrift/
  envs/            gitea.py, nextcloud.py, wordpress.py, base.py (start/stop/seed/reset, pinned versions)
  tasks/<app>/     *.yaml (instruction, setup, checker ref, change_type per pair)
  checkers/<app>.py
  drivers/         playwright_driver.py (screenshot, a11y snapshot, click/type), vnc_driver.py (stretch)
  agents/          base.py, coord_replay.py, selector_replay.py, similo_replay.py, claude_cua.py, uitars.py, opencua.py
  reground/        anchor.py, store.py (SQLite), similarity.py, staleness.py, tiers/{a11y,ocr_icon,grounder,cua}.py, effect.py, guard.py, middleware.py
  harness/         runner.py, recorder.py, cli.py
  analysis/        metrics.py, stats.py (McNemar, bootstrap CIs), plots.py
  tests/           unit tests + a tiny two-version fixture app used ONLY for tests (never reported)
```

---

## 6. Experimental protocol

Conditions per (agent, app, version pair):
1. **A-fresh** — agent on A, no memory. Record trajectories; successful ones become the A-memory.
2. **B-fresh** — agent on B, no memory. (zero-shot drift gap = 1 − 2)
3. **B-coord-replay** — replay A trajectory by coordinates only (RPA floor).
4. **B-selector-replay** — replay by CSS/XPath (classic test-automation floor; web only).
5. **B-similo** — multi-attribute locator replay (strong prior-art baseline).
6. **B-reground-replay** — replay with ReGround (tiers T0–T3, ablations removing each tier, with/without a11y).
7. **B-agent+A-memory** — agent on B given A trajectory as exemplar, without ReGround.
8. **B-agent+ReGround** — same, with ReGround middleware.

3 seeds for stochastic agents. Paired McNemar per condition pair; bootstrap 95% CIs.

Metrics (from brief, plus additions):
- Drift gap (overall and by change type) — headline.
- Recovery rate = (success_ReGround − success_coord) / (success_A − success_coord).
- Staleness detector P/R per step.
- Cost: extra model calls, seconds, fraction resolved at T0/T1.
- **Correct-abstention rate** on `workflow_restructure`/`feature_removed` (added: the brief asks ReGround to "recognise" these; this measures it).
- **Wrong destructive actions** (added: safety).
- Synthetic-vs-real correlation: rank agents/grounders on GUI-Perturbed-style perturbations of version A vs real drift to B; Spearman ρ across agents. Note: with 3–4 agents, ρ is meaningless; do this at the **grounder** level (6–10 grounding models on step-level re-grounding), not the agent level.

---

## 7. Timeline (today = Mon 2026-11-02; 10 weeks part-time → ends ~Fri 2027-01-08; holidays reduce this, realistic end mid-Jan 2027)

| Week (starting) | Deliverable | Exit criterion |
|---|---|---|
| W1 Nov 2 | Read & verify papers; pick version pairs from changelogs; repo skeleton; Gitea env + 5 tasks + checkers; coord-replay baseline | coord-replay runs end-to-end on Gitea A→B with a pass/fail table |
| W2 Nov 9 | Gitea 25 tasks + change labels; ReGround T0 + anchor store + effect verifier; Similo baseline | ReGround-replay vs coord vs Similo numbers on Gitea |
| W3 Nov 16 | Nextcloud + WordPress envs (Docker, pinned digests), 20 tasks each | both apps reset deterministically in < 60 s |
| W4 Nov 23 | 4th app; GPU box up; UI-TARS / OpenCUA / Claude adapters; A-fresh & B-fresh baselines | baseline drift-gap table, 3 agents |
| W5–6 Nov 30 – Dec 13 | T1 (OCR+icon), T2 (grounder), T3 (CUA escalation); staleness τ tuning; ablations | full condition matrix on 4 apps |
| W7 Dec 14 | Destructive guard; abstention on workflow changes; safety metrics | 0 wrong destructive clicks or documented cases |
| W8 Dec 21 (holiday risk) | stretch: GIMP/LibreOffice via VNC | — (slips first) |
| W9 Jan 4 | synthetic-vs-real correlation at grounder level; stats | figures + CIs |
| W10 Jan 11 | release: pinned images, task suite, library, write-up | someone else re-runs one app from README |

---

## 8. Related work map (to read; ✱ = in brief but unverified by me)

- **Robustness benchmarks:** GUI-Perturbed✱, AndroidReality✱ (stale-coordinate stuck), AgentHijack✱, VenusBench-Mobile✱, WorldGUI, D-GARA (AAAI 2026)✱, GUI-Robust, OpenApps/cua-bench✱.
- **Environments/benchmarks:** OSWorld (+Verified), WebArena, VisualWebArena, Mind2Web, AndroidWorld, WindowsAgentArena, WebLINX.
- **Grounding models:** SeeClick, ScreenSpot / -v2 / -Pro, OS-Atlas, UGround, Aguvis, ShowUI, UI-TARS / UI-TARS-1.5, OSWorld-G / Jedi, OpenCUA.
- **Agent memory / reuse:** Agent Workflow Memory (AWM), Synapse (trajectory-as-exemplar), AppAgent & AutoDroid (exploration-built app docs), Hi-Agent✱ (planner/grounder split).
- **Self-healing locators (direct prior art for ReGround):** WATER, ROBULA+, Similo/VON Similo, Healenium, UiPath Healing Agent.
- **Effect/verification:** "reflection"/verification steps in Agent S, UFO; process reward models for GUI agents.
- **Evaluation hygiene:** benchmark-gaming / checker-exploit studies (verify the Berkeley RDI reference).

---

## 9. Decisions and alternatives not taken

| Decision | Alternative | Why not |
|---|---|---|
| Real version pairs | Synthetic perturbations | Already crowded; the gap is real drift. Synthetic used only for the correlation study. |
| Middleware beside any agent | Fine-tune a drift-robust grounder | Needs data+GPUs; not deployable on closed API agents; brief says no retraining. |
| Main result in "deployed agent with A-memory" setting | Main result = zero-shot drift gap | Zero-shot live agents rarely hit stale coordinates; gap likely small/noisy (§1.1). |
| Cascade cheap→expensive | Always call a grounding model | Cost and latency; most drift is cosmetic/relocation, cheap tiers should solve it — and that fraction is itself a result. |
| a11y + vision fused anchors | DOM selectors only | Doesn't transfer to desktop/canvas; selectors are the classic broken baseline. |
| Effect verification as the final judge | Trust top-1 re-ground | A plausible wrong click (Archive vs Delete) is the main safety risk. |
| Web apps first, desktop last | Desktop first (more "CUA-like") | Docker/VNC desktop envs cost the most time; web gives results by W4. |
| Published binaries/images, pinned digests | Build from git tags | Old builds rot. |
| State-based checkers | VLM judges | Judges are gameable and noisy; the brief itself flags gamed leaderboards. |
| Gitea as first app | Nextcloud first | Gitea runs without Docker — buildable in this session today. |
| Grounder-level correlation study | Agent-level | 3–4 agents give a meaningless ρ. |
| Python + Playwright | Selenium / pure VNC for web | Playwright gives a11y snapshots, deterministic waits; already installed here. |

---

## 10. What I will build first in this session (after approval)

Constraint-aware: no GPU, no API key → build everything that needs no model, end-to-end on one real app.

User decisions (2026-11-02): model-free build first; code goes to a **new GitHub repo** (create with `gh repo create versiondrift --private` under the user's account, push on a feature branch, commit after each working milestone so nothing is lost if the container is reclaimed); headline = **A-memory setting**, zero-shot drift gap secondary.

1. Create `/home/user/versiondrift/` (git init), `pyproject.toml`, deps: playwright, pyyaml, pydantic, rapidocr-onnxruntime (later), pytest.
2. `envs/gitea.py`: download 2 pinned Gitea versions (e.g. 1.17.x and 1.22.x; final choice after checking changelogs and that the binaries run here), start each on its own port with SQLite, create admin user via CLI, seed a repo, reset by restoring a DB snapshot.
3. `drivers/playwright_driver.py`: screenshot, a11y snapshot (`page.accessibility` / aria snapshot), element-at-point, click/type, wait-for-settle.
4. 5–8 Gitea tasks with API-based checkers (create repo, add label, star repo, change repo description in settings, add collaborator, create issue with label, change user full name, create branch protection).
5. Scripted reference trajectories on A (Playwright-recorded as coordinate actions + captured anchors) and on B (for solvability + change labels).
6. `agents/coord_replay.py` (RPA floor) and `agents/selector_replay.py`.
7. `reground/` T0: anchor capture, SQLite store, multi-attribute similarity, staleness detector, effect capture/verify, destructive guard, middleware.
8. `harness/runner.py` + `analysis/metrics.py`; produce first table: coord-replay vs selector-replay vs ReGround-T0 on Gitea A→B, by change type.
9. Unit tests for similarity/staleness/effect on a tiny fixture.

Stop point for this session: that first table, honestly reported (including failures), plus a README. Model-based agents (Claude CUA, UI-TARS, OpenCUA) and T1–T3 come once a GPU box and API key exist.

---

## 11. Verification

- `pytest versiondrift/tests` passes.
- `python -m versiondrift.harness.cli run --app gitea --pair A,B --agent coord_replay` and `--agent reground_replay` both produce `runs/<id>/results.json`; checkers verified by running the human reference trajectory on each version (must pass 100%) and a no-op trajectory (must fail 100%).
- Manually inspect 3 re-grounded steps' before/after screenshots to confirm the right element was clicked.
- Re-run with a fresh DB reset to confirm determinism.

---

## 12. Next step: publish to https://github.com/sykeriin/VDrift  (added 2026-11-03)

Local repo `/home/user/versiondrift` has 3 commits on the default branch; `GH_TOKEN` in this container was invalid.
1. Attach the repo with `add_repo(owner=sykeriin, repo=VDrift, access=push)`; this is the supported way to get push credentials. Do not pre-check with curl/gh.
2. If attach succeeds: `git remote add origin <url>`; create branch `claude/initial-versiondrift` (do not push straight to the default branch); `git push -u origin claude/initial-versiondrift` (retry up to 4x with backoff on network errors only).
3. If access is denied: relay the tool's exact reason; user fixes it via claude.ai Settings -> Connectors / GitHub app install. No retry.
4. Verify with `git ls-remote origin`. No PR unless asked.
Note: repo name differs from the package/dir name (`versiondrift`); keep the package name, no renames.

---

## 13. Build iteration 2 (2026-11-03). Rule from user: keep building what is required, TEST AT THE END, always.

Code lives in `/home/user/versiondrift` (branch `claude/initial-versiondrift`, remote `origin` = sykeriin/VDrift; user asked for pushes to `main`). `/home/user/vdrift` is an empty clone, ignore it.

Work order (each step committed; push to `main` at the end after tests pass):
1. **Fix selector baseline** (`agents/replay.py`): it fails 5/9 on the SAME version, so it is invalid. Diagnose per failing step (dropdown items, modal buttons, suggestion links), fix until A->A = 9/9. Until then it is excluded from any claim.
2. **More real drift, same app**: download Gitea 1.19.4 and 1.21.x (add to `PORTS`, `BIN_DIR`), record trajectories on each, run all consecutive pairs (1.17.4->1.19.4, 1.19.4->1.21.x, 1.21.x->1.22.3) plus the long jump. Gives drift of different sizes without a new app.
3. **Held-out discipline**: tune ReGround thresholds (tau, tau_cand, tau_hi) on ONE pair only, report on the others. Principled fix for the observed miss ("Branch: main" -> "main": token containment in `name_sim`), reported as a post-hoc change with before/after numbers.
4. **Change-type labels**: auto-label each (task, step, pair) from demo anchors (same name+place = cosmetic; same name, moved = relocation; renamed = rename); report drift gap and success by type. `workflow_restructure`/`feature_removed` tasks are still missing: add 2-3 if a pair really has one, otherwise state that none were found.
5. **Docker feasibility check** (time-boxed): try starting `dockerd` here. If it works, add Nextcloud (2 versions) as app #2; if not, record that and try a second no-Docker app instead. No claims about app #2 until it runs.
6. Metrics additions: bootstrap CIs, per-pair tables, wrong-destructive-click count, ReGround tier/cost counts.
7. Update README honestly (what improved, what did not).

**Testing at the end (mandatory, report failures as-is):**
- `pytest tests` (add tests: selector fallback, no-op trajectory must FAIL every checker, reference trajectories must PASS on every version, label logic).
- Re-record all reference trajectories; every task must pass on every version.
- Full condition run; selector A->A must be 9/9 or the baseline stays marked invalid.
- Determinism: re-run one condition twice, results must match.
- Then `git push origin HEAD:main`.

Still blocked / not doable here: GPU and API key (model agents, T2/T3), `gh` auth (default branch must be changed by the user in GitHub settings).
