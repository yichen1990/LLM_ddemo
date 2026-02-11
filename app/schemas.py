from pydantic import BaseModel, Field
from typing import List, Literal

Action = Literal["ALLOW", "BLOCK", "ALLOW_WITH_GUARDRAILS"]
Severity = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]

class Threat(BaseModel):
    type: str
    severity: Severity
    evidence: str
    exploit_path: str

class TriageOutput(BaseModel):
    action: Action
    risk_score: int = Field(ge=0, le=100)
    risk_rationale: str
    threats: List[Threat] = Field(default_factory=list)
    safe_response: str
    recommended_controls: List[str] = Field(default_factory=list)

class FileToGenerate(BaseModel):
    name: str
    content: str

class AnswerOutput(BaseModel):
    final_answer: str
    checklist: List[str] = Field(default_factory=list)
    citations: List[str] = Field(default_factory=list)
    files_to_generate: List[FileToGenerate] = Field(default_factory=list)
