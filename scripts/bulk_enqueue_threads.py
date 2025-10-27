#!/usr/bin/env python3
"""Utility script to enqueue multiple Reddit threads for ingestion."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Iterable, Tuple


def _bootstrap_backend(env: str | None) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    backend_path = repo_root / "src" / "backend"
    if str(backend_path) not in sys.path:
        sys.path.insert(0, str(backend_path))

    env_file = repo_root / "config" / "environments" / f"{env or 'development'}.env"
    if env_file.exists():
        os.environ.setdefault("ENV_FILE", str(env_file))
    os.environ.setdefault("PYTHONPATH", str(backend_path))


def _parse_entries(source: Iterable[str], default_subreddit: str | None) -> list[Tuple[str, str]]:
    entries: list[Tuple[str, str]] = []
    for raw_line in source:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        parts = [chunk.strip() for chunk in line.replace(",", " ").split() if chunk.strip()]
        if not parts:
            continue

        thread_id = parts[0]
        subreddit = parts[1] if len(parts) > 1 else default_subreddit
        if not subreddit:
            raise ValueError(f"Missing subreddit for thread '{thread_id}'. Provide --subreddit or include it per line.")
        entries.append((thread_id, subreddit))
    return entries


def enqueue(entries: list[Tuple[str, str]], queue: str, dry_run: bool) -> None:
    if dry_run:
        print("Dry run. The following tasks would be enqueued:")
        for thread_id, subreddit in entries:
            print(f"- thread={thread_id} subreddit={subreddit} queue={queue}")
        return

    from app.tasks.ingestion import fetch_thread

    for thread_id, subreddit in entries:
        fetch_thread.apply_async(args=[thread_id, subreddit], queue=queue)
        print(f"Queued ingestion for thread {thread_id} on /r/{subreddit} (queue={queue})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Bulk enqueue Reddit threads for ingestion.")
    parser.add_argument(
        "input",
        nargs="?",
        type=Path,
        help="Path to a file containing thread IDs (one per line or 'id subreddit'). Reads stdin when omitted.",
    )
    parser.add_argument(
        "--subreddit",
        help="Subreddit to use when the input file only contains thread IDs.",
    )
    parser.add_argument(
        "--env",
        default=os.getenv("ENV", "development"),
        help="Environment config to load (development|staging|production). Default: %(default)s",
    )
    parser.add_argument(
        "--queue",
        default="ingestion",
        help="Celery queue name. Default: %(default)s",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print tasks without enqueueing them.",
    )

    args = parser.parse_args()

    _bootstrap_backend(args.env)

    if args.input:
        lines = args.input.read_text(encoding="utf-8").splitlines()
    else:
        lines = sys.stdin.read().splitlines()

    entries = _parse_entries(lines, args.subreddit)
    if not entries:
        print("No thread IDs found. Supply an input file or pipe data via stdin.")
        return

    enqueue(entries, args.queue, args.dry_run)


if __name__ == "__main__":
    main()
