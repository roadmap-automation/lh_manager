from enum import Enum
from pydantic import BaseModel

class MethodError(BaseModel):
    
    name: str
    error: str

class SampleStatus(str, Enum):
    INACTIVE = 'inactive'
    PENDING = 'pending'
    ACTIVE = 'active'
    PARTIAL = 'partially complete'
    FAILED = 'failed'
    COMPLETED = 'completed'