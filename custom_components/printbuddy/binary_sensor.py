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
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import PrintbuddyCoordinator
from .entity import PrintbuddyEntity, PrintbuddyInstanceEntity
from .telemetry import (
    ai_failure_detected,
    ai_printer_state_exists,
    ai_warning_detected,
    ams_slots,
    binary_sensor_exists,
    hms_has_error,
    obico_enabled,
    obico_running,
    panda_breath_devices,
    panda_breath_is_available,
)


@dataclass(frozen=True, kw_only=True)
class PrintbuddyBinarySensorDescription(BinarySensorEntityDescription):
    """Description for a Printbuddy binary sensor."""

    value_fn: Callable[[dict[str, Any]], bool | None]
    exists_fn: Callable[[dict[str, Any], Any | None], bool] = lambda status, printer: True


@dataclass(frozen=True, kw_only=True)
class PrintbuddyInstanceBinarySensorDescription(BinarySensorEntityDescription):
    """Description for a Printbuddy instance-level binary sensor."""

    value_fn: Callable[[dict[str, Any]], bool | None]
    data_key: str
    exists_fn: Callable[[dict[str, Any]], bool] = lambda payload: bool(payload)


@dataclass(frozen=True, kw_only=True)
class PandaBreathBinarySensorDescription(BinarySensorEntityDescription):
    """Description for a Panda Breath binary sensor."""

    value_key: str


BINARY_SENSOR_DESCRIPTIONS: tuple[PrintbuddyBinarySensorDescription, ...] = (
    PrintbuddyBinarySensorDescription(
        key="connected",
        translation_key="connected",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=lambda status: bool(status.get("connected")),
        exists_fn=lambda status, printer: binary_sensor_exists("connected", status, printer),
    ),
    PrintbuddyBinarySensorDescription(
        key="door_open",
        translation_key="door_open",
        device_class=BinarySensorDeviceClass.DOOR,
        value_fn=lambda status: bool(status.get("door_open")),
        exists_fn=lambda status, printer: binary_sensor_exists("door_open", status, printer),
    ),
    PrintbuddyBinarySensorDescription(
        key="chamber_light",
        translation_key="chamber_light",
        device_class=BinarySensorDeviceClass.LIGHT,
        value_fn=lambda status: bool(status.get("chamber_light")),
        exists_fn=lambda status, printer: binary_sensor_exists("chamber_light", status, printer),
    ),
    PrintbuddyBinarySensorDescription(
        key="sdcard",
        translation_key="sdcard",
        icon="mdi:sd",
        value_fn=lambda status: bool(status.get("sdcard")),
        exists_fn=lambda status, printer: binary_sensor_exists("sdcard", status, printer),
    ),
    PrintbuddyBinarySensorDescription(
        key="store_to_sdcard",
        translation_key="store_to_sdcard",
        icon="mdi:sd",
        value_fn=lambda status: bool(status.get("store_to_sdcard")),
        exists_fn=lambda status, printer: binary_sensor_exists("store_to_sdcard", status, printer),
    ),
    PrintbuddyBinarySensorDescription(
        key="timelapse",
        translation_key="timelapse",
        icon="mdi:camera-timer",
        value_fn=lambda status: bool(status.get("timelapse")),
        exists_fn=lambda status, printer: binary_sensor_exists("timelapse", status, printer),
    ),
    PrintbuddyBinarySensorDescription(
        key="camera_live_view_enabled",
        translation_key="camera_live_view_enabled",
        icon="mdi:cctv",
        value_fn=lambda status: bool(status.get("ipcam")),
        exists_fn=lambda status, _printer: "ipcam" in status and status.get("ipcam") is not None,
    ),
    PrintbuddyBinarySensorDescription(
        key="awaiting_plate_clear",
        translation_key="awaiting_plate_clear",
        icon="mdi:clipboard-alert-outline",
        value_fn=lambda status: bool(status.get("awaiting_plate_clear")),
        exists_fn=lambda status, printer: binary_sensor_exists("awaiting_plate_clear", status, printer),
    ),
    PrintbuddyBinarySensorDescription(
        key="has_error",
        translation_key="has_error",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=hms_has_error,
        exists_fn=lambda status, _printer: "hms_errors" in status,
    ),
    PrintbuddyBinarySensorDescription(
        key="developer_lan_mode",
        translation_key="developer_lan_mode",
        icon="mdi:lan-connect",
        value_fn=lambda status: status.get("developer_mode") if isinstance(status.get("developer_mode"), bool) else None,
        exists_fn=lambda status, _printer: isinstance(status.get("developer_mode"), bool),
    ),
    PrintbuddyBinarySensorDescription(
        key="wired_network",
        translation_key="wired_network",
        icon="mdi:ethernet",
        value_fn=lambda status: bool(status.get("wired_network")),
        exists_fn=lambda status, _printer: "wired_network" in status and status.get("wired_network") is not None,
    ),
    PrintbuddyBinarySensorDescription(
        key="supports_drying",
        translation_key="supports_drying",
        icon="mdi:hair-dryer-outline",
        value_fn=lambda status: bool(status.get("supports_drying")),
        exists_fn=lambda status, _printer: "supports_drying" in status and status.get("supports_drying") is not None,
    ),
    PrintbuddyBinarySensorDescription(
        key="fila_switch_installed",
        translation_key="fila_switch_installed",
        icon="mdi:transit-connection-variant",
        value_fn=lambda status: bool((status.get("fila_switch") or {}).get("installed")) if isinstance(status.get("fila_switch"), dict) else None,
        exists_fn=lambda status, _printer: isinstance(status.get("fila_switch"), dict),
    ),
    PrintbuddyBinarySensorDescription(
        key="ams_exists",
        translation_key="ams_exists",
        icon="mdi:spool",
        value_fn=lambda status: bool(status.get("ams_exists") or status.get("ams")),
        exists_fn=lambda status, _printer: "ams_exists" in status or "ams" in status,
    ),
)

