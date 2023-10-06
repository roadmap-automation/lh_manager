from enum import Enum
from pydantic.dataclasses import dataclass

class StageName(str, Enum):
    PREP = 'prep'
    INJECT = 'inject'

@dataclass
class Item:

    id: str
    stage: StageName

@dataclass
class MethodError:
    
    name: str
    error: str

@dataclass
class LHError:
    
    item: Item | str
    error: str

