# Observer-Defined Reality Engine

A small, transaction-oriented Python library implementing a strict
state-machine for **weighted-set selection under coordinated
observation**. The construction is inspired by the von-Neumann picture
of quantum measurement but is presented here as a concrete engineering
artefact: an instruction set, a phase state machine, and a Python API
that enforces them.

> *Reality emerges from questions, not from systems.*

The slogan is the design intent: in this engine, a *Question* is the
operator that turns a state with multiple potentials into a single
collapsed result; the engine guarantees that no Question can read a
result it itself helped produce, that all Questions registered to the
same window observe the same pre-collapse state, and that collapse is
atomic.

---

## What the engine does, in one sentence

Given a state described as a weighted set of micro-states and a set of
Questions that partition that state into subspaces, the engine performs
a single, atomic, weighted-random selection of one subspace and
collapses the state to a uniform distribution over the corresponding
micro-states, recording the entire transaction in an immutable history
log.

That sentence is the whole specification. Everything else is the
machinery that makes it true.

## Architecture

### Phase state machine

```
IDLE → MW_OPEN → PROJECTION → DECISION_BOUNDARY → POST_COLLAPSE → IDLE
```

Each transition is gated by the engine. Operations performed outside the
phase they belong to raise `RuntimeError`. The states are:

| Phase | What is legal | What is illegal |
|---|---|---|
| `IDLE` | Open a measurement window | Register a question, modify state |
| `MW_OPEN` | Register questions (frozen on registration) | Modify state, collapse |
| `PROJECTION` | Project every registered Q against the pre-collapse state | Add or remove Qs, mutate state |
| `DECISION_BOUNDARY` | Atomic collapse (single operation) | Anything else |
| `POST_COLLAPSE` | Update state, append to history | Re-collapse, re-project |

### Core components

| Module | Role |
|---|---|
| `engine.state` | `State`, `ProjectedState`, `StateManager` — the weighted-set primitives |
| `engine.question` | `Question` — partition rule + visibility + lifetime + (optional) correlation policy and weight modifier |
| `engine.measurement_window` | The transaction object that holds the active question set and the projected set |
| `engine.history` | Immutable log of `(MW snapshot, result)` tuples; defines the engine's notion of time |
| `engine.isa` | A low-level instruction set (`STATE.DEF`, `STATE.LOAD`, `Q.DEF`, `Q.EXEC`, `MW.BEGIN`, `MW.REG`, `MW.SNAPSHOT`, `MW.COMMIT`, …) |
| `engine.core` | The phase state machine that wires the above together and exposes `execute_measurement_cycle()` |

### Key invariants

The engine enforces five invariants. They are the engineering content
of the project; everything else is bookkeeping around them.

1. **Single MW = single collapse.** A measurement window cannot be
   reused after collapse.
2. **State immutability during a window.** The state observed by every
   registered Q at projection time is the state at MW open.
3. **Question scoping.** A Q cannot read or be referenced outside the
   MW that registered it.
4. **Atomic collapse.** Selection, invalidation of all active Qs, state
   update, and history append happen in a single observable step.
5. **History completeness.** No history entry can be written without
   the corresponding MW snapshot.

## Quick start

```python
from engine import Engine
from engine.question import create_simple_question

engine = Engine()
engine.state_manager.define_omega({"w1", "w2", "w3"})
engine.state_manager.load_weights({"w1": 0.25, "w2": 0.40, "w3": 0.35})

Q_A = create_simple_question(
    "Q_A",
    {"E1": {"w1"}, "E2": {"w2", "w3"}},  # "is it A?"
)

result = engine.execute_measurement_cycle([Q_A])
print(f"collapsed: {result}")
print(f"state after collapse: {engine.state_manager.get_mu()}")
```

For two simultaneous Qs in the same window, and for a low-level ISA
example, see `examples/basic_example.py`.

## Running the example

```bash
python examples/basic_example.py
```

The example walks through:
- a single-question measurement,
- two questions in the same MW (the engine combines their projections
  before selection),
- a low-level ISA program equivalent to the high-level call,
- a sequence of three measurements showing how time = `len(history)`.

## Testing

```bash
pip install -r tests/requirements.txt
python -m pytest tests/ -v
```

Continuous integration runs the suite on every push under
`.github/workflows/python-tests.yml` (Python 3.10 / 3.11 / 3.12).

## Scope and posture

This is a **conceptual reference implementation**, not a quantum
simulator or a probabilistic-programming engine. It does not model
amplitude interference, density matrices, or unitary evolution between
measurements. The single feature it commits to is *the integrity of the
measurement transaction itself*: the five invariants above, enforced
deterministically.

What it is useful for:
- teaching the von-Neumann measurement picture with executable code,
- building DSLs over state-with-potentials that need strict
  observer/state separation,
- reasoning about transactional semantics in a non-cryptographic
  setting where commit boundaries matter (workflow engines, decision
  trees, observability pipelines).

What it is *not* useful for:
- as a quantum-circuit simulator,
- as a foundation for hardware-level constant-time analysis (see
  CTPhys for that),
- as a security primitive (no adversary model is assumed).

## Limitations

- **Single-threaded.** The phase state machine is not thread-safe.
  Concurrent measurement windows are explicitly out of scope.
- **No persistence.** History lives in memory.
- **No interference / amplitudes.** All weights are non-negative reals;
  the model is purely classical-stochastic.
- **No proof of correctness.** The invariants are enforced by runtime
  checks and unit tests, not by a formal model checker.

## Documentation

- `docs/architecture.md` — engineering reference: state machine
  details, ISA semantics, component contracts.
- `docs/formal_model.md` — mathematical formalisation: state space,
  projection, collapse, entropy, invariants.

## References

- J. von Neumann, *Mathematische Grundlagen der Quantenmechanik*,
  Springer, 1932. (Measurement postulate as transactional projection.)
- P. Busch, P. Lahti, P. Mittelstaedt, *The Quantum Theory of
  Measurement*, Springer, 1996.
- J. G. Cramer, *The Transactional Interpretation of Quantum
  Mechanics*, Reviews of Modern Physics 58 (1986). (Conceptual prior
  for the "transaction" framing used here.)
- C. Shannon, *A Mathematical Theory of Communication*, Bell System
  Technical Journal, 1948. (Entropy as information measure; underpins
  the engine's entropy-evolution view of time.)

## Status

Research / educational. The implementation is small, pure-Python, and
intended to be read straight through. No external dependencies.

## License

MIT — see `LICENSE`.
