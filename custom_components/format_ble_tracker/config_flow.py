"""Config flow for Format BLE Tracker integration."""
from __future__ import annotations

import re
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
    AWAY_WHEN_OR,
    AWAY_WHEN_AND,
    MAC,
    MAC_REGEX,
    MERGE_IDS,
    MERGE_LOGIC,
    NAME,
    UUID_REGEX,
)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(MAC): str,
        vol.Optional(NAME): str,
    }
)

CONF_ACTION = "conf_action"
CONF_ADD_DEVICE = "add_device"
CONF_MERGE_DEVICES = "merge_devices"
CONF_ENTITIES = "conf_entities"

CONF_ACTIONS = {
    CONF_ADD_DEVICE: "Add new beacon",
    CONF_MERGE_DEVICES: "Combine trackers",
}

CHOOSE_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ACTION, default=CONF_ADD_DEVICE): vol.In(CONF_ACTIONS),
    }
)

CONF_MERGE_LOGIC = {
    AWAY_WHEN_OR: "Show as away, when ANY tracker is away",
    AWAY_WHEN_AND: "Show as away, when ALL trackers are away"
}

MERGE_SCHEMA = vol.Schema(
    {
        vol.Required(NAME): str,
        vol.Required(MERGE_LOGIC, default=AWAY_WHEN_OR): vol.In(CONF_MERGE_LOGIC),
        vol.Required(CONF_ENTITIES): selector.EntitySelector(
            selector.EntitySelectorConfig(
                integration="format_ble_tracker", domain="device_tracker", multiple=True
            ),
        ),
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Format BLE Tracker."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None or CONF_ACTION not in user_input:
            return self.async_show_form(step_id="user", data_schema=CHOOSE_DATA_SCHEMA)

        if user_input[CONF_ACTION] == CONF_ADD_DEVICE:
            return await self.async_step_add_device(user_input)

        return await self.async_step_combine_devices(user_input)

    async def async_step_add_device(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Add new beacon device."""
        if user_input is None or MAC not in user_input:
            return self.async_show_form(
                step_id="add_device", data_schema=STEP_USER_DATA_SCHEMA
            )
        mac = user_input[MAC].strip().upper()
        if not re.match(MAC_REGEX, mac) and not re.match(UUID_REGEX, mac):
            return self.async_abort(reason="not_id")
        await self.async_set_unique_id(mac)
        self._abort_if_unique_id_configured()

        given_name = user_input[NAME] if NAME in user_input else mac

        return self.async_create_entry(
            title=given_name, data={MAC: mac, NAME: given_name}
        )

    async def async_step_combine_devices(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Add new combined tracker."""
        if user_input is None or CONF_ENTITIES not in user_input:
            return self.async_show_form(
                step_id="combine_devices", data_schema=MERGE_SCHEMA
            )
        entities = user_input[CONF_ENTITIES]
        if len(entities) < 2:
            return self.async_abort(reason="less_than_two_children")
        given_name = user_input[NAME]
        return self.async_create_entry(
            title=given_name,
            data={
                NAME: given_name,
                MERGE_LOGIC: user_input[MERGE_LOGIC],
                MERGE_IDS: entities,
            },
        )
