"""Diagnostics support for Printbuddy."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_TOKEN, DOMAIN


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    data = dict(entry.data)
    if CONF_TOKEN in data:
        data[CONF_TOKEN] = "***REDACTED***"
    return {
        "entry": data,
        "printer_count": len(coordinator.data.get("printers", {})),
        "status_count": len(coordinator.data.get("statuses", {})),
    }
