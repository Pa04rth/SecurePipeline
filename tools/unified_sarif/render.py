from collections import Counter

from .schema import NormalizedFinding

_SEVERITY_ORDER = ["error", "warning", "note", "none"]
_SEVERITY_EMOJI = {"error": "🔴", "warning": "🟠", "note": "🔵", "none": "⚪"}


def summary_table(findings: list[NormalizedFinding]) -> str:
    if not findings:
        return "No findings.\n"

    by_scanner = Counter(f.scanner for f in findings)
    by_severity = Counter(f.severity for f in findings)

    lines = [
        f"**Total findings:** {len(findings)}",
        "",
        "| Scanner | Count |",
        "| --- | ---: |",
    ]
    for scanner, count in sorted(by_scanner.items(), key=lambda x: (-x[1], x[0])):
        lines.append(f"| {scanner} | {count} |")

    lines += [
        "",
        "| Severity | Count |",
        "| --- | ---: |",
    ]
    for sev in _SEVERITY_ORDER:
        count = by_severity.get(sev, 0)
        if count:
            lines.append(f"| {_SEVERITY_EMOJI[sev]} {sev} | {count} |")

    return "\n".join(lines) + "\n"


def markdown_pr_comment(findings: list[NormalizedFinding], top_n: int = 10) -> str:
    if not findings:
        return "## Security scans clean\n\nNo findings across the SARIF outputs.\n"

    sections = ["## Security scan findings", "", summary_table(findings), ""]

    for sev in _SEVERITY_ORDER:
        bucket = [f for f in findings if f.severity == sev]
        if not bucket:
            continue
        sections.append(f"### {_SEVERITY_EMOJI[sev]} {sev.upper()} ({len(bucket)})")
        for f in bucket[:top_n]:
            location = f"`{f.file}:{f.start_line}`" if f.file and f.start_line else (
                f"`{f.file}`" if f.file else "—"
            )
            link = f" [docs]({f.help_uri})" if f.help_uri else ""
            sections.append(
                f"- **[{f.scanner}]** `{f.rule_id}` at {location}{link} — {f.message}"
            )
        if len(bucket) > top_n:
            sections.append(f"_…and {len(bucket) - top_n} more {sev} finding(s)._")
        sections.append("")

    return "\n".join(sections)
