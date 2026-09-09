# Observer-Defined Reality Engine — Build & Verification

> *Quality gate for this project. This file answers:
> "Is this project buildable, runnable, and behaving as documented?"*

## 1. Build

### 1.1 Primary build path

- **Platform**: Python 3.10, 3.11, or 3.12 (CI matrix in `.github/workflows/python-tests.yml`). Locally verified on Python 3.14 — passes.
- **Toolchain**: `pip` + `venv` (no compiled extensions, no setup.py, no pyproject.toml). The project is run "in place" from a checkout; it is *not* installed as a package.
- **Command** (from the repository root):

  ```bash
  python -m venv .venv
  # Windows: .venv\Scripts\activate     |     POSIX: source .venv/bin/activate
  pip install -r requirements.txt       # no-op: file lists no required packages
  pip install -r tests/requirements.txt # installs pytest>=7.0
  ```

- **Output**: No build artefacts. The `engine/` directory is the importable package. It must be importable from the working directory (i.e. `python` must be invoked from the repo root, or `PYTHONPATH` must contain the repo root, or the suite must be run via `python -m`). Tests rely on `tests/conftest.py` to inject the repo root into `sys.path`.

### 1.2 Alternative build paths

- **Run as a module** (no `PYTHONPATH` plumbing needed):
  ```bash
  python -m engine
  ```
  Executes `engine/__main__.py`, which itself runs the four bundled examples.
- **Editable install** is *not* supported — there is no `setup.py` or `pyproject.toml`. Reported as a fragility in section 3.1.
- **CI build** (GitHub Actions): `.github/workflows/python-tests.yml` runs on push/PR to `main`/`master`, installs `tests/requirements.txt`, runs `pytest tests/ -v`, then smoke-tests `examples/basic_example.py`.

### 1.3 Dependencies

- **Required (runtime)**: None. `requirements.txt` is a commented-only file; the engine is pure standard-library Python (`enum`, `dataclasses`, `typing`, `uuid`, `random`).
- **Required (testing)**: `pytest>=7.0` (from `tests/requirements.txt`).
- **Optional**: `mypy>=1.0.0` is mentioned as a commented-out hint in `requirements.txt`; no type-check job is wired into CI.

## 2. Expected behavior

### 2.1 What this project does

The engine implements a strict five-phase state machine (`IDLE → MW_OPEN → PROJECTION → DECISION_BOUNDARY → POST_COLLAPSE → IDLE`) for weighted-set selection under coordinated observation. A measurement cycle:

1. Defines a state space Ω and a weight distribution μ over it.
2. Opens a Measurement Window (MW) and registers one or more `Question`s, each of which partitions Ω into named subspaces.
3. Projects every registered Q against a frozen snapshot of μ.
4. Performs an atomic weighted-random collapse to a single result, invalidates all registered Qs, and replaces μ with a uniform distribution over the surviving micro-states (a Dirac delta when only one micro-state survives).
5. Appends the (MW snapshot, result) pair to an immutable history log; `len(history)` is the engine's notion of time.

The engine is presented as a conceptual / educational artefact — explicitly *not* a quantum simulator and *not* a security primitive.

### 2.2 Acceptance criteria

- [ ] `pip install -r tests/requirements.txt` succeeds in a clean venv on Python 3.10 / 3.11 / 3.12.
- [ ] `python -m pytest tests/ -v` from the repo root reports **25 passed** in < 5 s.
- [ ] `python -m engine` prints four labelled example sections ("Example 1" … "Example 4") and exits 0.
- [ ] The README "Quick start" snippet runs without error in a REPL launched from the repo root and prints a collapsed result in `{"E1", "E2"}` and a post-collapse μ whose weights are uniform.
- [ ] Phase invariants hold: each of `register_question`, `project_all`, `collapse`, and a second `open_measurement_window` raises `RuntimeError` when invoked outside its legal phase.
- [ ] Determinism contract: two engines seeded with the same `random.seed(...)` and given the same questions return identical results (covered by `test_collapse_is_deterministic_given_seed`).
- [ ] `History` length increases by exactly 1 per completed cycle (covered by `test_invariant_history_grows_by_one_per_cycle`).

### 2.3 Manual verification

Launched from the repo root so that `engine/` is importable:

```bash
$ cd /path/to/ObserverRealityEngine
$ python -m engine
```

Expected output (truncated; exact `result` values vary because the example does not seed the RNG):

```
============================================================
ObserverRealityEngine - Examples
============================================================

============================================================
Example 1: Simple Measurement
============================================================
Initial state: {'w1': 0.25, 'w2': 0.4, 'w3': 0.35}
Collapsed result: E2
Final state: {'w2': 0.5, 'w3': 0.5}
Time (measurements): 1
...
============================================================
All examples completed!
============================================================
```

REPL smoke-test (mirrors the README "Quick start"; uses ASCII labels because the bundled examples do — see section 3.1):

