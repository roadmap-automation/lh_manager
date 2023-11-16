from enum import Enum
from dataclasses import field
from pydantic.v1.dataclasses import dataclass

class StageName(str, Enum):
    PREP = 'prep'
    INJECT = 'inject'

@dataclass
class Item:

    id: str
    stage: StageName
    data: dict = field(default_factory=dict)

    def __repr__(self) -> str:
        return f'Sample {self.id} Stage {self.stage} with data {self.data}'

@dataclass
class MethodError:
    
    name: str
    error: str

