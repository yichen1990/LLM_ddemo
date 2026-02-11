# app/exporters.py
from pathlib import Path
import json
from .schemas import TriageOutput, AnswerOutput
from .pdfgen import markdown_to_pdf


def _write_text(p: Path, s: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(s, encoding="utf-8")


def _write_json(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def append_jsonl(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def _auto_pdf(case_dir: Path, md_name: str, md_content: str) -> None:
    """
    Convert specific markdown artifacts into PDF automatically.
    """
    targets = {"assessment_brief.md", "rubric.md", "submission_checklist.md"}
    if md_name in targets:
        pdf_name = md_name.replace(".md", ".pdf")
        title = md_name.replace("_", " ").replace(".md", "").title()
        markdown_to_pdf(md_content, case_dir / pdf_name, title=title)


def export_allow(case_dir: Path, triage: TriageOutput, answer: AnswerOutput) -> None:
    case_dir.mkdir(parents=True, exist_ok=True)

    _write_json(case_dir / "triage.json", triage.model_dump())
    _write_json(case_dir / "answer.json", answer.model_dump())

    # Human-readable summary
    md = []
    md.append(f"# Result: {triage.action}\n")
    md.append(f"**Risk score:** {triage.risk_score}\n")
    md.append(answer.final_answer + "\n")
    md.append("## Checklist\n" + "\n".join([f"- {x}" for x in answer.checklist]) + "\n")
    if answer.citations:
        md.append("## Citations\n" + "\n".join([f"- {c}" for c in answer.citations]) + "\n")
    _write_text(case_dir / "answer.md", "\n".join(md))

    # Write generated files and auto-create PDFs for key teaching artifacts
    for f in answer.files_to_generate:
        _write_text(case_dir / f.name, f.content)
        if f.name.endswith(".md"):
            _auto_pdf(case_dir, f.name, f.content)


def export_block(case_dir: Path, triage: TriageOutput) -> None:
    case_dir.mkdir(parents=True, exist_ok=True)

    _write_json(case_dir / "triage.json", triage.model_dump())

    md = []
    md.append(f"# Result: {triage.action}\n")
    md.append(f"**Risk score:** {triage.risk_score}\n")
    if triage.threats:
        md.append("## Threats\n" + "\n".join([f"- **{t.type}** ({t.severity}): `{t.evidence}`" for t in triage.threats]) + "\n")
    md.append("## Safe response\n" + triage.safe_response + "\n")
    if triage.recommended_controls:
        md.append("## Recommended controls\n" + "\n".join([f"- {c}" for c in triage.recommended_controls]) + "\n")
    _write_text(case_dir / "blocked.md", "\n".join(md))

    incident = {
        "action": triage.action,
        "risk_score": triage.risk_score,
        "threats": [t.model_dump() for t in triage.threats],
    }
    _write_json(case_dir / "incident_log.json", incident)