```python
>>> import random; random.seed(0)
>>> from engine import Engine
>>> from engine.question import create_simple_question
>>> e = Engine()
>>> e.state_manager.define_omega({"w1", "w2", "w3"})
>>> e.state_manager.load_weights({"w1": 0.25, "w2": 0.40, "w3": 0.35})
>>> Q_A = create_simple_question("Q_A", {"E1": {"w1"}, "E2": {"w2", "w3"}})
>>> result = e.execute_measurement_cycle([Q_A])
>>> result in {"E1", "E2"}
True
>>> set(e.state_manager.get_mu().values())   # uniform after collapse
{0.5}                                         # or {1.0} if E1 was selected
>>> len(e.history)
1
```

### 2.4 Automated verification

```bash
python -m pytest tests/ -v
```

Pass indicator (locally observed, Python 3.14, pytest 9.0.3):

```
tests/test_engine.py  ... 15 passed
tests/test_history.py ...  3 passed
tests/test_isa.py     ...  3 passed
tests/test_state.py   ...  4 passed
============================= 25 passed in 0.18s ==============================
```

The 25 tests cover: phase-transition guard rails, the five named invariants (single-MW-single-collapse, state immutability during projection, Q invalidation on collapse, atomic collapse, history completeness), weight normalisation, Dirac-delta post-collapse state, RNG determinism under seed, and the ISA-level transaction path.

## 3. Alternatives & improvements

### 3.1 Known fragilities

- `examples/basic_example.py` prepends the repo root to `sys.path` at import time (mirroring `engine/__main__.py`), so `python examples/basic_example.py` works directly from the repo root with no `PYTHONPATH` plumbing needed.
- The README "Quick start" and `examples/basic_example.py` both use the same ASCII micro-state ids (`w1`/`w2`/`w3`), so copy-pasting between them is safe. Greek Ω/ω appear only in the conceptual prose as math notation, never in runnable code.
- Root `requirements.txt` is intentionally empty (pure stdlib, no runtime deps) and points readers at `tests/requirements.txt` for the actual test dependency (`pytest>=7.0`).
- **No `setup.py` / `pyproject.toml`.** The project cannot be `pip install`-ed or `pip install -e`-d; downstream consumers must vendor the `engine/` directory or set `PYTHONPATH`. ⚠️
- **CI tests `head -40` of the example output.** On a system without `head` (native Windows `cmd.exe`), the smoke-test step would fail; CI is pinned to `ubuntu-latest`, so this is currently safe but coupled to the runner OS.
- **No thread safety.** Documented in README "Limitations" — the phase state machine assumes single-threaded use.
- **History is in-memory only.** Documented; no persistence layer.

### 3.2 Fallbacks

- If `requirements.txt` somehow does declare a package that cannot install, the engine still runs — it has no runtime imports outside the standard library.
- If `pytest` is unavailable, the invariants can be exercised manually via the four bundled examples (`python -m engine`); each example prints the pre- and post-collapse state and the history length, which together cover invariants 1, 2, 4, and 5 by inspection.
- If the user is on Python ≥ 3.13 (outside the CI matrix), the test suite still passes locally — there are no version-specific APIs in use.

### 3.3 Roadmap

- **Short-term (≤ 1 day)**:
  - Either delete the empty `requirements.txt` and point the README at `tests/requirements.txt`, or move `pytest` into the root file.
- **Medium-term (≤ 1 week)**:
  - Add a minimal `pyproject.toml` (PEP 621) so the engine is `pip install`-able and editable installs work; CI can then drop the `PYTHONPATH` assumption.
  - Add a `tox.ini` or matrix-aware `nox` config so contributors can reproduce the CI matrix locally.
  - Wire `mypy` into CI (the hint already exists in `requirements.txt`).
- **Long-term**:
  - Optional persistent history backend (SQLite or JSONL) behind the existing `History` interface.
  - Property-based tests (Hypothesis) for the invariants — Hypothesis is already on the local box (visible in the pytest banner) but not declared as a dev dep.
  - Formalise the five invariants in a model checker (TLA+ / Alloy) per the README "no proof of correctness" caveat.

## 4. Sanity check

| Check | Status | Notes |
|-------|--------|-------|
| README documents build | ✅ | "Testing" section gives `pip install -r tests/requirements.txt; python -m pytest tests/ -v`. |
| Build files present | ⚠️ | Root `requirements.txt` now clearly states "no runtime dependencies (pure stdlib)" and points to `tests/requirements.txt` (the real test-dep manifest). Still no `setup.py`/`pyproject.toml` — the project is run in-place via `python -m engine` (documented design). |
| Build files internally consistent | ✅ | Root `requirements.txt` (no runtime deps) and `tests/requirements.txt` (pytest) agree and no longer mislead; README Quick-start ids match the example. |
| Source structure matches README | ✅ | `engine.{state,question,measurement_window,history,isa,core}` — every module the README's Architecture table names exists with the documented role. `python examples/basic_example.py` from the repo root runs as the README documents. |
| Tests exist | ✅ | 25 tests across `test_engine.py`, `test_history.py`, `test_isa.py`, `test_state.py`; conftest patches `sys.path`. |
| Test invocation documented | ✅ | README "Testing" + `.github/workflows/python-tests.yml` both show `python -m pytest tests/ -v`. |
| Output artifacts named in build files | ✅ (N/A) | Pure-Python library, no compiled artefacts; the importable `engine/` package is the deliverable. CI smoke-tests the bundled example as the runnable artefact. |
