"""The xi_home integration."""
from __future__ import annotations
from datetime import timedelta
import logging
import async_timeout

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import update_coordinator
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN
from .helper import request_data

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.LIGHT,
    Platform.CLIMATE,
    Platform.SENSOR,
    Platform.FAN,
    Platform.SWITCH,
    Platform.BUTTON,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up xi_home from a config entry."""
    coordinator = MyCoordinator(hass, entry.data["token"], entry.data["username"])
    await coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN] = coordinator

    device_registry = dr.async_get(hass)
    for room in coordinator.data["groups"]:
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, room["name"])},
            manufacturer="XiSmartHome",
            suggested_area=room["name"],
            name=room["name"],
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


class MyCoordinator(update_coordinator.DataUpdateCoordinator):
    """My custom coordinator."""

    def __init__(self, hass: HomeAssistant, token, user_id, session_id=None) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name="xi_home",
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=timedelta(minutes=1),
        )
        self.token = token
        self.user_id = user_id
        self.session_id = session_id
        self.lobby_door_data = None

    async def _async_update_data(self):
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        # Note: asyncio.TimeoutError and aiohttp.ClientError are already
        # handled by the data update coordinator.
        async with async_timeout.timeout(10):
            # Grab active context variables to limit data required to be fetched from API
            # Note: using context is not required if there is no need or ability to limit
            # data retrieved from API.
            data = await self.hass.async_add_executor_job(self.get_xi_home_api_data)
            return data

    def get_xi_home_api_data(self):
        """Get the latest data from xi_home."""
        if self.session_id is None:
            self.session_id = self.get_xi_home_session_id()

        if self.lobby_door_data is None:
            self.lobby_door_data = self.get_lobby_door_data()

        body = {"sessionid": self.session_id, "userid": self.user_id}

        data = request_data("/device/list-redis", self.token, body)
        indexed = dict()
        for device in data["devices"]:
            if device["type"] == "acs" and device["status"] != {}:
                # acs data from list-redis api is not correct
                acs_data = self.get_acs_data(device["device_id"], device["groupID"])
                device["status"]["dust_value"] = acs_data["dust_value"]
                device["status"]["co2_value"] = acs_data["co2_value"]
                device["status"]["smell_value"] = acs_data["smell_value"]
                device["status"]["dust_unit"] = acs_data["dust_unit"]

                if device["status"]["dust_unit"] != "PM2.5":
                    self.acs_change_unit(
                        device["device_id"], device["groupID"], "PM2.5"
                    )
                    acs_data = self.get_acs_data(device["device_id"], device["groupID"])
                    device["status"]["dust_value"] = acs_data["dust_value"]
                    device["status"]["dust_unit"] = acs_data["dust_unit"]
                if "fau_mode" not in device["status"]:
                    device["status"]["fau_mode"] = ""
                if "erv_mode" not in device["status"]:
                    device["status"]["erv_mode"] = ""
                if "fau_airvolume" not in device["status"]:
                    device["status"]["fau_airvolume"] = 0
                if "erv_airvolume" not in device["status"]:
                    device["status"]["erv_airvolume"] = 0

            indexed[device["idx"]] = device

        data["indexed_devices"] = indexed
        return data

    def acs_change_unit(self, device_id, group_id, unit):
        """Chance unit of acs device."""
        body = {
            "device_id": device_id,
            "type": "acs",
            "groupId": group_id,
            "status": {
                "dust_unit": unit,
                "fau_runstate": 0,
                "erv_runstate": 0,
                "fau_mode": "",
                "erv_mode": "",
                "fau_air_volume": 0,
                "erv_air_volume": 0,
            },
            "userid": self.user_id,
        }
        _response = request_data("/device/command", self.token, body)

    def get_acs_data(self, device_id, group_id):
        """Get acs data from xi_home."""
        body = {
            "device_id": device_id,
            "type": "acs",
            "groupId": group_id,
            "userid": self.user_id,
        }
        response = request_data("/device/status", self.token, body)
        return response["status"]

    def get_lobby_door_data(self):
        """Get lobby door data from xi_home."""
        body = {"type": "doorlock", "userid": self.user_id}
        response = request_data("/public", self.token, body)
        return response["data"]["list"]

    def get_xi_home_session_id(self):
        """Get session id from xi_home."""
        body = {"userid": self.user_id}
        response = request_data("/auth/user", self.token, body)
        return response["sessionid"]


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].data.pop(entry.entry_id)

    return unload_ok
