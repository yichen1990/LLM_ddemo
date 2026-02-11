# demo.py
# Secure Guarded LLM + RAG Demo (Option B: LLM-based intent routing)

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

from pydantic import BaseModel, Field

from app.llm_client import LLMClient
from app.rag import LocalRAG
from app.schemas import TriageOutput, AnswerOutput
from app.prompts import (
    INTENT_SYSTEM,
    INTENT_USER,
    TRIAGE_SYSTEM,
    TRIAGE_USER,
    ANSWER_SYSTEM,
    ANSWER_USER_GENERIC,
    ANSWER_USER_ASSESSMENT,
)
from app.postprocess import parse_or_repair
from app.gates import simple_screen, enforce_triage, enforce_answer
from app.exporters import export_allow, export_block, append_jsonl
from app.capstone import write_capstone_brief


# ----------------------------
# Utilities
# ----------------------------

def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def slugify(text: str, max_len: int = 40) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", text.lower()).strip("_")
    return s[:max_len] if s else "query"


def make_case_folder_name(prompt: str, action: str, intent: str) -> str:
    return f"{now_stamp()}_{slugify(prompt)}_{intent}_{action}"


def load_cases_jsonl(path: Path):
    cases = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                cases.append(json.loads(line))
    return cases


# ----------------------------
# Intent schema (kept in demo.py to avoid extra file edits)
# ----------------------------

class IntentOutput(BaseModel):
    intent: str = Field(pattern="^(GENERIC_QA|ASSESSMENT_GEN|OTHER)$")
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str
    signals: list[str] = []


# ----------------------------
# JSON repair
# ----------------------------

def make_repair_fn(llm: LLMClient):
    def repair_fn(bad: str, err: str) -> str:
        msgs = [
            {
                "role": "system",
                "content": "You are a JSON repair tool. Output MUST be a single valid JSON object. No commentary. No markdown."
            },
            {
                "role": "user",
                "content": f"""
Fix this to valid JSON matching the required schema.

Rules:
- Output ONE JSON object only.
- Double-quoted keys and strings.
- No trailing commas.
- Include all required keys.

Validation error:
{err}

Bad output:
{bad}
"""
            }
        ]
        return llm.chat(msgs, temperature=0.0)
    return repair_fn


# ----------------------------
# LLM stages
# ----------------------------

def intent_case(llm: LLMClient, app_context: str, user_prompt: str) -> IntentOutput:
    case = {"app_context": app_context, "user_prompt": user_prompt}
    msgs = [
        {"role": "system", "content": INTENT_SYSTEM},
        {"role": "user", "content": INTENT_USER.format(**case)},
    ]
    raw = llm.chat(msgs, temperature=0.0)
    intent = parse_or_repair(raw, IntentOutput, make_repair_fn(llm), max_tries=5)
    return intent


def triage_case(llm: LLMClient, case: dict) -> TriageOutput:
    msgs = [
        {"role": "system", "content": TRIAGE_SYSTEM},
        {"role": "user", "content": TRIAGE_USER.format(**case)},
    ]
    raw = llm.chat(msgs, temperature=0.1)
    triage = parse_or_repair(raw, TriageOutput, make_repair_fn(llm), max_tries=5)
    enforce_triage(triage)
    return triage


def answer_case(llm: LLMClient, case: dict, mode: str) -> AnswerOutput:
    if mode == "ASSESSMENT_GEN":
        user_prompt = ANSWER_USER_ASSESSMENT.format(**case)
    else:
        user_prompt = ANSWER_USER_GENERIC.format(**case)

    msgs = [
        {"role": "system", "content": ANSWER_SYSTEM},
        {"role": "user", "content": user_prompt},
    ]
    raw = llm.chat(msgs, temperature=0.1)
    ans = parse_or_repair(raw, AnswerOutput, make_repair_fn(llm), max_tries=5)
    enforce_answer(ans)
    return ans


# ----------------------------
# Pipeline (crash-safe)
# ----------------------------

