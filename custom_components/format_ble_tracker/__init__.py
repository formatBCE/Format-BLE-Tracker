"""The Format BLE Tracker integration."""
from __future__ import annotations

import asyncio
from asyncio import events
import json
import time
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    ALIVE_NODES_TOPIC,
    DOMAIN,
    MAC,
    NAME,
    ROOM,
    ROOT_TOPIC,
    RSSI,
    TIMESTAMP,
    MERGE_IDS,
)

PLATFORMS: list[Platform] = [
    Platform.DEVICE_TRACKER,
    Platform.SENSOR,
    Platform.NUMBER
]
_LOGGER = logging.getLogger(__name__)

MQTT_PAYLOAD = vol.Schema(
    vol.All(
        json.loads,
        vol.Schema(
            {
                vol.Required(RSSI): vol.Coerce(int),
                vol.Optional(TIMESTAMP): vol.Coerce(int)
            },
            extra=vol.ALLOW_EXTRA,
        ),
    )
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Format BLE Tracker from a config entry."""

    hass.data.setdefault(DOMAIN, {})

    if MAC in entry.data:
        mac = entry.data[MAC]
        coordinator = BeaconCoordinator(hass, entry.data)
        state_topic = ROOT_TOPIC + "/" + mac + "/+"
        _LOGGER.info("Subscribing to %s", state_topic)
        await mqtt.async_subscribe(hass, state_topic, coordinator.message_received, 1)
        alive_topic = ALIVE_NODES_TOPIC + "/" + mac
        _LOGGER.info("Notifying alive to %s", alive_topic)
        await mqtt.async_publish(hass, alive_topic, True, 1, retain=True)
        hass.data[DOMAIN][entry.entry_id] = coordinator
        hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    elif MERGE_IDS in entry.data:
        hass.config_entries.async_setup_platforms(entry, [Platform.DEVICE_TRACKER])


    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    if entry.entry_id in hass.data[DOMAIN]:
        platforms = PLATFORMS
    else:
        platforms = [Platform.DEVICE_TRACKER]

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, platforms) and entry.entry_id in hass.data[DOMAIN]:
        hass.data[DOMAIN].pop(entry.entry_id)

    if MAC in entry.data:
        mac = entry.data[MAC]
        alive_topic = ALIVE_NODES_TOPIC + "/" + mac
        _LOGGER.info("Notifying dead to %s", alive_topic)
        await mqtt.async_publish(hass, alive_topic, "", 1, retain=True)

    return unload_ok


class BeaconCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to arrange interaction with MQTT"""

    def __init__(self, hass: HomeAssistant, data) -> None:
        self.mac = data[MAC]
        self.expiration_time : int
        self.default_expiration_time : int = 2
        given_name = data[NAME] if data.__contains__(NAME) else self.mac
        self.room_data = dict[str, int]()
        self.room_expiration_timers = dict[str, asyncio.TimerHandle]()
        self.room = None

        super().__init__(hass, _LOGGER, name=given_name)

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via library."""
        if len(self.room_data) == 0:
            self.room = None
        else:
            self.room = next(
                iter(
                    dict(
                        sorted(
                            self.room_data.items(),
                            key=lambda item: item[1],
                            reverse=True,
                        )
                    )
                )
            )
        return {**{ROOM: self.room}}

    async def subscribe_to_mqtt(self) -> None:
        """Subscribe coordinator to MQTT messages"""

    @callback
    async def message_received(self, msg):
        """Handle new MQTT messages."""
        try:
            data = MQTT_PAYLOAD(msg.payload)
        except vol.MultipleInvalid as error:
            _LOGGER.debug("Skipping update because of malformatted data: %s", error)
            return
        msg_time = data.get(TIMESTAMP)
        if (msg_time is not None):
            current_time = int(time.time())
            if (current_time - msg_time >= self.get_expiration_time()):
                _LOGGER.info("Received message with old timestamp, skipping")
                return

        room_topic = msg.topic.split("/")[2]

        await self.schedule_data_expiration(room_topic)
        self.room_data[room_topic] = data.get(RSSI)
        await self.async_refresh()

    async def schedule_data_expiration(self, room):
        """Start timer for data expiration for certain room"""
        if room in self.room_expiration_timers:
            self.room_expiration_timers[room].cancel()
        loop = asyncio.get_event_loop()
        timer = loop.call_later(
            self.get_expiration_time(),
            lambda: asyncio.ensure_future(self.expire_data(room)),
        )
        self.room_expiration_timers[room] = timer

    def get_expiration_time(self):
        """Calculate current expiration delay"""
        return getattr(self, "expiration_time", self.default_expiration_time) * 60

    async def expire_data(self, room):
        """Set data for certain room expired"""
        del self.room_data[room]
        del self.room_expiration_timers[room]
        await self.async_refresh()

    async def on_expiration_time_changed(self, new_time : int):
        """Respond to expiration time changed by user"""
        if new_time is None:
            return
        self.expiration_time = new_time
        for room in self.room_expiration_timers.keys():
            await self.schedule_data_expiration(room)
