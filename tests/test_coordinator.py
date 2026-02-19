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


async def test_coordinator_setup_succeeds_despite_refresh_error(
    hass: HomeAssistant,
    device: MagicMock,
    config_entry: MockConfigEntry,
    client: MagicMock,
) -> None:
    """Test setup succeeds even if device.refresh would error.

    The first coordinator refresh is skipped (discover already fetched data),
    so a transient device.refresh error does not block setup.
    """
    device.refresh = AsyncMock(side_effect=ClientConnectionError())
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Setup succeeds because the first coordinator refresh is skipped
    assert config_entry.state is ConfigEntryState.LOADED


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


async def test_coordinator_null_cookie_returns_cached_data(
    hass: HomeAssistant,
    device: MagicMock,
    config_entry: MockConfigEntry,
    client: MagicMock,
) -> None:
    """Test null cookie auth error is treated as transient, not credential failure."""
    await init_integration(hass, config_entry)

    entity_id = f"climate.{device.name}"
    assert hass.states.get(entity_id).state == "off"

    # Refresh triggers UnauthorizedError, both re-login attempts fail
    # with null cookie errors (site is down, not bad credentials)
    device.refresh.side_effect = aiosomecomfort.UnauthorizedError
    client.login.side_effect = aiosomecomfort.AuthError("Null cookie connection error 200")
    async_fire_time_changed(hass, utcnow() + SCAN_INTERVAL)
    await hass.async_block_till_done()

    # Should return cached data, NOT trigger reauth
    assert hass.states.get(entity_id).state == "off"
    assert not any(config_entry.async_get_active_flows(hass, {"reauth"}))


async def test_coordinator_relogin_retry_transient_error(
    hass: HomeAssistant,
    device: MagicMock,
    config_entry: MockConfigEntry,
    client: MagicMock,
) -> None:
    """Test transient error during login retry returns cached data."""
    await init_integration(hass, config_entry)

    entity_id = f"climate.{device.name}"
    assert hass.states.get(entity_id).state == "off"

    # Refresh triggers UnauthorizedError, first re-login fails with AuthError,
    # retry re-login hits APIRateLimited -> should return cached data
    device.refresh.side_effect = aiosomecomfort.UnauthorizedError
    client.login.side_effect = [aiosomecomfort.AuthError, aiosomecomfort.APIRateLimited]
    async_fire_time_changed(hass, utcnow() + SCAN_INTERVAL)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "off"
    assert not any(config_entry.async_get_active_flows(hass, {"reauth"}))


async def test_first_refresh_skipped_then_second_refreshes(
    hass: HomeAssistant,
    device: MagicMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test _skip_next_refresh prevents refresh on first cycle, allows on second."""
    await init_integration(hass, config_entry)

    # discover() already refreshed devices; the first coordinator cycle should
    # have been skipped, so device.refresh should not have been called.
    device.refresh.assert_not_called()

    # Second cycle (triggered by time advance) should call refresh normally.
    device.refresh.reset_mock()
    async_fire_time_changed(hass, utcnow() + SCAN_INTERVAL)
    await hass.async_block_till_done()

    device.refresh.assert_called_once()


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
