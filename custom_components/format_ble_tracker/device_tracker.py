"""Device tracker implementation"""
from homeassistant.components import device_tracker
from homeassistant.components.device_tracker.config_entry import BaseTrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_HOME, STATE_NOT_HOME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .common import BeaconDeviceEntity
from .__init__ import BeaconCoordinator
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add device tracker entities from a config_entry."""

    coordinator: BeaconCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([BleDeviceTracker(coordinator)], True)


class BleDeviceTracker(BeaconDeviceEntity, BaseTrackerEntity):
    """Define an device tracker entity."""

    _attr_should_poll = False

    def __init__(self, coordinator: BeaconCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_name = coordinator.name + " tracker"
        self._attr_unique_id = self.formatted_mac_address + "_tracker"
        self.entity_id = f"{device_tracker.DOMAIN}.{self._attr_unique_id}"

    @property
    def source_type(self) -> str:
        """Return the source type, eg gps or router, of the device."""
        return "bluetooth_le"

    @property
    def state(self) -> str:
        """Return the state of the device."""
        if self.coordinator.room is None:
            return STATE_NOT_HOME
        return STATE_HOME

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle data update."""
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Subscribe to MQTT events."""
        # await self.coordinator.async_on_entity_added_to_ha()
        return await super().async_added_to_hass()
