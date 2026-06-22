"""Camera entities for the Printbuddy integration."""

from __future__ import annotations

from homeassistant.components.camera import Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import PrintbuddyCoordinator
from .entity import PrintbuddyEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up Printbuddy cameras."""
    coordinator: PrintbuddyCoordinator = hass.data[DOMAIN][entry.entry_id]
    known_entities: set[int] = set()

    def add_entities_for_known_printers() -> None:
        entities: list[PrintbuddyCamera] = []
        for printer_id, printer in coordinator.data.get("printers", {}).items():
            status = coordinator.data.get("statuses", {}).get(printer_id)
            status_has_native_camera = bool(status and status.raw.get("ipcam"))
            if printer_id in known_entities or not (printer.has_camera or status_has_native_camera):
                continue
            known_entities.add(printer_id)
            entities.append(PrintbuddyCamera(coordinator, printer_id))
        if entities:
            async_add_entities(entities)

    add_entities_for_known_printers()
    entry.async_on_unload(coordinator.async_add_listener(add_entities_for_known_printers))


class PrintbuddyCamera(PrintbuddyEntity, Camera):
    """Representation of a Printbuddy camera stream."""

    _attr_translation_key = "camera"
    _attr_icon = "mdi:webcam"

    def __init__(self, coordinator: PrintbuddyCoordinator, printer_id: int) -> None:
        """Initialize the camera."""
        Camera.__init__(self)
        PrintbuddyEntity.__init__(self, coordinator, printer_id, "camera")

    @property
    def available(self) -> bool:
        """Return if this camera is available."""
        if not super().available:
            return False
        printer = self.printer
        if printer and printer.external_camera_enabled and printer.external_camera_url:
            return True
        return bool(self.status.get("connected") and self.status.get("ipcam"))

    async def stream_source(self) -> str | None:
        """Return a stream URL for Home Assistant."""
        token = await self.coordinator.client.async_create_camera_stream_token()
        return self.coordinator.client.camera_stream_url(self.printer_id, token)

    async def async_camera_image(self, width: int | None = None, height: int | None = None) -> bytes | None:
        """Return a still image from the Printbuddy camera."""
        return await self.coordinator.client.async_get_camera_snapshot(self.printer_id)
