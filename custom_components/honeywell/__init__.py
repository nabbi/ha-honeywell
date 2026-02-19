"""Support for Honeywell (US) Total Connect Comfort climate systems."""

import aiosomecomfort
from aiohttp.client_exceptions import ClientConnectionError
from aiosomecomfort import APIRateLimited
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .const import _LOGGER, CONF_COOL_AWAY_TEMPERATURE, CONF_HEAT_AWAY_TEMPERATURE
from .coordinator import HoneywellConfigEntry, HoneywellCoordinator, HoneywellData

__all__ = ["HoneywellConfigEntry", "HoneywellData"]

PLATFORMS = [Platform.CLIMATE, Platform.HUMIDIFIER, Platform.SENSOR, Platform.SWITCH]

MIGRATE_OPTIONS_KEYS = {CONF_COOL_AWAY_TEMPERATURE, CONF_HEAT_AWAY_TEMPERATURE}


@callback
def _async_migrate_data_to_options(hass: HomeAssistant, config_entry: HoneywellConfigEntry) -> None:
    if not MIGRATE_OPTIONS_KEYS.intersection(config_entry.data):
        return
    hass.config_entries.async_update_entry(
        config_entry,
        data={k: v for k, v in config_entry.data.items() if k not in MIGRATE_OPTIONS_KEYS},
        options={
            **config_entry.options,
            **{k: config_entry.data.get(k) for k in MIGRATE_OPTIONS_KEYS},
        },
    )


async def async_setup_entry(hass: HomeAssistant, config_entry: HoneywellConfigEntry) -> bool:
    """Set up the Honeywell thermostat."""
    _async_migrate_data_to_options(hass, config_entry)

    username = config_entry.data[CONF_USERNAME]
    password = config_entry.data[CONF_PASSWORD]

    # Always create a new session for Honeywell to prevent cookie injection
    # issues. Even with response_url handling in aiosomecomfort 0.0.33+,
    # cookies can still leak into other integrations when using the shared
    # session. See issue #147395.
    session = async_create_clientsession(hass)
    client = aiosomecomfort.AIOSomeComfort(username, password, session=session)
    try:
        await client.login()
        await client.discover()

    except aiosomecomfort.device.AuthError as ex:
        raise ConfigEntryAuthFailed("Incorrect Password") from ex

    except APIRateLimited as ex:
        raise ConfigEntryNotReady("API rate limited, will retry with backoff") from ex

    except (
        aiosomecomfort.device.ConnectionError,
        aiosomecomfort.device.ConnectionTimeout,
        aiosomecomfort.device.SomeComfortError,
        ClientConnectionError,
        TimeoutError,
    ) as ex:
        raise ConfigEntryNotReady(
            "Failed to initialize the Honeywell client: Connection error"
        ) from ex

    devices: dict[int, aiosomecomfort.device.Device] = {}
    for location in client.locations_by_id.values():
        for device in location.devices_by_id.values():
            devices[device.deviceid] = device

    if len(devices) == 0:
        _LOGGER.debug("No devices found")
        return False

    coordinator = HoneywellCoordinator(hass, config_entry, client, devices)
    await coordinator.async_config_entry_first_refresh()

    config_entry.runtime_data = HoneywellData(coordinator)
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: HoneywellConfigEntry) -> bool:
    """Unload the config and platforms."""
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)
