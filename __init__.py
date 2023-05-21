"""The xi_home integration."""
from __future__ import annotations
from datetime import timedelta
import logging
import requests
import json
import async_timeout

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import update_coordinator
from homeassistant.helpers.reload import async_integration_yaml_config
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN, COMMAND_URL, STATUS_URL, DATA_URL


_LOGGER = logging.getLogger(__name__)

# TODO List the platforms that you want to support.
# For your initial PR, limit it to 1 platform.
PLATFORMS: list[Platform] = [Platform.LIGHT, Platform.CLIMATE, Platform.SENSOR, Platform.FAN]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up xi_home from a config entry."""

    _conf = await async_integration_yaml_config(hass, DOMAIN)
    if not _conf or DOMAIN not in _conf:
        _LOGGER.warning(
            "No `xi_home:` key found in configuration.yaml"
        )
    else:
        config = _conf[DOMAIN]


    coordinator = MyCoordinator(hass, config["token"], config["username"])
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

    def __init__(self, hass, token, user_id):
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
        self.session_id = "xxxxxxxx"

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

        body = {"sessionid": self.session_id,
                "userid": self.user_id}

        response = requests.post(DATA_URL, data=json.dumps(body), headers=self.get_header(), timeout=5)
        data = response.json()
        indexed = dict()
        for device in data["devices"]:
            if device["type"] == "acs":
                if device["status"]["dust_unit"] == "":
                    acs_data = self.get_acs_data(device["device_id"], device["groupID"])
                    device["status"]["dust_value"] = acs_data["dust_value"]
                    device["status"]["co2_value"] = acs_data["co2_value"]
                    device["status"]["smell_value"] = acs_data["smell_value"]
                    device["status"]["dust_unit"] = acs_data["dust_unit"]

                if device["status"]["dust_unit"] != "PM2.5":
                    self.acs_change_unit(device["device_id"], device["groupID"], "PM2.5")
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
                "erv_air_volume": 0
            },
            "userid": self.user_id
        }
        response = requests.post(COMMAND_URL, data=json.dumps(body), headers=self.get_header(), timeout=5)

    def get_acs_data(self, device_id, group_id):
        body = {
            "device_id": device_id,
            "type": "acs",
            "groupId": group_id,
            "userid": self.user_id
        }
        response = requests.post(STATUS_URL, data=json.dumps(body), headers=self.get_header(), timeout=5)
        return response.json()["status"]

    def get_xi_home_session_id(self):
        """Get session id from xi_home."""
        url = "https://smartcareback.twinspace.co.kr:20001/auth/user"
        headers = {
            "authorization": "Bearer {}".format(self.token),
            "content-type": "application/json",
        }
        body = {"userid": self.user_id}
        response = requests.post(url, data=json.dumps(body), headers=headers, timeout=1.5)
        return response.json()['sessionid']

    def get_header(self):
        return {
            "authorization": "Bearer {}".format(self.token),
            "content-type": "application/json",
        }

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].data.pop(entry.entry_id)

    return unload_ok
