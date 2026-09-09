"""
Core Engine - Phase State Machine
Implements the transactional measurement lifecycle.
"""

from enum import Enum
from typing import Dict, Set, Optional, List, Tuple, TYPE_CHECKING
from dataclasses import dataclass, field
import uuid

if TYPE_CHECKING:
    from .state import ProjectedState
    from .question import Question
    from .measurement_window import MeasurementWindow


class Phase(Enum):
    """Engine phase states"""
    IDLE = "IDLE"
    MW_OPEN = "MW_OPEN"  # Pre-Measure
    PROJECTION = "PROJECTION"
    DECISION_BOUNDARY = "DECISION_BOUNDARY"  # Atomic
    POST_COLLAPSE = "POST_COLLAPSE"


@dataclass
class Engine:
    """
    Core measurement engine with phase state machine.
    
    Invariants:
    1. Single MW = single collapse
    2. State unchanged until MW closes
    3. Q's cannot leak outside MW
    4. Collapse moment is atomic
    5. History written only with MW snapshot
    """
    
    # Core state
    phase: Phase = Phase.IDLE
    active_mw: Optional['MeasurementWindow'] = None
    
    # Registered components (will be injected)
    state_manager: Optional['StateManager'] = None
    history: Optional['History'] = None
    
    def __post_init__(self):
        """Initialize engine"""
        if self.state_manager is None:
            from .state import StateManager
            self.state_manager = StateManager()
        if self.history is None:
            from .history import History
            self.history = History()
    
    def is_idle(self) -> bool:
        """Check if engine is in IDLE phase"""
        return self.phase == Phase.IDLE
    
    def open_measurement_window(self) -> 'MeasurementWindow':
        """
        PHASE 0 -> PHASE 1: MW_OPEN
        Opens a new measurement window.
        
        Rules:
        - Only allowed from IDLE
        - Creates new MW
        - Transitions to MW_OPEN
        """
        if not self.is_idle():
            raise RuntimeError(f"Cannot open MW: engine in {self.phase} phase")
        
        from .measurement_window import MeasurementWindow
        self.active_mw = MeasurementWindow()
        self.phase = Phase.MW_OPEN
        return self.active_mw
    
    def register_question(self, question: 'Question') -> bool:
        """
        Register a question in the active MW.
        
        Rules:
        - MW must be open
        - Q must not be invalidated
        - Q becomes immutable after registration
        """
        if self.phase != Phase.MW_OPEN:
            raise RuntimeError(f"Cannot register Q: engine in {self.phase} phase")
        
        if self.active_mw is None:
            raise RuntimeError("No active measurement window")
        
        if question.is_invalidated():
            return False
        
        self.active_mw.register(question)
        return True
    
    def project_all(self) -> Dict[str, 'ProjectedState']:
        """
        PHASE 1 -> PHASE 2: PROJECTION
        Projects all registered questions.
        
        Returns:
            Dictionary mapping question IDs to projected states
        """
        if self.phase != Phase.MW_OPEN:
            raise RuntimeError(f"Cannot project: engine in {self.phase} phase")
        
        if self.active_mw is None:
            raise RuntimeError("No active measurement window")
        
        self.phase = Phase.PROJECTION
        
        # Get current state and history window
        state = self.state_manager.get_state()
        history_window = self.history.get_window()
        
        # Project all questions
        projected_set = {}
        active_questions = self.active_mw.get_active_questions()
        
        for q in active_questions:
            projected = q.project(state, history_window, projected_set)
            projected_set[q.id] = projected
        
        self.active_mw.set_projected_set(projected_set)
        return projected_set
    
    def collapse(self) -> str:
        """
        PHASE 2 -> PHASE 3 -> PHASE 4: DECISION_BOUNDARY -> POST_COLLAPSE
        Atomic collapse operation.
        
        Rules:
        - Must be in PROJECTION phase
        - Selects single result from projected set
        - Invalidates all Q's atomically
        - Closes MW
        - Updates state
        - Appends to history
        
        Returns:
            Selected result (SET identifier)
        """
        if self.phase != Phase.PROJECTION:
            raise RuntimeError(f"Cannot collapse: engine in {self.phase} phase")
        
        if self.active_mw is None:
            raise RuntimeError("No active measurement window")
        
        # ATOMIC: DECISION_BOUNDARY
        self.phase = Phase.DECISION_BOUNDARY
        
        # Get projected set
        projected_set = self.active_mw.get_projected_set()
        if not projected_set:
            raise RuntimeError("No projected states to collapse")
        
        # Collapse: weighted random selection
        result_set = self._weighted_random_collapse(projected_set)
        
        # Map SET back to micro-states
        # Find which question(s) contain this SET and get micro-states
        active_questions = self.active_mw.get_active_questions()
        current_state = self.state_manager.get_state()
        micro_states = None
        
        for q in active_questions:
            partition = q.partition_rule(current_state)
            if result_set in partition:
                micro_states = partition[result_set]
                break
        
        # If no match found, treat result_set as a micro-state itself
        # (for backward compatibility with single-state results)
        if micro_states is None:
            micro_states = {result_set}
        
        # ATOMIC: Invalidate all Q's
        for q in active_questions:
            q.invalidate()
        
        # Close MW
        mw_snapshot = self.active_mw.snapshot()
        self.active_mw = None
        
        # POST_COLLAPSE
        self.phase = Phase.POST_COLLAPSE
        
        # Update state (DIRAC delta on micro-states)
        # Store micro-states, not SET identifier
        self.state_manager.store_micro_states(micro_states)
        
        # Append to history (store SET identifier for history)
        self.history.append(mw_snapshot, result_set)
        
        # Return to IDLE
        self.phase = Phase.IDLE
        
        return result_set
    
    def _weighted_random_collapse(self, projected_set: Dict[str, 'ProjectedState']) -> str:
        """
        Collapse projected set to single result using weighted random.
        
        This is the core collapse mechanism.
        """
        import random
        
        # Collect all possible results with their weights
        result_weights = {}
        
        for q_id, projected in projected_set.items():
            for set_id, weight in projected.weights.items():
                if set_id not in result_weights:
                    result_weights[set_id] = 0.0
                result_weights[set_id] += weight
        
        # Normalize
        total = sum(result_weights.values())
        if total == 0:
            raise RuntimeError("All weights are zero")
        
        normalized = {k: v / total for k, v in result_weights.items()}
        
        # Weighted random selection
        choices = list(normalized.keys())
        weights = list(normalized.values())
        result = random.choices(choices, weights=weights, k=1)[0]
        
        return result
    
    def execute_measurement_cycle(self, questions: List['Question']) -> str:
        """
        Execute complete measurement cycle:
        1. Open MW
        2. Register Q's
        3. Project
        4. Collapse
        5. Return result
        
        Convenience method for full cycle.
        """
        mw = self.open_measurement_window()
        
        for q in questions:
            self.register_question(q)
        
        self.project_all()
        result = self.collapse()
        
        return result

