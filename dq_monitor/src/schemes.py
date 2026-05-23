from pydantic import BaseModel
from dataclasses import dataclass
from typing import List, Literal

@dataclass
class Recomendation(BaseModel):
    problem: str
    impact: str
    solution: str
    priority: Literal["High", "Medium", "Low"]

class Recomendations(BaseModel):
    recomendations: List[Recomendation]
