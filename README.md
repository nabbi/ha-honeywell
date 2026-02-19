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

## API Load Impact Analysis (3,211 active installations)

Comparison of Honeywell API load between the original core integration logic and this
custom integration's error handling, assuming 3,211 active installations averaging
1.5 devices each.

### Steady-state (no errors)

Both versions are identical — no change in API load.

| Metric | Value |
|--------|-------|
| Poll interval | 60 s |
| Requests per poll | 1–2 per device (CheckDataSession + conditional GetData) |
| Polls/min (fleet) | ~53 |
| HTTP requests/min (fleet) | ~120–160 |

### During a Honeywell outage

The critical difference is what happens when the API returns errors.

#### Original core logic

| Scenario | Behavior | API calls per installation |
|----------|----------|--------------------------|
| Timeout / connection error | `UpdateFailed` → entities unavailable, keeps polling at 60 s | 1 failing request/min |
| 401 → re-login → AuthError | `ConfigEntryAuthFailed` → **reauth flow triggered, polling stops** | 2 requests then silence |
| 401 → re-login → null cookie | `ConfigEntryAuthFailed` → **reauth flow triggered, polling stops** | 2 requests then silence |

During an extended outage with auth errors, most installations enter reauth state within
1–2 poll cycles. Polling stops. **Fleet load drops to near zero.**

**Recovery**: all 3,211 users must manually re-enter credentials in the HA UI. As users
discover the problem and re-authenticate (often shortly after the API comes back up),
the fleet generates a concentrated burst:

```
Recovery burst = 3,211 × (login + discover + N×refresh)
               ≈ 3,211 × 4 calls
               ≈ 12,844 API calls in a short window (thundering herd)
```

#### New logic (this integration)

| Scenario | Behavior | API calls per installation |
|----------|----------|--------------------------|
| Timeout / connection error | Return cached data, entities stay available, keeps polling at 60 s | 1 failing request/min |
| 401 → re-login → AuthError | Retry login once more; if null cookie → cached data, keeps polling | 3 requests/cycle then 1/min |
| 401 → re-login → persistent AuthError | After retry, `ConfigEntryAuthFailed` (same as original) | 3 requests then silence |
| APIRateLimited (3 failed logins) | aiosomecomfort enforces 10-min backoff, caught as transient → cached data | 0 requests for 10 min |

During an outage, installations **keep polling at 60 s** with ~1 extra login retry per
auth-error cycle. The built-in rate limiter (3 failed logins → 10-min backoff) caps
login attempts automatically.

```
Outage load ≈ 53 polls/min (failing but graceful)
             + ~53 extra login retries/min (until rate limiter kicks in)
             → rate limiter engages within ~3 min
             → drops to 53 polls/min + 0 login attempts for 10-min windows
```

**Recovery**: seamless. The next successful poll returns fresh data. No user
intervention required. No burst.

### Net comparison

| Phase | Original (fleet) | New (fleet) |
|-------|------------------|-------------|
| Steady-state | ~120–160 req/min | ~120–160 req/min (identical) |
| Outage (first 3 min) | ~53 req/min + logins, then drops to ~0 | ~106 req/min + login retries |
| Outage (sustained) | ~0 (most in reauth state) | ~53 req/min (rate limiter blocks logins) |
| Recovery | **~12,844 burst** (thundering herd) | **0 burst** (transparent recovery) |
| User intervention | Required (manual reauth) | Not required |

**Conclusion**: the new logic trades slightly higher sustained load during outages
(~53 failing polls/min vs near-zero) for eliminating the thundering herd on recovery
(~12,844 burst → 0) and removing the need for 3,211 users to manually re-authenticate.
For the Honeywell API, predictable low-rate failures are far less damaging than a
concentrated burst of thousands of login+discover+refresh sequences hitting
simultaneously.

## Platforms

- **Climate** — thermostat control (heat, cool, auto, off), fan modes, preset modes (away, hold)
- **Sensor** — indoor/outdoor temperature and humidity
- **Switch** — emergency heat mode
- **Humidifier** — humidifier and dehumidifier control

## License

Apache-2.0
