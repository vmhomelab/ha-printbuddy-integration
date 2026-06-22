"""Sensors for the Printbuddy integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, SIGNAL_STRENGTH_DECIBELS_MILLIWATT, UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import PrintbuddyCoordinator
from .entity import PrintbuddyEntity
from .entity_availability import get_temperature_value, has_temperature


def _temperature_sensor_value(sensor_key: str) -> Callable[[dict[str, Any]], Any | None]:
    return lambda status: get_temperature_value(status, sensor_key)


def _temperature_sensor_exists(sensor_key: str) -> Callable[[dict[str, Any], Any | None], bool]:
    return lambda status, _printer=None: has_temperature(status, sensor_key)


def _raw_value(key: str) -> Callable[[dict[str, Any]], Any | None]:
    return lambda status: status.get(key)


def _raw_exists(key: str) -> Callable[[dict[str, Any], Any | None], bool]:
    return lambda status, _printer=None: status.get(key) is not None


@dataclass(frozen=True, kw_only=True)
class PrintbuddySensorDescription(SensorEntityDescription):
    """Description for a Printbuddy sensor."""

    value_fn: Callable[[dict[str, Any]], Any | None]
    exists_fn: Callable[[dict[str, Any], Any | None], bool] = lambda status, _printer=None: True
    attributes_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None


def _status_attributes(status: dict[str, Any]) -> dict[str, Any]:
    return {
        "connected": status.get("connected"),
        "current_print": status.get("current_print"),
        "subtask_name": status.get("subtask_name"),
        "gcode_file": status.get("gcode_file"),
        "layer_num": status.get("layer_num"),
        "total_layers": status.get("total_layers"),
        "hms_error_count": len(status.get("hms_errors") or []),
        "awaiting_plate_clear": status.get("awaiting_plate_clear"),
    }


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
        exists_fn=lambda status, _printer=None: any(
            status.get(k) for k in ("current_print", "subtask_name", "gcode_file")
        ),
    ),
    PrintbuddySensorDescription(
        key="nozzle_temperature",
        translation_key="nozzle_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_temperature_sensor_value("nozzle_temperature"),
        exists_fn=_temperature_sensor_exists("nozzle_temperature"),
    ),
    PrintbuddySensorDescription(
        key="nozzle_target_temperature",
        translation_key="nozzle_target_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_temperature_sensor_value("nozzle_target_temperature"),
        exists_fn=_temperature_sensor_exists("nozzle_target_temperature"),
    ),
    PrintbuddySensorDescription(
        key="right_nozzle_temperature",
        translation_key="right_nozzle_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_temperature_sensor_value("right_nozzle_temperature"),
        exists_fn=_temperature_sensor_exists("right_nozzle_temperature"),
    ),
    PrintbuddySensorDescription(
        key="right_nozzle_target_temperature",
        translation_key="right_nozzle_target_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_temperature_sensor_value("right_nozzle_target_temperature"),
        exists_fn=_temperature_sensor_exists("right_nozzle_target_temperature"),
    ),
    PrintbuddySensorDescription(
        key="bed_temperature",
        translation_key="bed_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_temperature_sensor_value("bed_temperature"),
        exists_fn=_temperature_sensor_exists("bed_temperature"),
    ),
    PrintbuddySensorDescription(
        key="bed_target_temperature",
        translation_key="bed_target_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_temperature_sensor_value("bed_target_temperature"),
        exists_fn=_temperature_sensor_exists("bed_target_temperature"),
    ),
    PrintbuddySensorDescription(
        key="chamber_temperature",
        translation_key="chamber_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_temperature_sensor_value("chamber_temperature"),
        exists_fn=_temperature_sensor_exists("chamber_temperature"),
    ),
    PrintbuddySensorDescription(
        key="chamber_target_temperature",
        translation_key="chamber_target_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_temperature_sensor_value("chamber_target_temperature"),
        exists_fn=_temperature_sensor_exists("chamber_target_temperature"),
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
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up Printbuddy sensors."""
    coordinator: PrintbuddyCoordinator = hass.data[DOMAIN][entry.entry_id]
    known_entities: set[tuple[int, str]] = set()

    def add_entities_for_known_printers() -> None:
        entities: list[PrintbuddySensor] = []
        printers = coordinator.data.get("printers", {})
        for printer_id, status in coordinator.data.get("statuses", {}).items():
            raw = status.raw
            printer = printers.get(printer_id)
            for description in SENSOR_DESCRIPTIONS:
                entity_id = (printer_id, description.key)
                if entity_id in known_entities or not description.exists_fn(raw, printer):
                    continue
                known_entities.add(entity_id)
                entities.append(PrintbuddySensor(coordinator, printer_id, description))
        if entities:
            async_add_entities(entities)

    add_entities_for_known_printers()
    entry.async_on_unload(coordinator.async_add_listener(add_entities_for_known_printers))


class PrintbuddySensor(PrintbuddyEntity, SensorEntity):
    """Representation of a Printbuddy sensor."""

    entity_description: PrintbuddySensorDescription

    def __init__(
        self,
        coordinator: PrintbuddyCoordinator,
        printer_id: int,
        description: PrintbuddySensorDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, printer_id, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any | None:
        """Return the current sensor value."""
        if not self.entity_description.exists_fn(self.status, self.printer):
            return None
        return self.entity_description.value_fn(self.status)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return sensor attributes."""
        attrs = super().extra_state_attributes
        if self.entity_description.attributes_fn:
            attrs.update(self.entity_description.attributes_fn(self.status))
        return attrs
