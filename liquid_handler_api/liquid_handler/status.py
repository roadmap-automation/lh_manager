from enum import Enum
from pydantic import BaseModel

class MethodError(BaseModel):
    
    name: str
    error: str

class SampleStatus(str, Enum):
    """General status enum

        For tasks:
        - INACTIVE: just created, submission not confirmed
        - PENDING: submission confirmed
        - ACTIVE: currently being executed
        - ERROR: currently in error state
        - PARTIAL: not used
        - FAILED: submission failed
        - COMPLETED: task is complete
        - CANCELLED: task was cancelled
        - UNKNOWN: task status unknown
    """
    INACTIVE = 'inactive'           
    PENDING = 'pending'
    ACTIVE = 'active'
    ERROR = 'error'
    PARTIAL = 'partially complete'
    FAILED = 'failed'
    COMPLETED = 'completed'
    CANCELLED = 'cancelled'
    UNKNOWN = 'unknown'