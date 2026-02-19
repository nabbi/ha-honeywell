"""Test the Honeywell humidity domain."""

from unittest.mock import MagicMock

import pytest
from aiosomecomfort import SomeComfortError
from homeassistant.components.humidifier import (
    ATTR_HUMIDITY,
    SERVICE_SET_HUMIDITY,
)
from homeassistant.components.humidifier import (
    DOMAIN as HUMIDIFIER_DOMAIN,
)
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import init_integration


async def test_humidifier_service_calls(
    hass: HomeAssistant, device: MagicMock, config_entry: MagicMock
) -> None:
    """Test the setup of the climate entities when there are no additional options available."""
    device.has_humidifier = True
    await init_integration(hass, config_entry)
    entity_id = f"humidifier.{device.name}_humidifier"
    assert hass.states.get(f"humidifier.{device.name}_dehumidifier") is None

    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    device.set_humidifier_auto.assert_called_once()

    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    device.set_humidifier_off.assert_called_once()

    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_SET_HUMIDITY,
        {ATTR_ENTITY_ID: entity_id, ATTR_HUMIDITY: 40},
        blocking=True,
    )
    device.set_humidifier_setpoint.assert_called_once_with(40)


async def test_dehumidifier_service_calls(
    hass: HomeAssistant, device: MagicMock, config_entry: MagicMock
) -> None:
    """Test the setup of the climate entities when there are no additional options available."""
    device.has_dehumidifier = True
    await init_integration(hass, config_entry)
    entity_id = f"humidifier.{device.name}_dehumidifier"
    assert hass.states.get(f"humidifier.{device.name}_humidifier") is None

    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    device.set_dehumidifier_auto.assert_called_once()

    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    device.set_dehumidifier_off.assert_called_once()

    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_SET_HUMIDITY,
        {ATTR_ENTITY_ID: entity_id, ATTR_HUMIDITY: 40},
        blocking=True,
    )
    device.set_dehumidifier_setpoint.assert_called_once_with(40)


async def test_humidifier_error_handling(
    hass: HomeAssistant, device: MagicMock, config_entry: MagicMock
) -> None:
    """Test humidifier service calls raise HomeAssistantError on API failure."""
    device.has_humidifier = True
    await init_integration(hass, config_entry)
    entity_id = f"humidifier.{device.name}_humidifier"

    device.set_humidifier_auto.side_effect = SomeComfortError
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            HUMIDIFIER_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

    device.set_humidifier_off.side_effect = SomeComfortError
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            HUMIDIFIER_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

    device.set_humidifier_setpoint.side_effect = SomeComfortError
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            HUMIDIFIER_DOMAIN,
            SERVICE_SET_HUMIDITY,
            {ATTR_ENTITY_ID: entity_id, ATTR_HUMIDITY: 40},
            blocking=True,
        )


async def test_dehumidifier_error_handling(
    hass: HomeAssistant, device: MagicMock, config_entry: MagicMock
) -> None:
    """Test dehumidifier service calls raise HomeAssistantError on API failure."""
    device.has_dehumidifier = True
    await init_integration(hass, config_entry)
    entity_id = f"humidifier.{device.name}_dehumidifier"

    device.set_dehumidifier_auto.side_effect = SomeComfortError
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            HUMIDIFIER_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

    device.set_dehumidifier_off.side_effect = SomeComfortError
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            HUMIDIFIER_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

    device.set_dehumidifier_setpoint.side_effect = SomeComfortError
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            HUMIDIFIER_DOMAIN,
            SERVICE_SET_HUMIDITY,
            {ATTR_ENTITY_ID: entity_id, ATTR_HUMIDITY: 40},
            blocking=True,
        )
