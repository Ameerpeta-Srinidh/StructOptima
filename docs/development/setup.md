# Development Setup

**As of:** 2026-10-20. Supported by project configuration: `requirements.txt`,
`.github/workflows/ci.yml` (Python 3.11, 3.12, 3.13), `Dockerfile` (python:3.12-slim).

## Prerequisites

- Python 3.11–3.13 (pinned numpy 2.4.2 requires ≥ 3.11). **Not 3.14**: the pinned `pydantic-core==2.33.2` has no
  3.14 wheel and fails to build. Development machines: Windows 3.13.7 (until 2026-10-16), Ubuntu 3.12.15 (since
  2026-10-20).
- Git.
- `ifcopenshell` (IFC import/export) is installed from `requirements.txt` (Linux wheels need glibc ≥ 2.31).

## Install

```bash
git clone <repository-url>
cd civil
python -m venv .venv
# Windows: .venv\Scripts\activate    Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt   # includes ifcopenshell
pip install pytest-cov            # optional, coverage (used by CI)
pip install pypdfium2             # needed by test_drawings.py::test_outputs_are_consistent (not in requirements.txt, KD-22)
```

If the system Python is 3.14 (recent Ubuntu), create the environment with Python 3.12 through `uv`, without sudo:

```bash
python3 -m venv ~/.local/share/uv-tool && ~/.local/share/uv-tool/bin/pip install uv
~/.local/share/uv-tool/bin/uv venv --python 3.12 .venv
~/.local/share/uv-tool/bin/uv pip install --python .venv/bin/python -r requirements.txt pypdfium2
```

## Run

```bash
streamlit run app.py                               # web app at http://localhost:8501
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
