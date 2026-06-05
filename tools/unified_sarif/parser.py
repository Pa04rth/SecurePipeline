from collections.abc import Iterable
from pathlib import Path
import json

from .schema import NormalizedFinding

_VALID_LEVELS = {"error", "warning", "note", "none"}


def _normalize_level(raw) -> str:
    level = (raw or "").lower()
    return level if level in _VALID_LEVELS else "warning"


def parse_sarif_file(path) -> Iterable[NormalizedFinding]:
    with open(path, "r", encoding="utf-8") as f:
        sarif = json.load(f)

    for run in sarif.get("runs", []):
        driver = run.get("tool", {}).get("driver", {})
        scanner = driver.get("name", "unknown")
        rule_uri = {
            r.get("id"): r.get("helpUri")
            for r in driver.get("rules", [])
            if r.get("id")
        }

        for result in run.get("results", []):
            rule_id = result.get("ruleId", "unknown")
            locations = result.get("locations") or [{}]
            physical = locations[0].get("physicalLocation", {})

            yield NormalizedFinding(
                scanner=scanner,
                rule_id=rule_id,
                severity=_normalize_level(result.get("level")),
                message=(result.get("message", {}).get("text") or "")[:500],
                file=physical.get("artifactLocation", {}).get("uri"),
                start_line=physical.get("region", {}).get("startLine"),
                help_uri=rule_uri.get(rule_id),
            )


def parse_directory(directory) -> list[NormalizedFinding]:
    findings: list[NormalizedFinding] = []
    for sarif_path in Path(directory).rglob("*.sarif"):
        findings.extend(parse_sarif_file(sarif_path))
    return findings
