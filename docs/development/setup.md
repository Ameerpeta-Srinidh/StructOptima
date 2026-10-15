# Development Setup

**As of:** 2026-10-15. Supported by project configuration: `requirements.txt`,
`.github/workflows/ci.yml` (Python 3.11, 3.12, 3.13), `Dockerfile` (python:3.12-slim).

## Prerequisites

- Python 3.11–3.13 (pinned numpy 2.4.2 requires ≥ 3.11; the development machine used 3.13.7).
- Git.
- Optional: `ifcopenshell` for IFC import (`pip install ifcopenshell`; not in requirements).

## Install

```bash
git clone <repository-url>
cd civil
python -m venv .venv
# Windows: .venv\Scripts\activate    Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
pip install pytest-cov            # optional, coverage (used by CI)
```

## Run

```bash
streamlit run app.py                               # dashboard at http://localhost:8501
python main.py --help                              # CLI options
python main.py --width 18 --length 12 --stories 2 --zone III --report out.pdf
python main.py --cad samples/sample_design.dxf --stories 2 --report cad.pdf
```

The CLI writes `structural_design.log` in the current directory. The Streamlit
app logs to the console only.

## Docker

```bash
docker compose up --build        # serves the app on port 8501
```

(Container setup not re-verified on 2026-10-15; the Dockerfile health check
calls `curl`, which `python:3.12-slim` does not include by default — NOT_ASSESSED.)

## Environment variables

| Variable | Effect |
|---|---|
| `LOG_LEVEL` | DEBUG / INFO (default) / WARNING / ERROR |
| `STRUCTOPTIMA_LOG_FILE` | Path; enables file logging for library imports |
| `SENTRY_DSN` | Enables Sentry error reporting |

## Tests

See [../verification/test-execution-guide.md](../verification/test-execution-guide.md).
