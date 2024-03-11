from pydantic.v1.dataclasses import dataclass

@dataclass
class MethodError:
    
    name: str
    error: str