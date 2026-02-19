"""Test the Honeywell coordinator."""

from unittest.mock import AsyncMock, MagicMock

import aiosomecomfort
import pytest
from aiohttp import ClientConnectionError
from homeassistant.config_entries import ConfigEntryState
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
    """Test coordinator returns cached data after re-login connection error."""
    await init_integration(hass, config_entry)

    entity_id = f"climate.{device.name}"
    state = hass.states.get(entity_id)
    assert state.state == "off"

    # First refresh raises UnauthorizedError, re-login succeeds,
    # but the second refresh raises a connection error -> returns cached data
    device.refresh.side_effect = [aiosomecomfort.UnauthorizedError, ClientConnectionError()]
    client.login.side_effect = None
    async_fire_time_changed(hass, utcnow() + SCAN_INTERVAL)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == "off"


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
    """Test all connection error types after re-login return cached data."""
    await init_integration(hass, config_entry)

    entity_id = f"climate.{device.name}"
    assert hass.states.get(entity_id).state == "off"

    device.refresh.side_effect = [aiosomecomfort.UnauthorizedError, error()]
    client.login.side_effect = None
    async_fire_time_changed(hass, utcnow() + SCAN_INTERVAL)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "off"


@pytest.mark.parametrize(
    "error",
    [
        TimeoutError,
        aiosomecomfort.ConnectionError,
        aiosomecomfort.APIRateLimited,
        ClientConnectionError,
    ],
)
async def test_coordinator_transient_error_returns_cached_data(
    hass: HomeAssistant,
    device: MagicMock,
    config_entry: MockConfigEntry,
    error: type[Exception],
) -> None:
    """Test transient errors return cached data instead of going unavailable."""
    await init_integration(hass, config_entry)

    entity_id = f"climate.{device.name}"
    assert hass.states.get(entity_id).state == "off"

    device.refresh.side_effect = error()
    async_fire_time_changed(hass, utcnow() + SCAN_INTERVAL)
    await hass.async_block_till_done()

    # Entity should keep its last known state, not go unavailable
    assert hass.states.get(entity_id).state == "off"


async def test_coordinator_transient_error_no_prior_data(
    hass: HomeAssistant,
    device: MagicMock,
    config_entry: MockConfigEntry,
    client: MagicMock,
) -> None:
    """Test transient error on first refresh raises UpdateFailed."""
    # Make the first coordinator refresh fail (during async_config_entry_first_refresh)
    device.refresh = AsyncMock(side_effect=ClientConnectionError())
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_coordinator_unexpected_response_returns_cached_data(
    hass: HomeAssistant,
    device: MagicMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test UnexpectedResponse returns cached data instead of going unavailable."""
    await init_integration(hass, config_entry)

    entity_id = f"climate.{device.name}"
    assert hass.states.get(entity_id).state == "off"

    device.refresh.side_effect = aiosomecomfort.UnexpectedResponse()
    async_fire_time_changed(hass, utcnow() + SCAN_INTERVAL)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "off"


async def test_coordinator_relogin_transient_auth_error(
    hass: HomeAssistant,
    device: MagicMock,
    config_entry: MockConfigEntry,
    client: MagicMock,
) -> None:
    """Test coordinator retries login on transient auth error and recovers."""
    await init_integration(hass, config_entry)

    entity_id = f"climate.{device.name}"
    assert hass.states.get(entity_id).state == "off"

    # Refresh triggers UnauthorizedError, first re-login fails with AuthError,
    # retry re-login succeeds and refresh succeeds
    device.refresh.side_effect = [aiosomecomfort.UnauthorizedError, None]
    client.login.side_effect = [aiosomecomfort.AuthError, True]
    async_fire_time_changed(hass, utcnow() + SCAN_INTERVAL)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "off"


async def test_coordinator_relogin_persistent_auth_error(
    hass: HomeAssistant,
    device: MagicMock,
    config_entry: MockConfigEntry,
    client: MagicMock,
) -> None:
    """Test coordinator triggers reauth after two consecutive auth failures."""
    await init_integration(hass, config_entry)

    entity_id = f"climate.{device.name}"
    assert hass.states.get(entity_id).state == "off"

    # Refresh triggers UnauthorizedError, both re-login attempts fail
    device.refresh.side_effect = aiosomecomfort.UnauthorizedError
    client.login.side_effect = aiosomecomfort.AuthError
    async_fire_time_changed(hass, utcnow() + SCAN_INTERVAL)
    await hass.async_block_till_done()

    # Persistent auth failure triggers reauth flow
    assert any(config_entry.async_get_active_flows(hass, {"reauth"}))


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
