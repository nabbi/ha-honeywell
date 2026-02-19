"""Test the Honeywell diagnostics."""

from unittest.mock import MagicMock

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from . import init_integration


async def test_diagnostics(
    hass: HomeAssistant,
    device: MagicMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test diagnostics returns expected device data."""
    await init_integration(hass, config_entry)

    from custom_components.honeywell.diagnostics import async_get_config_entry_diagnostics

    result = await async_get_config_entry_diagnostics(hass, config_entry)

    assert f"Device {device.deviceid}" in result
    device_diag = result[f"Device {device.deviceid}"]
    assert device_diag["UI Data"] == device.raw_ui_data
    assert device_diag["Fan Data"] == device.raw_fan_data
    assert device_diag["DR Data"] == device.raw_dr_data
