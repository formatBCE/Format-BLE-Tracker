"""Room sensor implementation"""
from homeassistant.components import sensor
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .common import BeaconDeviceEntity
from .__init__ import BeaconCoordinator
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add sensor entities from a config_entry."""

    coordinator: BeaconCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([BleCurrentRoomSensor(coordinator)], True)


class BleCurrentRoomSensor(BeaconDeviceEntity, SensorEntity):
    """Define an room sensor entity."""

    _attr_should_poll = False

    def __init__(self, coordinator: BeaconCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_name = coordinator.name + " current room"
        self._attr_native_value = coordinator.room
        self._attr_unique_id = self.formatted_mac_address + "_current_room"
        self.entity_id = f"{sensor.DOMAIN}.{self._attr_unique_id}"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle data update."""
        self._attr_native_value = self.coordinator.room
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the humidifier."""
        if len(self.coordinator.room_data) == 0:
            return None
        attr = {}
        attr["current_rooms"] = {}
        for key, value in self.coordinator.room_data.items():
            attr["current_rooms"][key] = f"{value} dBm"
        return attr
