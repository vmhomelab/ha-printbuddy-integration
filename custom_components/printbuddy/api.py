"""Async client for the Printbuddy REST API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Self
from urllib.parse import urlencode, urljoin

from aiohttp import ClientError, ClientResponseError, ClientSession

from .const import DEFAULT_TIMEOUT


class PrintbuddyError(Exception):
    """Base Printbuddy client error."""


class PrintbuddyAuthError(PrintbuddyError):
    """Printbuddy rejected authentication."""


class PrintbuddyConnectionError(PrintbuddyError):
    """Printbuddy could not be reached."""


class PrintbuddyApiError(PrintbuddyError):
    """Printbuddy returned an unexpected response."""


@dataclass(slots=True)
class PrintbuddyPrinter:
    """A configured Printbuddy printer."""

    id: int
    name: str
    provider: str | None = None
    model: str | None = None
    serial_number: str | None = None
    ip_address: str | None = None
    location: str | None = None
    is_active: bool = True
    external_camera_enabled: bool = False
    external_camera_url: str | None = None
    external_camera_type: str | None = None
    native_camera_enabled: bool = False

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> Self:
        """Create a printer from a Printbuddy API payload."""
        return cls(
            id=int(payload["id"]),
            name=str(payload.get("name") or f"Printer {payload['id']}"),
            provider=payload.get("provider"),
            model=payload.get("model"),
            serial_number=payload.get("serial_number"),
            ip_address=payload.get("ip_address"),
            location=payload.get("location"),
            is_active=bool(payload.get("is_active", True)),
            external_camera_enabled=bool(payload.get("external_camera_enabled", False)),
            external_camera_url=payload.get("external_camera_url"),
            external_camera_type=payload.get("external_camera_type"),
            native_camera_enabled=bool(payload.get("ipcam", False)),
        )

    @property
    def has_camera(self) -> bool:
        """Return whether Printbuddy can expose a camera stream for this printer."""
        return self.native_camera_enabled or (self.external_camera_enabled and bool(self.external_camera_url))


@dataclass(slots=True)
class PrintbuddyStatus:
    """Current Printbuddy printer status."""

    id: int
    name: str
    connected: bool
    raw: dict[str, Any]

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> Self:
        """Create a status object from a Printbuddy API payload."""
        return cls(
            id=int(payload["id"]),
            name=str(payload.get("name") or f"Printer {payload['id']}"),
            connected=bool(payload.get("connected", False)),
            raw=payload,
        )


class PrintbuddyClient:
    """Minimal async Printbuddy API client."""

    def __init__(
        self,
        session: ClientSession,
        url: str,
        token: str | None = None,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        """Initialize the client."""
        self._session = session
        self.base_url = self.normalize_url(url)
        self._token = token.strip() if token else None
        self._timeout = timeout

    @staticmethod
    def normalize_url(url: str) -> str:
        """Normalize a Printbuddy base URL."""
        normalized = url.strip().rstrip("/")
        if not normalized:
            raise PrintbuddyApiError("Printbuddy URL is empty")
        if not normalized.startswith(("http://", "https://")):
            normalized = f"http://{normalized}"
        return normalized

    @property
    def instance_id(self) -> str:
        """Return a stable instance identifier."""
        return self.base_url.lower().replace("https://", "").replace("http://", "").strip("/")

    def _url(self, path: str) -> str:
        return urljoin(f"{self.base_url}/", path.lstrip("/"))

    def _headers(self, *, accept: str = "application/json") -> dict[str, str]:
        headers = {"Accept": accept}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    async def _request(self, path: str, *, method: str = "GET") -> Any:
        try:
            async with self._session.request(
                method,
                self._url(path),
                headers=self._headers(),
                timeout=float(self._timeout),
            ) as response:
                if response.status in (401, 403):
                    raise PrintbuddyAuthError("Printbuddy authentication failed")
                response.raise_for_status()
                return await response.json()
        except PrintbuddyAuthError:
            raise
        except ClientResponseError as err:
            raise PrintbuddyApiError(f"Printbuddy API returned HTTP {err.status}") from err
        except ClientError as err:
            raise PrintbuddyConnectionError("Could not connect to Printbuddy") from err
        except TimeoutError as err:
            raise PrintbuddyConnectionError("Timed out connecting to Printbuddy") from err

    async def _request_object(self, path: str, *, error_label: str) -> dict[str, Any]:
        """Return a JSON object from a Printbuddy endpoint."""
        payload = await self._request(path)
        if not isinstance(payload, dict):
            raise PrintbuddyApiError(f"{error_label} endpoint did not return an object")
        return payload

    async def _request_bytes(self, url: str) -> bytes:
        try:
            async with self._session.get(
                url,
                headers=self._headers(accept="image/*,*/*"),
                timeout=float(self._timeout),
            ) as response:
                if response.status in (401, 403):
                    raise PrintbuddyAuthError("Printbuddy authentication failed")
                response.raise_for_status()
                return await response.read()
        except PrintbuddyAuthError:
            raise
        except ClientResponseError as err:
            raise PrintbuddyApiError(f"Printbuddy API returned HTTP {err.status}") from err
        except ClientError as err:
            raise PrintbuddyConnectionError("Could not connect to Printbuddy") from err
        except TimeoutError as err:
            raise PrintbuddyConnectionError("Timed out connecting to Printbuddy") from err

    async def async_check_connection(self) -> None:
        """Check that the Printbuddy API is reachable and authenticated."""
        await self.async_get_printers()

    async def async_get_printers(self) -> list[PrintbuddyPrinter]:
        """Return all printers configured in Printbuddy."""
        payload = await self._request("/api/v1/printers/")
        if not isinstance(payload, list):
            raise PrintbuddyApiError("Printbuddy printers endpoint did not return a list")
        return [PrintbuddyPrinter.from_api(item) for item in payload if isinstance(item, dict)]

    async def async_get_status(self, printer_id: int) -> PrintbuddyStatus:
        """Return the current status for one Printbuddy printer."""
        payload = await self._request_object(f"/api/v1/printers/{printer_id}/status", error_label="Printbuddy status")
        return PrintbuddyStatus.from_api(payload)

    async def async_get_all_statuses(self) -> dict[int, PrintbuddyStatus]:
        """Return all configured printers with their status payloads."""
        printers = await self.async_get_printers()
        statuses: dict[int, PrintbuddyStatus] = {}
        for printer in printers:
            try:
                statuses[printer.id] = await self.async_get_status(printer.id)
            except PrintbuddyError:
                statuses[printer.id] = PrintbuddyStatus(
                    id=printer.id,
                    name=printer.name,
                    connected=False,
                    raw={
                        "id": printer.id,
                        "name": printer.name,
                        "connected": False,
                    },
                )
        return statuses

    async def async_get_mqtt_status(self) -> dict[str, Any]:
        """Return Printbuddy MQTT relay status."""
        return await self._request_object("/api/v1/settings/mqtt/status", error_label="Printbuddy MQTT status")

    async def async_get_panda_breath_status(self) -> dict[str, Any]:
        """Return Printbuddy Panda Breath bridge status."""
        return await self._request_object(
            "/api/v1/settings/panda-breath/status", error_label="Printbuddy Panda Breath status"
        )

    async def async_get_obico_status(self) -> dict[str, Any]:
        """Return Printbuddy Obico AI detection status."""
        return await self._request_object("/api/v1/obico/status", error_label="Printbuddy Obico status")

    async def async_create_camera_stream_token(self) -> str:
        """Create a Printbuddy camera stream token for image/stream URLs."""
        payload = await self._request("/api/v1/printers/camera/stream-token", method="POST")
        if not isinstance(payload, dict) or not isinstance(payload.get("token"), str) or not payload["token"]:
            raise PrintbuddyApiError("Printbuddy camera stream token endpoint did not return a token")
        return payload["token"]

    def camera_stream_url(self, printer_id: int, token: str, *, fps: int | None = None) -> str:
        """Return a tokenized Printbuddy MJPEG camera stream URL."""
        query_params: dict[str, str | int] = {}
        if fps is not None:
            query_params["fps"] = fps
        query_params["token"] = token
        query = urlencode(query_params)
        return f"{self._url(f'/api/v1/printers/{printer_id}/camera/stream')}?{query}"

    def camera_snapshot_url(self, printer_id: int, token: str) -> str:
        """Return a tokenized Printbuddy camera snapshot URL."""
        query = urlencode({"token": token})
        return f"{self._url(f'/api/v1/printers/{printer_id}/camera/snapshot')}?{query}"

    async def async_get_camera_stream_url(self, printer_id: int, fps: int = 10) -> str:
        """Return a tokenized camera stream URL for Home Assistant."""
        token = await self.async_create_camera_stream_token()
        return self.camera_stream_url(printer_id, token, fps=fps)

    async def async_get_camera_snapshot_url(self, printer_id: int) -> str:
        """Return a tokenized camera snapshot URL for Home Assistant."""
        token = await self.async_create_camera_stream_token()
        return self.camera_snapshot_url(printer_id, token)

    async def async_get_camera_snapshot(self, printer_id: int) -> bytes:
        """Fetch one JPEG snapshot through Printbuddy's camera endpoint."""
        return await self._request_bytes(await self.async_get_camera_snapshot_url(printer_id))
