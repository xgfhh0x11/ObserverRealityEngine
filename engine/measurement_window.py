"""
Measurement Window - Transactional Context
MW groups questions that share the same collapse moment.
"""

from typing import List, Dict, Optional, TYPE_CHECKING
from dataclasses import dataclass, field
import uuid
from datetime import datetime

if TYPE_CHECKING:
    from .question import Question
    from .state import ProjectedState


@dataclass
class MeasurementWindow:
    """
    Measurement Window (MW)
    
    Rules:
    - Q's registered in same MW share collapse moment
    - MW is atomic transaction boundary
    - Q's are immutable after registration
    - MW destroyed after collapse
    """
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.now)
    
    # Registered questions
    active_questions: List['Question'] = field(default_factory=list)
    
    # Projected states (set during PROJECTION phase)
    projected_set: Optional[Dict[str, 'ProjectedState']] = None
    
    def register(self, question: 'Question'):
        """
        Register a question in this MW.
        
        Rules:
        - Q must not be invalidated
        - Q becomes immutable after registration
        """
        if question.is_invalidated():
            raise ValueError(f"Question {question.id} is already invalidated")
        
        if question in self.active_questions:
            return  # Already registered
        
        self.active_questions.append(question)
    
    def get_active_questions(self) -> List['Question']:
        """Get all active questions"""
        return list(self.active_questions)
    
    def set_projected_set(self, projected_set: Dict[str, 'ProjectedState']):
        """Set projected states (called during PROJECTION phase)"""
        self.projected_set = projected_set
    
    def get_projected_set(self) -> Dict[str, 'ProjectedState']:
        """Get projected states"""
        if self.projected_set is None:
            return {}
        return self.projected_set
    
    def snapshot(self) -> Dict:
        """
        Create snapshot for history.
        Captures MW state at collapse moment.
        """
        return {
            'mw_id': self.id,
            'created_at': self.created_at.isoformat(),
            'question_ids': [q.id for q in self.active_questions],
            'projected_set': {
                q_id: {
                    'weights': dict(proj.weights)
                }
                for q_id, proj in (self.projected_set or {}).items()
            }
        }

