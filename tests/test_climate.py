"""Test the Honeywell climate domain."""

import datetime
from unittest.mock import MagicMock

import aiosomecomfort
import pytest
from aiohttp import ClientConnectionError
from freezegun.api import FrozenDateTimeFactory
from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    ATTR_HVAC_MODE,
    ATTR_PRESET_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    FAN_AUTO,
    FAN_DIFFUSE,
    FAN_ON,
    PRESET_AWAY,
    PRESET_NONE,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACMode,
)
from homeassistant.components.climate import (
    DOMAIN as CLIMATE_DOMAIN,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.util.dt import utcnow
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.honeywell.climate import (
    DOMAIN,
    MODE_PERMANENT_HOLD,
    MODE_TEMPORARY_HOLD,
    PRESET_HOLD,
)
from custom_components.honeywell.coordinator import SCAN_INTERVAL

from . import init_integration, reset_mock

FAN_ACTION = "fan_action"


async def test_no_thermostat_options(
    hass: HomeAssistant, device: MagicMock, config_entry: MagicMock
) -> None:
    """Test the setup of the climate entities when there are no additional options available."""
    device._data = {}
    await init_integration(hass, config_entry)
    assert hass.states.get("climate.device1")
    assert hass.states.get("sensor.device1_temperature")
    assert hass.states.get("sensor.device1_humidity")


async def test_dynamic_attributes(
    hass: HomeAssistant, device: MagicMock, config_entry: MagicMock
) -> None:
    """Test dynamic attributes."""
    await init_integration(hass, config_entry)

    entity_id = f"climate.{device.name}"
    state = hass.states.get(entity_id)
    assert state.state == HVACMode.OFF
    attributes = state.attributes
    assert attributes["current_temperature"] == 20
    assert attributes["current_humidity"] == 50

    device.system_mode = "cool"
    device.current_temperature = 21
    device.current_humidity = 55

    async_fire_time_changed(
        hass,
        utcnow() + SCAN_INTERVAL,
    )
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == HVACMode.COOL
    attributes = state.attributes
    assert attributes["current_temperature"] == 21
    assert attributes["current_humidity"] == 55

    device.system_mode = "heat"
    device.current_temperature = 61
    device.current_humidity = 50

    async_fire_time_changed(
        hass,
        utcnow() + SCAN_INTERVAL,
    )
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == HVACMode.HEAT
    attributes = state.attributes
    assert attributes["current_temperature"] == 61
    assert attributes["current_humidity"] == 50

    device.system_mode = "auto"

    async_fire_time_changed(
        hass,
        utcnow() + SCAN_INTERVAL,
    )
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == HVACMode.HEAT_COOL
    attributes = state.attributes
    assert attributes["current_temperature"] == 61
    assert attributes["current_humidity"] == 50


async def test_mode_service_calls(
    hass: HomeAssistant,
    device: MagicMock,
    config_entry: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test controlling the entity mode through service calls."""
    await init_integration(hass, config_entry)
    entity_id = f"climate.{device.name}"

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    device.set_system_mode.assert_called_once_with("off")

    device.set_system_mode.reset_mock()
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    device.set_system_mode.assert_called_once_with("auto")

    device.set_system_mode.reset_mock()
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_HVAC_MODE: HVACMode.COOL},
        blocking=True,
    )
    device.set_system_mode.assert_called_once_with("cool")

    device.set_system_mode.reset_mock()
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_HVAC_MODE: HVACMode.HEAT},
        blocking=True,
    )
    device.set_system_mode.assert_called_once_with("heat")

    device.set_system_mode.reset_mock()
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_HVAC_MODE: HVACMode.HEAT_COOL},
        blocking=True,
    )
    device.set_system_mode.assert_called_once_with("auto")

    device.set_system_mode.reset_mock()
    device.set_system_mode.side_effect = aiosomecomfort.SomeComfortError
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: entity_id, ATTR_HVAC_MODE: HVACMode.HEAT_COOL},
            blocking=True,
        )
    device.set_system_mode.assert_called_once_with("auto")

    device.set_system_mode.reset_mock()
    device.set_system_mode.side_effect = aiosomecomfort.UnexpectedResponse
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: entity_id, ATTR_HVAC_MODE: HVACMode.HEAT_COOL},
            blocking=True,
        )


async def test_fan_modes_service_calls(
    hass: HomeAssistant, device: MagicMock, config_entry: MagicMock
) -> None:
    """Test controlling the fan modes through service calls."""
    await init_integration(hass, config_entry)
    entity_id = f"climate.{device.name}"

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_FAN_MODE: FAN_AUTO},
        blocking=True,
    )

    device.set_fan_mode.assert_called_once_with("auto")

    device.set_fan_mode.reset_mock()
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_FAN_MODE: FAN_ON},
        blocking=True,
    )

    device.set_fan_mode.assert_called_once_with("on")

    device.set_fan_mode.reset_mock()
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_FAN_MODE: FAN_DIFFUSE},
        blocking=True,
    )

    device.set_fan_mode.assert_called_once_with("circulate")

    device.set_fan_mode.reset_mock()

    device.set_fan_mode.side_effect = aiosomecomfort.SomeComfortError
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_FAN_MODE,
            {ATTR_ENTITY_ID: entity_id, ATTR_FAN_MODE: FAN_DIFFUSE},
            blocking=True,
        )

    device.set_fan_mode.side_effect = aiosomecomfort.UnexpectedResponse
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_FAN_MODE,
            {ATTR_ENTITY_ID: entity_id, ATTR_FAN_MODE: FAN_DIFFUSE},
            blocking=True,
        )


async def test_service_calls_off_mode(
    hass: HomeAssistant,
    device: MagicMock,
    config_entry: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test controlling the entity through service calls."""
    device.system_mode = "off"

    await init_integration(hass, config_entry)
    entity_id = f"climate.{device.name}"

    async_fire_time_changed(
        hass,
        utcnow() + SCAN_INTERVAL,
    )
    await hass.async_block_till_done()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: entity_id, ATTR_TEMPERATURE: 35},
        blocking=True,
    )

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_TARGET_TEMP_LOW: 25.0,
            ATTR_TARGET_TEMP_HIGH: 35.0,
        },
        blocking=True,
    )
    device.set_setpoint_cool.assert_called_with(35)
    device.set_setpoint_heat.assert_called_with(25)

    device.set_setpoint_heat.reset_mock()
    device.set_setpoint_heat.side_effect = aiosomecomfort.SomeComfortError
    caplog.clear()

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {
                ATTR_ENTITY_ID: entity_id,
                ATTR_TARGET_TEMP_LOW: 24.0,
                ATTR_TARGET_TEMP_HIGH: 34.0,
            },
            blocking=True,
        )
    device.set_setpoint_cool.assert_called_with(34)
    device.set_setpoint_heat.assert_called_with(24)
    assert "Invalid temperature" in caplog.text

    device.set_setpoint_heat.reset_mock()
    device.set_setpoint_heat.side_effect = aiosomecomfort.UnexpectedResponse
    caplog.clear()

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {
                ATTR_ENTITY_ID: entity_id,
                ATTR_TARGET_TEMP_LOW: 25.0,
                ATTR_TARGET_TEMP_HIGH: 35.0,
            },
            blocking=True,
        )
    device.set_setpoint_cool.assert_called_with(35)
    device.set_setpoint_heat.assert_called_with(25)

    reset_mock(device)
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: entity_id, ATTR_TEMPERATURE: 35},
        blocking=True,
    )
    device.set_setpoint_heat.assert_not_called()
    device.set_setpoint_cool.assert_not_called()

    reset_mock(device)
    device.raw_ui_data["StatusHeat"] = 2
    device.raw_ui_data["StatusCool"] = 2

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: PRESET_HOLD},
        blocking=True,
    )

    device.set_hold_cool.assert_not_called()
    device.set_hold_heat.assert_not_called()

    reset_mock(device)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: PRESET_AWAY},
        blocking=True,
    )

    device.set_hold_cool.assert_not_called()
    device.set_setpoint_cool.assert_not_called()
    device.set_hold_heat.assert_not_called()
    device.set_setpoint_heat.assert_not_called()

    device.set_hold_heat.reset_mock()
    device.set_hold_cool.reset_mock()

    device.set_setpoint_cool.reset_mock()
    device.set_setpoint_heat.reset_mock()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: PRESET_NONE},
        blocking=True,
    )

    device.set_hold_heat.assert_called_once_with(False)
    device.set_hold_cool.assert_called_once_with(False)

    device.set_hold_heat.reset_mock()
    device.set_hold_cool.reset_mock()

    device.set_setpoint_cool.reset_mock()
    device.set_setpoint_heat.reset_mock()

    reset_mock(device)

    device.raw_ui_data["StatusHeat"] = 2
    device.raw_ui_data["StatusCool"] = 2

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: PRESET_HOLD},
        blocking=True,
    )

    device.set_hold_heat.assert_not_called()
    device.set_hold_cool.assert_not_called()

    reset_mock(device)
    device.set_hold_heat.side_effect = aiosomecomfort.SomeComfortError
    device.raw_ui_data["StatusHeat"] = 2
    device.raw_ui_data["StatusCool"] = 2
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: PRESET_HOLD},
        blocking=True,
    )

    device.set_hold_heat.assert_not_called()
    device.set_hold_cool.assert_not_called()


