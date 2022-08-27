"""The Format BLE Tracker integration."""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any
#import numpy as np
import math

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
    MERGE_IDS,
    NAME,
    ROOM,
    ROOT_TOPIC,
    RSSI,
    TIMESTAMP,
)

PLATFORMS: list[Platform] = [Platform.DEVICE_TRACKER, Platform.SENSOR, Platform.NUMBER]
_LOGGER = logging.getLogger(__name__)

MQTT_PAYLOAD = vol.Schema(
    vol.All(
        json.loads,
        vol.Schema(
            {
                vol.Required(RSSI): vol.Coerce(int),
                vol.Optional(TIMESTAMP): vol.Coerce(int),
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

    if (
        unload_ok := await hass.config_entries.async_unload_platforms(entry, platforms)
        and entry.entry_id in hass.data[DOMAIN]
    ):
        hass.data[DOMAIN].pop(entry.entry_id)

    if MAC in entry.data:
        mac = entry.data[MAC]
        alive_topic = ALIVE_NODES_TOPIC + "/" + mac
        _LOGGER.info("Notifying dead to %s", alive_topic)
        await mqtt.async_publish(hass, alive_topic, "", 1, retain=True)

    return unload_ok


class BeaconCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to arrange interaction with MQTT."""

    def __init__(self, hass: HomeAssistant, data) -> None:
        """Initialise coordinator."""
        self.mac = data[MAC]
        self.expiration_time: int
        self.default_expiration_time: int = 2
        given_name = data[NAME] if data.__contains__(NAME) else self.mac
        self.room_data = dict[str, int]()
        self.filtered_room_data = dict[str, int]()
        self.room_filters = dict[str, KalmanFilter]()
        self.room_expiration_timers = dict[str, asyncio.TimerHandle]()
        self.room: str | None = None
        self.last_received_adv_time = None

        super().__init__(hass, _LOGGER, name=given_name)

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via library."""
        if len(self.filtered_room_data) == 0:
            self.room = None
            self.last_received_adv_time = None
        else:
            self.room = next(
                iter(
                    dict(
                        sorted(
                            self.filtered_room_data.items(),
                            key=lambda item: item[1],
                            reverse=True,
                        )
                    )
                )
            )
        return {**{ROOM: self.room}}

    async def subscribe_to_mqtt(self) -> None:
        """Subscribe coordinator to MQTT messages."""

    @callback
    async def message_received(self, msg):
        """Handle new MQTT messages."""
        try:
            data = MQTT_PAYLOAD(msg.payload)
        except vol.MultipleInvalid as error:
            _LOGGER.debug("Skipping update because of malformatted data: %s", error)
            return
        msg_time = data.get(TIMESTAMP)
        if msg_time is not None:
            current_time = int(time.time())
            if current_time - msg_time >= self.get_expiration_time():
                _LOGGER.info("Received message with old timestamp, skipping")
                return

        self.time_from_previous = None if self.last_received_adv_time is None else (current_time  - self.last_received_adv_time)
        self.last_received_adv_time = current_time

        room_topic = msg.topic.split("/")[2]

        await self.schedule_data_expiration(room_topic)

        rssi = data.get(RSSI)
        self.room_data[room_topic] = rssi
        self.filtered_room_data[room_topic] = self.get_filtered_value(room_topic, rssi)

        await self.async_refresh()

    async def schedule_data_expiration(self, room):
        """Start timer for data expiration for certain room."""
        if room in self.room_expiration_timers:
            self.room_expiration_timers[room].cancel()
        loop = asyncio.get_event_loop()
        timer = loop.call_later(
            self.get_expiration_time(),
            lambda: asyncio.ensure_future(self.expire_data(room)),
        )
        self.room_expiration_timers[room] = timer

    def get_filtered_value(self, room, value) -> int:
        """Apply Kalman filter"""
        k_filter: KalmanFilter
        if room in self.room_filters:
            k_filter = self.room_filters[room]
        else:
            k_filter = KalmanFilter(0.01, 5)
            self.room_filters[room] = k_filter
        return int(k_filter.filter(value))

    def get_expiration_time(self):
        """Calculate current expiration delay."""
        return getattr(self, "expiration_time", self.default_expiration_time) * 60

    async def expire_data(self, room):
        """Set data for certain room expired."""
        del self.room_data[room]
        del self.filtered_room_data[room]
        del self.room_filters[room]
        del self.room_expiration_timers[room]
        await self.async_refresh()

    async def on_expiration_time_changed(self, new_time: int):
        """Respond to expiration time changed by user."""
        if new_time is None:
            return
        self.expiration_time = new_time
        for room in self.room_expiration_timers.keys():
            await self.schedule_data_expiration(room)

class KalmanFilter:
    """Filtering RSSI data."""

    cov = float('nan')
    x = float('nan')

    def __init__(self, R, Q):
        """
        Constructor
        :param R: Process Noise
        :param Q: Measurement Noise
        """
        self.A = 1
        self.B = 0
        self.C = 1

        self.R = R
        self.Q = Q

    def filter(self, measurement):
        """
        Filters a measurement
        :param measurement: The measurement value to be filtered
        :return: The filtered value
        """
        u = 0
        if math.isnan(self.x):
            self.x = (1 / self.C) * measurement
            self.cov = (1 / self.C) * self.Q * (1 / self.C)
        else:
            pred_x = (self.A * self.x) + (self.B * u)
            pred_cov = ((self.A * self.cov) * self.A) + self.R

            # Kalman Gain
            K = pred_cov * self.C * (1 / ((self.C * pred_cov * self.C) + self.Q));

            # Correction
            self.x = pred_x + K * (measurement - (self.C * pred_x));
            self.cov = pred_cov - (K * self.C * pred_cov);

        return self.x

    def last_measurement(self):
        """
        Returns the last measurement fed into the filter
        :return: The last measurement fed into the filter
        """
        return self.x

    def set_measurement_noise(self, noise):
        """
        Sets measurement noise
        :param noise: The new measurement noise
        """
        self.Q = noise

    def set_process_noise(self, noise):
        """
        Sets process noise
        :param noise: The new process noise
        """
        self.R = noise