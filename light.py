"""Platform for light integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ColorMode,
    LightEntity,
)

from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .helper import request_data

_LOGGER = logging.getLogger(__name__)


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
    """Setup lights"""
    coordinator = hass.data[DOMAIN]
    entities = []
    for device in coordinator.data["devices"]:
        if device["type"] == "light" or device["type"] == "dimming":
            entities.append(XiHomeLight(device, coordinator))

    async_add_entities(entities)


class XiHomeLight(CoordinatorEntity, LightEntity):
    """Representation of an Xihome Light."""

    def __init__(self, device_data, coordinator) -> None:
        """Initialize an XihomeLight."""
        self.idx = device_data["idx"]
        super().__init__(coordinator, context=self.idx)

        self.entity_id = "light." + device_data["device_id"]
        self._name = "{} Light {}".format(
            device_data["group"], device_data["name"].split(".")[0]
        )
        self._device_id = device_data["device_id"]
        self._group_id = device_data["groupID"]
        self._state = device_data["status"]["power"]
        self._group = device_data["group"]
        self._type = device_data["type"]
        self._brightness = -1
        # brightness range: 1-4 when on, 0 when off
        if self._type == "dimming":
            self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
            self._brightness = int(device_data["status"]["dimming"])
        else:
            self._attr_supported_color_modes = {ColorMode.ONOFF}

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

    @property
    def brightness(self):
        """Return the brightness of the light."""
        return int(self._brightness / 4 * 255)

    def turn_on(self, **kwargs: Any) -> None:
        """Instruct the light to turn on."""
        body = {
            "device_id": self._device_id,
            "type": self._type,
            "groupId": self._group_id,
            "status": {"power": True},
            "userid": self.coordinator.user_id,
        }

        if ATTR_BRIGHTNESS in kwargs:
            self._brightness = max(1, int(4 * kwargs[ATTR_BRIGHTNESS] / 255))

        if self._type == "dimming":
            body["status"]["dimming"] = str(self._brightness)

        _response = request_data("/device/command", self.coordinator.token, body)
        self._state = True
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""
        body = {
            "device_id": self._device_id,
            "type": self._type,
            "groupId": self._group_id,
            "status": {"power": False},
            "userid": self.coordinator.user_id,
        }
        if self._type == "dimming":
            body["status"]["dimming"] = "0"

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
