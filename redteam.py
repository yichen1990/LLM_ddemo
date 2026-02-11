import argparse
import json
from pathlib import Path

def load_jsonl(path: Path):
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default="logs/run_log.jsonl")
    ap.add_argument("--out", default="out_eval")
    args = ap.parse_args()

    runs = load_jsonl(Path(args.runs))
    outdir = Path(args.out); outdir.mkdir(parents=True, exist_ok=True)

    total = len(runs)
    if total == 0:
        raise SystemExit("No runs found. Run demo.py first.")

    blocks = sum(1 for r in runs if r["action"] == "BLOCK")
    allows = sum(1 for r in runs if r["action"] in ("ALLOW", "ALLOW_WITH_GUARDRAILS"))
    avg_risk = sum(r["risk_score"] for r in runs) / total

    report = {
        "total_runs": total,
        "allow_count": allows,
        "block_count": blocks,
        "avg_risk_score": avg_risk,
    }

    (outdir / "eval_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    md = []
    md.append("# Evaluation Report\n")
    md.append(f"- Total runs: {total}")
    md.append(f"- ALLOW(+guardrails): {allows}")
    md.append(f"- BLOCK: {blocks}")
    md.append(f"- Avg risk score: {avg_risk:.1f}\n")
    (outdir / "eval_report.md").write_text("\n".join(md), encoding="utf-8")

    print("Wrote", outdir / "eval_report.md")

if __name__ == "__main__":
    main()