"""Common values."""
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .__init__ import BeaconCoordinator
from .const import DOMAIN


class BeaconDeviceEntity(CoordinatorEntity[BeaconCoordinator]):
    """Base device class."""

    def __init__(self, coordinator: BeaconCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self.formatted_mac_address = format_mac(coordinator.mac)

    @property
    def device_info(self):
        """Device info creation."""
        return {
            "identifiers": {
                # MAC addresses are unique identifiers within a specific domain
                (DOMAIN, self.formatted_mac_address)
            },
            "name": self.coordinator.name,
        }
