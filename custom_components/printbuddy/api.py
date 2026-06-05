"""Async client for the Printbuddy REST API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Self
from urllib.parse import urljoin

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
        )


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

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    async def _request(self, path: str) -> Any:
        try:
            async with self._session.get(
                self._url(path),
                headers=self._headers(),
                timeout=self._timeout,
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
        payload = await self._request(f"/api/v1/printers/{printer_id}/status")
        if not isinstance(payload, dict):
            raise PrintbuddyApiError("Printbuddy status endpoint did not return an object")
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
