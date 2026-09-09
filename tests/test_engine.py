"""Tests for the phase state machine and the five invariants.

These tests use a fixed RNG seed so that the collapse result is
deterministic across runs.
"""
import random

import pytest

from engine import Engine, Phase
from engine.question import create_simple_question


def _basic_engine(seed: int = 0):
    random.seed(seed)
    engine = Engine()
    engine.state_manager.define_omega({"ω1", "ω2", "ω3"})
    engine.state_manager.load_weights({"ω1": 0.25, "ω2": 0.40, "ω3": 0.35})
    return engine


def _qA():
    return create_simple_question(
        "Q_A",
        {"E1": {"ω1"}, "E2": {"ω2", "ω3"}},
    )


def _qB():
    return create_simple_question(
        "Q_B",
        {"F1": {"ω2"}, "F2": {"ω1", "ω3"}},
    )


def test_engine_starts_idle():
    engine = _basic_engine()
    assert engine.is_idle()
    assert engine.phase is Phase.IDLE


def test_open_window_transitions_to_mw_open():
    engine = _basic_engine()
    engine.open_measurement_window()
    assert engine.phase is Phase.MW_OPEN
    assert engine.active_mw is not None


def test_cannot_open_window_twice():
    engine = _basic_engine()
    engine.open_measurement_window()
    with pytest.raises(RuntimeError, match='Cannot open MW'):
        engine.open_measurement_window()


def test_register_outside_mw_open_raises():
    engine = _basic_engine()
    with pytest.raises(RuntimeError, match='Cannot register Q'):
        engine.register_question(_qA())


def test_project_outside_mw_open_raises():
    engine = _basic_engine()
    with pytest.raises(RuntimeError, match='Cannot project'):
        engine.project_all()


def test_collapse_outside_projection_raises():
    engine = _basic_engine()
    engine.open_measurement_window()
    engine.register_question(_qA())
    with pytest.raises(RuntimeError, match='Cannot collapse'):
        engine.collapse()


def test_full_cycle_returns_to_idle():
    engine = _basic_engine(seed=42)
    result = engine.execute_measurement_cycle([_qA()])
    assert engine.is_idle()
    assert result in {"E1", "E2"}


def test_invariant_single_mw_single_collapse():
    """An MW that has collapsed cannot be re-collapsed: after the cycle
    the engine is IDLE with no active window."""
    engine = _basic_engine(seed=1)
    engine.execute_measurement_cycle([_qA()])
    assert engine.active_mw is None
    assert engine.is_idle()


def test_invariant_questions_invalidated_atomically():
    """Every Q registered to a window is invalidated by the time the
    cycle returns."""
    engine = _basic_engine(seed=2)
    q1, q2 = _qA(), _qB()
    engine.execute_measurement_cycle([q1, q2])
    assert q1.is_invalidated()
    assert q2.is_invalidated()


def test_invariant_state_changes_only_after_collapse():
    """Until collapse occurs, get_mu() reports the pre-collapse
    weights. After collapse, the state is a DIRAC delta on the
    surviving micro-states."""
    engine = _basic_engine(seed=3)
    pre = dict(engine.state_manager.get_mu())
    engine.execute_measurement_cycle([_qA()])
    post = dict(engine.state_manager.get_mu())
    assert pre != post
    # DIRAC: every surviving micro-state has equal weight.
    weights = set(post.values())
    assert len(weights) == 1, f'post-collapse weights are not uniform: {post}'


def test_invariant_history_grows_by_one_per_cycle():
    engine = _basic_engine(seed=4)
    assert len(engine.history) == 0
    engine.execute_measurement_cycle([_qA()])
    assert len(engine.history) == 1
    engine.execute_measurement_cycle([_qA()])
    assert len(engine.history) == 2


def test_engine_handles_two_questions_in_same_window():
    engine = _basic_engine(seed=5)
    result = engine.execute_measurement_cycle([_qA(), _qB()])
    # Result must be a SET id from either partition.
    assert result in {"E1", "E2", "F1", "F2"}


def test_collapse_is_deterministic_given_seed():
    """Two runs with the same seed and same input produce the same
    result. (Pins the collapse RNG contract for downstream code.)"""
    engine_a = _basic_engine(seed=1234)
    engine_b = _basic_engine(seed=1234)
    res_a = engine_a.execute_measurement_cycle([_qA()])
    res_b = engine_b.execute_measurement_cycle([_qA()])
    assert res_a == res_b


def test_post_collapse_state_micro_states_subset_of_original_omega():
    engine = _basic_engine(seed=6)
    engine.execute_measurement_cycle([_qA()])
    surviving = engine.state_manager.get_state().omega_global
    original = {"ω1", "ω2", "ω3"}
    assert surviving.issubset(original)
    assert len(surviving) >= 1


def test_invalidated_question_cannot_be_reregistered():
    """A Q that has been through a collapse must not be re-registered
    to a fresh window."""
    engine = _basic_engine(seed=7)
    q = _qA()
    engine.execute_measurement_cycle([q])
    assert q.is_invalidated()
    # Open a new window and try to re-register the dead Q.
    engine.open_measurement_window()
    ok = engine.register_question(q)
    assert ok is False
