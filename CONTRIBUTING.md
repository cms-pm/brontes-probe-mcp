# Contributing

Thank you for your interest in contributing to brontes-probe-mcp.

## Development setup

```bash
git clone https://github.com/cms-pm/brontes-probe-mcp
cd brontes-probe-mcp
pip install -e ".[dev]"
```

This installs the package in editable mode with all development dependencies
(`pytest`, `pytest-cov`, `ruff`, `mypy`, `build`, `jinja2`).

## Running the checks locally

```bash
ruff check src/ tests/          # lint
mypy src/                       # type check
pytest -q                       # tests
python -m build                 # build wheel + sdist
python scripts/render_client_configs.py --check  # template drift check
```

## Pull request process

1. Fork the repository and create a feature branch off `main`.
2. Make your changes, keeping commits focused and messages concise.
3. Ensure all checks pass locally before opening a PR.
4. Open a pull request against `main`. A maintainer will review within a
   few business days.
5. Squash-merge is preferred; the PR title becomes the commit message.

## Typed surface contract

The `BrokerCore` typed method signatures in `src/brontes_probe_mcp/core/broker.py`
are the binding interface contract for all transport adapters and downstream
integrations. Any change to a method signature must update the corresponding
test in `tests/test_broker_not_implemented.py` in the same commit.
