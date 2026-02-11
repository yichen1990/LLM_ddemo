# app/capstone.py
from __future__ import annotations

from pathlib import Path
from typing import Optional, List, Set
from .schemas import TriageOutput, AnswerOutput


def _extract_sources(retrieved_snippets: Optional[str]) -> List[str]:
    """
    Extract [source.md] tags from retrieved snippets like:
      [policy_ai_use.md] ...
    Returns unique sources in appearance order.
    """
    if not retrieved_snippets:
        return []
    sources: List[str] = []
    seen: Set[str] = set()
    for line in retrieved_snippets.splitlines():
        line = line.strip()
        if line.startswith("[") and "]" in line:
            src = line[1: line.index("]")]
            if src and src not in seen:
                seen.add(src)
                sources.append(src)
    return sources


def _threat_table(triage: TriageOutput) -> str:
    if not triage.threats:
        return "_No threats detected._"

    rows = []
    rows.append("| Threat type | Severity | Evidence | Exploit path |")
    rows.append("|---|---|---|---|")
    for t in triage.threats:
        ev = (t.evidence or "").replace("\n", " ")
        ep = (t.exploit_path or "").replace("\n", " ")
        rows.append(f"| {t.type} | {t.severity} | `{ev}` | {ep} |")
    return "\n".join(rows)


def write_capstone_brief(
    case_dir: Path,
    app_context: str,
    user_prompt: str,
    triage: TriageOutput,
    answer: Optional[AnswerOutput],
    retrieved_snippets: Optional[str] = None,
) -> None:
    """
    Generate a capstone/thesis brief that is *driven by the actual run*:
    - Reflects the user's prompt
    - Uses triage decision + threats + evidence
    - References retrieved sources
    - Adapts content if BLOCK vs ALLOW
    """
    case_dir.mkdir(parents=True, exist_ok=True)

    sources = _extract_sources(retrieved_snippets)
    sources_md = "\n".join([f"- `{s}`" for s in sources]) if sources else "_No sources retrieved._"

    # Use triage to set a meaningful "project angle" dynamically
    if triage.action == "BLOCK":
        project_goal = "Design a secure assistant that reliably blocks prompt-injection and data-exfiltration attempts while maintaining auditability."
        deliverable_focus = "security controls + incident workflow + regression tests"
    elif triage.action == "ALLOW_WITH_GUARDRAILS":
        project_goal = "Design a secure assistant that answers helpfully while preventing verbatim leakage of internal documents via guardrailed summarisation."
        deliverable_focus = "guardrails + citation + leakage prevention"
    else:
        project_goal = "Design a secure RAG assistant that answers reliably with citations and structured outputs, and can be stress-tested with adversarial prompts."
        deliverable_focus = "RAG + structured outputs + evaluation"

    # Pull a compact “output snapshot” from the real answer (if exists)
    answer_snapshot = ""
    checklist_md = ""
    if answer is not None:
        answer_snapshot = answer.final_answer.strip()
        if answer.checklist:
            checklist_md = "\n".join([f"- {x}" for x in answer.checklist[:8]])  # cap for brevity

    # Threat content from real triage
    threat_md = _threat_table(triage)

    # Minimal, relevant evaluation plan (tied to this run)
    eval_metrics = [
        "JSON schema validity rate (triage + answer)",
        "Correct decision rate on red-team set (BLOCK vs ALLOW/guardrails)",
        "Leakage checks (no verbatim policy dumps; no secret-like strings)",
        "Citation coverage for RAG-backed answers (sources used vs sources retrieved)",
    ]

    # If threats exist, add one threat-specific metric
    if triage.threats:
        eval_metrics.append("Attack-type breakdown (e.g., injection vs exfiltration) and per-type pass rate")

    eval_md = "\n".join([f"- {m}" for m in eval_metrics])

    brief = f"""# Capstone / Thesis Brief (Run-derived)

## Prompt driving this brief
**User request:** {user_prompt}

**Application context:** {app_context}

## System decision
- **Action:** `{triage.action}`
- **Risk score:** `{triage.risk_score}`
- **Rationale:** {triage.risk_rationale}

## Retrieved sources (RAG)
{sources_md}

## Threat analysis (from triage)
{threat_md}

## Project goal
{project_goal}

## Proposed system (what students build)
- Local RAG over a document set (e.g., university policies / compliance notes)
- Two-stage LLM pipeline:
  1) **Triage** → structured `{{
     "action","risk_score","threats","evidence"
  }}`
  2) **Answer** (only if allowed) → structured `{{
     "final_answer","checklist","citations","files_to_generate"
  }}`
- Deterministic enforcement (policy-as-code): block exfiltration, prevent verbatim dumps, output scanning
- Artifact generation: per-run folder containing triage trace, answer trace, incident report (if blocked), and generated user files
- Regression testing: build/append a red-team dataset from blocked/guardrailed attempts

## Deliverable focus for this run
**{deliverable_focus}**

## Evaluation plan
{eval_md}
"""

    if answer_snapshot:
        brief += f"""
## Output snapshot (from this run)
{answer_snapshot}
"""
    if checklist_md:
        brief += f"""
## Checklist snapshot (from this run)
{checklist_md}
"""

    (case_dir / "capstone_brief.md").write_text(brief, encoding="utf-8")
