from __future__ import annotations

import argparse

from app.config import get_settings
from app.db import Database


DEFAULT_PATTERNS = [
    "eval_",
    "report-",
    "smoke-",
    "grounding-",
    "fix-grounding",
    "hi-test",
    "unknown-check",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Archive technical chat threads without deleting user chats.")
    parser.add_argument(
        "--patterns",
        default=",".join(DEFAULT_PATTERNS),
        help="Comma-separated patterns to match on session id/title.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = get_settings()
    db = Database(settings.db_path)
    db.init_db()

    before_active = len(db.list_threads(limit=5000, include_archived=False))
    before_all = len(db.list_threads(limit=5000, include_archived=True))

    patterns = [item.strip() for item in args.patterns.split(",") if item.strip()]
    archived_ids = db.archive_threads_by_patterns(patterns)

    after_active = len(db.list_threads(limit=5000, include_archived=False))
    after_all = len(db.list_threads(limit=5000, include_archived=True))

    print(f"before_active={before_active}")
    print(f"before_all={before_all}")
    print(f"after_active={after_active}")
    print(f"after_all={after_all}")
    print(f"archived_count={len(archived_ids)}")
    if archived_ids:
        print("archived_ids=" + ",".join(archived_ids))


if __name__ == "__main__":
    main()
