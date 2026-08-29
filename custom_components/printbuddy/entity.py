"""Shared entity helpers for Printbuddy."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN
from .coordinator import PrintbuddyCoordinator


def coordinator_instance_id(coordinator: PrintbuddyCoordinator) -> str:
    """Return the stable instance device identifier suffix."""
    return coordinator.client.instance_id


class PrintbuddyInstanceEntity(CoordinatorEntity[PrintbuddyCoordinator]):
    """Base class for Printbuddy instance-level entities."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(self, coordinator: PrintbuddyCoordinator, key: str) -> None:
        """Initialize an instance-level entity."""
        super().__init__(coordinator)
        self.entity_key = key
        self._attr_unique_id = f"{coordinator.client.instance_id}_{key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return Home Assistant device info for the Printbuddy instance."""
        return DeviceInfo(
            identifiers={(DOMAIN, coordinator_instance_id(self.coordinator))},
            name="Printbuddy",
            manufacturer="Printbuddy",
            configuration_url=self.coordinator.client.base_url,
        )


class PrintbuddyEntity(CoordinatorEntity[PrintbuddyCoordinator]):
    """Base class for Printbuddy entities."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(self, coordinator: PrintbuddyCoordinator, printer_id: int, key: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.printer_id = printer_id
        self.entity_key = key
        self._attr_unique_id = f"{coordinator.client.instance_id}_{printer_id}_{key}"

    @property
    def printer(self) -> Any | None:
        """Return the Printbuddy printer object."""
        return self.coordinator.data.get("printers", {}).get(self.printer_id)

    @property
    def status(self) -> dict[str, Any]:
        """Return the raw Printbuddy status payload."""
        status = self.coordinator.data.get("statuses", {}).get(self.printer_id)
        return status.raw if status else {}

    @property
    def available(self) -> bool:
        """Return if entity data is available."""
        return super().available and self.printer_id in self.coordinator.data.get("printers", {})

    @property
    def device_info(self) -> DeviceInfo:
        """Return Home Assistant device info for this printer."""
        printer = self.printer
        name = printer.name if printer else f"Printbuddy Printer {self.printer_id}"
        model = printer.model if printer else None
        provider = (printer.provider if printer else None) or "Printbuddy"
        serial = printer.serial_number if printer else None
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self.coordinator.client.instance_id}_{self.printer_id}")},
            name=name,
            manufacturer=provider.title(),
            model=model,
            serial_number=serial,
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return common attributes."""
        printer = self.printer
        attrs: dict[str, Any] = {"printer_id": self.printer_id}
        if printer:
            attrs.update(
                {
                    "provider": printer.provider,
                    "model": printer.model,
                    "ip_address": printer.ip_address,
                    "location": printer.location,
                    "is_active": printer.is_active,
                    "external_camera_enabled": printer.external_camera_enabled,
                    "external_camera_type": printer.external_camera_type,
                    "native_camera_enabled": printer.native_camera_enabled,
                }
            )
        return attrs