async def test_service_calls_cool_mode(
    hass: HomeAssistant,
    device: MagicMock,
    config_entry: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test controlling the entity through service calls."""
    device.system_mode = "cool"

    await init_integration(hass, config_entry)
    entity_id = f"climate.{device.name}"

    async_fire_time_changed(
        hass,
        utcnow() + SCAN_INTERVAL,
    )
    await hass.async_block_till_done()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: entity_id, ATTR_TEMPERATURE: 15},
        blocking=True,
    )
    device.set_hold_cool.assert_called_once_with(datetime.time(2, 30), 15)
    device.set_hold_cool.reset_mock()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_TARGET_TEMP_LOW: 15.0,
            ATTR_TARGET_TEMP_HIGH: 20.0,
        },
        blocking=True,
    )
    device.set_setpoint_cool.assert_called_with(20)
    device.set_setpoint_heat.assert_called_with(15)

    caplog.clear()
    device.set_setpoint_cool.reset_mock()
    device.set_setpoint_cool.side_effect = aiosomecomfort.SomeComfortError

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {
                ATTR_ENTITY_ID: entity_id,
                ATTR_TARGET_TEMP_LOW: 15.0,
                ATTR_TARGET_TEMP_HIGH: 20.0,
            },
            blocking=True,
        )
    device.set_setpoint_cool.assert_called_with(20)
    device.set_setpoint_heat.assert_called_with(15)
    assert "Invalid temperature" in caplog.text

    reset_mock(device)
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: PRESET_AWAY},
        blocking=True,
    )

    device.set_hold_cool.assert_called_once_with(True, 12)
    device.set_hold_heat.assert_not_called()
    device.set_setpoint_heat.assert_not_called()

    reset_mock(device)

    device.set_hold_cool.side_effect = aiosomecomfort.SomeComfortError
    caplog.clear()

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: PRESET_AWAY},
            blocking=True,
        )

    device.set_hold_cool.assert_called_once_with(True, 12)
    device.set_hold_heat.assert_not_called()
    device.set_setpoint_heat.assert_not_called()
    assert "Temperature out of range" in caplog.text

    reset_mock(device)

    device.raw_ui_data["StatusHeat"] = 2
    device.raw_ui_data["StatusCool"] = 2

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: PRESET_HOLD},
            blocking=True,
        )

    device.set_hold_cool.assert_called_once_with(True)
    device.set_hold_heat.assert_not_called()

    device.hold_heat = True
    device.hold_cool = True

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: entity_id, ATTR_TEMPERATURE: "20"},
            blocking=True,
        )

    device.set_setpoint_cool.assert_called_once()

    reset_mock(device)
    device.set_hold_cool.side_effect = aiosomecomfort.SomeComfortError

    device.raw_ui_data["StatusHeat"] = 2
    device.raw_ui_data["StatusCool"] = 2
    caplog.clear()
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: PRESET_HOLD},
            blocking=True,
        )
    device.set_hold_cool.assert_called_once_with(True)
    device.set_hold_heat.assert_not_called()
    assert "Couldn't set permanent hold" in caplog.text

    reset_mock(device)
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: PRESET_NONE},
            blocking=True,
        )

    device.set_hold_heat.assert_not_called()
    device.set_hold_cool.assert_called_once_with(False)

    reset_mock(device)
    caplog.clear()

    device.set_hold_cool.side_effect = aiosomecomfort.SomeComfortError
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: PRESET_NONE},
            blocking=True,
        )

    device.set_hold_heat.assert_not_called()
    device.set_hold_cool.assert_called_once_with(False)
    assert "Can not stop hold mode" in caplog.text

    reset_mock(device)

    device.raw_ui_data["StatusHeat"] = 2
    device.raw_ui_data["StatusCool"] = 2

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: PRESET_HOLD},
            blocking=True,
        )

    device.set_hold_cool.assert_called_once_with(True)
    device.set_hold_heat.assert_not_called()

    reset_mock(device)
    caplog.clear()

    device.set_hold_cool.side_effect = aiosomecomfort.SomeComfortError

    device.raw_ui_data["StatusHeat"] = 2
    device.raw_ui_data["StatusCool"] = 2
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: PRESET_HOLD},
            blocking=True,
        )

    device.set_hold_cool.assert_called_once_with(True)
    device.set_hold_heat.assert_not_called()
    assert "Couldn't set permanent hold" in caplog.text

    reset_mock(device)
    caplog.clear()

    device.raw_ui_data["StatusHeat"] = 2
    device.raw_ui_data["StatusCool"] = 2
    device.system_mode = "Junk"

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: PRESET_HOLD},
            blocking=True,
        )

    device.set_hold_cool.assert_not_called()
    device.set_hold_heat.assert_not_called()
    assert "Invalid system mode returned" in caplog.text


async def test_service_calls_heat_mode(
    hass: HomeAssistant,
    device: MagicMock,
    config_entry: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test controlling the entity through service calls."""
    device.system_mode = "heat"

    await init_integration(hass, config_entry)
    entity_id = f"climate.{device.name}"

    async_fire_time_changed(
        hass,
        utcnow() + SCAN_INTERVAL,
    )
    await hass.async_block_till_done()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: entity_id, ATTR_TEMPERATURE: 25},
        blocking=True,
    )
    device.set_hold_heat.assert_called_once_with(datetime.time(2, 30), 25)
    device.set_hold_heat.reset_mock()

    device.set_hold_heat.side_effect = aiosomecomfort.SomeComfortError
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: entity_id, ATTR_TEMPERATURE: 25},
            blocking=True,
        )
    device.set_hold_heat.assert_called_once_with(datetime.time(2, 30), 25)
    device.set_hold_heat.reset_mock()
    assert "Invalid temperature" in caplog.text

    device.set_hold_heat.side_effect = aiosomecomfort.UnexpectedResponse
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: entity_id, ATTR_TEMPERATURE: 25},
            blocking=True,
        )
    device.set_hold_heat.assert_called_once_with(datetime.time(2, 30), 25)
    device.set_hold_heat.reset_mock()

    caplog.clear()
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_TARGET_TEMP_LOW: 25.0,
            ATTR_TARGET_TEMP_HIGH: 35.0,
        },
        blocking=True,
    )
    device.set_setpoint_cool.assert_called_with(35)
    device.set_setpoint_heat.assert_called_with(25)

    device.set_setpoint_heat.reset_mock()
    device.set_setpoint_heat.side_effect = aiosomecomfort.SomeComfortError
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {
                ATTR_ENTITY_ID: entity_id,
                ATTR_TARGET_TEMP_LOW: 25.0,
                ATTR_TARGET_TEMP_HIGH: 35.0,
            },
            blocking=True,
        )
    device.set_setpoint_cool.assert_called_with(35)
    device.set_setpoint_heat.assert_called_with(25)
    assert "Invalid temperature" in caplog.text

    reset_mock(device)
    device.raw_ui_data["StatusHeat"] = 2
    device.raw_ui_data["StatusCool"] = 2

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: PRESET_HOLD},
            blocking=True,
        )

    device.set_hold_heat.assert_called_once_with(True)
    device.set_hold_cool.assert_not_called()

    device.hold_heat = True
    device.hold_cool = True

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: entity_id, ATTR_TEMPERATURE: "20"},
            blocking=True,
        )

    device.set_setpoint_heat.assert_called_once()

    reset_mock(device)
    caplog.clear()

    device.set_hold_heat.side_effect = aiosomecomfort.SomeComfortError

    device.raw_ui_data["StatusHeat"] = 2
    device.raw_ui_data["StatusCool"] = 2

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: PRESET_HOLD},
            blocking=True,
        )
    device.set_hold_heat.assert_called_once_with(True)
    device.set_hold_cool.assert_not_called()
    assert "Couldn't set permanent hold" in caplog.text

    reset_mock(device)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: PRESET_AWAY},
            blocking=True,
        )

    device.set_hold_heat.assert_called_once_with(True, 22)
    device.set_hold_cool.assert_not_called()
    device.set_setpoint_cool.assert_not_called()

    reset_mock(device)
    caplog.clear()

    device.set_hold_heat.side_effect = aiosomecomfort.SomeComfortError

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: PRESET_AWAY},
            blocking=True,
        )

    device.set_hold_heat.assert_called_once_with(True, 22)
    device.set_hold_cool.assert_not_called()
    device.set_setpoint_cool.assert_not_called()
    assert "Temperature out of range" in caplog.text

    device.set_hold_heat.side_effect = aiosomecomfort.UnexpectedResponse

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: PRESET_AWAY},
            blocking=True,
        )

    reset_mock(device)
    caplog.clear()
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: PRESET_NONE},
            blocking=True,
        )

    device.set_hold_heat.assert_called_once_with(False)
    device.set_hold_cool.assert_called_once_with(False)

    device.set_hold_heat.reset_mock()
    device.set_hold_cool.reset_mock()
    device.set_hold_heat.side_effect = aiosomecomfort.SomeComfortError
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: PRESET_NONE},
            blocking=True,
        )

    device.set_hold_heat.assert_called_once_with(False)
    assert "Can not stop hold mode" in caplog.text

    reset_mock(device)
    device.raw_ui_data["StatusHeat"] = 2
    device.raw_ui_data["StatusCool"] = 2

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: PRESET_HOLD},
            blocking=True,
        )

    device.set_hold_heat.assert_called_once_with(True)
    device.set_hold_cool.assert_not_called()

    reset_mock(device)
    device.set_hold_heat.side_effect = aiosomecomfort.SomeComfortError

    device.raw_ui_data["StatusHeat"] = 2
    device.raw_ui_data["StatusCool"] = 2

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: PRESET_HOLD},
            blocking=True,
        )

    device.set_hold_heat.assert_called_once_with(True)
    device.set_hold_cool.assert_not_called()

    reset_mock(device)


