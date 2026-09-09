"""Tests for the history log."""
import random

from engine import Engine
from engine.question import create_simple_question


def _engine():
    random.seed(0)
    engine = Engine()
    engine.state_manager.define_omega({"a", "b"})
    engine.state_manager.load_weights({"a": 0.5, "b": 0.5})
    return engine


def _q():
    return create_simple_question("Q", {"X": {"a"}, "Y": {"b"}})


def test_history_time_equals_measurement_count():
    engine = _engine()
    assert engine.history.get_time() == 0
    engine.execute_measurement_cycle([_q()])
    assert engine.history.get_time() == 1
    engine.execute_measurement_cycle([_q()])
    assert engine.history.get_time() == 2


def test_history_entries_contain_mw_snapshot_and_result():
    engine = _engine()
    engine.execute_measurement_cycle([_q()])
    entries = engine.history.get_all()
    assert len(entries) == 1
    e = entries[0]
    assert e.result in {"X", "Y"}
    assert e.mw_snapshot is not None
    # measurement_number is the *index* of the entry (0-based for the
    # first collapse); the test pins the contract.
    assert e.measurement_number == 0


def test_history_window_returns_subsequence():
    engine = _engine()
    for _ in range(5):
        engine.execute_measurement_cycle([_q()])
    win = engine.history.get_window(n=2)
    assert len(win.entries) == 2
    # 5 cycles -> measurement_numbers 0..4. Last is 4.
    assert win.entries[-1].measurement_number == 4
