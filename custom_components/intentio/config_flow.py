"""Config flow for Intentio."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, OptionsFlow, ConfigEntry
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    DOMAIN,
    CONF_AI_PROVIDER,
    CONF_AI_KEY,
    CONF_AI_BASE_URL,
    CONF_AI_MODEL,
    DEFAULT_PROVIDER,
    PROVIDERS,
)


def _schema(defaults: dict) -> vol.Schema:
    return vol.Schema({
        vol.Required(CONF_AI_PROVIDER, default=defaults.get(CONF_AI_PROVIDER, DEFAULT_PROVIDER)):
            vol.In(PROVIDERS),
        vol.Optional(CONF_AI_KEY, default=defaults.get(CONF_AI_KEY, "")):
            str,
        vol.Optional(CONF_AI_BASE_URL, default=defaults.get(CONF_AI_BASE_URL, "")):
            str,
        vol.Optional(CONF_AI_MODEL, default=defaults.get(CONF_AI_MODEL, "")):
            str,
    })


class IntentioConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            return self.async_create_entry(title="Intentio", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=_schema({}),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return IntentioOptionsFlow(config_entry)


class IntentioOptionsFlow(OptionsFlow):
    def __init__(self, entry: ConfigEntry) -> None:
        self._entry = entry

    async def async_step_init(self, user_input=None) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        defaults = {**self._entry.data, **self._entry.options}
        return self.async_show_form(
            step_id="init",
            data_schema=_schema(defaults),
        )
