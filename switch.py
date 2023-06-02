"""Platform for switch integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .helper import request_data

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Setup switches"""
    coordinator = hass.data[DOMAIN]
    entities = []
    for device in coordinator.data["devices"]:
        if device["type"] == "lightall":
            entities.append(XiHomeAllLightSwtich(device, coordinator))

    async_add_entities(entities)


class XiHomeAllLightSwtich(CoordinatorEntity, SwitchEntity):
    """Representation of an Xihome AllLight Switch."""

    def __init__(self, device_data, coordinator) -> None:
        """Initialize an XiHomeAllLightSwtich."""
        self.idx = device_data["idx"]
        super().__init__(coordinator, context=self.idx)

        self.entity_id = "switch." + device_data["device_id"]
        self._name = "All light switch"
        self._device_id = device_data["device_id"]
        self._group_id = device_data["groupID"]
        self._state = device_data["status"]["power"]
        self._group = device_data["group"]
        self._type = device_data["type"]

    @property
    def name(self) -> str:
        """Return the display name of this light."""
        return self._name

    @property
    def is_on(self) -> bool | None:
        """Return true if light is on."""
        return self._state

    @property
    def unique_id(self) -> str:
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return self._device_id + str(self.idx)

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._group)},
        )

    def turn_on(self, **kwargs: Any) -> None:
        """Instruct the switch to turn on."""
        body = {
            "device_id": self._device_id,
            "type": self._type,
            "groupId": self._group_id,
            "status": {"power": True},
            "userid": self.coordinator.user_id,
        }
        _response = request_data("/device/command", self.coordinator.token, body)
        self._state = True
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs: Any) -> None:
        """Instruct the switch to turn off."""
        body = {
            "device_id": self._device_id,
            "type": self._type,
            "groupId": self._group_id,
            "status": {"power": False},
            "userid": self.coordinator.user_id,
        }

        _response = request_data("/device/command", self.coordinator.token, body)
        self._state = False
        self.schedule_update_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._state = self.coordinator.data["indexed_devices"][self.idx]["status"][
            "power"
        ]
        self.async_write_ha_state()
