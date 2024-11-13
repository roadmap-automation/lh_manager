from pydantic import BaseModel

class MethodError(BaseModel):
    
    name: str
    error: str