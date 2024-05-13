"""Platform for climate integration."""
from __future__ import annotations

import logging
from typing import Any
from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate import HVACMode, ClimateEntityFeature

from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature, PRECISION_WHOLE

from .const import DOMAIN
from .helper import request_data

# erv
VENTILATION_OFF = "Ventilation Off"
VENTILATION_LOW = "Ventilation Low"
VENTILATION_MEDIUM = "Ventilation Medium"
VENTILATION_HIGH = "Ventilation High"
VENTILATION_AUTO = "Ventilation Auto Mode"
VENTILATION_SLEEP = "Ventilation Sleep Mode"

# fau
AIR_PURIFY_OFF = "Aur Purify Off"
AIR_PURIFY_LOW = "Aur Purify Low"
AIR_PURIFY_MEDIUM = "Aur Purify Medium"
AIR_PURIFY_HIGH = "Aur Purify High"
AIR_PURIFY_MAX = "Aur Purify Max"
AIR_PURIFY_AUTO = "Aur Purify Auto Mode"
AIR_PURIFY_SLEEP = "Aur Purify Sleep Mode"

COMMAND_VALUES = {
    AIR_PURIFY_OFF: [0, 0, ""],
    AIR_PURIFY_LOW: [1, 1, "manual"],
    AIR_PURIFY_MEDIUM: [1, 2, "manual"],
    AIR_PURIFY_HIGH: [1, 3, "manual"],
    AIR_PURIFY_MAX: [1, 4, "manual"],
    AIR_PURIFY_AUTO: [1, 2, "auto"],
    AIR_PURIFY_SLEEP: [1, 9, "sleep"],
    VENTILATION_OFF: [0, 0, ""],
    VENTILATION_LOW: [1, 1, "manual"],
    VENTILATION_MEDIUM: [1, 2, "manual"],
    VENTILATION_HIGH: [1, 3, "manual"],
    VENTILATION_AUTO: [1, 0, "auto"],
    VENTILATION_SLEEP: [1, 0, "sleep"],
}

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Setup heating systems"""
    coordinator = hass.data[DOMAIN]
    entities = []
    for device in coordinator.data["devices"]:
        if device["type"] == "heating-system":
            entities.append(XiHomeHeatingSystem(device, coordinator))

    async_add_entities(entities)


class XiHomeHeatingSystem(CoordinatorEntity, ClimateEntity):
    """Representation of an Xihome Heating System."""

    def __init__(self, device_data, coordinator) -> None:
        """Initialize an XiHomeHeatingSystem."""
        self.idx = device_data["idx"]
        super().__init__(coordinator, context=self.idx)

        self.entity_id = "climate." + device_data["device_id"]
        self._group_id = device_data["groupID"]
        self._group = device_data["group"]
        self._type = device_data["type"]
        self._name = "{} Heating System".format(device_data["group"])
        self._device_id = device_data["device_id"]
        self._current_temperature = int(device_data["status"]["curtemp"])
        self._target_temperature = int(device_data["status"]["settemp"])  # minimum 5

        self._temperature_unit = UnitOfTemperature.CELSIUS
        self._precision = PRECISION_WHOLE
        self._hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
        self._current_hvac_mode = (
            HVACMode.HEAT if device_data["status"]["power"] else HVACMode.OFF
        )
        self._supported_features = (
            ClimateEntityFeature.TURN_OFF | ClimateEntityFeature.TURN_ON |
            ClimateEntityFeature.TARGET_TEMPERATURE
        )
        self._enable_turn_on_off_backwards_compatibility = False
        self._min_temp = 5
        self._max_temp = 40

    @property
    def name(self) -> str:
        """Return the display name of this heater."""
        return self._name

    @property
    def is_on(self) -> bool | None:
        """Return true if heating system is on."""
        return self._current_hvac_mode != HVACMode.OFF

    @property
    def unique_id(self) -> str:
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return self._device_id + str(self.idx)

    @property
    def current_temperature(self):
        """Return the sensor temperature."""
        return self._current_temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temperature

    @property
    def temperature_unit(self):
        """Return the temperature unit."""
        return self._temperature_unit

    @property
    def precision(self):
        """Return the temperature precision."""
        return self._precision

    @property
    def hvac_modes(self):
        """Return the available HVAC modes."""
        return self._hvac_modes

    @property
    def hvac_mode(self):
        """Return the current HVAC mode."""
        return self._current_hvac_mode

    @property
    def supported_features(self):
        """Return supported features."""
        return self._supported_features

    @property
    def max_temp(self):
        """Return maximum available temperature."""
        return self._max_temp

    @property
    def min_temp(self):
        """Return minimum available temperature."""
        return self._min_temp

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._group)},
        )

    def set_temperature(self, **kwargs: Any):
        """Set new target temperature."""
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is not None:
            self._target_temperature = int(temp)
            if self.is_on:
                self.turn_on()

    def set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode."""
        if self._current_hvac_mode == HVACMode.OFF and hvac_mode == HVACMode.HEAT:
            self.turn_on()
        elif self._current_hvac_mode == HVACMode.HEAT and hvac_mode == HVACMode.OFF:
            self.turn_off()
        self._current_hvac_mode = hvac_mode

    def turn_on(self, **kwargs: Any) -> None:
        """Instruct the heating system to turn on."""
        body = {
            "device_id": self._device_id,
            "type": self._type,
            "groupId": self._group_id,
            "status": {
                "power": True,
                "mode": 1,
                "curtemp": self._current_temperature,
                "settemp": self._target_temperature,
            },
            "userid": self.coordinator.user_id,
        }
        _response = request_data("/device/command", self.coordinator.token, body)
        self._current_hvac_mode = HVACMode.HEAT
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs: Any) -> None:
        """Instruct the heating system to turn on."""
        body = {
            "device_id": self._device_id,
            "type": self._type,
            "groupId": self._group_id,
            "status": {
                "power": False,
                "mode": 0,
                "curtemp": self._current_temperature,
                "settemp": 5,
            },
            "userid": self.coordinator.user_id,
        }
        _response = request_data("/device/command", self.coordinator.token, body)
        self._current_hvac_mode = HVACMode.OFF
        self.schedule_update_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        data = self.coordinator.data["indexed_devices"][self.idx]
        self._current_temperature = int(data["status"]["curtemp"])
        self._current_hvac_mode = (
            HVACMode.HEAT if data["status"]["mode"] else HVACMode.OFF
        )
        if self._current_hvac_mode == HVACMode.HEAT:
            self._target_temperature = int(data["status"]["settemp"])
        self.async_write_ha_state()
