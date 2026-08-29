"""Sensors for the Printbuddy integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, SIGNAL_STRENGTH_DECIBELS_MILLIWATT, UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import PrintbuddyCoordinator
from .entity import PrintbuddyEntity, PrintbuddyInstanceEntity
from .telemetry import (
    ai_printer_state_exists,
    ai_printer_value,
    ams_slot_attributes,
    ams_slot_name,
    ams_slots,
    ams_units,
    first_hms_error,
    highest_hms_severity,
    hms_error_count,
    loaded_spool_attributes,
    loaded_spool_exists,
    loaded_spool_summary,
    panda_breath_devices,
    panda_breath_exists,
    panda_breath_state_value,
    raw_scalar_exists,
    raw_scalar_value,
    temperature_exists,
    temperature_value,
)


def _temperature_value(key: str) -> Callable[[dict[str, Any]], Any | None]:
    def value(status: dict[str, Any]) -> Any | None:
        return temperature_value(status, key)

    return value


def _raw_value(key: str) -> Callable[[dict[str, Any]], Any | None]:
    return lambda status: raw_scalar_value(status, key)


def _temperature_exists(key: str) -> Callable[[dict[str, Any]], bool]:
    return lambda status: temperature_exists(status, key)


def _raw_exists(key: str) -> Callable[[dict[str, Any]], bool]:
    return lambda status: raw_scalar_exists(status, key)


def _hms_error_attribute(status: dict[str, Any], key: str) -> Any | None:
    error = first_hms_error(status)
    return error.get(key) if error else None


def _stage_state(status: dict[str, Any]) -> Any | None:
    return status.get("stg_cur_name") or raw_scalar_value(status, "stg_cur")


def _speed_level_name(status: dict[str, Any]) -> str | None:
    value = raw_scalar_value(status, "speed_level")
    if isinstance(value, int):
        return {1: "silent", 2: "standard", 3: "sport", 4: "ludicrous"}.get(value, str(value))
    return str(value) if value is not None else None


def _airduct_mode_name(status: dict[str, Any]) -> str | None:
    value = raw_scalar_value(status, "airduct_mode")
    if isinstance(value, int):
        return {0: "cooling", 1: "heating"}.get(value, str(value))
    return str(value) if value is not None else None


def _status_attributes(status: dict[str, Any]) -> dict[str, Any]:
    return {
        "connected": status.get("connected"),
        "current_print": status.get("current_print"),
        "subtask_name": status.get("subtask_name"),
        "gcode_file": status.get("gcode_file"),
        "layer_num": status.get("layer_num"),
        "total_layers": status.get("total_layers"),
        "hms_error_count": hms_error_count(status),
        "awaiting_plate_clear": status.get("awaiting_plate_clear"),
        "stage": status.get("stg_cur_name"),
        "firmware_version": status.get("firmware_version"),
    }


def _last_hms_error_attributes(status: dict[str, Any]) -> dict[str, Any]:
    error = first_hms_error(status)
    return dict(error or {})


def _nozzle_attributes(status: dict[str, Any]) -> dict[str, Any]:
    return {"nozzles": status.get("nozzles") or [], "nozzle_rack": status.get("nozzle_rack") or []}


def _fila_switch_summary(status: dict[str, Any]) -> Any | None:
    fila_switch = status.get("fila_switch")
    if not isinstance(fila_switch, dict):
        return None
    if not fila_switch.get("installed"):
        return None
    return fila_switch.get("stat", "installed")


def _fila_switch_attributes(status: dict[str, Any]) -> dict[str, Any]:
    fila_switch = status.get("fila_switch")
    return dict(fila_switch) if isinstance(fila_switch, dict) else {}


def _active_nozzle_value(status: dict[str, Any], index: int, field: str) -> Any | None:
    nozzles = status.get("nozzles")
    if not isinstance(nozzles, list) or len(nozzles) <= index or not isinstance(nozzles[index], dict):
        return None
    return nozzles[index].get(field)


def _obico_global_value(key: str) -> Callable[[dict[str, Any]], Any | None]:
    return lambda obico: obico.get(key)


@dataclass(frozen=True, kw_only=True)
class PrintbuddySensorDescription(SensorEntityDescription):
    """Description for a Printbuddy sensor."""

    value_fn: Callable[[dict[str, Any]], Any | None]
    exists_fn: Callable[[dict[str, Any]], bool] = lambda status: True
    attributes_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None


@dataclass(frozen=True, kw_only=True)
class PrintbuddyInstanceSensorDescription(SensorEntityDescription):
    """Description for a Printbuddy instance-level sensor."""

    value_fn: Callable[[dict[str, Any]], Any | None]
    data_key: str
    exists_fn: Callable[[dict[str, Any]], bool] = lambda payload: bool(payload)
    attributes_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None


@dataclass(frozen=True, kw_only=True)
class PandaBreathSensorDescription(SensorEntityDescription):
    """Description for a Panda Breath sensor."""

    value_key: str
    exists_fn: Callable[[dict[str, Any]], bool] | None = None


SENSOR_DESCRIPTIONS: tuple[PrintbuddySensorDescription, ...] = (
    PrintbuddySensorDescription(
        key="status",
        translation_key="status",
        value_fn=lambda status: status.get("state") or ("offline" if not status.get("connected") else "idle"),
        attributes_fn=_status_attributes,
    ),
    PrintbuddySensorDescription(
        key="current_print",
        translation_key="current_print",
        icon="mdi:file-document-outline",
        value_fn=lambda status: status.get("current_print") or status.get("subtask_name") or status.get("gcode_file"),
        exists_fn=lambda status: any(status.get(k) for k in ("current_print", "subtask_name", "gcode_file")),
    ),
    PrintbuddySensorDescription(
        key="loaded_spool",
        translation_key="loaded_spool",
        icon="mdi:spool",
        value_fn=loaded_spool_summary,
        exists_fn=loaded_spool_exists,
        attributes_fn=loaded_spool_attributes,
    ),
    PrintbuddySensorDescription(
        key="nozzle_temperature",
        translation_key="nozzle_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_temperature_value("nozzle"),
        exists_fn=_temperature_exists("nozzle"),
    ),
    PrintbuddySensorDescription(
        key="nozzle_target_temperature",
        translation_key="nozzle_target_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_temperature_value("nozzle_target"),
        exists_fn=_temperature_exists("nozzle_target"),
    ),
    PrintbuddySensorDescription(
        key="right_nozzle_temperature",
        translation_key="right_nozzle_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_temperature_value("nozzle_2"),
        exists_fn=_temperature_exists("nozzle_2"),
    ),
    PrintbuddySensorDescription(
        key="right_nozzle_target_temperature",
        translation_key="right_nozzle_target_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_temperature_value("nozzle_2_target"),
        exists_fn=_temperature_exists("nozzle_2_target"),
    ),
    PrintbuddySensorDescription(
        key="bed_temperature",
        translation_key="bed_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_temperature_value("bed"),
        exists_fn=_temperature_exists("bed"),
    ),
    PrintbuddySensorDescription(
        key="bed_target_temperature",
        translation_key="bed_target_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_temperature_value("bed_target"),
        exists_fn=_temperature_exists("bed_target"),
    ),
    PrintbuddySensorDescription(
        key="chamber_temperature",
        translation_key="chamber_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_temperature_value("chamber"),
        exists_fn=_temperature_exists("chamber"),
    ),
    PrintbuddySensorDescription(
        key="chamber_target_temperature",
        translation_key="chamber_target_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_temperature_value("chamber_target"),
        exists_fn=_temperature_exists("chamber_target"),
    ),
    PrintbuddySensorDescription(
        key="progress",
        translation_key="progress",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_raw_value("progress"),
        exists_fn=_raw_exists("progress"),
    ),
    PrintbuddySensorDescription(
        key="remaining_time",
        translation_key="remaining_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_raw_value("remaining_time"),
        exists_fn=_raw_exists("remaining_time"),
    ),
    PrintbuddySensorDescription(
        key="current_layer",
        translation_key="current_layer",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:layers-outline",
        value_fn=_raw_value("layer_num"),
        exists_fn=_raw_exists("layer_num"),
    ),
    PrintbuddySensorDescription(
        key="total_layers",
        translation_key="total_layers",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:layers-triple-outline",
        value_fn=_raw_value("total_layers"),
        exists_fn=_raw_exists("total_layers"),
    ),
    PrintbuddySensorDescription(
        key="wifi_signal",
        translation_key="wifi_signal",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_raw_value("wifi_signal"),
        exists_fn=_raw_exists("wifi_signal"),
    ),
    PrintbuddySensorDescription(
        key="cooling_fan_speed",
        translation_key="cooling_fan_speed",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:fan",
        value_fn=_raw_value("cooling_fan_speed"),
        exists_fn=_raw_exists("cooling_fan_speed"),
    ),
    PrintbuddySensorDescription(
        key="auxiliary_fan_speed",
        translation_key="auxiliary_fan_speed",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:fan",
        value_fn=_raw_value("big_fan1_speed"),
        exists_fn=_raw_exists("big_fan1_speed"),
    ),
    PrintbuddySensorDescription(
        key="chamber_fan_speed",
        translation_key="chamber_fan_speed",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:fan",
        value_fn=_raw_value("big_fan2_speed"),
        exists_fn=_raw_exists("big_fan2_speed"),
    ),
    PrintbuddySensorDescription(
        key="heatbreak_fan_speed",
        translation_key="heatbreak_fan_speed",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:fan",
        value_fn=_raw_value("heatbreak_fan_speed"),
        exists_fn=_raw_exists("heatbreak_fan_speed"),
    ),
    PrintbuddySensorDescription(
        key="hms_error_count",
        translation_key="hms_error_count",
        icon="mdi:alert-circle-outline",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=hms_error_count,
        exists_fn=lambda status: "hms_errors" in status,
    ),
    PrintbuddySensorDescription(
        key="highest_hms_severity",
        translation_key="highest_hms_severity",
        icon="mdi:alert-decagram-outline",
        value_fn=highest_hms_severity,
        exists_fn=lambda status: hms_error_count(status) > 0,
    ),
    PrintbuddySensorDescription(
        key="last_hms_error",
        translation_key="last_hms_error",
        icon="mdi:alert-outline",
        value_fn=lambda status: _hms_error_attribute(status, "code"),
        exists_fn=lambda status: hms_error_count(status) > 0,
        attributes_fn=_last_hms_error_attributes,
    ),
    PrintbuddySensorDescription(
        key="firmware_version",
        translation_key="firmware_version",
        entity_category="diagnostic",
        icon="mdi:chip",
        value_fn=_raw_value("firmware_version"),
        exists_fn=_raw_exists("firmware_version"),
    ),
    PrintbuddySensorDescription(
        key="stage",
        translation_key="stage",
        icon="mdi:progress-clock",
        value_fn=_stage_state,
        exists_fn=lambda status: status.get("stg_cur_name") is not None or raw_scalar_exists(status, "stg_cur"),
    ),
    PrintbuddySensorDescription(
        key="stage_code",
        translation_key="stage_code",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:numeric",
        value_fn=_raw_value("stg_cur"),
        exists_fn=_raw_exists("stg_cur"),
    ),
    PrintbuddySensorDescription(
        key="speed_level",
        translation_key="speed_level",
        icon="mdi:speedometer",
        value_fn=_speed_level_name,
        exists_fn=_raw_exists("speed_level"),
    ),
    PrintbuddySensorDescription(
        key="airduct_mode",
        translation_key="airduct_mode",
        icon="mdi:air-filter",
        value_fn=_airduct_mode_name,
        exists_fn=_raw_exists("airduct_mode"),
    ),
    PrintbuddySensorDescription(
        key="current_plate",
        translation_key="current_plate",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:rectangle-outline",
        value_fn=_raw_value("current_plate_id"),
        exists_fn=_raw_exists("current_plate_id"),
    ),
    PrintbuddySensorDescription(
        key="current_archive_id",
        translation_key="current_archive_id",
        entity_category="diagnostic",
        icon="mdi:archive-outline",
        value_fn=_raw_value("current_archive_id"),
        exists_fn=_raw_exists("current_archive_id"),
    ),
    PrintbuddySensorDescription(
        key="printable_objects_count",
        translation_key="printable_objects_count",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:select-group",
        value_fn=_raw_value("printable_objects_count"),
        exists_fn=_raw_exists("printable_objects_count"),
    ),
    PrintbuddySensorDescription(
        key="active_extruder",
        translation_key="active_extruder",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:printer-3d-nozzle",
        value_fn=_raw_value("active_extruder"),
        exists_fn=_raw_exists("active_extruder"),
    ),
    PrintbuddySensorDescription(
        key="left_nozzle_type",
        translation_key="left_nozzle_type",
        entity_category="diagnostic",
        icon="mdi:printer-3d-nozzle-outline",
        value_fn=lambda status: _active_nozzle_value(status, 0, "nozzle_type"),
        exists_fn=lambda status: _active_nozzle_value(status, 0, "nozzle_type") is not None,
    ),
    PrintbuddySensorDescription(
        key="left_nozzle_diameter",
        translation_key="left_nozzle_diameter",
        entity_category="diagnostic",
        icon="mdi:diameter-outline",
        value_fn=lambda status: _active_nozzle_value(status, 0, "nozzle_diameter"),
        exists_fn=lambda status: _active_nozzle_value(status, 0, "nozzle_diameter") is not None,
    ),
    PrintbuddySensorDescription(
        key="right_nozzle_type",
        translation_key="right_nozzle_type",
        entity_category="diagnostic",
        icon="mdi:printer-3d-nozzle-outline",
        value_fn=lambda status: _active_nozzle_value(status, 1, "nozzle_type"),
        exists_fn=lambda status: _active_nozzle_value(status, 1, "nozzle_type") is not None,
    ),
    PrintbuddySensorDescription(
        key="right_nozzle_diameter",
        translation_key="right_nozzle_diameter",
        entity_category="diagnostic",
        icon="mdi:diameter-outline",
        value_fn=lambda status: _active_nozzle_value(status, 1, "nozzle_diameter"),
        exists_fn=lambda status: _active_nozzle_value(status, 1, "nozzle_diameter") is not None,
    ),
    PrintbuddySensorDescription(
        key="nozzle_rack_summary",
        translation_key="nozzle_rack_summary",
        entity_category="diagnostic",
        icon="mdi:tools",
        value_fn=lambda status: len(status.get("nozzle_rack") or []),
        exists_fn=lambda status: bool(status.get("nozzle_rack")),
        attributes_fn=_nozzle_attributes,
    ),
    PrintbuddySensorDescription(
        key="fila_switch_status",
        translation_key="fila_switch_status",
        entity_category="diagnostic",
        icon="mdi:transit-connection-variant",
        value_fn=_fila_switch_summary,
        exists_fn=lambda status: _fila_switch_summary(status) is not None,
        attributes_fn=_fila_switch_attributes,
    ),
    PrintbuddySensorDescription(
        key="ams_status_main",
        translation_key="ams_status_main",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:swap-horizontal",
        value_fn=_raw_value("ams_status_main"),
        exists_fn=_raw_exists("ams_status_main"),
    ),
    PrintbuddySensorDescription(
        key="ams_status_sub",
        translation_key="ams_status_sub",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:swap-horizontal-variant",
        value_fn=_raw_value("ams_status_sub"),
        exists_fn=_raw_exists("ams_status_sub"),
    ),
    PrintbuddySensorDescription(
        key="filament_change_stage",
        translation_key="filament_change_stage",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:timeline-clock-outline",
        value_fn=_raw_value("mc_print_sub_stage"),
        exists_fn=_raw_exists("mc_print_sub_stage"),
    ),
    PrintbuddySensorDescription(
        key="last_ams_update",
        translation_key="last_ams_update",
        entity_category="diagnostic",
        icon="mdi:clock-outline",
        value_fn=_raw_value("last_ams_update"),
        exists_fn=_raw_exists("last_ams_update"),
    ),
    PrintbuddySensorDescription(
        key="active_tray",
        translation_key="active_tray",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:tray-full",
        value_fn=_raw_value("tray_now"),
        exists_fn=_raw_exists("tray_now"),
    ),
)

OBICO_SENSOR_DESCRIPTIONS: tuple[PrintbuddyInstanceSensorDescription, ...] = (
    PrintbuddyInstanceSensorDescription(
        key="obico_sensitivity",
        translation_key="obico_sensitivity",
        data_key="obico",
        icon="mdi:tune-variant",
        value_fn=_obico_global_value("sensitivity"),
        exists_fn=lambda obico: obico.get("sensitivity") is not None,
    ),
    PrintbuddyInstanceSensorDescription(
        key="obico_action",
        translation_key="obico_action",
        data_key="obico",
        icon="mdi:gesture-tap-button",
        value_fn=_obico_global_value("action"),
        exists_fn=lambda obico: obico.get("action") is not None,
    ),
    PrintbuddyInstanceSensorDescription(
        key="obico_poll_interval",
        translation_key="obico_poll_interval",
        data_key="obico",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_obico_global_value("poll_interval"),
        exists_fn=lambda obico: obico.get("poll_interval") is not None,
    ),
    PrintbuddyInstanceSensorDescription(
        key="obico_last_error",
        translation_key="obico_last_error",
        data_key="obico",
        entity_category="diagnostic",
        icon="mdi:alert-outline",
        value_fn=lambda obico: obico.get("last_error") or "none",
    ),
    PrintbuddyInstanceSensorDescription(
        key="obico_low_threshold",
        translation_key="obico_low_threshold",
        data_key="obico",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:chart-bell-curve",
        value_fn=lambda obico: (obico.get("thresholds") or {}).get("low") if isinstance(obico.get("thresholds"), dict) else None,
        exists_fn=lambda obico: isinstance(obico.get("thresholds"), dict) and (obico.get("thresholds") or {}).get("low") is not None,
    ),
    PrintbuddyInstanceSensorDescription(
        key="obico_high_threshold",
        translation_key="obico_high_threshold",
        data_key="obico",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:chart-bell-curve-cumulative",
        value_fn=lambda obico: (obico.get("thresholds") or {}).get("high") if isinstance(obico.get("thresholds"), dict) else None,
        exists_fn=lambda obico: isinstance(obico.get("thresholds"), dict) and (obico.get("thresholds") or {}).get("high") is not None,
    ),
)

AI_PRINTER_SENSOR_DESCRIPTIONS: tuple[PrintbuddySensorDescription, ...] = (
    PrintbuddySensorDescription(
        key="ai_detection_class",
        translation_key="ai_detection_class",
        icon="mdi:robot-industrial-outline",
        value_fn=lambda status: None,
    ),
    PrintbuddySensorDescription(
        key="ai_failure_score",
        translation_key="ai_failure_score",
        icon="mdi:robot-confused-outline",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda status: None,
    ),
    PrintbuddySensorDescription(
        key="ai_frame_count",
        translation_key="ai_frame_count",
        icon="mdi:counter",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda status: None,
    ),
)

PANDA_BREATH_SENSOR_DESCRIPTIONS: tuple[PandaBreathSensorDescription, ...] = (
    PandaBreathSensorDescription(key="panda_breath_chamber_temperature", translation_key="panda_breath_chamber_temperature", value_key="chamber_actual", device_class=SensorDeviceClass.TEMPERATURE, native_unit_of_measurement=UnitOfTemperature.CELSIUS, state_class=SensorStateClass.MEASUREMENT),
    PandaBreathSensorDescription(key="panda_breath_target_temperature", translation_key="panda_breath_target_temperature", value_key="chamber_target", device_class=SensorDeviceClass.TEMPERATURE, native_unit_of_measurement=UnitOfTemperature.CELSIUS, state_class=SensorStateClass.MEASUREMENT),
    PandaBreathSensorDescription(key="panda_breath_bed_temperature", translation_key="panda_breath_bed_temperature", value_key="bed_temperature", device_class=SensorDeviceClass.TEMPERATURE, native_unit_of_measurement=UnitOfTemperature.CELSIUS, state_class=SensorStateClass.MEASUREMENT),
    PandaBreathSensorDescription(key="panda_breath_bed_limit", translation_key="panda_breath_bed_limit", value_key="bed_limit", device_class=SensorDeviceClass.TEMPERATURE, native_unit_of_measurement=UnitOfTemperature.CELSIUS, state_class=SensorStateClass.MEASUREMENT),
    PandaBreathSensorDescription(key="panda_breath_filter_activation_temperature", translation_key="panda_breath_filter_activation_temperature", value_key="filter_activation_temp", device_class=SensorDeviceClass.TEMPERATURE, native_unit_of_measurement=UnitOfTemperature.CELSIUS, state_class=SensorStateClass.MEASUREMENT),
    PandaBreathSensorDescription(key="panda_breath_heater_trigger_temperature", translation_key="panda_breath_heater_trigger_temperature", value_key="heater_trigger_temp", device_class=SensorDeviceClass.TEMPERATURE, native_unit_of_measurement=UnitOfTemperature.CELSIUS, state_class=SensorStateClass.MEASUREMENT),
    PandaBreathSensorDescription(key="panda_breath_custom_temperature", translation_key="panda_breath_custom_temperature", value_key="custom_temp", device_class=SensorDeviceClass.TEMPERATURE, native_unit_of_measurement=UnitOfTemperature.CELSIUS, state_class=SensorStateClass.MEASUREMENT),
    PandaBreathSensorDescription(key="panda_breath_drying_temperature", translation_key="panda_breath_drying_temperature", value_key="drying_temperature", device_class=SensorDeviceClass.TEMPERATURE, native_unit_of_measurement=UnitOfTemperature.CELSIUS, state_class=SensorStateClass.MEASUREMENT),
    PandaBreathSensorDescription(key="panda_breath_drying_remaining", translation_key="panda_breath_drying_remaining", value_key="drying_remaining_min", device_class=SensorDeviceClass.DURATION, native_unit_of_measurement=UnitOfTime.MINUTES, state_class=SensorStateClass.MEASUREMENT),
    PandaBreathSensorDescription(key="panda_breath_drying_time", translation_key="panda_breath_drying_time", value_key="drying_time_hours", device_class=SensorDeviceClass.DURATION, native_unit_of_measurement=UnitOfTime.HOURS, state_class=SensorStateClass.MEASUREMENT),
    PandaBreathSensorDescription(key="panda_breath_slicer_target_temperature", translation_key="panda_breath_slicer_target_temperature", value_key="slicer_target", device_class=SensorDeviceClass.TEMPERATURE, native_unit_of_measurement=UnitOfTemperature.CELSIUS, state_class=SensorStateClass.MEASUREMENT),
    PandaBreathSensorDescription(key="panda_breath_mode", translation_key="panda_breath_mode", value_key="mode", icon="mdi:state-machine"),
    PandaBreathSensorDescription(key="panda_breath_filament_drying_mode", translation_key="panda_breath_filament_drying_mode", value_key="filament_drying_mode", icon="mdi:air-filter"),
    PandaBreathSensorDescription(key="panda_breath_status", translation_key="panda_breath_status", value_key="status", icon="mdi:list-status"),
    PandaBreathSensorDescription(key="panda_breath_lock_status", translation_key="panda_breath_lock_status", value_key="lock_status", icon="mdi:lock-outline"),
    PandaBreathSensorDescription(key="panda_breath_firmware_version", translation_key="panda_breath_firmware_version", value_key="version", icon="mdi:chip", entity_category="diagnostic"),
    PandaBreathSensorDescription(key="panda_breath_bound_printer", translation_key="panda_breath_bound_printer", value_key="printer_name", icon="mdi:printer-3d", entity_category="diagnostic"),
    PandaBreathSensorDescription(key="panda_breath_last_seen", translation_key="panda_breath_last_seen", value_key="last_seen", device_class=SensorDeviceClass.TIMESTAMP, entity_category="diagnostic"),
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up Printbuddy sensors."""
    coordinator: PrintbuddyCoordinator = hass.data[DOMAIN][entry.entry_id]
    known_entities: set[tuple[Any, str]] = set()

    def add_entities_for_known_data() -> None:
        entities: list[SensorEntity] = []
        for description in OBICO_SENSOR_DESCRIPTIONS:
            payload = coordinator.data.get(description.data_key, {})
            entity_id = ("instance", description.key)
            if entity_id not in known_entities and description.exists_fn(payload):
                known_entities.add(entity_id)
                entities.append(PrintbuddyInstanceSensor(coordinator, description))

        for printer_id, status in coordinator.data.get("statuses", {}).items():
            raw = status.raw
            for description in SENSOR_DESCRIPTIONS:
                entity_id = (printer_id, description.key)
                if entity_id in known_entities or not description.exists_fn(raw):
                    continue
                known_entities.add(entity_id)
                entities.append(PrintbuddySensor(coordinator, printer_id, description))
            if ai_printer_state_exists(coordinator.data.get("obico", {}), printer_id):
                for description in AI_PRINTER_SENSOR_DESCRIPTIONS:
                    entity_id = (printer_id, description.key)
                    if entity_id in known_entities:
                        continue
                    known_entities.add(entity_id)
                    entities.append(PrintbuddyAiSensor(coordinator, printer_id, description))
            for slot_id, tray in ams_slots(raw):
                entity_id = (printer_id, f"ams_slot_{slot_id}")
                if entity_id in known_entities:
                    continue
                known_entities.add(entity_id)
                entities.append(PrintbuddyAmsSlotSensor(coordinator, printer_id, slot_id, tray))
            for unit in ams_units(raw):
                ams_id = unit.get("id")
                for key in ("humidity", "temp", "dry_time", "sw_ver", "serial_number", "module_type"):
                    entity_id = (printer_id, f"ams_{ams_id}_{key}")
                    if entity_id in known_entities or unit.get(key) in (None, ""):
                        continue
                    known_entities.add(entity_id)
                    entities.append(PrintbuddyAmsUnitSensor(coordinator, printer_id, int(ams_id or 0), key))

        for device_id, state in panda_breath_devices(coordinator.data.get("panda_breath", {})):
            for description in PANDA_BREATH_SENSOR_DESCRIPTIONS:
                exists_fn = description.exists_fn or (lambda s, k=description.value_key: panda_breath_exists(s, k))
                entity_id = (device_id, description.key)
                if entity_id in known_entities or not exists_fn(state):
                    continue
                known_entities.add(entity_id)
                entities.append(PandaBreathSensor(coordinator, device_id, description))

        if entities:
            async_add_entities(entities)

    add_entities_for_known_data()
    entry.async_on_unload(coordinator.async_add_listener(add_entities_for_known_data))


