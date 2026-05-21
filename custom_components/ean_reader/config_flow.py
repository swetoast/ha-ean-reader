"""Config flow for EAN Reader integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_AUTO_ADD_TO_SHOPPING_LIST,
    CONF_CONTACT_EMAIL,
    CONF_ENABLE_WEBHOOK,
    CONF_LANGUAGE_PRIORITY,
    CONF_SHOW_IMAGES,
    CONF_SHOW_NOTIFICATIONS,
    CONF_TRACK_EXPIRY,
    CONF_TRACK_PRICES,
    DEFAULT_AUTO_ADD,
    DEFAULT_ENABLE_WEBHOOK,
    DEFAULT_LANGUAGE_PRIORITY,
    DEFAULT_SHOW_IMAGES,
    DEFAULT_SHOW_NOTIFICATIONS,
    DEFAULT_TRACK_EXPIRY,
    DEFAULT_TRACK_PRICES,
    DEFAULT_USER_EMAIL,
    DOMAIN,
)


class EANReaderConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for EAN Reader."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            return self.async_create_entry(
                title="EAN Reader",
                data={},
                options=user_input,
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_CONTACT_EMAIL,
                        default=DEFAULT_USER_EMAIL,
                    ): str,
                    vol.Optional(
                        CONF_AUTO_ADD_TO_SHOPPING_LIST,
                        default=DEFAULT_AUTO_ADD,
                    ): bool,
                    vol.Optional(
                        CONF_SHOW_NOTIFICATIONS,
                        default=DEFAULT_SHOW_NOTIFICATIONS,
                    ): bool,
                    vol.Optional(
                        CONF_SHOW_IMAGES,
                        default=DEFAULT_SHOW_IMAGES,
                    ): bool,
                    vol.Optional(
                        CONF_TRACK_PRICES,
                        default=DEFAULT_TRACK_PRICES,
                    ): bool,
                    vol.Optional(
                        CONF_TRACK_EXPIRY,
                        default=DEFAULT_TRACK_EXPIRY,
                    ): bool,
                    vol.Optional(
                        CONF_ENABLE_WEBHOOK,
                        default=DEFAULT_ENABLE_WEBHOOK,
                    ): bool,
                }
            ),
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> EANReaderOptionsFlowHandler:
        """Get the options flow for this handler."""
        return EANReaderOptionsFlowHandler(config_entry)


class EANReaderOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for EAN Reader."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = self.config_entry.options

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_CONTACT_EMAIL,
                        default=options.get(CONF_CONTACT_EMAIL, DEFAULT_USER_EMAIL),
                    ): str,
                    vol.Optional(
                        CONF_AUTO_ADD_TO_SHOPPING_LIST,
                        default=options.get(
                            CONF_AUTO_ADD_TO_SHOPPING_LIST, DEFAULT_AUTO_ADD
                        ),
                    ): bool,
                    vol.Optional(
                        CONF_SHOW_NOTIFICATIONS,
                        default=options.get(
                            CONF_SHOW_NOTIFICATIONS, DEFAULT_SHOW_NOTIFICATIONS
                        ),
                    ): bool,
                    vol.Optional(
                        CONF_SHOW_IMAGES,
                        default=options.get(CONF_SHOW_IMAGES, DEFAULT_SHOW_IMAGES),
                    ): bool,
                    vol.Optional(
                        CONF_TRACK_PRICES,
                        default=options.get(CONF_TRACK_PRICES, DEFAULT_TRACK_PRICES),
                    ): bool,
                    vol.Optional(
                        CONF_TRACK_EXPIRY,
                        default=options.get(CONF_TRACK_EXPIRY, DEFAULT_TRACK_EXPIRY),
                    ): bool,
                    vol.Optional(
                        CONF_ENABLE_WEBHOOK,
                        default=options.get(CONF_ENABLE_WEBHOOK, DEFAULT_ENABLE_WEBHOOK),
                    ): bool,
                    vol.Optional(
                        CONF_LANGUAGE_PRIORITY,
                        default=",".join(
                            options.get(CONF_LANGUAGE_PRIORITY, DEFAULT_LANGUAGE_PRIORITY)
                        ),
                    ): str,
                }
            ),
        )