INSTANCE_BINARY_SENSOR_DESCRIPTIONS: tuple[PrintbuddyInstanceBinarySensorDescription, ...] = (
    PrintbuddyInstanceBinarySensorDescription(
        key="mqtt_relay_connected",
        translation_key="mqtt_relay_connected",
        data_key="mqtt",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=lambda mqtt: bool(mqtt.get("connected")),
    ),
    PrintbuddyInstanceBinarySensorDescription(
        key="obico_enabled",
        translation_key="obico_enabled",
        data_key="obico",
        icon="mdi:robot-industrial-outline",
        value_fn=obico_enabled,
    ),
    PrintbuddyInstanceBinarySensorDescription(
        key="obico_service_running",
        translation_key="obico_service_running",
        data_key="obico",
        icon="mdi:robot-industrial",
        value_fn=obico_running,
    ),
    PrintbuddyInstanceBinarySensorDescription(
        key="panda_breath_bridge_connected",
        translation_key="panda_breath_bridge_connected",
        data_key="panda_breath",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=lambda panda: bool(panda.get("connected")) or any(
            panda_breath_is_available(state) for _device_id, state in panda_breath_devices(panda)
        ),
    ),
)

PANDA_BREATH_BINARY_SENSOR_DESCRIPTIONS: tuple[PandaBreathBinarySensorDescription, ...] = (
    PandaBreathBinarySensorDescription(
        key="panda_breath_available",
        translation_key="panda_breath_available",
        value_key="availability",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
    ),
    PandaBreathBinarySensorDescription(
        key="panda_breath_fan",
        translation_key="panda_breath_fan",
        value_key="fan_on",
        icon="mdi:fan",
    ),
    PandaBreathBinarySensorDescription(
        key="panda_breath_power",
        translation_key="panda_breath_power",
        value_key="power_on",
        device_class=BinarySensorDeviceClass.POWER,
    ),
    PandaBreathBinarySensorDescription(
        key="panda_breath_working",
        translation_key="panda_breath_working",
        value_key="work_on",
        icon="mdi:progress-clock",
    ),
    PandaBreathBinarySensorDescription(
        key="panda_breath_drying_running",
        translation_key="panda_breath_drying_running",
        value_key="drying_running",
        icon="mdi:air-filter",
    ),
    PandaBreathBinarySensorDescription(
        key="panda_breath_slicer_priority_mode",
        translation_key="panda_breath_slicer_priority_mode",
        value_key="slicer_priority_mode",
        icon="mdi:priority-high",
    ),
)

