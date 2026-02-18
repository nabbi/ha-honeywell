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

## Platforms

- **Climate** — thermostat control (heat, cool, auto, off), fan modes, preset modes (away, hold)
- **Sensor** — indoor/outdoor temperature and humidity
- **Switch** — emergency heat mode
- **Humidifier** — humidifier and dehumidifier control

## License

Apache-2.0
