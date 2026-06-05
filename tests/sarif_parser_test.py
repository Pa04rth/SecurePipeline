import json
from pathlib import Path

import pytest

from tools.unified_sarif.parser import parse_sarif_file, parse_directory

FIXTURES_DIR = Path(__file__).parent / "fixtures"

EXPECTED_SCANNERS = [
    ("sample_checkov.sarif", "Checkov"),
    ("sample_trivy.sarif", "Trivy"),
    ("sample_zap.sarif", "OWASP ZAP"),
    ("sample_gitleaks.sarif", "gitleaks"),
    ("sample_semgrep.sarif", "Semgrep OSS"),
]

VALID_SEVERITIES = {"error", "warning", "note", "none"}


@pytest.mark.parametrize("filename,expected_scanner", EXPECTED_SCANNERS)
def test_scanner_name_is_correct(filename, expected_scanner):
    raw = json.loads((FIXTURES_DIR / filename).read_text(encoding="utf-8"))
    actual = raw["runs"][0]["tool"]["driver"]["name"]
    assert actual == expected_scanner
    findings = list(parse_sarif_file(FIXTURES_DIR / filename))
    if findings:
        assert all(f.scanner == expected_scanner for f in findings)


@pytest.mark.parametrize("filename,_", EXPECTED_SCANNERS)
def test_every_finding_has_valid_severity(filename, _):
    findings = list(parse_sarif_file(FIXTURES_DIR / filename))
    for f in findings:
        assert f.severity in VALID_SEVERITIES, (
            f"{filename}: rule {f.rule_id} has invalid severity {f.severity!r}"
        )


def test_help_uri_is_extracted_when_present():
    findings = parse_directory(FIXTURES_DIR)
    with_help = [f for f in findings if f.help_uri]
    assert len(with_help) > 0, "No fixture surfaced a help_uri — parser likely broken"


def test_parse_directory_returns_findings_from_at_least_one_scanner():
    findings = parse_directory(FIXTURES_DIR)
    assert len(findings) > 0
    scanners_seen = {f.scanner for f in findings}
    assert "OWASP ZAP" in scanners_seen


def test_empty_sarif_returns_no_findings(tmp_path):
    empty_sarif = tmp_path / "empty.sarif"
    empty_sarif.write_text(
        json.dumps({"version": "2.1.0", "runs": []}), encoding="utf-8"
    )
    findings = list(parse_sarif_file(empty_sarif))
    assert findings == []


def test_malformed_json_raises(tmp_path):
    bad = tmp_path / "broken.sarif"
    bad.write_text("not json {{{", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        list(parse_sarif_file(bad))


def test_missing_region_does_not_crash(tmp_path):
    sarif = {
        "version": "2.1.0",
        "runs": [{
            "tool": {"driver": {"name": "TestScanner", "rules": []}},
            "results": [{
                "ruleId": "TEST-001",
                "level": "warning",
                "message": {"text": "no location"},
            }],
        }],
    }
    path = tmp_path / "no_location.sarif"
    path.write_text(json.dumps(sarif), encoding="utf-8")
    findings = list(parse_sarif_file(path))
    assert len(findings) == 1
    assert findings[0].file is None
    assert findings[0].start_line is None


def test_normalized_finding_is_serializable():
    findings = parse_directory(FIXTURES_DIR)
    sample = findings[0]
    payload = sample.to_dict()
    assert isinstance(payload, dict)
    assert payload["scanner"] == sample.scanner
    assert json.dumps(payload)
