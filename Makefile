.ONESHELL:
.PHONY: run-dev run-prod test install-dev install-prod dev docker-build lint frontend clean all coverage \
        scan scan-secrets scan-sast scan-sca demo
PORT ?= 8000

test:
	uv run pytest -v
coverage:
	uv run pytest --cov=app --cov-report=term-missing
lint:
	uv run black . && uv run ruff check .
install-dev:
	uv sync --locked --all-extras --dev
install-prod:
	uv sync --locked --all-extras
run-dev:
	uv run uvicorn app.main:app --reload
run-prod:
	uv run uvicorn app.main:app --host 0.0.0.0 --port 8000

docker-dev:
	docker build -f Dockerfile.dev -t securepipeline-dev:$(shell git rev-parse HEAD) .

docker-prod:
	docker build -f Dockerfile -t securepipeline:$(shell git rev-parse HEAD) .

docker-dev-run:
	docker run -it -p 127.0.0.1:$(PORT):$(PORT) securepipeline-dev:$(shell git rev-parse HEAD)

docker-prod-run:
	docker run -it -p $(PORT):$(PORT) securepipeline:$(shell git rev-parse HEAD)

scan-secrets:
	docker run --rm -v "$(CURDIR):/repo" -w /repo zricethezav/gitleaks:latest \
		detect --source . --config .gitleaks.toml --redact --verbose

scan-sast:
	docker run --rm -v "$(CURDIR):/src" -w /src returntocorp/semgrep:latest \
		semgrep scan --config p/python --config p/owasp-top-ten --config p/security-audit --error

scan-sca:
	docker run --rm -v "$(CURDIR):/repo" -w /repo aquasec/trivy:latest \
		fs --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1 .

scan: scan-secrets scan-sast scan-sca

demo: install-dev test coverage run-dev
