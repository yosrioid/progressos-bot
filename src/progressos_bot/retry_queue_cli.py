import argparse
import json
from pathlib import Path

from progressos_bot.retry_queue import (
    SQLiteRetryQueue,
    summarize_dead_letters,
    summarize_retry_queue,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Inspect ProgressOS retry queue operator metadata."
    )
    parser.add_argument(
        "--path",
        type=Path,
        required=True,
        help="Path to the SQLite retry queue configured by RETRY_QUEUE_PATH.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("status", help="Print queued and dead-letter counts as JSON.")
    subparsers.add_parser(
        "dead-letters",
        help="Print redacted dead-letter metadata as JSON.",
    )
    args = parser.parse_args(argv)

    queue = SQLiteRetryQueue(path=str(args.path))

    if args.command == "status":
        print(summarize_retry_queue(queue).model_dump_json(indent=2))
        return 0
    if args.command == "dead-letters":
        summaries = summarize_dead_letters(queue)
        print(
            json.dumps(
                [summary.model_dump(mode="json") for summary in summaries],
                indent=2,
            )
        )
        return 0

    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
