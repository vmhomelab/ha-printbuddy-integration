"""Binary sensors for the Printbuddy integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import PrintbuddyCoordinator
from .entity import PrintbuddyEntity
from .entity_availability import is_binary_sensor_supported


@dataclass(frozen=True, kw_only=True)
class PrintbuddyBinarySensorDescription(BinarySensorEntityDescription):
    """Description for a Printbuddy binary sensor."""

    value_fn: Callable[[dict[str, Any]], bool]
    exists_fn: Callable[[dict[str, Any], Any | None], bool] = lambda status, _printer=None: True


BINARY_SENSOR_DESCRIPTIONS: tuple[PrintbuddyBinarySensorDescription, ...] = (
    PrintbuddyBinarySensorDescription(
        key="connected",
        translation_key="connected",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=lambda status: bool(status.get("connected")),
    ),
    PrintbuddyBinarySensorDescription(
        key="door_open",
        translation_key="door_open",
        device_class=BinarySensorDeviceClass.DOOR,
        value_fn=lambda status: bool(status.get("door_open")),
        exists_fn=lambda status, printer=None: is_binary_sensor_supported("door_open", status, printer),
    ),
    PrintbuddyBinarySensorDescription(
        key="chamber_light",
        translation_key="chamber_light",
        device_class=BinarySensorDeviceClass.LIGHT,
        value_fn=lambda status: bool(status.get("chamber_light")),
        exists_fn=lambda status, printer=None: is_binary_sensor_supported("chamber_light", status, printer),
    ),
    PrintbuddyBinarySensorDescription(
        key="sdcard",
        translation_key="sdcard",
        icon="mdi:sd",
        value_fn=lambda status: bool(status.get("sdcard")),
        exists_fn=lambda status, printer=None: is_binary_sensor_supported("sdcard", status, printer),
    ),
    PrintbuddyBinarySensorDescription(
        key="timelapse",
        translation_key="timelapse",
        icon="mdi:camera-timer",
        value_fn=lambda status: bool(status.get("timelapse")),
        exists_fn=lambda status, printer=None: is_binary_sensor_supported("timelapse", status, printer),
    ),
    PrintbuddyBinarySensorDescription(
        key="awaiting_plate_clear",
        translation_key="awaiting_plate_clear",
        icon="mdi:clipboard-alert-outline",
        value_fn=lambda status: bool(status.get("awaiting_plate_clear")),
        exists_fn=lambda status, printer=None: is_binary_sensor_supported("awaiting_plate_clear", status, printer),
    ),
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up Printbuddy binary sensors."""
    coordinator: PrintbuddyCoordinator = hass.data[DOMAIN][entry.entry_id]
    known_entities: set[tuple[int, str]] = set()

    def add_entities_for_known_printers() -> None:
        entities: list[PrintbuddyBinarySensor] = []
        printers = coordinator.data.get("printers", {})
        for printer_id, status in coordinator.data.get("statuses", {}).items():
            raw = status.raw
            printer = printers.get(printer_id)
            for description in BINARY_SENSOR_DESCRIPTIONS:
                entity_id = (printer_id, description.key)
                if entity_id in known_entities or not description.exists_fn(raw, printer):
                    continue
                known_entities.add(entity_id)
                entities.append(PrintbuddyBinarySensor(coordinator, printer_id, description))
        if entities:
            async_add_entities(entities)

    add_entities_for_known_printers()
    entry.async_on_unload(coordinator.async_add_listener(add_entities_for_known_printers))


class PrintbuddyBinarySensor(PrintbuddyEntity, BinarySensorEntity):
    """Representation of a Printbuddy binary sensor."""

    entity_description: PrintbuddyBinarySensorDescription

    def __init__(
        self,
        coordinator: PrintbuddyCoordinator,
        printer_id: int,
        description: PrintbuddyBinarySensorDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, printer_id, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool:
        """Return the binary sensor state."""
        return self.entity_description.value_fn(self.status)
