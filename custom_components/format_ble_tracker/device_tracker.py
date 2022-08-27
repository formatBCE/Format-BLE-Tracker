"""Device tracker implementation."""
import logging

from homeassistant.components import device_tracker
from homeassistant.components.device_tracker.config_entry import BaseTrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_HOME, STATE_NOT_HOME, STATE_UNKNOWN
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event

from .__init__ import BeaconCoordinator
from .common import BeaconDeviceEntity
from .const import (
    DOMAIN,
    ENTITY_ID,
    AWAY_WHEN_OR,
    AWAY_WHEN_AND,
    MERGE_IDS,
    MERGE_LOGIC,
    NAME,
    NEW_STATE,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add device tracker entities from a config_entry."""

    if entry.entry_id in hass.data[DOMAIN]:
        coordinator = hass.data[DOMAIN][entry.entry_id]
        async_add_entities([BleDeviceTracker(coordinator)], True)
    elif MERGE_IDS in entry.data:
        async_add_entities(
            [
                MergedDeviceTracker(
                    entry.entry_id,
                    entry.data[NAME],
                    entry.data[MERGE_LOGIC],
                    entry.data[MERGE_IDS],
                )
            ],
            True,
        )


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


class MergedDeviceTracker(BaseTrackerEntity):
    """Define an device tracker entity."""

    _attr_should_poll = False

    def __init__(self, entry_id, name, merge_logic, merge_ids) -> None:
        """Initialize."""
        super().__init__()
        self._attr_name = name
        self._attr_unique_id = entry_id
        self.entity_id = f"{device_tracker.DOMAIN}.combined_{self._attr_unique_id}"
        self.logic = merge_logic
        self.ids = merge_ids
        self.states = {key: None for key in merge_ids}
        self.merged_state = STATE_UNKNOWN

    @property
    def source_type(self) -> str:
        """Return the source type, eg gps or router, of the device."""
        return "bluetooth_le"

    @property
    def state(self) -> str:
        """Return the state of the device."""
        return self.merged_state

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""

        for ent_id in self.ids:
            state_obj = self.hass.states.get(ent_id)
            if state_obj is None:
                state = None
            else:
                state = state_obj.state
            self.on_state_changed(ent_id, state)

        @callback
        def _async_state_changed_listener(event: Event) -> None:
            """Handle updates."""
            if ENTITY_ID in event.data and NEW_STATE in event.data:
                self.on_state_changed(
                    event.data[ENTITY_ID], event.data[NEW_STATE].state
                )

        self.async_on_remove(
            async_track_state_change_event(
                self.hass, self.ids, _async_state_changed_listener
            )
        )

    def on_state_changed(self, entity_id, new_state):
        """Calculate new state."""
        self.states[entity_id] = new_state
        states = self.states.values()
        if STATE_HOME not in states and STATE_NOT_HOME not in states:
            self.merged_state = STATE_UNKNOWN
        else:
            if self.logic == AWAY_WHEN_OR:
                if STATE_NOT_HOME in states:
                    self.merged_state = STATE_NOT_HOME
                else:
                    self.merged_state = STATE_HOME
            elif self.logic == AWAY_WHEN_AND:
                if STATE_HOME in states:
                    self.merged_state = STATE_HOME
                else:
                    self.merged_state = STATE_NOT_HOME
        self.async_write_ha_state()


    @property
    def extra_state_attributes(self):
        """Return the state attributes of the sensor."""
        if len(self.ids) == 0:
            return None
        attr = {}
        attr["included_trackers"] = self.ids
        if self.logic == AWAY_WHEN_OR:
            logic = "Home when all are home"
        elif self.logic == AWAY_WHEN_AND:
            logic = "Home when any is home"
        else:
            logic = None
        attr["show_home_when"] = logic
        return attr
