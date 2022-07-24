"""Expiration setter implementation"""
from homeassistant.components import input_number
from homeassistant.components.number import NumberEntity, NumberMode, RestoreNumber
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
    async_add_entities([BleDataExpirationNumber(coordinator)], True)


class BleDataExpirationNumber(BeaconDeviceEntity, RestoreNumber, NumberEntity):
    """Define an room sensor entity."""

    _attr_should_poll = False

    def __init__(self, coordinator: BeaconCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_name = coordinator.name + " expiration delay"
        self._attr_mode = NumberMode.SLIDER
        self._attr_native_unit_of_measurement = "min"
        self._attr_native_max_value = 10
        self._attr_native_min_value = 1
        self._attr_native_step = 1
        self._attr_unique_id = self.formatted_mac_address + "_expiration"
        self.entity_id = f"{input_number.DOMAIN}.{self._attr_unique_id}"

    async def async_added_to_hass(self):
        """Entity has been added to hass, restoring state"""
        restored = await self.async_get_last_number_data()
        native_value = 2 if restored is None else restored.native_value
        await self.update_value(native_value)

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        val = min(10, max(1, int(value)))
        await self.update_value(val)


    async def update_value(self, value: int):
        """Set value to HA and coordinator"""
        self._attr_native_value = value
        await self.coordinator.on_expiration_time_changed(value)
        self.async_write_ha_state()

