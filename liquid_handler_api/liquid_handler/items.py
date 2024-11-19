from enum import Enum
from dataclasses import field
from pydantic import BaseModel

class Item(BaseModel):

    id: str
    stage: str
    data: dict = field(default_factory=dict)

    def __repr__(self) -> str:
        return f'Sample {self.id} Stage {self.stage} with data {self.data}'

class MethodError(BaseModel):
    
    name: str
    error: str

