"""Platform for sensor integration."""
from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)

from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Setup sensors"""
    coordinator = hass.data[DOMAIN]
    entities = []
    for device in coordinator.data["devices"]:
        if device["type"] == "acs":
            entities.append(XiHomePM25Sensor(device, coordinator))
            entities.append(XiHomeCO2Sensor(device, coordinator))

    async_add_entities(entities)


class XiHomePM25Sensor(CoordinatorEntity, SensorEntity):
    """Representation of an Xihome pm2.5 Sensor."""

    def __init__(self, device_data, coordinator) -> None:
        """Initialize an XiHomePM25Sensor."""
        self.idx = device_data["idx"]
        super().__init__(coordinator, context=self.idx)

        self._group = device_data["group"]
        self.entity_id = "sensor." + device_data["device_id"] + "_PM25"
        self._name = "{} PM2.5 Sensor".format(device_data["group"])

        self._attr_device_class = SensorDeviceClass.PM25
        self._attr_native_unit_of_measurement = "µg/m³"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_value = int(device_data["status"]["dust_value"])

    @property
    def name(self) -> str:
        """Return the display name of this sensor."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return self.entity_id + str(self.idx)

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._group)},
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_native_value = int(
            self.coordinator.data["indexed_devices"][self.idx]["status"]["dust_value"]
        )
        self.async_write_ha_state()


class XiHomeCO2Sensor(CoordinatorEntity, SensorEntity):
    """Representation of an Xihome CO2 Sensor."""

    def __init__(self, device_data, coordinator) -> None:
        """Initialize an XiHomeCO2Sensor."""
        self.idx = device_data["idx"]
        super().__init__(coordinator, context=self.idx)

        self._group = device_data["group"]
        self.entity_id = "sensor." + device_data["device_id"] + "_CO2"
        self._name = "{} CO2 Sensor".format(device_data["group"])

        self._attr_device_class = SensorDeviceClass.CO2
        self._attr_native_unit_of_measurement = "ppm"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_value = int(device_data["status"]["co2_value"])

    @property
    def name(self) -> str:
        """Return the display name of this sensor."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return self.entity_id + str(self.idx)

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._group)},
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_native_value = int(
            self.coordinator.data["indexed_devices"][self.idx]["status"]["co2_value"]
        )
        self.async_write_ha_state()
