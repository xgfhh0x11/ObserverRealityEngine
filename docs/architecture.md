# Architecture

This document is the engineering reference for the Observer-Defined
Reality Engine. It is paired with `docs/formal_model.md`, which states
the same content as mathematics. Where the formal model says *what*,
this document says *how*.

## Layered structure

```
+------------------------------------------+
|  High-level API: engine.core.Engine      |
|  - execute_measurement_cycle(questions)  |
|  - phase state machine                   |
+------------------------------------------+
                 |
                 v
+------------------------------------------+
|  ISA: engine.isa.ISA                     |
|  - STATE.DEF / STATE.LOAD / STATE.STORE  |
|  - Q.DEF / Q.EXEC                        |
|  - MW.BEGIN / MW.REG / MW.SNAPSHOT /     |
|    MW.COMMIT                             |
|  - INVALIDATE.QS / HISTORY.APPEND        |
+------------------------------------------+
                 |
                 v
+------------------------------------------+
|  Core types                              |
|  - engine.state.{State, StateManager,    |
|    ProjectedState}                       |
|  - engine.question.Question              |
|  - engine.measurement_window.            |
|    MeasurementWindow                     |
|  - engine.history.History                |
+------------------------------------------+
```

`engine.core.Engine` is what most callers use. The ISA is exposed as a
flat instruction set for callers that want to write transactional
programs in a deterministic, instruction-by-instruction style; it is
the layer the high-level engine itself sits on top of.

## Phase state machine

```
IDLE → MW_OPEN → PROJECTION → DECISION_BOUNDARY → POST_COLLAPSE → IDLE
```

The transitions are:

| From | To | Trigger | Side effects |
|---|---|---|---|
| IDLE | MW_OPEN | `open_measurement_window()` | A fresh `MeasurementWindow` is created |
| MW_OPEN | MW_OPEN | `register_question(q)` | `q` is added to the window's active set; `q` becomes immutable |
| MW_OPEN | PROJECTION | `project_all()` | Every registered Q's `project()` is invoked against the pre-collapse state |
| PROJECTION | DECISION_BOUNDARY | `collapse()` | Aggregated weights are computed; a single result SET is sampled |
| DECISION_BOUNDARY | POST_COLLAPSE | (continuation of `collapse()`) | All active Qs are invalidated atomically; the state is replaced with the DIRAC delta over the result SET's micro-states |
| POST_COLLAPSE | IDLE | (continuation of `collapse()`) | The MW snapshot + result are appended to history; the MW is destroyed |

Operations performed in the wrong phase raise `RuntimeError` with a
phase-name in the message. There is no recovery path.

## Component contracts

### State (`engine.state.State`)

```python
@dataclass
class State:
    omega_global: Set[str]        # all possible micro-states
    mu_global: Dict[str, float]   # weight of each micro-state; sums to 1.0
```

State is mutable in principle, but only `StateManager` is permitted to
mutate it. After a measurement cycle, the state becomes a DIRAC delta:
the surviving micro-states all carry weight `1 / |Ω_new|`.

### Question (`engine.question.Question`)

A Question carries six parameters that the engine *transports but does
not interpret*:

| Parameter | Required | Role |
|---|---|---|
| `partition_rule` | yes | `State -> Dict[SET_id, Set[micro_state]]` — exhaustive, disjoint partition of the current state |
| `history_scope` | yes | `History -> History` — selects the slice of history this Q is permitted to read |
| `correlation_policy` | no | `(own_projection, all_projections, history) -> adjusted_weights` |
| `weight_modifier` | no | `weights -> weights` — final user-supplied bias |
| `lifetime` | yes | `MW_ONLY` / `MULTI_MW` / `UNTIL_INVALIDATED` |
| `visibility` | yes | `PRIVATE` / `SHARED` / `COMPETING` |

