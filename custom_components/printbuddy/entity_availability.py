"""Entity availability helpers for the Printbuddy integration.

The Printbuddy API currently serializes some provider state fields with default
``False`` values even when a printer/provider cannot physically expose that
capability. Keep those policy decisions in this Home Assistant-free module so
we can regression-test them without importing Home Assistant.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

TEMPERATURE_SENSOR_KEYS: dict[str, tuple[str, ...]] = {
    "nozzle_temperature": ("nozzle", "nozzle_temperature", "nozzle_temp"),
    "nozzle_target_temperature": ("nozzle_target", "nozzle_target_temperature", "nozzle_target_temp"),
    "right_nozzle_temperature": ("nozzle_2", "right_nozzle", "right_nozzle_temperature"),
    "right_nozzle_target_temperature": (
        "nozzle_2_target",
        "right_nozzle_target",
        "right_nozzle_target_temperature",
    ),
    "bed_temperature": ("bed", "bed_temperature", "bed_temp"),
    "bed_target_temperature": ("bed_target", "bed_target_temperature", "bed_target_temp"),
    "chamber_temperature": ("chamber", "chamber_temperature", "chamber_temp"),
    "chamber_target_temperature": ("chamber_target", "chamber_target_temperature", "chamber_target_temp"),
}

# Provider capability allow-lists for fields that Printbuddy may expose as a
# default False even when unsupported. ``connected`` is handled separately.
BINARY_SENSOR_PROVIDER_ALLOWLIST: dict[str, set[str]] = {
    "door_open": {"bambu"},
    "chamber_light": {"bambu"},
    "sdcard": {"bambu", "prusalink", "prusaconnect"},
    "timelapse": {"bambu"},
    "awaiting_plate_clear": {"bambu"},
}


def _field(source: Any, key: str) -> Any:
    """Read a field from a dict-like object or dataclass-like object."""
    if isinstance(source, Mapping):
        return source.get(key)
    return getattr(source, key, None)


def provider_key(printer: Any | None) -> str:
    """Return a normalized Printbuddy provider key."""
    provider = str(_field(printer, "provider") or "").strip().lower()
    if provider in {"fluidd", "mainsail", "klipper"}:
        return "moonraker"
    return provider


def is_present_value(value: Any) -> bool:
    """Return True for scalar telemetry values that should create an entity."""
    return value is not None and not isinstance(value, bool | Mapping | list | tuple | set)


def get_temperature_value(status: Mapping[str, Any], sensor_key: str) -> Any:
    """Return a normalized temperature value from nested or top-level telemetry."""
    temperatures = status.get("temperatures")
    temperature_map = temperatures if isinstance(temperatures, Mapping) else {}
    for key in TEMPERATURE_SENSOR_KEYS.get(sensor_key, ()):
        if key in temperature_map:
            return temperature_map.get(key)
        if key in status:
            return status.get(key)
    return None


def has_temperature(status: Mapping[str, Any], sensor_key: str) -> bool:
    """Return whether a normalized temperature sensor has a usable value."""
    return is_present_value(get_temperature_value(status, sensor_key))


def supported_temperature_keys(status: Mapping[str, Any]) -> set[str]:
    """Return normalized temperature sensor keys available in a status payload."""
    return {sensor_key for sensor_key in TEMPERATURE_SENSOR_KEYS if has_temperature(status, sensor_key)}


def is_binary_sensor_supported(sensor_key: str, status: Mapping[str, Any], printer: Any | None = None) -> bool:
    """Return whether a binary sensor should be exposed for this printer."""
    if sensor_key == "connected":
        return "connected" in status

    if status.get(sensor_key) is None:
        return False

    provider = provider_key(printer)
    allowed_providers = BINARY_SENSOR_PROVIDER_ALLOWLIST.get(sensor_key)
    if not allowed_providers:
        return True
    return provider in allowed_providers
