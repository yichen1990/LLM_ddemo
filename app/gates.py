import re
from .schemas import TriageOutput, AnswerOutput

INJECTION_KEYWORDS = [
    "ignore previous instructions",
    "system override",
    "reveal the system prompt",
    "developer message",
    "api key",
    "token",
    "password",
    "verbatim",
    "dump",
    "exfiltrate",
]

SECRET_PATTERNS = [
    r"sk-[A-Za-z0-9]{20,}",
    r"AKIA[0-9A-Z]{16}",
    r"-----BEGIN (?:RSA|EC|OPENSSH) PRIVATE KEY-----",
]

def simple_screen(text: str) -> bool:
    t = text.lower()
    return any(k in t for k in INJECTION_KEYWORDS)

def enforce_triage(triage: TriageOutput) -> None:
    if triage.action in ("BLOCK", "ALLOW_WITH_GUARDRAILS") and not triage.safe_response.strip():
        raise ValueError("Missing safe_response for non-ALLOW triage.")
    for th in triage.threats:
        if not th.evidence.strip():
            raise ValueError("Threat missing evidence span.")

def enforce_answer(answer: AnswerOutput) -> None:
    if not answer.files_to_generate:
        raise ValueError("files_to_generate required.")
    full = answer.final_answer + "\n" + "\n".join(answer.checklist) + "\n" + "\n".join(f.content for f in answer.files_to_generate)
    for pat in SECRET_PATTERNS:
        if re.search(pat, full):
            raise ValueError("Secret-like content detected in output.")