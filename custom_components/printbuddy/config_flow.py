"""Config flow for the Printbuddy integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from aiohttp import ClientSession
from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import PrintbuddyAuthError, PrintbuddyClient, PrintbuddyConnectionError, PrintbuddyError
from .const import CONF_SCAN_INTERVAL, CONF_TOKEN, CONF_URL, DEFAULT_SCAN_INTERVAL, DOMAIN, MIN_SCAN_INTERVAL


class CannotConnect(Exception):
    """Error to indicate we cannot connect."""


class InvalidAuth(Exception):
    """Error to indicate there is invalid auth."""


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, str]:
    """Validate user input by reaching Printbuddy."""
    session: ClientSession = async_get_clientsession(hass)
    client = PrintbuddyClient(session, data[CONF_URL], data.get(CONF_TOKEN))

    try:
        await client.async_check_connection()
    except PrintbuddyAuthError as err:
        raise InvalidAuth from err
    except PrintbuddyConnectionError as err:
        raise CannotConnect from err
    except PrintbuddyError as err:
        raise CannotConnect from err

    return {"title": f"Printbuddy ({client.instance_id})"}


class PrintbuddyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Printbuddy."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            user_input[CONF_URL] = PrintbuddyClient.normalize_url(user_input[CONF_URL])
            if token := user_input.get(CONF_TOKEN):
                user_input[CONF_TOKEN] = token.strip()
            else:
                user_input.pop(CONF_TOKEN, None)
            user_input[CONF_SCAN_INTERVAL] = max(int(user_input[CONF_SCAN_INTERVAL]), MIN_SCAN_INTERVAL)

            await self.async_set_unique_id(user_input[CONF_URL].lower())
            self._abort_if_unique_id_configured()

            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # noqa: BLE001
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_URL): str,
                    vol.Optional(CONF_TOKEN): str,
                    vol.Required(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
                        vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL)
                    ),
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> PrintbuddyOptionsFlow:
        """Create the options flow."""
        return PrintbuddyOptionsFlow(config_entry)


class PrintbuddyOptionsFlow(config_entries.OptionsFlow):
    """Handle Printbuddy options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """Manage options."""
        if user_input is not None:
            user_input[CONF_SCAN_INTERVAL] = max(int(user_input[CONF_SCAN_INTERVAL]), MIN_SCAN_INTERVAL)
            return self.async_create_entry(title="", data=user_input)

        current = self._config_entry.options.get(
            CONF_SCAN_INTERVAL,
            self._config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SCAN_INTERVAL, default=current): vol.All(
                        vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL)
                    ),
                }
            ),
        )
