"""Constants for the Printbuddy integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "printbuddy"

CONF_URL = "url"
CONF_TOKEN = "token"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_SCAN_INTERVAL = 30
MIN_SCAN_INTERVAL = 10
DEFAULT_TIMEOUT = 15

PLATFORMS = ["sensor", "binary_sensor"]

ATTRIBUTION = "Data provided by Printbuddy"

DEFAULT_UPDATE_INTERVAL = timedelta(seconds=DEFAULT_SCAN_INTERVAL)