class PrintbuddySensor(PrintbuddyEntity, SensorEntity):
    """Representation of a Printbuddy sensor."""

    entity_description: PrintbuddySensorDescription

    def __init__(self, coordinator: PrintbuddyCoordinator, printer_id: int, description: PrintbuddySensorDescription) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, printer_id, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any | None:
        """Return the current sensor value."""
        if not self.entity_description.exists_fn(self.status):
            return None
        return self.entity_description.value_fn(self.status)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return sensor attributes."""
        attrs = super().extra_state_attributes
        if self.entity_description.attributes_fn:
            attrs.update(self.entity_description.attributes_fn(self.status))
        return attrs


class PrintbuddyAiSensor(PrintbuddySensor):
    """Representation of a per-printer Obico AI sensor."""

    @property
    def native_value(self) -> Any | None:
        """Return the AI state value."""
        key_map = {"ai_detection_class": "class", "ai_failure_score": "score", "ai_frame_count": "frame_count"}
        return ai_printer_value(self.coordinator.data.get("obico", {}), self.printer_id, key_map[self.entity_description.key])


class PrintbuddyInstanceSensor(PrintbuddyInstanceEntity, SensorEntity):
    """Representation of a Printbuddy instance-level sensor."""

    entity_description: PrintbuddyInstanceSensorDescription

    def __init__(self, coordinator: PrintbuddyCoordinator, description: PrintbuddyInstanceSensorDescription) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any | None:
        """Return the current sensor value."""
        payload = self.coordinator.data.get(self.entity_description.data_key, {})
        return self.entity_description.value_fn(payload)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        payload = self.coordinator.data.get(self.entity_description.data_key, {})
        return self.entity_description.attributes_fn(payload) if self.entity_description.attributes_fn else {}


class PrintbuddyAmsUnitSensor(PrintbuddyEntity, SensorEntity):
    """Representation of one AMS unit property."""

    def __init__(self, coordinator: PrintbuddyCoordinator, printer_id: int, ams_id: int, key: str) -> None:
        """Initialize the AMS unit sensor."""
        super().__init__(coordinator, printer_id, f"ams_{ams_id}_{key}")
        self.ams_id = ams_id
        self.key = key
        self._attr_translation_key = f"ams_{key}"
        self._attr_icon = "mdi:spool"
        if key in {"humidity"}:
            self._attr_native_unit_of_measurement = PERCENTAGE
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif key in {"temp"}:
            self._attr_device_class = SensorDeviceClass.TEMPERATURE
            self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif key == "dry_time":
            self._attr_device_class = SensorDeviceClass.DURATION
            self._attr_native_unit_of_measurement = UnitOfTime.MINUTES
            self._attr_state_class = SensorStateClass.MEASUREMENT

    def _unit(self) -> dict[str, Any] | None:
        return next((unit for unit in ams_units(self.status) if int(unit.get("id", 0) or 0) == self.ams_id), None)

    @property
    def native_value(self) -> Any | None:
        """Return the AMS unit value."""
        unit = self._unit()
        return unit.get(self.key) if unit else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return AMS context."""
        attrs = super().extra_state_attributes
        unit = self._unit()
        if unit:
            attrs.update({"ams_id": self.ams_id, "ams_name": unit.get("name"), "is_ams_ht": unit.get("is_ams_ht")})
        return attrs


