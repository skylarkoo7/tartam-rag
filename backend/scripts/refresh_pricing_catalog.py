from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path

import httpx


DEFAULT_URL = "https://openai.com/api/pricing"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh pricing catalog metadata from OpenAI pricing page.")
    parser.add_argument(
        "--catalog",
        default=Path(__file__).resolve().parents[1] / "app" / "pricing_catalog.json",
        type=Path,
        help="Path to pricing catalog JSON",
    )
    parser.add_argument("--url", default=DEFAULT_URL, help="Pricing source URL")
    parser.add_argument("--dry-run", action="store_true", help="Do not write file")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    catalog_path: Path = args.catalog
    payload = json.loads(catalog_path.read_text(encoding="utf-8"))

    with httpx.Client(timeout=20.0, follow_redirects=True) as client:
        response = client.get(args.url)
        response.raise_for_status()
        html = response.text

    # The pricing page structure can change; this script performs conservative checks
    # and only updates catalog metadata timestamp/source, while printing model-hit hints.
    models = ["gpt-5.2", "gpt-5-mini", "gpt-5-nano", "text-embedding-3-large", "text-embedding-3-small"]
    found = {model: bool(re.search(re.escape(model), html, flags=re.IGNORECASE)) for model in models}

    payload["version"] = date.today().isoformat()
    payload["source_url"] = args.url

    if args.dry_run:
        print("dry_run=true")
    else:
        catalog_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"updated_catalog={catalog_path}")

    for model, hit in found.items():
        print(f"{model}: {'found' if hit else 'not_found'}")
    print("Note: verify rates manually against official pricing before committing value changes.")


if __name__ == "__main__":
    main()
