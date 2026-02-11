import argparse
import re
from pathlib import Path
from urllib.parse import urlparse

import requests


def slugify(s: str, max_len: int = 60) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", s).strip("_")
    return s[:max_len] if s else "doc"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url", help="URL to ingest into knowledge base")
    ap.add_argument("--out", default="knowledge_base", help="KB folder")
    ap.add_argument("--timeout", type=int, default=20)
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    r = requests.get(args.url, timeout=args.timeout, headers={"User-Agent": "llm-demo-ingestor/1.0"})
    r.raise_for_status()

    # Save raw HTML for traceability
    parsed = urlparse(args.url)
    host = parsed.netloc.replace(":", "_")
    path = parsed.path.strip("/").replace("/", "_")
    base = slugify(f"{host}_{path}") or "page"

    html_path = out_dir / f"{base}.html"
    html_path.write_text(r.text, encoding="utf-8")

    # Also save a crude text version (strip tags lightly)
    text = re.sub(r"(?is)<script.*?>.*?</script>", "", r.text)
    text = re.sub(r"(?is)<style.*?>.*?</style>", "", text)
    text = re.sub(r"(?is)<[^>]+>", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()

    md_path = out_dir / f"{base}.md"
    md_path.write_text(f"# Source: {args.url}\n\n{text[:8000]}\n", encoding="utf-8")


    print(f"Ingested:\n- {md_path}\n- {html_path}")


if __name__ == "__main__":
    main()
