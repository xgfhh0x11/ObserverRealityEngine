"""
Instruction Set Architecture (ISA)
Low-level operations for the engine.
"""

from typing import Dict, Set, List, Optional
from .state import StateManager, State
from .question import Question
from .measurement_window import MeasurementWindow
from .history import History
from .core import Engine


class ISA:
    """
    Instruction Set Architecture
    
    Implements all ISA operations:
    - MEMORY: STATE.DEF, STATE.LOAD, STATE.STORE
    - PARTITION: Q.DEF, Q.EXEC
    - TRANSACTION: MW.BEGIN, MW.REG, MW.SNAPSHOT, MW.COMMIT, MW.END
    - CONTROL: INVALIDATE.QS, HISTORY.APPEND
    """
    
    def __init__(self, engine: Optional[Engine] = None):
        """
        Initialize ISA with engine.
        If no engine provided, creates new one.
        """
        if engine is None:
            self.engine = Engine()
        else:
            self.engine = engine
        
        self.state_manager = self.engine.state_manager
        self.history = self.engine.history
    
    # ========== MEMORY OPERATIONS ==========
    
    def state_def(self, omega_global: Set[str]):
        """
        STATE.DEF: Define global state space.
        
        Args:
            omega_global: Set of all possible micro-states
        """
        self.state_manager.define_omega(omega_global)
    
    def state_load(self, mu_global: Dict[str, float]):
        """
        STATE.LOAD: Load global weights.
        
        Args:
            mu_global: Map from micro-state to weight
        """
        self.state_manager.load_weights(mu_global)
    
    def state_store(self, result_set: str):
        """
        STATE.STORE: Store collapsed result as DIRAC delta.
        
        Args:
            result_set: Selected SET identifier
        """
        self.state_manager.store_result(result_set)
    
    # ========== PARTITION OPERATIONS ==========
    
    def q_def(
        self,
        question_id: str,
        partition_rule,
        history_scope,
        visibility='PRIVATE',
        lifetime='MW_ONLY'
    ) -> Question:
        """
        Q.DEF: Define a question.
        
        Args:
            question_id: Unique identifier
            partition_rule: Function (State) -> Dict[str, Set[str]]
            history_scope: Function (History) -> History
            visibility: 'PRIVATE' | 'SHARED' | 'COMPETING'
            lifetime: 'MW_ONLY' | 'MULTI_MW' | 'UNTIL_INVALIDATED'
        
        Returns:
            Question object
        """
        from .question import Question, Visibility, Lifetime
        
        vis_enum = Visibility[visibility]
        life_enum = Lifetime[lifetime]
        
        return Question(
            id=question_id,
            partition_rule=partition_rule,
            history_scope=history_scope,
            visibility=vis_enum,
            lifetime=life_enum
        )
    
    def q_exec(self, question: Question, state: State) -> Dict[str, float]:
        """
        Q.EXEC: Execute question projection.
        
        Args:
            question: Question to execute
            state: Current state
        
        Returns:
            Dictionary mapping SET -> weight
        """
        from .state import ProjectedState
        
        # Create empty projected set (for visibility)
        projected_set = {}
        
        # Get history window
        history_window = self.history.get_window()
        
        # Project
        projected = question.project(state, history_window, projected_set)
        
        return projected.weights
    
    # ========== TRANSACTION OPERATIONS ==========
    
    def mw_begin(self) -> MeasurementWindow:
        """
        MW.BEGIN: Open measurement window.
        
        Returns:
            MeasurementWindow object
        """
        return self.engine.open_measurement_window()
    
    def mw_reg(self, question: Question):
        """
        MW.REG: Register question in active MW.
        
        Args:
            question: Question to register
        """
        self.engine.register_question(question)
    
    def mw_snapshot(self) -> Dict[str, Dict[str, float]]:
        """
        MW.SNAPSHOT: Get all projected states.
        
        Returns:
            Dictionary mapping question_id -> {SET: weight}
        """
        if self.engine.phase.value != 'PROJECTION':
            raise RuntimeError(f"Cannot snapshot: engine in {self.engine.phase} phase")
        
        projected_set = self.engine.active_mw.get_projected_set()
        
        return {
            q_id: dict(proj.weights)
            for q_id, proj in projected_set.items()
        }
    
    def mw_commit(self) -> str:
        """
        MW.COMMIT: Atomic collapse operation.
        
        Returns:
            Selected result (SET identifier)
        """
        return self.engine.collapse()
    
    def mw_end(self):
        """
        MW.END: End measurement window.
        (Actually handled by collapse, but kept for ISA completeness)
        """
        # MW is automatically destroyed after collapse
        pass
    
    # ========== CONTROL OPERATIONS ==========
    
    def invalidate_qs(self):
        """
        INVALIDATE.QS: Invalidate all questions in active MW.
        (Actually handled by collapse, but kept for ISA completeness)
        """
        if self.engine.active_mw:
            for q in self.engine.active_mw.get_active_questions():
                q.invalidate()
    
    def history_append(self, mw_snapshot: Dict, result: str):
        """
        HISTORY.APPEND: Append measurement to history.
        
        Args:
            mw_snapshot: MW snapshot
            result: Collapsed result
        """
        self.history.append(mw_snapshot, result)
    
    # ========== HIGH-LEVEL EXECUTION ==========
    
    def execute_program(self, program: List[Dict]):
        """
        Execute a program (list of ISA instructions).
        
        Program format:
        [
            {'op': 'STATE.DEF', 'omega': {...}},
            {'op': 'STATE.LOAD', 'mu': {...}},
            {'op': 'Q.DEF', 'id': 'Q_A', ...},
            {'op': 'MW.BEGIN'},
            {'op': 'MW.REG', 'question': q},
            {'op': 'MW.SNAPSHOT'},
            {'op': 'MW.COMMIT'},
            {'op': 'MW.END'},
        ]
        """
        questions = {}  # Store defined questions
        
        for instruction in program:
            op = instruction['op']
            
            if op == 'STATE.DEF':
                self.state_def(instruction['omega'])
            
            elif op == 'STATE.LOAD':
                self.state_load(instruction['mu'])
            
            elif op == 'Q.DEF':
                q = self.q_def(
                    instruction['id'],
                    instruction['partition_rule'],
                    instruction['history_scope'],
                    instruction.get('visibility', 'PRIVATE'),
                    instruction.get('lifetime', 'MW_ONLY')
                )
                questions[instruction['id']] = q
            
            elif op == 'MW.BEGIN':
                self.mw_begin()
            
            elif op == 'MW.REG':
                q_id = instruction['question']
                if isinstance(q_id, str):
                    q = questions[q_id]
                else:
                    q = q_id
                self.mw_reg(q)
            
            elif op == 'MW.SNAPSHOT':
                snapshot = self.mw_snapshot()
                instruction['result'] = snapshot
            
            elif op == 'MW.COMMIT':
                result = self.mw_commit()
                instruction['result'] = result
            
            elif op == 'MW.END':
                self.mw_end()
            
            else:
                raise ValueError(f"Unknown instruction: {op}")

