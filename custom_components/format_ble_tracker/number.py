"""Expiration setter implementation."""
from homeassistant.components import input_number
from homeassistant.components.number import NumberEntity, NumberMode, RestoreNumber
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .__init__ import BeaconCoordinator
from .common import BeaconDeviceEntity
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add sensor entities from a config_entry."""

    coordinator: BeaconCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [BleDataExpirationNumber(coordinator), BleMinimumRssiNumber(coordinator)], True
    )


class BleDataExpirationNumber(BeaconDeviceEntity, RestoreNumber, NumberEntity):
    """Define expiration time number entity."""

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
        """Entity has been added to hass, restoring state."""
        restored = await self.async_get_last_number_data()
        native_value = (
            self.coordinator.default_expiration_time
            if restored is None
            else restored.native_value
        )
        await self.update_value(native_value)

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        val = min(10, max(1, int(value)))
        await self.update_value(val)

    async def update_value(self, value: int):
        """Set value to HA and coordinator."""
        self._attr_native_value = value
        await self.coordinator.on_expiration_time_changed(value)
        self.async_write_ha_state()


class BleMinimumRssiNumber(BeaconDeviceEntity, RestoreNumber, NumberEntity):
    """Define minimum RSSI number entity."""

    _attr_should_poll = False

    def __init__(self, coordinator: BeaconCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_name = coordinator.name + " minimum RSSI"
        self._attr_mode = NumberMode.SLIDER
        self._attr_native_unit_of_measurement = "dBm"
        self._attr_native_max_value = -20
        self._attr_native_min_value = -100
        self._attr_native_step = 1
        self._attr_unique_id = self.formatted_mac_address + "_min_rssi"
        self.entity_id = f"{input_number.DOMAIN}.{self._attr_unique_id}"

    async def async_added_to_hass(self):
        """Entity has been added to hass, restoring state."""
        restored = await self.async_get_last_number_data()
        native_value = (
            self.coordinator.default_min_rssi
            if restored is None
            else restored.native_value
        )
        await self.update_value(native_value)

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        val = min(-20, max(-100, int(value)))
        await self.update_value(val)

    async def update_value(self, value: int):
        """Set value to HA and coordinator."""
        self._attr_native_value = value
        await self.coordinator.on_min_rssi_changed(value)
        self.async_write_ha_state()
