# Developer Guide

## Setup

Create and activate a virtual environment, then install the project with dev dependencies:

```bash
python3.14 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e '.[dev]'
pip install tox
```

This installs the project in editable mode along with all dev tools (pytest, ruff, mypy, tox,
etc.) as defined in `pyproject.toml` under `[project.optional-dependencies] dev`.

> **Note:** The `[tool.hatch.build.targets.wheel] packages` setting must point to
> `["custom_components"]` (not `["custom_components/honeywell"]`). This ensures the editable
> install adds `custom_components` to `sys.path` as `custom_components.honeywell`, avoiding a
> namespace collision with the `honeywell` package if one exists.

## Running Tests

### Full QA suite (lint + type check + tests)

```bash
tox
```

### Tests only

```bash
tox -e py314
# or directly:
pytest tests -v
```

### Single test file or test

```bash
pytest tests/test_climate.py -v
pytest tests/test_sensor.py::test_outdoor_sensor -v
```

### Linting

```bash
tox -e lint
# or directly:
ruff check custom_components tests
ruff format --check custom_components tests
```

Auto-fix lint issues:

```bash
ruff check --fix custom_components tests
ruff format custom_components tests
```

### Type checking

```bash
tox -e typing
```
