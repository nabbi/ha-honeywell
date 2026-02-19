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
- **Parallel device refresh** — multi-device setups refresh all devices concurrently via `asyncio.gather` instead of sequentially, reducing wall-clock time from O(N) to O(1)
- **Eliminated startup double-fetch** — `discover()` already refreshes all devices; the first coordinator cycle is skipped to avoid 2 redundant HTTP calls per device on every HA restart

## API Load Impact Analysis (3,211 active installations)

Comparison of Honeywell API load between the original core integration logic and this
custom integration's error handling, assuming 3,211 active installations averaging
1.5 devices each.

### Steady-state (no errors)

The original core integration uses **per-entity polling at 30 s** — each climate entity
independently calls `device.refresh()`. This integration uses a **DataUpdateCoordinator
at 60 s** — one poll per installation refreshes all devices in a single cycle.

| Metric | Original (per-entity, 30 s) | New (coordinator, 60 s) |
|--------|-----------------------------|-------------------------|
| Poll interval | 30 s | 60 s |
| Poll unit | Per climate entity | Per installation |
| Polls/min (fleet) | 3,211 × 1.5 devices × 2/min = **~9,634** | 3,211 × 1/min = **~53** |
| HTTP requests/min (fleet) | ~9,634–19,267 | ~80–160 |
| **Reduction** | | **~99%** |

### During a Honeywell outage

The critical difference is what happens when the API returns errors.

#### Original core logic

| Scenario | Behavior | API calls per installation |
|----------|----------|--------------------------|
| Timeout / connection error | Entity goes unavailable after 3 retries, keeps polling at 30 s per entity | ~3 failing requests/min per device |
| 401 → re-login → AuthError | `ConfigEntryAuthFailed` → **reauth flow triggered, polling stops** | 2 requests then silence |
| 401 → re-login → null cookie | `ConfigEntryAuthFailed` → **reauth flow triggered, polling stops** | 2 requests then silence |

During an extended outage with connection errors, each entity keeps polling at 30 s
(~9,634 failing requests/min fleet-wide). With auth errors, most installations enter
reauth state within 1–2 poll cycles and polling stops. **Fleet load drops to near zero
for auth errors, but stays high for connection errors.**

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
| Steady-state | **~9,634–19,267 req/min** (per-entity, 30 s) | **~80–160 req/min** (coordinator, 60 s) |
| Outage (connection errors) | ~9,634 failing req/min | ~53 failing req/min |
| Outage (auth errors) | drops to ~0 (reauth stops polling) | ~53 req/min (rate limiter blocks logins) |
| Recovery | **~12,844 burst** (thundering herd) | **0 burst** (transparent recovery) |
| User intervention | Required (manual reauth) | Not required |

**Conclusion**: the coordinator migration alone reduces steady-state API load by ~99%
(~9,634 → ~53 polls/min). During outages, the new logic maintains ~53 failing polls/min
instead of either ~9,634 (connection errors) or dropping to zero then bursting ~12,844
calls on recovery (auth errors). For the Honeywell API, a predictable 53 req/min is far
less damaging than either 9,634 req/min of failing polls or a concentrated thundering
herd of login+discover+refresh sequences from 3,211 installations recovering
simultaneously.

## Platforms

- **Climate** — thermostat control (heat, cool, auto, off), fan modes, preset modes (away, hold)
- **Sensor** — indoor/outdoor temperature and humidity
- **Switch** — emergency heat mode
- **Humidifier** — humidifier and dehumidifier control

## License

Apache-2.0
