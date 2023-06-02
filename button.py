"""Platform for button integration."""
from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .helper import request_data

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Setup buttons"""
    coordinator = hass.data[DOMAIN]
    entities = []
    for device in coordinator.data["devices"]:
        if device["type"] == "public-elevator":
            entities.append(XiHomeElevatorButton(device, coordinator))
    for door in coordinator.lobby_door_data:
        entities.append(XiHomeDoorButton(door, coordinator))

    async_add_entities(
        entities
    )


class XiHomeElevatorButton(ButtonEntity):
    """Representation of an Xihome Elevator Button."""

    def __init__(self, device_data, coordinator) -> None:
        """Initialize an XiHomeElevatorButton."""
        self.idx = device_data["idx"]
        self.coordinator = coordinator

        self.entity_id = "button." + device_data["device_id"]
        self._name = "Elevator"
        self._device_id = device_data["device_id"]
        self._group = device_data["group"]
        self._type = device_data["type"]

    @property
    def name(self) -> str:
        """Return the display name of this light."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return self._device_id + str(self.idx)

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={
                (DOMAIN, self._group)
            },
        )

    def press(self) -> None:
        """Handle the button press."""
        body = {
            "type": "elevator",
            "userid":self.coordinator.user_id,
            }
        _response = request_data("/public", self.coordinator.token, body)


class XiHomeDoorButton(ButtonEntity):
    """Representation of an Xihome Door Button."""

    def __init__(self, door_data, coordinator) -> None:
        """Initialize an XiHomeDoorButton."""
        self.coordinator = coordinator
        self._lobbyho = door_data["lobbyHo"]
        self._lobbydong = door_data["lobbydong"]
        self._comment = door_data["comment"]
        self._group = "public"

        self.entity_id = "button." + self._lobbydong + self._comment.split(" ")[-1]
        self._name = "{}-{}".format(self._lobbydong, self._comment.split(" ")[-1])

    @property
    def name(self) -> str:
        """Return the display name of this light."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return self._lobbyho + self._lobbydong

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={
                (DOMAIN, self._group)
            },
        )

    def press(self) -> None:
        """Handle the button press."""
        body = {
            "door": "{}&{}".format(self._lobbydong, self._lobbyho),
            "userid":self.coordinator.user_id,
            }
        _response = request_data("/public/openlobby", self.coordinator.token, body)