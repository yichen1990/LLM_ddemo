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

# Simple private-data request keywords (doxxing-ish). Optional to use in triage.
PRIVATE_DATA_KEYWORDS = [
    "home address",
    "address",
    "phone number",
    "mobile number",
    "private email",
    "email address",
    "where does he live",
    "where does she live",
    "exact location",
    "current location",
    "ssn",
    "passport",
]

SECRET_PATTERNS = [
    r"sk-[A-Za-z0-9]{20,}",
    r"AKIA[0-9A-Z]{16}",
    r"-----BEGIN (?:RSA|EC|OPENSSH) PRIVATE KEY-----",
]


def simple_screen(text: str) -> bool:
    t = text.lower()
    return any(k in t for k in INJECTION_KEYWORDS)


def private_data_screen(text: str) -> bool:
    t = text.lower()
    return any(k in t for k in PRIVATE_DATA_KEYWORDS)


def enforce_triage(triage: TriageOutput) -> None:
    # Keep your original enforcement
    if triage.action in ("BLOCK", "ALLOW_WITH_GUARDRAILS") and not triage.safe_response.strip():
        raise ValueError("Missing safe_response for non-ALLOW triage.")
    for th in triage.threats:
        if not th.evidence.strip():
            raise ValueError("Threat missing evidence span.")


def enforce_answer(answer: AnswerOutput) -> None:
    # Keep your original secret scanning, but a bit safer around None/empty fields.
    if not answer.files_to_generate:
        raise ValueError("files_to_generate required.")

    checklist = "\n".join(answer.checklist or [])
    files = "\n".join(f.content for f in (answer.files_to_generate or []))
    full = (answer.final_answer or "") + "\n" + checklist + "\n" + files

    for pat in SECRET_PATTERNS:
        if re.search(pat, full):
            raise ValueError("Secret-like content detected in output.")