def run_one(
    llm: LLMClient,
    rag: LocalRAG,
    out_root: Path,
    logs_dir: Path,
    app_context: str,
    user_prompt: str,
    capstone: bool,
    retrieval_k: int = 3,
) -> Tuple[Path, IntentOutput, TriageOutput, Optional[AnswerOutput]]:

    # 0) Intent routing (LLM call #0)
    try:
        intent = intent_case(llm, app_context, user_prompt)
    except Exception as e:
        intent = IntentOutput(
            intent="GENERIC_QA",
            confidence=0.5,
            rationale=f"Intent parse failed; defaulted to GENERIC_QA ({e})",
            signals=[]
        )

    # 1) RAG retrieve
    snippets = rag.retrieve(user_prompt, k=retrieval_k)
    retrieved_snippets = "\n".join(snippets) if snippets else ""

    case = {
        "app_context": app_context,
        "user_prompt": user_prompt,
        "retrieved_snippets": retrieved_snippets,
    }

    # 2) Deterministic pre-screen
    screened = simple_screen(user_prompt + "\n" + retrieved_snippets)

    # 3) Security triage (LLM call #1)
    try:
        triage = triage_case(llm, case)
    except Exception as e:
        triage = TriageOutput(
            action="ALLOW_WITH_GUARDRAILS",
            risk_score=50,
            risk_rationale=f"Triage JSON parsing failed; fallback applied ({e})",
            threats=[],
            safe_response="System encountered a parsing issue during triage. Proceeding with guardrails.",
            recommended_controls=["Improve JSON enforcement"]
        )

    # 4) Create per-case folder AFTER decision
    folder_name = make_case_folder_name(user_prompt, triage.action, intent.intent)
    case_dir = out_root / folder_name
    case_dir.mkdir(parents=True, exist_ok=True)

    # 5) Log run
    append_jsonl(
        logs_dir / "run_log.jsonl",
        {
            "timestamp": now_stamp(),
            "case_folder": str(case_dir),
            "intent": intent.intent,
            "intent_confidence": intent.confidence,
            "action": triage.action,
            "risk_score": triage.risk_score,
            "screened": screened,
            "user_prompt": user_prompt,
        },
    )

    append_jsonl(
        logs_dir / "redteam_dataset.jsonl",
        {
            "timestamp": now_stamp(),
            "case_folder": str(case_dir),
            "app_context": app_context,
            "user_prompt": user_prompt,
            "expected_action": triage.action,
            "intent": intent.intent
        },
    )

    # Save intent trace for transparency (professional touch)
    (case_dir / "intent.json").write_text(intent.model_dump_json(indent=2), encoding="utf-8")

    # 6) Decide
    if triage.action in ("ALLOW", "ALLOW_WITH_GUARDRAILS"):
        try:
            ans = answer_case(llm, case, mode=intent.intent)
            export_allow(case_dir, triage, ans)

            if capstone:
                write_capstone_brief(
                    case_dir,
                    app_context,
                    user_prompt,
                    triage,
                    ans,
                    retrieved_snippets,
                )

            return case_dir, intent, triage, ans

        except Exception as e:
            # Always generate something (no hard crash)
            (case_dir / "debug_answer_error.txt").write_text(str(e), encoding="utf-8")
            (case_dir / "debug_context.txt").write_text(
                f"PROMPT:\n{user_prompt}\n\nSNIPPETS:\n{retrieved_snippets}",
                encoding="utf-8"
            )
            triage.safe_response = (
                "The assistant could not produce a valid structured output. "
                "A debug file was written. Please retry or simplify the request."
            )
            export_block(case_dir, triage)

            if capstone:
                write_capstone_brief(
                    case_dir,
                    app_context,
                    user_prompt,
                    triage,
                    None,
                    retrieved_snippets,
                )

            return case_dir, intent, triage, None

    # BLOCK
    export_block(case_dir, triage)

    if capstone:
        write_capstone_brief(
            case_dir,
            app_context,
            user_prompt,
            triage,
            None,
            retrieved_snippets,
        )

    return case_dir, intent, triage, None


# ----------------------------
# CLI
# ----------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--interactive", action="store_true")
    ap.add_argument("--cases")
    ap.add_argument("--rag", default="knowledge_base")
    ap.add_argument("--out", default="out")
    ap.add_argument("--logs", default="logs")
    ap.add_argument("--model", default="llama3.1")
    ap.add_argument("--base-url", default="http://localhost:11434")
    ap.add_argument("--capstone", action="store_true")
    ap.add_argument("--k", type=int, default=3)
    args = ap.parse_args()

    out_root = Path(args.out)
    logs_dir = Path(args.logs)
    out_root.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    llm = LLMClient(base_url=args.base_url, model=args.model)
    rag = LocalRAG(Path(args.rag))

    default_context = "You are a university assistant using secure RAG over local guidance documents."

    if args.interactive:
        print("\nSecure Guarded LLM Demo (Option B: Intent Routing)")
        print("Type 'exit' to quit.\n")

        while True:
            user_prompt = input("> ").strip()
            if user_prompt.lower() in ("exit", "quit"):
                break
            if not user_prompt:
                continue

            case_dir, intent, triage, ans = run_one(
                llm=llm,
                rag=rag,
                out_root=out_root,
                logs_dir=logs_dir,
                app_context=default_context,
                user_prompt=user_prompt,
                capstone=args.capstone,
                retrieval_k=args.k,
            )

            print(f"\nIntent: {intent.intent} (conf={intent.confidence:.2f})")
            print(f"Decision: {triage.action} | Risk: {triage.risk_score}")

            if ans is not None:
                print("\n" + ans.final_answer)
            else:
                print("\n" + triage.safe_response)

            print(f"\nArtifacts saved in:\n  {case_dir}\n")

        return

    if not args.cases:
        raise SystemExit("Provide --interactive or --cases <file.jsonl>")

    cases = load_cases_jsonl(Path(args.cases))

    for c in cases:
        case_dir, intent, triage, _ = run_one(
            llm=llm,
            rag=rag,
            out_root=out_root,
            logs_dir=logs_dir,
            app_context=c.get("app_context", default_context),
            user_prompt=c["user_prompt"],
            capstone=args.capstone,
            retrieval_k=args.k,
        )
        print(f"{intent.intent} | {triage.action} → {case_dir}")

    print("\nBatch run completed.\n")


if __name__ == "__main__":
    main()
