# Guarded LLM + Secure RAG Demo (Interview Build)

## What it demonstrates
- LLM API calls (Ollama /api/chat)
- Real RAG over local markdown knowledge base
- Security triage (ALLOW/BLOCK/ALLOW_WITH_GUARDRAILS) with evidence + risk scoring
- Strict JSON outputs validated by Pydantic + auto-repair loop
- Deterministic policy gates + incident logging
- Artifact generation: reports, checklists, capstone/thesis brief
- Logging + evaluation harness

## Run (interactive)
python demo.py --interactive --rag knowledge_base/ --out out/ --model llama3.1 --capstone

## Run (batch)
python demo.py --cases data/cases.jsonl --rag knowledge_base/ --out out/ --model llama3.1 --capstone

## Evaluate
python redteam.py --runs logs/run_log.jsonl --out out_eval/

## Copilot workflow (Claude Code / Codex)
During development, a coding copilot can be used to:
- scaffold pytest unit tests (e.g., gates + parsing)
- refactor exporters and CLI structure
- generate docstrings and documentation
Runtime does not depend on paid APIs; it runs locally for privacy and cost control.
