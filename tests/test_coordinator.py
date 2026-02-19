"""Test the Honeywell coordinator."""

from unittest.mock import MagicMock

import aiosomecomfort
import pytest
from aiohttp import ClientConnectionError
from homeassistant.core import HomeAssistant
from homeassistant.util.dt import utcnow
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.honeywell.coordinator import SCAN_INTERVAL

from . import init_integration


async def test_coordinator_relogin_connection_error(
    hass: HomeAssistant,
    device: MagicMock,
    config_entry: MockConfigEntry,
    client: MagicMock,
) -> None:
    """Test coordinator: UnauthorizedError -> re-login -> connection error on refresh."""
    await init_integration(hass, config_entry)

    entity_id = f"climate.{device.name}"
    state = hass.states.get(entity_id)
    assert state.state == "off"

    # First refresh raises UnauthorizedError, re-login succeeds,
    # but the second refresh raises a connection error -> UpdateFailed
    device.refresh.side_effect = [aiosomecomfort.UnauthorizedError, ClientConnectionError()]
    client.login.side_effect = None
    async_fire_time_changed(hass, utcnow() + SCAN_INTERVAL)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == "unavailable"


@pytest.mark.parametrize(
    "error",
    [
        TimeoutError,
        aiosomecomfort.ConnectionError,
        aiosomecomfort.APIRateLimited,
        ClientConnectionError,
    ],
)
async def test_coordinator_relogin_connection_errors_parametrized(
    hass: HomeAssistant,
    device: MagicMock,
    config_entry: MockConfigEntry,
    client: MagicMock,
    error: type[Exception],
) -> None:
    """Test all connection error types after re-login raise UpdateFailed."""
    await init_integration(hass, config_entry)

    entity_id = f"climate.{device.name}"
    assert hass.states.get(entity_id).state == "off"

    device.refresh.side_effect = [aiosomecomfort.UnauthorizedError, error()]
    client.login.side_effect = None
    async_fire_time_changed(hass, utcnow() + SCAN_INTERVAL)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "unavailable"


async def test_honeywelldata_client_property(
    hass: HomeAssistant,
    device: MagicMock,
    config_entry: MockConfigEntry,
    client: MagicMock,
) -> None:
    """Test HoneywellData.client property returns the coordinator's client."""
    await init_integration(hass, config_entry)

    data = config_entry.runtime_data
    assert data.client is client