`PRIVATE` Qs cannot see other Qs' projections; `SHARED` and
`COMPETING` can. The engine does not enforce semantic conflict between
competing Qs — it just aggregates their projected weights and lets the
weighted-random selection make the call.

### MeasurementWindow (`engine.measurement_window.MeasurementWindow`)

A `MeasurementWindow` owns:
- a unique id and an open-time timestamp,
- the list of active Qs,
- the projected set (a dict from Q id to `ProjectedState`),
- a snapshot operation for history.

Once collapse occurs, the window is destroyed. There is no resurrect
path.

### History (`engine.history.History`)

A sequence of `(timestamp, MW_snapshot, result, measurement_number)`
records. Time in the engine is defined as `len(history)` — every
collapse advances time by one.

`history_scope` parameters on Qs operate against `History` and return
a (possibly smaller) `History`-shaped object. The engine itself never
filters history.

### ISA (`engine.isa.ISA`)

The instruction set is documented inline in `engine/isa.py`. The
high-level `Engine.execute_measurement_cycle()` is exactly equivalent
to:

```
MW.BEGIN
MW.REG q_1
MW.REG q_2
...
MW.SNAPSHOT          # PROJECTION
MW.COMMIT            # DECISION_BOUNDARY -> POST_COLLAPSE
INVALIDATE.QS
STATE.STORE          # write the DIRAC delta
HISTORY.APPEND
```

A program in the ISA is a list of dicts, each carrying an `op` key
and op-specific arguments; `ISA.execute_program(program)` walks the
list and applies each instruction.

## Collapse, in detail

`Engine.collapse()` is the only function that crosses the
DECISION_BOUNDARY. Its body is:

1. **Aggregate weights.** For each Q in the active set and each SET in
   that Q's projection, sum the weight into a global
   `Dict[SET_id, float]`.
2. **Normalise.** Divide every entry by the total; the result is a
   categorical distribution over SET ids.
3. **Sample.** `random.choices(keys, weights=values, k=1)[0]`.
4. **Map SET to micro-states.** Walk the active Qs until one whose
   partition contains the chosen SET id is found; that Q's
   `partition_rule(current_state)[result_set]` gives the surviving
   micro-states.
5. **Invalidate.** Mark every active Q as `_invalidated = True`; any
   future call to `project()` or `partition_rule()` on those Qs raises.
6. **Update state.** Replace `state.omega_global` with the surviving
   micro-states and set `state.mu_global` to the uniform distribution
   over them.
7. **Append history.** Record a complete MW snapshot, the result, and
   the new measurement number.

Steps 3-7 are performed inside a single method without yielding to
external code, so from the caller's perspective the collapse appears
atomic. The engine is not thread-safe; this is the assumption that
makes the atomicity argument trivially true.

## Error semantics

The engine raises:

- `RuntimeError` for phase violations ("cannot register Q: engine in
  IDLE phase").
- `ValueError` for parameter violations ("question Q_X is already
  invalidated", "weights do not sum to 1").
- Standard library exceptions otherwise (e.g. `KeyError` for an
  unknown micro-state).

There is no recovery from a phase violation. The caller is expected
to throw away the engine state and start a fresh measurement cycle.

## Extension points

Two surfaces are deliberately left open for callers:

1. **Custom `partition_rule`s.** Any callable that returns an
   exhaustive disjoint partition is acceptable.
2. **Custom `correlation_policy`s.** Any callable matching the
   signature is plugged into projection unchanged; the engine never
   inspects what it does.

In particular, anti-correlation, history-weighted bias, and
suppression policies between competing Qs can all be implemented in
the correlation policy without touching the core engine.

## What is intentionally *not* in this engine

- Density matrices, amplitudes, interference. All weights are
  non-negative reals.
- Continuous state spaces. `Ω` is always a finite set.
- Asynchronous / multi-threaded operation. Single-threaded by design.
- Persistence. The history lives in memory; serialise it yourself if
  you need durability.
- Distributed coordination. There is no notion of "remote MW".
