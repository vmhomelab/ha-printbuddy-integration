"""Pure telemetry helpers for Printbuddy Home Assistant entities."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

BAMBU_PROVIDERS = {None, "", "bambu"}
BAMBU_ONLY_BINARY_SENSORS = {"door_open", "chamber_light", "sdcard", "timelapse"}

_TEMPERATURE_ALIASES: dict[str, tuple[str, ...]] = {
    "nozzle": ("nozzle_temperature", "nozzle_temp"),
    "nozzle_target": ("nozzle_target_temperature", "nozzle_target_temp"),
    "nozzle_2": ("right_nozzle_temperature", "right_nozzle_temp", "nozzle_2_temperature", "nozzle_2_temp"),
    "nozzle_2_target": ("right_nozzle_target_temperature", "right_nozzle_target_temp", "nozzle_2_target_temperature"),
    "bed": ("bed_temperature", "bed_temp"),
    "bed_target": ("bed_target_temperature", "bed_target_temp"),
    "chamber": ("chamber_temperature", "chamber_temp"),
    "chamber_target": ("chamber_target_temperature", "chamber_target_temp"),
}

_PANDA_BREATH_ALIASES: dict[str, tuple[str, ...]] = {
    "chamber_actual": ("chamber_temp", "actual_temp", "ist"),
    "chamber_target": ("target_temp", "soll"),
    "filter_activation_temp": ("filter_temp", "filtertemp"),
    "heater_trigger_temp": ("heater_temp",),
    "custom_timer_hours": ("custom_timer",),
    "drying_temperature": ("dry_temp",),
    "drying_time_hours": ("dry_time",),
    "slicer_target": ("slicer_target_temp", "slicer_soll"),
}


def scalar_value(value: Any) -> Any | None:
    """Return value only when it is safe to expose as a scalar HA state."""
    if isinstance(value, (bool, Mapping, list, tuple, set)):
        return None
    return value if value is not None else None


def _field(source: Any, key: str) -> Any:
    """Read a field from a dict-like or object-like source."""
    if isinstance(source, Mapping):
        return source.get(key)
    return getattr(source, key, None)


def temperature_value(status: dict[str, Any], key: str) -> Any | None:
    """Return a normalized scalar temperature value from nested or alias fields."""
    temperatures = status.get("temperatures")
    if isinstance(temperatures, Mapping):
        value = scalar_value(temperatures.get(key))
        if value is not None:
            return value
    for alias in _TEMPERATURE_ALIASES.get(key, (f"{key}_temperature", f"{key}_temp")):
        value = scalar_value(status.get(alias))
        if value is not None:
            return value
    return None


def temperature_exists(status: dict[str, Any], key: str) -> bool:
    """Return True when a scalar temperature value is currently present."""
    return temperature_value(status, key) is not None


def raw_scalar_value(status: dict[str, Any], key: str) -> Any | None:
    """Return a top-level scalar status value."""
    return scalar_value(status.get(key))


def raw_scalar_exists(status: dict[str, Any], key: str) -> bool:
    """Return True when a top-level scalar status value is present."""
    return raw_scalar_value(status, key) is not None


def _tray_display_name(tray: dict[str, Any]) -> str | None:
    name = scalar_value(tray.get("tray_sub_brands")) or scalar_value(tray.get("name"))
    material = scalar_value(tray.get("tray_type"))
    if name and material and str(name) != str(material):
        return f"{name} ({material})"
    return str(name or material) if (name or material) else None


def _tray_attributes(tray: dict[str, Any], source: str, slot: int | None) -> dict[str, Any]:
    return {
        "source": source,
        "slot": slot,
        "material": scalar_value(tray.get("tray_type")),
        "name": scalar_value(tray.get("tray_sub_brands")) or scalar_value(tray.get("name")),
        "color": scalar_value(tray.get("tray_color")),
        "filament_id": scalar_value(tray.get("tray_info_idx")) or scalar_value(tray.get("tray_id_name")),
        "remaining_percent": scalar_value(tray.get("remain")),
    }


def _loaded_tray(status: dict[str, Any]) -> tuple[dict[str, Any], str, int | None] | None:
    vt_tray = status.get("vt_tray")
    if isinstance(vt_tray, list):
        for tray in vt_tray:
            if isinstance(tray, dict) and _tray_display_name(tray):
                return tray, "virtual_tray", int(tray.get("id", 254) or 254)

    tray_now = status.get("tray_now")
    if not isinstance(tray_now, int) or tray_now == 255:
        return None

    ams_units = status.get("ams")
    if not isinstance(ams_units, list):
        return None
    for ams in ams_units:
        if not isinstance(ams, dict):
            continue
        ams_id = int(ams.get("id", 0) or 0)
        trays = ams.get("tray") or []
        if not isinstance(trays, list):
            continue
        for tray in trays:
            if not isinstance(tray, dict):
                continue
            local_tray_id = int(tray.get("id", -1) or 0)
            global_tray_id = ams_id * 4 + local_tray_id if ams_id < 128 else ams_id
            if global_tray_id == tray_now and _tray_display_name(tray):
                return tray, "ams", global_tray_id
    return None


def loaded_spool_summary(status: dict[str, Any]) -> str | None:
    """Return a readable loaded spool/filament description."""
    loaded = _loaded_tray(status)
    if not loaded:
        return None
    tray, _source, _slot = loaded
    return _tray_display_name(tray)


def loaded_spool_attributes(status: dict[str, Any]) -> dict[str, Any]:
    """Return attributes for the currently loaded spool/filament."""
    loaded = _loaded_tray(status)
    if not loaded:
        return {}
    tray, source, slot = loaded
    return _tray_attributes(tray, source, slot)


def loaded_spool_exists(status: dict[str, Any]) -> bool:
    """Return True if a loaded spool/filament can be derived."""
    return loaded_spool_summary(status) is not None


def camera_exists(printer: Any | None, status: dict[str, Any] | None = None) -> bool:
    """Return True when Printbuddy can provide a camera for the printer."""
    if printer and bool(getattr(printer, "external_camera_enabled", False)) and getattr(printer, "external_camera_url", None):
        return True
    raw = status or {}
    return bool(raw.get("ipcam") or raw.get("camera_enabled") or raw.get("has_camera"))


def binary_sensor_exists(key: str, status: dict[str, Any], printer: Any | None = None) -> bool:
    """Return True when a binary sensor should exist for this printer/provider."""
    if key == "connected":
        return True
    if key not in status or status.get(key) is None:
        return False
    provider = (getattr(printer, "provider", None) if printer else None) or "bambu"
    return not (key in BAMBU_ONLY_BINARY_SENSORS and provider not in BAMBU_PROVIDERS)


def hms_error_count(status: dict[str, Any]) -> int:
    """Return the number of active HMS errors."""
    errors = status.get("hms_errors")
    return len(errors) if isinstance(errors, list) else 0


def hms_has_error(status: dict[str, Any]) -> bool:
    """Return whether the printer reports active HMS errors."""
    return hms_error_count(status) > 0


def highest_hms_severity(status: dict[str, Any]) -> Any | None:
    """Return the highest-priority HMS severity value, where lower means worse."""
    errors = status.get("hms_errors")
    if not isinstance(errors, list):
        return None
    severities: list[int | float | str] = []
    for error in errors:
        if isinstance(error, Mapping) and error.get("severity") is not None:
            value = error.get("severity")
            if isinstance(value, (int, float, str)):
                severities.append(value)
    return min(severities) if severities else None


def first_hms_error(status: dict[str, Any]) -> dict[str, Any] | None:
    """Return the first HMS error dictionary if present."""
    errors = status.get("hms_errors")
    if not isinstance(errors, list):
        return None
    return next((dict(error) for error in errors if isinstance(error, Mapping)), None)


def ams_units(status: dict[str, Any]) -> list[dict[str, Any]]:
    """Return normalized AMS unit dictionaries."""
    units = status.get("ams")
    return [dict(unit) for unit in units if isinstance(unit, Mapping)] if isinstance(units, list) else []


def ams_slots(status: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """Return stable slot ids and tray dictionaries enriched with AMS context."""
    slots: list[tuple[str, dict[str, Any]]] = []
    for unit in ams_units(status):
        ams_id = int(unit.get("id", 0) or 0)
        trays = unit.get("tray") or []
        if not isinstance(trays, list):
            continue
        for tray in trays:
            if not isinstance(tray, Mapping):
                continue
            tray_dict = dict(tray)
            local_id = int(tray_dict.get("id", 0) or 0)
            tray_dict.update(
                {
                    "ams_id": ams_id,
                    "ams_name": unit.get("name"),
                    "ams_serial_number": unit.get("serial_number"),
                    "ams_module_type": unit.get("module_type"),
                    "global_tray_id": ams_id * 4 + local_id if ams_id < 128 else ams_id,
                }
            )
            slots.append((f"{ams_id}_{local_id}", tray_dict))
    return slots


def ams_slot_name(tray: dict[str, Any]) -> str | None:
    """Return a display value for an AMS slot."""
    return _tray_display_name(tray) or ("Empty" if tray.get("state") == 9 else None)


def ams_slot_attributes(tray: dict[str, Any]) -> dict[str, Any]:
    """Return useful AMS tray attributes."""
    return {
        "ams_id": tray.get("ams_id"),
        "ams_name": tray.get("ams_name"),
        "ams_serial_number": tray.get("ams_serial_number"),
        "ams_module_type": tray.get("ams_module_type"),
        "global_tray_id": tray.get("global_tray_id"),
        "material": scalar_value(tray.get("tray_type")),
        "name": scalar_value(tray.get("tray_sub_brands")) or scalar_value(tray.get("name")),
        "color": scalar_value(tray.get("tray_color")),
        "remaining_percent": scalar_value(tray.get("remain")),
        "k": scalar_value(tray.get("k")),
        "cali_idx": scalar_value(tray.get("cali_idx")),
        "tag_uid": scalar_value(tray.get("tag_uid")),
        "tray_uuid": scalar_value(tray.get("tray_uuid")),
        "nozzle_temp_min": scalar_value(tray.get("nozzle_temp_min")),
        "nozzle_temp_max": scalar_value(tray.get("nozzle_temp_max")),
        "drying_temp": scalar_value(tray.get("drying_temp")),
        "drying_time": scalar_value(tray.get("drying_time")),
        "state_code": scalar_value(tray.get("state")),
    }


def panda_breath_devices(payload: dict[str, Any] | None) -> list[tuple[str, dict[str, Any]]]:
    """Return known Panda Breath device states from native or singleton payloads."""
    if not isinstance(payload, Mapping):
        return []
    devices = payload.get("devices")
    if isinstance(devices, Mapping) and devices:
        return [(str(device_id), dict(state)) for device_id, state in devices.items() if isinstance(state, Mapping)]
    state = payload.get("state")
    if isinstance(state, Mapping) and state:
        device_id = str(state.get("device_id") or payload.get("device_id") or "panda_breath")
        return [(device_id, dict(state))]
    return []


def panda_breath_state_value(state: dict[str, Any], key: str) -> Any | None:
    """Return a Panda Breath state value, accepting native and legacy aliases."""
    value = state.get(key)
    if value is not None:
        return value
    for alias in _PANDA_BREATH_ALIASES.get(key, ()):  # native JSON occasionally keeps original keys
        value = state.get(alias)
        if value is not None:
            return value
    return None


def panda_breath_exists(state: dict[str, Any], key: str) -> bool:
    """Return whether a Panda Breath value exists."""
    return panda_breath_state_value(state, key) is not None


def panda_breath_is_available(state: dict[str, Any]) -> bool:
    """Return whether Panda Breath reports online availability."""
    return str(state.get("availability") or "").strip().lower() == "online"


def obico_enabled(payload: dict[str, Any] | None) -> bool:
    """Return whether Obico detection is enabled in Printbuddy."""
    return bool(payload.get("enabled")) if isinstance(payload, Mapping) else False


def obico_running(payload: dict[str, Any] | None) -> bool:
    """Return whether the Obico detection service task is running."""
    return bool(payload.get("is_running")) if isinstance(payload, Mapping) else False


def ai_printer_state(payload: dict[str, Any] | None, printer_id: int) -> dict[str, Any] | None:
    """Return the per-printer Obico AI state."""
    if not isinstance(payload, Mapping):
        return None
    per_printer = payload.get("per_printer")
    if not isinstance(per_printer, Mapping):
        return None
    value = per_printer.get(printer_id) or per_printer.get(str(printer_id))
    return dict(value) if isinstance(value, Mapping) else None


def ai_printer_state_exists(payload: dict[str, Any] | None, printer_id: int) -> bool:
    """Return whether the Obico payload has per-printer state."""
    return ai_printer_state(payload, printer_id) is not None


def ai_printer_value(payload: dict[str, Any] | None, printer_id: int, key: str) -> Any | None:
    """Return one per-printer Obico AI value."""
    state = ai_printer_state(payload, printer_id)
    return state.get(key) if state else None


def ai_failure_detected(payload: dict[str, Any] | None, printer_id: int) -> bool:
    """Return whether Obico classified this printer as failed."""
    return ai_printer_value(payload, printer_id, "class") == "failure"


def ai_warning_detected(payload: dict[str, Any] | None, printer_id: int) -> bool:
    """Return whether Obico classified this printer as warning."""
    return ai_printer_value(payload, printer_id, "class") == "warning"
