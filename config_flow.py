"""Config flow for Format BLE Tracker integration."""
from __future__ import annotations

import re
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN, MAC, MAC_REGEX, UUID_REGEX, NAME


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(MAC): str,
        vol.Optional(NAME): str,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Format BLE Tracker."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
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