AI_BINARY_SENSOR_KEYS = ("ai_failure_detected", "ai_warning_detected")


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up Printbuddy binary sensors."""
    coordinator: PrintbuddyCoordinator = hass.data[DOMAIN][entry.entry_id]
    known_entities: set[tuple[Any, str]] = set()

    def add_entities_for_known_data() -> None:
        entities: list[BinarySensorEntity] = []
        for description in INSTANCE_BINARY_SENSOR_DESCRIPTIONS:
            payload = coordinator.data.get(description.data_key, {})
            entity_id = ("instance", description.key)
            if entity_id in known_entities or not description.exists_fn(payload):
                continue
            known_entities.add(entity_id)
            entities.append(PrintbuddyInstanceBinarySensor(coordinator, description))

        for printer_id, status in coordinator.data.get("statuses", {}).items():
            raw = status.raw
            printer = coordinator.data.get("printers", {}).get(printer_id)
            for description in BINARY_SENSOR_DESCRIPTIONS:
                entity_id = (printer_id, description.key)
                if entity_id in known_entities or not description.exists_fn(raw, printer):
                    continue
                known_entities.add(entity_id)
                entities.append(PrintbuddyBinarySensor(coordinator, printer_id, description))
            if ai_printer_state_exists(coordinator.data.get("obico", {}), printer_id):
                for key in AI_BINARY_SENSOR_KEYS:
                    entity_id = (printer_id, key)
                    if entity_id in known_entities:
                        continue
                    known_entities.add(entity_id)
                    entities.append(PrintbuddyAiBinarySensor(coordinator, printer_id, key))
            for slot_id, _tray in ams_slots(raw):
                for key in ("empty", "loaded"):
                    entity_id = (printer_id, f"ams_slot_{slot_id}_{key}")
                    if entity_id in known_entities:
                        continue
                    known_entities.add(entity_id)
                    entities.append(PrintbuddyAmsSlotBinarySensor(coordinator, printer_id, slot_id, key))

        for device_id, state in panda_breath_devices(coordinator.data.get("panda_breath", {})):
            for description in PANDA_BREATH_BINARY_SENSOR_DESCRIPTIONS:
                entity_id = (device_id, description.key)
                if entity_id in known_entities or description.value_key not in state:
                    continue
                known_entities.add(entity_id)
                entities.append(PandaBreathBinarySensor(coordinator, device_id, description))

        if entities:
            async_add_entities(entities)

    add_entities_for_known_data()
    entry.async_on_unload(coordinator.async_add_listener(add_entities_for_known_data))


class PrintbuddyBinarySensor(PrintbuddyEntity, BinarySensorEntity):
    """Representation of a Printbuddy binary sensor."""

    entity_description: PrintbuddyBinarySensorDescription

    def __init__(self, coordinator: PrintbuddyCoordinator, printer_id: int, description: PrintbuddyBinarySensorDescription) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, printer_id, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        """Return the binary sensor state."""
        return self.entity_description.value_fn(self.status)


class PrintbuddyAiBinarySensor(PrintbuddyEntity, BinarySensorEntity):
    """Representation of a per-printer Obico AI binary sensor."""

    def __init__(self, coordinator: PrintbuddyCoordinator, printer_id: int, key: str) -> None:
        """Initialize the AI binary sensor."""
        super().__init__(coordinator, printer_id, key)
        self.key = key
        self._attr_translation_key = key
        self._attr_icon = "mdi:robot-confused-outline"
        if key == "ai_failure_detected":
            self._attr_device_class = BinarySensorDeviceClass.PROBLEM

    @property
    def is_on(self) -> bool:
        """Return whether AI has detected this class."""
        obico = self.coordinator.data.get("obico", {})
        if self.key == "ai_failure_detected":
            return ai_failure_detected(obico, self.printer_id)
        return ai_warning_detected(obico, self.printer_id)


class PrintbuddyAmsSlotBinarySensor(PrintbuddyEntity, BinarySensorEntity):
    """Representation of one AMS slot boolean state."""

    def __init__(self, coordinator: PrintbuddyCoordinator, printer_id: int, slot_id: str, key: str) -> None:
        """Initialize the AMS slot binary sensor."""
        super().__init__(coordinator, printer_id, f"ams_slot_{slot_id}_{key}")
        self.slot_id = slot_id
        self.key = key
        self._attr_translation_key = f"ams_slot_{key}"
        self._attr_icon = "mdi:spool"

    def _tray(self) -> dict[str, Any] | None:
        return next((tray for current_slot, tray in ams_slots(self.status) if current_slot == self.slot_id), None)

    @property
    def is_on(self) -> bool | None:
        """Return the AMS slot boolean state."""
        tray = self._tray()
        if not tray:
            return None
        state = tray.get("state")
        if self.key == "empty":
            return state == 9 or not bool(tray.get("tray_type") or tray.get("tray_sub_brands"))
        return state == 11 or bool(tray.get("tray_type") or tray.get("tray_sub_brands"))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return AMS slot context."""
        attrs = super().extra_state_attributes
        tray = self._tray()
        if tray:
            attrs.update(
                {
                    "ams_id": tray.get("ams_id"),
                    "global_tray_id": tray.get("global_tray_id"),
                    "material": tray.get("tray_type"),
                    "remaining_percent": tray.get("remain"),
                }
            )
        return attrs


class PrintbuddyInstanceBinarySensor(PrintbuddyInstanceEntity, BinarySensorEntity):
    """Representation of a Printbuddy instance-level binary sensor."""

    entity_description: PrintbuddyInstanceBinarySensorDescription

    def __init__(self, coordinator: PrintbuddyCoordinator, description: PrintbuddyInstanceBinarySensorDescription) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        """Return the binary state."""
        return self.entity_description.value_fn(self.coordinator.data.get(self.entity_description.data_key, {}))


class PandaBreathBinarySensor(PrintbuddyInstanceEntity, BinarySensorEntity):
    """Representation of a Panda Breath binary sensor."""

    entity_description: PandaBreathBinarySensorDescription

    def __init__(self, coordinator: PrintbuddyCoordinator, device_id: str, description: PandaBreathBinarySensorDescription) -> None:
        """Initialize the Panda Breath binary sensor."""
        super().__init__(coordinator, f"{device_id}_{description.key}")
        self.device_id = device_id
        self.entity_description = description

    def _state(self) -> dict[str, Any]:
        return next((state for device_id, state in panda_breath_devices(self.coordinator.data.get("panda_breath", {})) if device_id == self.device_id), {})

    @property
    def is_on(self) -> bool | None:
        """Return the Panda Breath binary state."""
        state = self._state()
        if self.entity_description.value_key == "availability":
            return panda_breath_is_available(state)
        value = state.get(self.entity_description.value_key)
        return value if isinstance(value, bool) else None

    @property
    def available(self) -> bool:
        """Return if Panda Breath state is available."""
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
