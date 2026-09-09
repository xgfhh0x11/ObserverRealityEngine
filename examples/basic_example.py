"""
Basic Example - Demonstrates the ObserverRealityEngine

This example shows:
1. State definition and loading
2. Question creation
3. Measurement window cycle
4. Collapse and history

Run from the repository root with `python examples/basic_example.py`.
The sys.path patch below lets the script find the local `engine` package
without requiring `pip install -e .` or `PYTHONPATH=.`.
"""

import os
import sys

# Add the repository root (parent of examples/) to sys.path so the
# local `engine` package resolves when this file is run as a script.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import Engine, StateManager, History
from engine.question import create_simple_question, Visibility
from engine.isa import ISA


def example_1_simple_measurement():
    """
    Example 1: Simple measurement with one question
    
    State: {ω1: 0.25, ω2: 0.40, ω3: 0.35}
    Question: "is it A?" -> {ω1} vs {ω2, ω3}
    """
    print("=" * 60)
    print("Example 1: Simple Measurement")
    print("=" * 60)
    
    # Create engine
    engine = Engine()
    
    # Define state space
    engine.state_manager.define_omega({"w1", "w2", "w3"})
    
    # Load weights
    engine.state_manager.load_weights({
        "w1": 0.25,
        "w2": 0.40,
        "w3": 0.35
    })
    
    print(f"Initial state: {engine.state_manager.get_mu()}")
    
    # Create question: "A mi?" -> {w1} vs {w2, w3}
    Q_A = create_simple_question(
        "Q_A",
        {
            "E1": {"w1"},  # A
            "E2": {"w2", "w3"}  # not-A
        }
    )
    
    # Execute measurement cycle
    result = engine.execute_measurement_cycle([Q_A])
    
    print(f"Collapsed result: {result}")
    print(f"Final state: {engine.state_manager.get_mu()}")
    print(f"Time (measurements): {len(engine.history)}")
    print()


def example_2_multiple_questions():
    """
    Example 2: Multiple questions in same MW
    
    Same state, but two different questions:
    - Q_A: {ω1} vs {ω2, ω3}
    - Q_B: {ω2} vs {ω1, ω3}
    """
    print("=" * 60)
    print("Example 2: Multiple Questions in Same MW")
    print("=" * 60)
    
    engine = Engine()
    
    # Define and load state
    engine.state_manager.define_omega({"w1", "w2", "w3"})
    engine.state_manager.load_weights({
        "w1": 0.25,
        "w2": 0.40,
        "w3": 0.35
    })
    
    print(f"Initial state: {engine.state_manager.get_mu()}")
    
    # Create two questions
    Q_A = create_simple_question(
        "Q_A",
        {"E1": {"w1"}, "E2": {"w2", "w3"}}
    )
    
    Q_B = create_simple_question(
        "Q_B",
        {"F1": {"w2"}, "F2": {"w1", "w3"}}
    )
    
    # Execute measurement cycle
    result = engine.execute_measurement_cycle([Q_A, Q_B])
    
    print(f"Collapsed result: {result}")
    print(f"Final state: {engine.state_manager.get_mu()}")
    print(f"Time: {len(engine.history)}")
    print()


def example_3_isa_program():
    """
    Example 3: Using ISA to execute a program
    
    This demonstrates the low-level ISA operations.
    """
    print("=" * 60)
    print("Example 3: ISA Program Execution")
    print("=" * 60)
    
    isa = ISA()
    
    # Define partition rules
    def partition_A(state):
        return {"E1": {"w1"}, "E2": {"w2", "w3"}}
    
    def partition_B(state):
        return {"F1": {"w2"}, "F2": {"w1", "w3"}}
    
    def history_scope_all(history):
        return history.get_window()
    
    # Execute ISA program
    program = [
        {'op': 'STATE.DEF', 'omega': {"w1", "w2", "w3"}},
        {'op': 'STATE.LOAD', 'mu': {"w1": 0.25, "w2": 0.40, "w3": 0.35}},
        {'op': 'Q.DEF', 'id': 'Q_A', 'partition_rule': partition_A, 
         'history_scope': history_scope_all},
        {'op': 'Q.DEF', 'id': 'Q_B', 'partition_rule': partition_B,
         'history_scope': history_scope_all},
        {'op': 'MW.BEGIN'},
        {'op': 'MW.REG', 'question': 'Q_A'},
        {'op': 'MW.REG', 'question': 'Q_B'},
    ]
    
    # Execute up to projection
    isa.execute_program(program)
    
    # Project
    projected = isa.engine.project_all()
    print("Projected states:")
    for q_id, proj in projected.items():
        print(f"  {q_id}: {proj.weights}")
    
    # Commit
    result = isa.mw_commit()
    print(f"\nCollapsed result: {result}")
    print(f"Final state: {isa.state_manager.get_mu()}")
    print(f"Time: {len(isa.history)}")
    print()


def example_4_sequential_measurements():
    """
    Example 4: Sequential measurements
    
    Shows how reality evolves through multiple measurements.
    """
    print("=" * 60)
    print("Example 4: Sequential Measurements")
    print("=" * 60)
    
    engine = Engine()
    
    # Initial state
    engine.state_manager.define_omega({"A", "B", "C"})
    engine.state_manager.load_weights({
        "A": 0.25,
        "B": 0.40,
        "C": 0.35
    })
    
    print(f"Initial state: {engine.state_manager.get_mu()}")
    print(f"Time: {len(engine.history)}\n")
    
    # First measurement: "is it A?"
    Q1 = create_simple_question(
        "Q1",
        {"A": {"A"}, "notA": {"B", "C"}}
    )
    
    result1 = engine.execute_measurement_cycle([Q1])
    print(f"Measurement 1 result: {result1}")
    print(f"State after M1: {engine.state_manager.get_mu()}")
    print(f"Time: {len(engine.history)}\n")
    
    # Second measurement: "B mi?" (on collapsed state)
    Q2 = create_simple_question(
        "Q2",
        {"B": {"B"}, "notB": {"A", "C"}}
    )
    
    result2 = engine.execute_measurement_cycle([Q2])
    print(f"Measurement 2 result: {result2}")
    print(f"State after M2: {engine.state_manager.get_mu()}")
    print(f"Time: {len(engine.history)}\n")
    
    # Show history
    print("History:")
    for i, entry in enumerate(engine.history.get_all()):
        print(f"  M{i+1}: {entry.result} (t={entry.measurement_number})")
    print()


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("ObserverRealityEngine - Examples")
    print("=" * 60 + "\n")
    
    example_1_simple_measurement()
    example_2_multiple_questions()
    example_3_isa_program()
    example_4_sequential_measurements()
    
    print("=" * 60)
    print("All examples completed!")
    print("=" * 60)