async def test_service_calls_auto_mode(
    hass: HomeAssistant,
    device: MagicMock,
    config_entry: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test controlling the entity through service calls."""
    device.system_mode = "auto"

    await init_integration(hass, config_entry)
    entity_id = f"climate.{device.name}"

    async_fire_time_changed(
        hass,
        utcnow() + SCAN_INTERVAL,
    )
    await hass.async_block_till_done()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: entity_id, ATTR_TEMPERATURE: 15},
        blocking=True,
    )
    device.set_setpoint_cool.assert_not_called()
    device.set_setpoint_heat.assert_not_called()

    reset_mock(device)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_TARGET_TEMP_LOW: 25.0,
            ATTR_TARGET_TEMP_HIGH: 35.0,
        },
        blocking=True,
    )
    device.set_setpoint_cool.assert_called_once_with(35)
    device.set_setpoint_heat.assert_called_once_with(25)

    reset_mock(device)
    caplog.clear()

    device.set_hold_cool.side_effect = aiosomecomfort.SomeComfortError
    device.set_hold_heat.side_effect = aiosomecomfort.SomeComfortError
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: entity_id, ATTR_TEMPERATURE: 15},
            blocking=True,
        )
    device.set_setpoint_heat.assert_not_called()
    assert "Invalid temperature" in caplog.text

    reset_mock(device)
    caplog.clear()

    device.set_setpoint_heat.side_effect = aiosomecomfort.SomeComfortError
    device.set_setpoint_cool.side_effect = aiosomecomfort.SomeComfortError
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {
                ATTR_ENTITY_ID: entity_id,
                ATTR_TARGET_TEMP_LOW: 25.0,
                ATTR_TARGET_TEMP_HIGH: 35.0,
            },
            blocking=True,
        )
    device.set_setpoint_heat.assert_not_called()
    assert "Invalid temperature" in caplog.text

    reset_mock(device)
    caplog.clear()

    device.set_hold_heat.side_effect = None
    device.set_hold_cool.side_effect = None

    device.raw_ui_data["StatusHeat"] = 2
    device.raw_ui_data["StatusCool"] = 2

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: PRESET_HOLD},
        blocking=True,
    )

    device.set_hold_cool.assert_called_once_with(True)
    device.set_hold_heat.assert_called_once_with(True)

    reset_mock(device)
    caplog.clear()

    device.set_hold_heat.side_effect = aiosomecomfort.SomeComfortError
    device.raw_ui_data["StatusHeat"] = 2
    device.raw_ui_data["StatusCool"] = 2

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: PRESET_HOLD},
            blocking=True,
        )
    device.set_hold_cool.assert_called_once_with(True)
    device.set_hold_heat.assert_called_once_with(True)
    assert "Couldn't set permanent hold" in caplog.text

    reset_mock(device)
    device.set_setpoint_heat.side_effect = None
    device.set_setpoint_cool.side_effect = None

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: PRESET_AWAY},
            blocking=True,
        )

    device.set_hold_cool.assert_called_once_with(True, 12)
    device.set_hold_heat.assert_called_once_with(True, 22)

    reset_mock(device)
    caplog.clear()

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: PRESET_NONE},
            blocking=True,
        )

    device.set_hold_heat.assert_called_once_with(False)
    device.set_hold_cool.assert_called_once_with(False)

    reset_mock(device)
    device.set_hold_cool.side_effect = aiosomecomfort.SomeComfortError
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: PRESET_NONE},
            blocking=True,
        )

    device.set_hold_heat.assert_not_called()
    device.set_hold_cool.assert_called_once_with(False)
    assert "Can not stop hold mode" in caplog.text

    reset_mock(device)
    caplog.clear()

    device.raw_ui_data["StatusHeat"] = 2
    device.raw_ui_data["StatusCool"] = 2

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: PRESET_HOLD},
            blocking=True,
        )

    device.set_hold_cool.assert_called_once_with(True)
    device.set_hold_heat.assert_not_called()

    reset_mock(device)

    device.set_hold_cool.side_effect = aiosomecomfort.SomeComfortError
    device.raw_ui_data["StatusHeat"] = 2
    device.raw_ui_data["StatusCool"] = 2

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: PRESET_HOLD},
            blocking=True,
        )

    device.set_hold_cool.assert_called_once_with(True)
    device.set_hold_heat.assert_not_called()
    assert "Couldn't set permanent hold" in caplog.text


async def test_async_update_errors(
    hass: HomeAssistant,
    device: MagicMock,
    config_entry: MagicMock,
    client: MagicMock,
) -> None:
    """Test transient errors return cached data, keeping entities available."""
    await init_integration(hass, config_entry)

    entity_id = f"climate.{device.name}"
    state = hass.states.get(entity_id)
    assert state.state == "off"

    # Simulate connection error - entity keeps cached state
    device.refresh.side_effect = ClientConnectionError
    async_fire_time_changed(
        hass,
        utcnow() + SCAN_INTERVAL,
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == "off"

    # Recovery
    device.refresh.side_effect = None
    async_fire_time_changed(
        hass,
        utcnow() + SCAN_INTERVAL,
    )
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == "off"

    # UnexpectedResponse also returns cached data
    device.refresh.side_effect = aiosomecomfort.UnexpectedResponse
    async_fire_time_changed(
        hass,
        utcnow() + SCAN_INTERVAL,
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == "off"

    # Recovery again
    device.refresh.side_effect = None
    async_fire_time_changed(
        hass,
        utcnow() + SCAN_INTERVAL,
    )
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == "off"

    # UnauthorizedError triggers re-login, then recovery
    device.refresh.side_effect = [aiosomecomfort.UnauthorizedError, None]
    client.login.side_effect = None
    async_fire_time_changed(
        hass,
        utcnow() + SCAN_INTERVAL,
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == "off"


async def test_async_update_auth_failed(
    hass: HomeAssistant,
    device: MagicMock,
    config_entry: MagicMock,
    client: MagicMock,
) -> None:
    """Test coordinator auth failure triggers reauth flow."""
    await init_integration(hass, config_entry)

    entity_id = f"climate.{device.name}"
    state = hass.states.get(entity_id)
    assert state.state == "off"

    # UnauthorizedError + AuthError on re-login -> ConfigEntryAuthFailed
    device.refresh.side_effect = aiosomecomfort.UnauthorizedError
    client.login.side_effect = aiosomecomfort.AuthError
    async_fire_time_changed(
        hass,
        utcnow() + SCAN_INTERVAL,
    )
    await hass.async_block_till_done()

    # Entity should be unavailable and reauth flow should be triggered
    state = hass.states.get(entity_id)
    assert state.state == "unavailable"


async def test_unique_id(
    hass: HomeAssistant,
    device: MagicMock,
    config_entry: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test unique id convert to string."""
    config_entry.add_to_hass(hass)
    entity_registry.async_get_or_create(
        Platform.CLIMATE,
        DOMAIN,
        device.deviceid,
        config_entry=config_entry,
        suggested_object_id=device.name,
    )
    await init_integration(hass, config_entry)
    entity_entry = entity_registry.async_get(f"climate.{device.name}")
    assert entity_entry.unique_id == str(device.deviceid)


async def test_preset_mode(
    hass: HomeAssistant,
    device: MagicMock,
    config_entry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test mode settings properly reflected."""
    await init_integration(hass, config_entry)
    entity_id = f"climate.{device.name}"

    device.raw_ui_data["StatusHeat"] = 3
    device.raw_ui_data["StatusCool"] = 3

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_PRESET_MODE] == PRESET_NONE

    device.raw_ui_data["StatusHeat"] = MODE_TEMPORARY_HOLD
    device.raw_ui_data["StatusCool"] = MODE_TEMPORARY_HOLD

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_PRESET_MODE] == PRESET_HOLD

    device.raw_ui_data["StatusHeat"] = MODE_PERMANENT_HOLD
    device.raw_ui_data["StatusCool"] = MODE_PERMANENT_HOLD

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_PRESET_MODE] == PRESET_HOLD

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: PRESET_AWAY},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_PRESET_MODE] == PRESET_AWAY

    device.raw_ui_data["StatusHeat"] = 3
    device.raw_ui_data["StatusCool"] = 3
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_PRESET_MODE] == PRESET_NONE

    # Test away mode re-entry: turning away off and back on should not
    # be corrupted by stale _away_hold state from the previous cycle.
    device.raw_ui_data["StatusHeat"] = MODE_PERMANENT_HOLD
    device.raw_ui_data["StatusCool"] = MODE_PERMANENT_HOLD

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: PRESET_AWAY},
        blocking=True,
    )
    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_PRESET_MODE] == PRESET_AWAY

    # Turn away off — simulate the device clearing hold status
    device.raw_ui_data["StatusHeat"] = 0
    device.raw_ui_data["StatusCool"] = 0
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: PRESET_NONE},
        blocking=True,
    )
    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_PRESET_MODE] == PRESET_NONE

    # Re-enter away mode with hold active — should show AWAY, not be
    # cancelled by stale _away_hold from the previous cycle.
    device.raw_ui_data["StatusHeat"] = MODE_PERMANENT_HOLD
    device.raw_ui_data["StatusCool"] = MODE_PERMANENT_HOLD
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: PRESET_AWAY},
        blocking=True,
    )
    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_PRESET_MODE] == PRESET_AWAY
