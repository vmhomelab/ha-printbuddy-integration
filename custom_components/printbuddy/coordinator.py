"""Data coordinator for the Printbuddy integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import PrintbuddyClient, PrintbuddyError, PrintbuddyStatus
from .const import CONF_SCAN_INTERVAL, CONF_TOKEN, CONF_URL, DEFAULT_SCAN_INTERVAL, DOMAIN


class PrintbuddyCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetch Printbuddy printer data."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        self.client = PrintbuddyClient(
            async_get_clientsession(hass),
            entry.data[CONF_URL],
            entry.data.get(CONF_TOKEN),
        )
        interval = int(entry.options.get(CONF_SCAN_INTERVAL, entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)))
        super().__init__(
            hass,
            logger=__import__("logging").getLogger(__name__),
            name=DOMAIN,
            update_interval=timedelta(seconds=interval),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from Printbuddy."""
        try:
            printers = await self.client.async_get_printers()
            statuses = {}
            for printer in printers:
                try:
                    statuses[printer.id] = await self.client.async_get_status(printer.id)
                except PrintbuddyError as err:
                    self.logger.warning("Could not update Printbuddy printer %s: %s", printer.id, err)
                    statuses[printer.id] = PrintbuddyStatus(
                        id=printer.id,
                        name=printer.name,
                        connected=False,
                        raw={"id": printer.id, "name": printer.name, "connected": False},
                    )
            mqtt_status: dict[str, Any] = {}
            panda_breath_status: dict[str, Any] = {}
            obico_status: dict[str, Any] = {}
            try:
                mqtt_status = await self.client.async_get_mqtt_status()
            except PrintbuddyError as err:
                self.logger.debug("Could not update Printbuddy MQTT status: %s", err)
            try:
                panda_breath_status = await self.client.async_get_panda_breath_status()
            except PrintbuddyError as err:
                self.logger.debug("Could not update Printbuddy Panda Breath status: %s", err)
            try:
                obico_status = await self.client.async_get_obico_status()
            except PrintbuddyError as err:
                self.logger.debug("Could not update Printbuddy Obico status: %s", err)
            return {
                "printers": {printer.id: printer for printer in printers},
                "statuses": statuses,
                "mqtt": mqtt_status,
                "panda_breath": panda_breath_status,
                "obico": obico_status,
            }
        except PrintbuddyError as err:
            raise UpdateFailed(str(err)) from err
