# ha-honeywell

[![QA](https://github.com/nabbi/ha-honeywell/actions/workflows/qa.yml/badge.svg)](https://github.com/nabbi/ha-honeywell/actions/workflows/qa.yml)

Honeywell Total Connect Comfort custom integration for Home Assistant (HACS-compatible).

This is an independently maintained version of the core Honeywell integration,
extracted to enable independent development, bug fixes, and modernization.

The integration uses the same `honeywell` domain — when installed, it overrides
the built-in core integration.

## Compatibility

Based on the core Honeywell integration using **AIOSomecomfort 0.0.35**.

## Installation

### HACS (recommended)

Add this repository as a custom repository in HACS, then install **Honeywell Total Connect Comfort**.

### Manual

Copy `custom_components/honeywell/` into your Home Assistant
`config/custom_components/` directory and restart Home Assistant.

## Quick Start

1. **Settings > Devices & Services > Add Integration > Honeywell Total Connect Comfort**
2. Enter your mytotalconnectcomfort.com credentials
3. Configure away temperatures via **Configure** options

## Changes from Core

Resilience and error handling improvements over the built-in `homeassistant.components.honeywell`:

- **Cached data on transient errors** — coordinator returns last known state on timeout, connection, and rate-limit errors instead of marking entities unavailable
- **Null cookie detection** — when the Honeywell site is down and returns empty auth cookies, the integration returns cached data instead of triggering a reauth flow that forces re-entry of valid credentials
- **Service call error handling** — `TimeoutError` and `ClientConnectionError` from aiohttp are caught in all entity service methods (set_temperature, set_fan_mode, set_hvac_mode, turn_on/off, set_humidity) and surfaced as user-friendly error toasts instead of unhandled exceptions
- **Login retry on transient auth errors** — Honeywell sometimes rejects valid credentials under load; setup retries once before backing off with `ConfigEntryNotReady`, avoiding unnecessary reauth prompts
- **Login timeout** — 30-second timeout on login calls prevents a hung Honeywell API from blocking HA startup
- **APIRateLimited during setup** — raises `ConfigEntryNotReady` with backoff instead of failing setup entirely

## Platforms

- **Climate** — thermostat control (heat, cool, auto, off), fan modes, preset modes (away, hold)
- **Sensor** — indoor/outdoor temperature and humidity
- **Switch** — emergency heat mode
- **Humidifier** — humidifier and dehumidifier control

## License

Apache-2.0
