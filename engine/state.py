"""
State Management - Global state with scale labels
Implements Ω_global and μ_global with micro/local/window/global scales.
"""

from typing import Dict, Set, Optional
from dataclasses import dataclass, field
from collections import defaultdict


@dataclass
class State:
    """
    Global state representation.
    
    Structure:
    - Ω_global: Set of all possible micro-states
    - μ_global: Weights/potentials for each micro-state
    """
    
    omega_global: Set[str] = field(default_factory=set)
    mu_global: Dict[str, float] = field(default_factory=dict)
    
    def normalize(self):
        """Normalize weights to sum to 1.0"""
        total = sum(self.mu_global.values())
        if total > 0:
            self.mu_global = {k: v / total for k, v in self.mu_global.items()}
    
    def get_weight(self, micro_state: str) -> float:
        """Get weight for a micro-state"""
        return self.mu_global.get(micro_state, 0.0)
    
    def set_weight(self, micro_state: str, weight: float):
        """Set weight for a micro-state"""
        if micro_state not in self.omega_global:
            self.omega_global.add(micro_state)
        self.mu_global[micro_state] = weight
    
    def get_total_weight(self) -> float:
        """Get sum of all weights"""
        return sum(self.mu_global.values())
    
    def to_dirac(self, selected_set: str) -> 'State':
        """
        Create DIRAC delta state from selected SET.
        All weight concentrated on selected_set.
        """
        new_state = State()
        new_state.omega_global = {selected_set}
        new_state.mu_global = {selected_set: 1.0}
        return new_state


@dataclass
class ProjectedState:
    """
    Projected state from a question.
    Represents partitioned weights.
    """
    
    question_id: str
    weights: Dict[str, float] = field(default_factory=dict)  # SET -> weight
    
    def normalize(self):
        """Normalize projected weights"""
        total = sum(self.weights.values())
        if total > 0:
            self.weights = {k: v / total for k, v in self.weights.items()}
    
    def get_weight(self, set_id: str) -> float:
        """Get weight for a SET"""
        return self.weights.get(set_id, 0.0)


class StateManager:
    """
    Manages global state operations.
    Implements ISA: STATE.DEF, STATE.LOAD, STATE.STORE
    """
    
    def __init__(self):
        self.state = State()
    
    def define_omega(self, omega_global: Set[str]):
        """
        STATE.DEF: Define the global state space.
        """
        self.state.omega_global = set(omega_global)
        # Initialize weights to zero for new states
        for micro_state in omega_global:
            if micro_state not in self.state.mu_global:
                self.state.mu_global[micro_state] = 0.0
    
    def load_weights(self, mu_global: Dict[str, float]):
        """
        STATE.LOAD: Load global weights.
        """
        # Ensure all states in omega
        for micro_state in mu_global.keys():
            if micro_state not in self.state.omega_global:
                self.state.omega_global.add(micro_state)
        
        self.state.mu_global = dict(mu_global)
        self.state.normalize()
    
    def store_result(self, result_set: str):
        """
        STATE.STORE: Store collapsed result as DIRAC delta.

        Deprecated and disabled. This conflates a SET identifier (a
        partition label such as "E1") with a micro-state name: it
        writes omega_global = {result_set} directly, which is only
        correct by coincidence when the SET id happens to equal one of
        the actual surviving micro-states. Resolving a SET id back to
        its real micro-states requires the originating Question's
        partition, which this method has no access to, so it cannot be
        fixed in place. Use store_micro_states() with the actual
        surviving micro-states instead -- Engine.collapse() already
        does this for the high-level API.
        """
        raise NotImplementedError(
            "StateManager.store_result() is deprecated and disabled: it "
            "conflates a SET identifier with a micro-state name and can "
            "silently corrupt post-collapse state. Use "
            "store_micro_states(micro_states) with the resolved "
            "surviving micro-states instead."
        )
    
    def store_micro_states(self, micro_states: Set[str]):
        """
        STATE.STORE: Store collapsed micro-states as DIRAC delta.
        
        Args:
            micro_states: Set of micro-states to store (all with equal weight)
        """
        new_state = State()
        new_state.omega_global = set(micro_states)
        # Distribute weight equally among micro-states
        weight_per_state = 1.0 / len(micro_states) if micro_states else 0.0
        new_state.mu_global = {ms: weight_per_state for ms in micro_states}
        self.state = new_state
    
    def get_state(self) -> State:
        """
        Get current state (read-only view).
        """
        return self.state
    
    def get_omega(self) -> Set[str]:
        """Get Ω_global"""
        return self.state.omega_global.copy()
    
    def get_mu(self) -> Dict[str, float]:
        """Get μ_global"""
        return self.state.mu_global.copy()

