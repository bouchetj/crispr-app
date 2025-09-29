from pydantic import BaseModel, Field
from typing import List

class ValidateSequenceRequest(BaseModel):
    sequence: str = Field(..., description="Raw DNA sequence")

class ValidateSequenceResponse(BaseModel):
    length: int
    normalized_sequence: str
    gc_content: float
    warnings: List[str] = []
    errors: List[str] = []
