# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ha-honeywell is a standalone HACS-compatible custom integration for Honeywell Total Connect Comfort in Home Assistant. It is extracted from the core HA integration (`homeassistant/components/honeywell/`) to enable independent development, bug fixes, and modernization without being constrained by HA core's contribution process.

The integration uses the same `honeywell` domain — when installed, it overrides the built-in core integration.

## Commands

### Setup
```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```

### Run all QA checks
```bash
tox
```

### Run tests only
```bash
tox -e py313
# or directly:
.venv/bin/pytest tests -v
```

### Run linting
```bash
tox -e lint
# or directly:
.venv/bin/ruff check custom_components tests
.venv/bin/ruff format --check custom_components tests
```

### Run type checking
```bash
tox -e typing
```

### Fix lint issues
```bash
.venv/bin/ruff check --fix custom_components tests
.venv/bin/ruff format custom_components tests
```

## Architecture

### Directory Layout
- `custom_components/honeywell/` — the integration source (installed into HA's config dir)
- `tests/` — pytest test suite using `pytest-homeassistant-custom-component`

### Key Files
- `__init__.py` — entry point, AIOSomeComfort client creation, device discovery
- `config_flow.py` — Config flow (user/reauth steps) and options flow
- `climate.py` — thermostat entity (HVAC modes, fan, presets, temperature control)
- `sensor.py` — indoor/outdoor temperature and humidity sensors
- `switch.py` — emergency heat switch
- `humidifier.py` — humidifier and dehumidifier entities
- `diagnostics.py` — diagnostics data export
- `const.py` — constants and defaults
- `manifest.json` — integration metadata (version, requirements, codeowners)
- `strings.json` — internationalization strings

### Testing
- Tests use `pytest-homeassistant-custom-component` which provides the `hass` fixture and HA test infrastructure
- The `auto_enable_custom_integrations` autouse fixture in `conftest.py` ensures HA's loader picks up `custom_components/honeywell/` instead of the built-in integration
- All patch targets use `custom_components.honeywell.*` (not `homeassistant.components.honeywell.*`)
- `from pytest_homeassistant_custom_component.common import async_fire_time_changed` replaces the core `tests.common` import

## Code Style

- **Ruff** for linting and formatting (line-length=100, target-version=py314)
- **mypy** for type checking (targets 3.14)
- Python 3.13+ (tested on both 3.13 and 3.14)
- Conventional commits: `feat:`, `fix:`, `test:`, `docs:`, `chore:`, `refactor:`

## Workflow

Before committing, always run **all** QA checks and confirm they pass:
1. `.venv/bin/ruff check custom_components tests` — linting
2. `.venv/bin/ruff format --check custom_components tests` — formatting
3. `.venv/bin/mypy custom_components` — type checking
4. `.venv/bin/pytest tests -v` — tests

Do not ask the user to commit until all four pass. Fix any failures first.

## Dependencies

- Runtime: `AIOSomecomfort==0.0.35`, `homeassistant`
- Test: `pytest-homeassistant-custom-component` (pulls in HA core + test fixtures)
