"""The Format BLE Tracker integration."""
from __future__ import annotations

import asyncio
import json
import logging

# import numpy as np
import math
import time
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
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    elif MERGE_IDS in entry.data:
        await hass.config_entries.async_forward_entry_setups(
            entry, [Platform.DEVICE_TRACKER]
        )

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
        self.min_rssi: int
        self.default_expiration_time: int = 2
        self.default_min_rssi: int = -80
        given_name = data[NAME] if data.__contains__(NAME) else self.mac
        self.room_data = dict[str, int]()
        self.filtered_room_data = dict[str, int]()
        self.room_filters = dict[str, KalmanFilter]()
        self.room_expiration_timers = dict[str, asyncio.TimerHandle]()
        self.room: str | None = None
        self.last_received_adv_time = None
        self.time_from_previous = None

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
            _LOGGER.debug("Skipping malformed message: %s", error)
            return
        msg_time = data.get(TIMESTAMP)
        if msg_time is not None:
            current_time = int(time.time())
            if current_time - msg_time >= self.get_expiration_time():
                _LOGGER.info("Skipping message with old timestamp")
                return
        rssi = data.get(RSSI)
        if rssi < self.get_min_rssi():
            _LOGGER.info("Skipping message with low RSSI (%s)", rssi)
            return
        self.time_from_previous = (
            None
            if self.last_received_adv_time is None
            else (current_time - self.last_received_adv_time)
        )
        self.last_received_adv_time = current_time

        room_topic = msg.topic.split("/")[2]

        await self.schedule_data_expiration(room_topic)

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
        """Apply Kalman filter."""
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

    def get_min_rssi(self):
        """Calculate current minimum RSSI to take."""
        return getattr(self, "min_rssi", self.default_min_rssi)

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

    async def on_min_rssi_changed(self, new_min_rssi: int):
        """Respond to min RSSI changed by user."""
        if new_min_rssi is None:
            return
        self.min_rssi = new_min_rssi


class KalmanFilter:
    """Filtering RSSI data."""

    cov = float("nan")
    param_x = float("nan")

    def __init__(self, param_r, param_q):
        """Initialize filter.

        :param R: Process Noise
        :param Q: Measurement Noise
        """
        self.param_a = 1
        self.param_b = 0
        self.param_c = 1

        self.param_r = param_r
        self.param_q = param_q

    def filter(self, measurement):
        """Filter measurement.

        :param measurement: The measurement value to be filtered
        :return: The filtered value
        """
        param_u = 0
        if math.isnan(self.param_x):
            self.param_x = (1 / self.param_c) * measurement
            self.cov = (1 / self.param_c) * self.param_q * (1 / self.param_c)
        else:
            pred_x = (self.param_a * self.param_x) + (self.param_b * param_u)
            pred_cov = ((self.param_a * self.cov) * self.param_a) + self.param_r

            # Kalman Gain
            param_k = (
                pred_cov
                * self.param_c
                * (1 / ((self.param_c * pred_cov * self.param_c) + self.param_q))
            )

            # Correction
            self.param_x = pred_x + param_k * (measurement - (self.param_c * pred_x))
            self.cov = pred_cov - (param_k * self.param_c * pred_cov)

        return self.param_x

    def last_measurement(self):
        """Return the last measurement fed into the filter.

        :return: The last measurement fed into the filter
        """
        return self.param_x

    def set_measurement_noise(self, noise):
        """Set measurement noise.

        :param noise: The new measurement noise
        """
        self.param_q = noise

    def set_process_noise(self, noise):
        """Set process noise.

        :param noise: The new process noise
        """
        self.param_r = noise
