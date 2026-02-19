"""DataUpdateCoordinator for Honeywell."""

from __future__ import annotations

import logging
from datetime import timedelta

from aiohttp.client_exceptions import ClientConnectionError
from aiosomecomfort import (
    AIOSomeComfort,
    APIRateLimited,
    AuthError,
    UnauthorizedError,
    UnexpectedResponse,
)
from aiosomecomfort import (
    ConnectionError as AscConnectionError,
)
from aiosomecomfort.device import Device as SomeComfortDevice
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=60)

type HoneywellConfigEntry = ConfigEntry[HoneywellData]


class HoneywellData:
    """Shared data for Honeywell stored in runtime_data."""

    def __init__(
        self,
        coordinator: HoneywellCoordinator,
    ) -> None:
        """Initialize."""
        self.coordinator = coordinator

    @property
    def client(self) -> AIOSomeComfort:
        """Return the client."""
        return self.coordinator.client

    @property
    def devices(self) -> dict[int, SomeComfortDevice]:
        """Return the devices."""
        return self.coordinator.devices


class HoneywellCoordinator(DataUpdateCoordinator[dict[int, SomeComfortDevice]]):
    """Class to manage fetching Honeywell data."""

    config_entry: HoneywellConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: HoneywellConfigEntry,
        client: AIOSomeComfort,
        devices: dict[int, SomeComfortDevice],
    ) -> None:
        """Initialize."""
        self.client = client
        self.devices = devices
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> dict[int, SomeComfortDevice]:
        """Fetch data from Honeywell."""
        try:
            for device in self.devices.values():
                await device.refresh()
        except UnauthorizedError:
            try:
                await self.client.login()
                for device in self.devices.values():
                    await device.refresh()
            except AuthError as ex:
                raise ConfigEntryAuthFailed("Incorrect credentials") from ex
            except (
                TimeoutError,
                AscConnectionError,
                APIRateLimited,
                ClientConnectionError,
            ) as ex:
                raise UpdateFailed(f"Failed to refresh after re-login: {ex}") from ex
        except (
            TimeoutError,
            AscConnectionError,
            APIRateLimited,
            ClientConnectionError,
        ) as err:
            raise UpdateFailed(f"Connection failed: {err}") from err
        except UnexpectedResponse as err:
            raise UpdateFailed(f"Unexpected API response: {err}") from err

        return self.devices
