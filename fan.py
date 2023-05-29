"""Platform for fan integration."""
from __future__ import annotations

import logging
from typing import Optional
from homeassistant.components.fan import FanEntityFeature, FanEntity

from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType


import requests
import json

from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN, COMMAND_URL

# erv
VENTILATION_OFF = "Ventilation Off"
VENTILATION_AUTO = "Ventilation Auto Mode"
VENTILATION_SLEEP = "Ventilation Sleep Mode"

# fau
AIR_PURIFY_OFF = "Aur Purify Off"
AIR_PURIFY_AUTO = "Aur Purify Auto Mode"
AIR_PURIFY_SLEEP = "Aur Purify Sleep Mode"
AIR_PURIFY_BOOST = "Aur Purify Boost Mode"

COMMAND_VALUES = {
    AIR_PURIFY_OFF: [0, 0, ""],
    AIR_PURIFY_AUTO: [1, 2, "auto"],
    AIR_PURIFY_SLEEP: [1, 9, "sleep"],
    AIR_PURIFY_BOOST: [1, 4, "manual"],
    VENTILATION_OFF: [0, 0, ""],
    VENTILATION_AUTO: [1, 0, "auto"],
    VENTILATION_SLEEP: [1, 0, "sleep"]
    }

def header(token: str) -> dict[str, str]:
    return {
            "authorization": "Bearer {}".format(token),
            "content-type": "application/json",
        }

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Setup heating systems"""
    coordinator = hass.data[DOMAIN]
    entities = []
    for device in coordinator.data["devices"]:
        if device["type"] == "acs":
            entities.append(XiHomeVentilationSystem(device, coordinator))
            entities.append(XiHomeFreshAirUnit(device, coordinator))

    async_add_entities(
        entities
    )

class XiHomeVentilationSystem(CoordinatorEntity, FanEntity):
    """Representation of an Xihome Ventilation System."""

    def __init__(self, device_data, coordinator) -> None:
        """Initialize an XiHomeVentilationSystem."""
        self.idx = device_data["idx"]
        super().__init__(coordinator, context=self.idx)

        self.entity_id = "fan." + device_data["device_id"] + "_erv"
        self._group_id = device_data["groupID"]
        self._group = device_data["group"]
        self._state = 0
        self._type = device_data["type"]
        self._name = "{} Ventilation".format(device_data["group"])
        self._device_id = device_data["device_id"]

        self._current_speed = 0
        self._speed_count = 3
        self._mode = ""

        self._supported_features = FanEntityFeature.PRESET_MODE | FanEntityFeature.SET_SPEED
        self._preset_modes = ["auto", "sleep"]
        self.set_state_from_status_data(device_data["status"])

    @property
    def name(self) -> str:
        """Return the display name of this fan."""
        return self._name

    @property
    def is_on(self) -> bool | None:
        """Return true if fan is on."""
        return self._state

    @property
    def unique_id(self) -> str:
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return self._device_id + str(self.idx) + "_erv"

    @property
    def preset_modes(self):
        """Return preset modes."""
        return self._preset_modes

    @property
    def preset_mode(self):
        """Return preset modes."""
        if self._mode in self._preset_modes:
            return self._mode
        return None

    @property
    def percentage(self) -> int:
        """Return the current speed percentage."""
        return int(self._current_speed / self._speed_count * 100)

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return self._speed_count

    @property
    def supported_features(self):
        """Return supported features."""
        return self._supported_features

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={
                (DOMAIN, self._group)
            },
        )

    def set_state_from_status_data(self, status):
        """Get status from data."""
        self._state = status["erv_runstate"]
        self._current_speed = int(status["erv_airvolume"])
        self._mode = status["erv_mode"]

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan."""
        if preset_mode == "auto":
            self._state = COMMAND_VALUES[VENTILATION_AUTO][0]
            self._current_speed = COMMAND_VALUES[VENTILATION_AUTO][1]
            self._mode = COMMAND_VALUES[VENTILATION_AUTO][2]
        elif preset_mode == "sleep":
            self._state = COMMAND_VALUES[VENTILATION_SLEEP][0]
            self._current_speed = COMMAND_VALUES[VENTILATION_SLEEP][1]
            self._mode = COMMAND_VALUES[VENTILATION_SLEEP][2]
        self.send_command()

    def set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        if percentage == 0:
            self.turn_off()
        self._state = 1
        self._current_speed = percentage / 100 * self._speed_count
        self._mode = "manual"
        self.send_command()

    def send_command(self):
        """Send command by api"""
        data = self.coordinator.data["indexed_devices"][self.idx]["status"]
        body = {
            "device_id": self._device_id,
            "type": self._type,
            "groupId": self._group_id,
            "status": {
                "fau_runstate": data["fau_runstate"],
                "erv_runstate": self._state,
                "fau_mode": data["fau_mode"],
                "erv_mode": self._mode,
                "fau_air_volume": int(data["fau_airvolume"]),
                "erv_air_volume": self._current_speed,
                "fau_reserve_time": 0,
                "erv_reserve_time": 0
            },
            "userid": self.coordinator.user_id
            }

        response = requests.post(COMMAND_URL, data=json.dumps(body), headers=header(self.coordinator.token), timeout=5)
        self.update_coordinator_data()
        self.schedule_update_ha_state()

    def update_coordinator_data(self):
        self.coordinator.data["indexed_devices"][self.idx]["status"]["erv_runstate"] = self._state
        self.coordinator.data["indexed_devices"][self.idx]["status"]["erv_mode"] = self._mode
        self.coordinator.data["indexed_devices"][self.idx]["status"]["erv_airvolume"] = self._current_speed

    def turn_on(self, percentage: Optional[int] = None, preset_mode: Optional[str] = None, **kwargs: Any) -> None:
        """Turn on the fan."""
        if preset_mode is not None:
            self.set_preset_mode(preset_mode)
            return
        if percentage is None:
            self._current_speed = 1
        else:
            self._current_speed = percentage / 100 * self._speed_count
        self._state = 1
        self._state = 1
        self._mode = "manual"
        self.send_command()

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the fan off."""
        self._state = COMMAND_VALUES[VENTILATION_OFF][0]
        self._current_speed = COMMAND_VALUES[VENTILATION_OFF][1]
        self._mode = COMMAND_VALUES[VENTILATION_OFF][2]
        self.send_command()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        data = self.coordinator.data["indexed_devices"][self.idx]["status"]
        self.set_state_from_status_data(data)
        self.async_write_ha_state()

class XiHomeFreshAirUnit(CoordinatorEntity, FanEntity):
    """Representation of an XiHome Fresh Air Unit."""

    def __init__(self, device_data, coordinator) -> None:
        """Initialize an XiHomeFreshAirUnit."""
        self.idx = device_data["idx"]
        super().__init__(coordinator, context=self.idx)

        self.entity_id = "fan." + device_data["device_id"] + "_fau"
        self._group_id = device_data["groupID"]
        self._group = device_data["group"]
        self._state = 0
        self._type = device_data["type"]
        self._name = "{} Fresh Air Unit".format(device_data["group"])
        self._device_id = device_data["device_id"]

        self._current_speed = 0
        self._speed_count = 3
        self._mode = ""

        self._supported_features = FanEntityFeature.PRESET_MODE | FanEntityFeature.SET_SPEED
        self._preset_modes = ["auto", "sleep", "boost"]
        self.set_state_from_status_data(device_data["status"])

    @property
    def name(self) -> str:
        """Return the display name of this fan."""
        return self._name

    @property
    def is_on(self) -> bool | None:
        """Return true if fan is on."""
        return self._state

    @property
    def unique_id(self) -> str:
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return self._device_id + str(self.idx) + "_fau"

    @property
    def preset_modes(self):
        """Return preset modes."""
        return self._preset_modes

    @property
    def preset_mode(self):
        """Return preset modes."""
        if self._mode in self._preset_modes:
            return self._mode
        if self._current_speed == 4:
            return "boost"
        return None

    @property
    def percentage(self) -> int:
        """Return the current speed percentage."""
        return int(self._current_speed / self._speed_count * 100)

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return self._speed_count

    @property
    def supported_features(self):
        """Return supported features."""
        return self._supported_features

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={
                (DOMAIN, self._group)
            },
        )

    def set_state_from_status_data(self, status):
        """Get status from data."""
        self._state = status["fau_runstate"]
        self._current_speed = int(status["fau_airvolume"])
        self._mode = status["fau_mode"]

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan."""
        if preset_mode == "auto":
            self._state = COMMAND_VALUES[AIR_PURIFY_AUTO][0]
            self._current_speed = COMMAND_VALUES[AIR_PURIFY_AUTO][1]
            self._mode = COMMAND_VALUES[AIR_PURIFY_AUTO][2]
        elif preset_mode == "sleep":
            self._state = COMMAND_VALUES[AIR_PURIFY_SLEEP][0]
            self._current_speed = COMMAND_VALUES[AIR_PURIFY_SLEEP][1]
            self._mode = COMMAND_VALUES[AIR_PURIFY_SLEEP][2]
        elif preset_mode == "boost":
            self._state = COMMAND_VALUES[AIR_PURIFY_BOOST][0]
            self._current_speed = COMMAND_VALUES[AIR_PURIFY_BOOST][1]
            self._mode = COMMAND_VALUES[AIR_PURIFY_BOOST][2]
        self.send_command()

    def set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        if percentage == 0:
            self.turn_off()
        self._state = 1
        self._current_speed = percentage / 100 * self._speed_count
        self._mode = "manual"
        self.send_command()

    def send_command(self):
        """Send command by api"""
        data = self.coordinator.data["indexed_devices"][self.idx]["status"]
        body = {
            "device_id": self._device_id,
            "type": self._type,
            "groupId": self._group_id,
            "status": {
                "fau_runstate": self._state,
                "erv_runstate": data["erv_runstate"],
                "fau_mode": self._mode,
                "erv_mode": data["erv_mode"],
                "fau_air_volume": self._current_speed,
                "erv_air_volume": int(data["erv_airvolume"]),
                "fau_reserve_time": 0,
                "erv_reserve_time": 0
            },
            "userid": self.coordinator.user_id
            }

        response = requests.post(COMMAND_URL, data=json.dumps(body), headers=header(self.coordinator.token), timeout=5)
        self.update_coordinator_data()
        self.schedule_update_ha_state()

    def update_coordinator_data(self):
        self.coordinator.data["indexed_devices"][self.idx]["status"]["fau_runstate"] = self._state
        self.coordinator.data["indexed_devices"][self.idx]["status"]["fau_mode"] = self._mode
        self.coordinator.data["indexed_devices"][self.idx]["status"]["fau_airvolume"] = self._current_speed

    def turn_on(self, percentage: Optional[int] = None, preset_mode: Optional[str] = None, **kwargs: Any) -> None:
        """Turn on the fan."""
        if preset_mode is not None:
            self.set_preset_mode(preset_mode)
            return
        if percentage is None:
            self._current_speed = 1
        else:
            self._current_speed = percentage / 100 * self._speed_count
        self._state = 1
        self._mode = "manual"
        self.send_command()

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the fan off."""
        self._state = COMMAND_VALUES[AIR_PURIFY_OFF][0]
        self._current_speed = COMMAND_VALUES[AIR_PURIFY_OFF][1]
        self._mode = COMMAND_VALUES[AIR_PURIFY_OFF][2]
        self.send_command()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        data = self.coordinator.data["indexed_devices"][self.idx]["status"]
        self.set_state_from_status_data(data)
        self.async_write_ha_state()

