"""DataUpdateCoordinator for Honeywell."""

from __future__ import annotations

import asyncio
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

_TRANSIENT_ERRORS = (
    TimeoutError,
    AscConnectionError,
    APIRateLimited,
    ClientConnectionError,
)


def _fmt_error(err: Exception) -> str:
    """Format an exception with its type name, useful when str(err) is empty."""
    msg = str(err)
    name = type(err).__name__
    return f"{name}: {msg}" if msg else name


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
        self._skip_next_refresh = False
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> dict[int, SomeComfortDevice]:
        """Fetch data from Honeywell."""
        if self._skip_next_refresh:
            self._skip_next_refresh = False
            return self.devices

        try:
            await self._async_refresh_devices()
        except UnauthorizedError:
            try:
                await self.client.login()
                await self._async_refresh_devices()
            except AuthError:
                # Retry login once — Honeywell sometimes rejects valid
                # credentials under load.
                try:
                    await self.client.login()
                    await self._async_refresh_devices()
                except AuthError as ex:
                    # Null cookie means the site is down, not bad credentials.
                    # Treat as transient to avoid forcing reauth with valid creds.
                    if "Null cookie" in str(ex):
                        return self._handle_transient_error(
                            f"Login failed (site may be down): {_fmt_error(ex)}", ex
                        )
                    raise ConfigEntryAuthFailed("Incorrect credentials") from ex
                except _TRANSIENT_ERRORS as ex:
                    return self._handle_transient_error(
                        f"Failed to refresh after re-login retry: {_fmt_error(ex)}", ex
                    )
            except _TRANSIENT_ERRORS as ex:
                return self._handle_transient_error(
                    f"Failed to refresh after re-login: {_fmt_error(ex)}", ex
                )
        except _TRANSIENT_ERRORS as err:
            return self._handle_transient_error(f"Connection failed: {_fmt_error(err)}", err)
        except UnexpectedResponse as err:
            return self._handle_transient_error(f"Unexpected API response: {_fmt_error(err)}", err)

        return self.devices

    async def _async_refresh_devices(self) -> None:
        """Refresh all devices in parallel."""
        if not self.devices:
            return
        loop = asyncio.get_running_loop()
        tasks = [
            asyncio.Task(device.refresh(), loop=loop, eager_start=True)
            for device in self.devices.values()
        ]
        await asyncio.gather(*tasks)

    def _handle_transient_error(self, msg: str, err: Exception) -> dict[int, SomeComfortDevice]:
        """Return stale data on transient errors, or raise if no prior data."""
        if self.data is not None:
            _LOGGER.warning("%s; returning cached data", msg)
            return self.devices
        raise UpdateFailed(msg) from err
