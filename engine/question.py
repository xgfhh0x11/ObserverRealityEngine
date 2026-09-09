"""
Question System - Measurement Operators
Questions partition state and project to subspaces.
"""

from enum import Enum
from typing import Dict, Set, Callable, Optional, Any, TYPE_CHECKING
from dataclasses import dataclass, field
import uuid

if TYPE_CHECKING:
    from .state import ProjectedState, State
    from .history import History


class Visibility(Enum):
    """Question visibility policy"""
    PRIVATE = "PRIVATE"  # Only sees own projection
    SHARED = "SHARED"    # Sees other Q's projections
    COMPETING = "COMPETING"  # Can suppress others


class Lifetime(Enum):
    """Question lifetime policy"""
    MW_ONLY = "MW_ONLY"  # Single MW
    MULTI_MW = "MULTI_MW"  # Multiple MWs
    UNTIL_INVALIDATED = "UNTIL_INVALIDATED"  # Until explicit invalidation


@dataclass
class Question:
    """
    Question = Measurement Operator
    
    Parameters (engine carries but doesn't interpret):
    - partition_rule: How to partition state
    - history_scope: Which history window to see
    - correlation_policy: How to correlate with other Q's
    - weight_modifier: How to adjust weights
    - lifetime: When Q can be reused
    - visibility: What Q can see
    """
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    # Core parameters
    partition_rule: Callable[['State'], Dict[str, Set[str]]] = None
    history_scope: Callable[['History'], 'History'] = None
    
    # Optional parameters
    correlation_policy: Optional[Callable] = None
    weight_modifier: Optional[Callable] = None
    lifetime: Lifetime = Lifetime.MW_ONLY
    visibility: Visibility = Visibility.PRIVATE
    
    # Internal state
    _invalidated: bool = False
    
    def __post_init__(self):
        """Validate required parameters"""
        if self.partition_rule is None:
            raise ValueError("partition_rule is required")
        if self.history_scope is None:
            raise ValueError("history_scope is required")
    
    def is_invalidated(self) -> bool:
        """Check if question is invalidated"""
        return self._invalidated
    
    def invalidate(self):
        """Invalidate question (called during collapse)"""
        self._invalidated = True
    
    def project(
        self,
        state: 'State',
        history_window: 'History',
        projected_set: Dict[str, 'ProjectedState']
    ) -> 'ProjectedState':
        """
        Project state using partition rule.
        
        Process:
        1. Apply partition_rule to get subspaces
        2. Sum weights for each subspace
        3. Apply correlation_policy if visible
        4. Apply weight_modifier if present
        5. Normalize
        
        Returns:
            ProjectedState with weights for each SET
        """
        # Step 1: Partition
        subspaces = self.partition_rule(state)
        
        # Step 2: Sum weights for each subspace
        weights = {}
        for set_id, micro_states in subspaces.items():
            total_weight = 0.0
            for micro_state in micro_states:
                total_weight += state.get_weight(micro_state)
            weights[set_id] = total_weight
        
        # Step 3: Apply correlation if visible
        if self.visibility != Visibility.PRIVATE and self.correlation_policy:
            weights = self.correlation_policy(projected_set, history_window, weights)
        
        # Step 4: Apply weight modifier
        if self.weight_modifier:
            weights = self.weight_modifier(weights)
        
        # Step 5: Create projected state
        from .state import ProjectedState
        projected = ProjectedState(question_id=self.id, weights=weights)
        projected.normalize()
        
        return projected


def create_simple_question(
    name: str,
    partition: Dict[str, Set[str]],
    visibility: Visibility = Visibility.PRIVATE
) -> Question:
    """
    Helper to create a simple question with explicit partition.
    
    Example:
        Q_A = create_simple_question(
            "Q_A",
            {"E1": {"ω1"}, "E2": {"ω2", "ω3"}}
        )
    """
    def partition_rule(state: 'State') -> Dict[str, Set[str]]:
        return partition
    
    def history_scope(history: 'History') -> 'History':
        # Default: see all history
        return history
    
    return Question(
        id=name,
        partition_rule=partition_rule,
        history_scope=history_scope,
        visibility=visibility,
        lifetime=Lifetime.MW_ONLY
    )

