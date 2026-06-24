import argparse
import json
import sys
from pathlib import Path

from progressos_bot.retry_queue import (
    SQLiteRetryQueue,
    build_retry_queue_diagnostic_bundle,
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
    requeue_parser = subparsers.add_parser(
        "requeue",
        help="Move one dead-letter entry back to the retry queue.",
    )
    _add_recovery_arguments(requeue_parser)
    discard_parser = subparsers.add_parser(
        "discard",
        help="Delete one dead-letter entry after operator confirmation.",
    )
    _add_recovery_arguments(discard_parser)
    diagnostic_parser = subparsers.add_parser(
        "diagnostic-bundle",
        help="Print a redacted diagnostic bundle for a correlation ID.",
    )
    diagnostic_parser.add_argument(
        "--correlation-id",
        required=True,
        help="Correlation ID returned to the user or found in structured logs.",
    )
    diagnostic_parser.add_argument(
        "--idempotency-key",
        default=None,
        help="Optional retry/dead-letter idempotency key to include matching metadata.",
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
    if args.command == "diagnostic-bundle":
        bundle = build_retry_queue_diagnostic_bundle(
            queue,
            correlation_id=args.correlation_id,
            idempotency_key=args.idempotency_key,
        )
        print(bundle.model_dump_json(indent=2))
        return 0
    if args.command == "requeue":
        _require_confirmation(parser, args.command, args.idempotency_key, args.confirm)
        queued = queue.requeue_dead_letter(args.idempotency_key)
        if queued is None:
            print(
                f"dead-letter not found: {args.idempotency_key}",
                file=sys.stderr,
            )
            return 1
        print(
            json.dumps(
                {
                    "action": "requeued",
                    "idempotency_key": queued.idempotency_key,
                    "attempt_count": queued.attempt_count,
                },
                indent=2,
            )
        )
        return 0
    if args.command == "discard":
        _require_confirmation(parser, args.command, args.idempotency_key, args.confirm)
        discarded = queue.discard_dead_letter(args.idempotency_key)
        if discarded is None:
            print(
                f"dead-letter not found: {args.idempotency_key}",
                file=sys.stderr,
            )
            return 1
        print(
            json.dumps(
                {
                    "action": "discarded",
                    "idempotency_key": discarded.idempotency_key,
                    "attempt_count": discarded.attempt_count,
                },
                indent=2,
            )
        )
        return 0

    parser.error(f"Unsupported command: {args.command}")
    return 2


def _add_recovery_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--idempotency-key",
        required=True,
        help="Dead-letter idempotency key to recover.",
    )
    parser.add_argument(
        "--confirm",
        required=True,
        help="Repeat the idempotency key to confirm the destructive operation.",
    )


def _require_confirmation(
    parser: argparse.ArgumentParser,
    command: str,
    idempotency_key: str,
    confirmation: str,
) -> None:
    if confirmation != idempotency_key:
        parser.error(
            f"{command} requires --confirm to exactly match --idempotency-key"
        )


if __name__ == "__main__":
    raise SystemExit(main())