class PrintbuddyAmsSlotSensor(PrintbuddyEntity, SensorEntity):
    """Representation of one AMS slot with useful tray attributes."""

    def __init__(self, coordinator: PrintbuddyCoordinator, printer_id: int, slot_id: str, initial_tray: dict[str, Any]) -> None:
        """Initialize the AMS slot sensor."""
        super().__init__(coordinator, printer_id, f"ams_slot_{slot_id}")
        self.slot_id = slot_id
        self.initial_tray = initial_tray
        self._attr_icon = "mdi:spool"
        self._attr_translation_key = "ams_slot"

    def _tray(self) -> dict[str, Any] | None:
        return next((tray for current_slot, tray in ams_slots(self.status) if current_slot == self.slot_id), self.initial_tray)

    @property
    def native_value(self) -> Any | None:
        """Return the slot material/name."""
        tray = self._tray()
        return ams_slot_name(tray) if tray else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return tray details."""
        attrs = super().extra_state_attributes
        tray = self._tray()
        if tray:
            attrs.update(ams_slot_attributes(tray))
        return attrs


class PandaBreathSensor(PrintbuddyInstanceEntity, SensorEntity):
    """Representation of a Panda Breath sensor."""

    entity_description: PandaBreathSensorDescription

    def __init__(self, coordinator: PrintbuddyCoordinator, device_id: str, description: PandaBreathSensorDescription) -> None:
        """Initialize the Panda Breath sensor."""
        super().__init__(coordinator, f"{device_id}_{description.key}")
        self.device_id = device_id
        self.entity_description = description

    def _state(self) -> dict[str, Any]:
        return next((state for device_id, state in panda_breath_devices(self.coordinator.data.get("panda_breath", {})) if device_id == self.device_id), {})

    @property
    def native_value(self) -> Any | None:
        """Return the Panda Breath value."""
        return panda_breath_state_value(self._state(), self.entity_description.value_key)

    @property
    def available(self) -> bool:
        """Return if the Panda Breath state is available."""
        return super().available and bool(self._state())

    @property
    def device_info(self) -> DeviceInfo:
        """Return Panda Breath device info."""
        state = self._state()
        name = state.get("printer_name") or f"Panda Breath {self.device_id}"
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self.coordinator.client.instance_id}_panda_breath_{self.device_id}")},
            name=str(name),
            manufacturer="BIQU",
            model="Panda Breath",
            sw_version=state.get("version"),
            via_device=(DOMAIN, self.coordinator.client.instance_id),
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return Panda Breath context."""
        state = self._state()
        return {
            "device_id": self.device_id,
            "availability": state.get("availability"),
            "printer_sn": state.get("printer_sn"),
            "printer_ip": state.get("printer_ip"),
            "printer_bind": state.get("printer_bind"),
        }
