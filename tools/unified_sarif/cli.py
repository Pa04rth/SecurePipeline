import argparse
import json
import sys
from pathlib import Path

from .parser import parse_directory
from .render import summary_table, markdown_pr_comment

_SEVERITY_ORDER = ["none", "note", "warning", "error"]


def _cmd_merge(args: argparse.Namespace) -> int:
    findings = parse_directory(args.input)

    if args.output:
        Path(args.output).write_text(
            json.dumps([f.to_dict() for f in findings], indent=2),
            encoding="utf-8",
        )

    if args.markdown:
        Path(args.markdown).write_text(
            markdown_pr_comment(findings), encoding="utf-8"
        )

    print(summary_table(findings))

    if args.fail_on:
        threshold = _SEVERITY_ORDER.index(args.fail_on)
        offenders = [
            f for f in findings
            if f.severity in _SEVERITY_ORDER
            and _SEVERITY_ORDER.index(f.severity) >= threshold
        ]
        if offenders:
            print(
                f"{len(offenders)} finding(s) at or above '{args.fail_on}'.",
                file=sys.stderr,
            )
            return 1
        print(f"No findings at or above '{args.fail_on}'.")
    return 0


def _cmd_summary(args: argparse.Namespace) -> int:
    findings = parse_directory(args.input)
    print(summary_table(findings))
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="unified-sarif",
        description="Normalize SARIF outputs from multiple scanners into a unified report.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True, title="subcommands")

    merge = sub.add_parser("merge", help="Merge SARIF files, write JSON/markdown, optionally gate by severity.")
    merge.add_argument("input", help="Directory containing .sarif files (recursively scanned).")
    merge.add_argument("--output", help="Path to write consolidated JSON.")
    merge.add_argument("--markdown", help="Path to write PR-comment markdown.")
    merge.add_argument(
        "--fail-on",
        choices=_SEVERITY_ORDER,
        help="Exit nonzero if any finding is at or above this severity.",
    )
    merge.set_defaults(func=_cmd_merge)

    summary = sub.add_parser("summary", help="Print a counts-only summary of SARIF findings.")
    summary.add_argument("input", help="Directory containing .sarif files (recursively scanned).")
    summary.set_defaults(func=_cmd_summary)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
