"""Tests for the ISA layer: each instruction maps to a documented
state transition and produces a documented result."""
import random

import pytest

from engine import ISA
from engine.question import create_simple_question


def test_state_def_then_load_then_store():
    isa = ISA()
    isa.state_def({"a", "b", "c"})
    isa.state_load({"a": 0.5, "b": 0.3, "c": 0.2})
    s = isa.state_manager.get_state()
    assert s.omega_global == {"a", "b", "c"}
    # state_store()/store_result() is deprecated and disabled: it
    # conflates a SET identifier with a micro-state name and can
    # silently produce a wrong post-collapse state. It now raises
    # instead of doing that silently; store_micro_states() (used by
    # Engine.collapse()) is the correct, real path.
    with pytest.raises(NotImplementedError):
        isa.state_store("a")


def test_full_transaction_via_isa():
    random.seed(0)
    isa = ISA()
    isa.state_def({"a", "b"})
    isa.state_load({"a": 0.6, "b": 0.4})

    q = create_simple_question("Q", {"X": {"a"}, "Y": {"b"}})
    isa.mw_begin()
    isa.mw_reg(q)
    # The ISA contract requires the engine to project before snapshot.
    isa.engine.project_all()
    snap = isa.mw_snapshot()
    assert "Q" in snap

    result = isa.mw_commit()
    assert result in {"X", "Y"}

    # The Q is invalidated as part of mw_commit (collapse atomically
    # invalidates every active Q). invalidate_qs() is a no-op after
    # commit but the post-condition still holds.
    assert q.is_invalidated()


def test_mw_begin_outside_idle_raises():
    isa = ISA()
    isa.state_def({"a", "b"})
    isa.state_load({"a": 0.5, "b": 0.5})
    isa.mw_begin()
    with pytest.raises(RuntimeError):
        isa.mw_begin()
