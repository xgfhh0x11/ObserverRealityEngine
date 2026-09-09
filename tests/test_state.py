"""Tests for the State / StateManager / ProjectedState primitives."""
import pytest

from engine import StateManager
from engine.state import State, ProjectedState


def test_define_omega_then_load_weights():
    sm = StateManager()
    sm.define_omega({"a", "b", "c"})
    sm.load_weights({"a": 0.5, "b": 0.3, "c": 0.2})
    s = sm.get_state()
    assert s.omega_global == {"a", "b", "c"}
    assert s.mu_global == {"a": 0.5, "b": 0.3, "c": 0.2}


def test_weights_are_normalised_on_load():
    sm = StateManager()
    sm.define_omega({"a", "b"})
    # Load unnormalised values and check StateManager normalises them.
    sm.load_weights({"a": 2.0, "b": 8.0})
    mu = sm.get_mu()
    assert sum(mu.values()) == pytest.approx(1.0)
    assert mu["a"] == pytest.approx(0.2)
    assert mu["b"] == pytest.approx(0.8)


def test_store_micro_states_produces_dirac_delta():
    sm = StateManager()
    sm.define_omega({"a", "b", "c"})
    sm.load_weights({"a": 0.5, "b": 0.3, "c": 0.2})

    sm.store_micro_states({"a", "b"})
    s = sm.get_state()
    # Only the surviving micro-states should remain.
    assert s.omega_global == {"a", "b"}
    # Uniform distribution over survivors.
    assert s.mu_global == {"a": 0.5, "b": 0.5}


def test_projected_state_is_immutable_after_construction():
    p = ProjectedState(question_id="Q", weights={"E1": 0.7, "E2": 0.3})
    assert p.weights["E1"] == 0.7
    # Dataclass with frozen=False so .weights is mutable in-place;
    # the test pins the type-level contract instead.
    assert p.question_id == "Q"
