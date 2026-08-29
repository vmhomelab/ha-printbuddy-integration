"""Tests for the Printbuddy API client."""

from __future__ import annotations

import pytest
from aiohttp import ClientSession, web

from custom_components.printbuddy.api import PrintbuddyApiError, PrintbuddyAuthError, PrintbuddyClient

CAMERA_TOKEN = "camera-token-123"


async def _start_server(app: web.Application) -> tuple[web.AppRunner, str]:
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    server = site._server
    assert server is not None
    port = server.sockets[0].getsockname()[1]
    return runner, f"http://127.0.0.1:{port}"


@pytest.mark.asyncio
async def test_get_printers_and_status() -> None:
    """The client fetches printers and individual status payloads."""
    app = web.Application()

    async def printers(_: web.Request) -> web.Response:
        return web.json_response(
            [
                {
                    "id": 1,
                    "name": "Neptune 4 Pro",
                    "provider": "fluidd",
                    "model": "Elegoo Neptune 4 Pro",
                    "serial_number": "KLIPPER-NEPTUNE",
                    "ip_address": "10.17.10.31",
                    "is_active": True,
                }
            ]
        )

    async def status(_: web.Request) -> web.Response:
        return web.json_response(
            {
                "id": 1,
                "name": "Neptune 4 Pro",
                "connected": True,
                "state": "RUNNING",
                "progress": 42.5,
                "remaining_time": 81,
                "temperatures": {"nozzle": 215, "bed": 60},
            }
        )

    app.router.add_get("/api/v1/printers/", printers)
    app.router.add_get("/api/v1/printers/1/status", status)
    runner, url = await _start_server(app)
    try:
        async with ClientSession() as session:
            client = PrintbuddyClient(session, url)
            printers_result = await client.async_get_printers()
            status_result = await client.async_get_status(1)
    finally:
        await runner.cleanup()

    assert printers_result[0].name == "Neptune 4 Pro"
    assert printers_result[0].provider == "fluidd"
    assert status_result.connected is True
    assert status_result.raw["temperatures"]["nozzle"] == 215


@pytest.mark.asyncio
async def test_printer_camera_configuration_and_stream_token() -> None:
    """The client exposes Printbuddy camera metadata and builds tokenized stream URLs."""
    app = web.Application()
    seen_auth_headers: list[str | None] = []

    async def printers(request: web.Request) -> web.Response:
        seen_auth_headers.append(request.headers.get("Authorization"))
        return web.json_response(
            [
                {
                    "id": 7,
                    "name": "P1S",
                    "provider": "bambu",
                    "model": "P1S",
                    "external_camera_enabled": True,
                    "external_camera_url": "http://cam.local/stream",
                    "external_camera_type": "mjpeg",
                    "ipcam": True,
                }
            ]
        )

    async def stream_token(request: web.Request) -> web.Response:
        seen_auth_headers.append(request.headers.get("Authorization"))
        return web.json_response({"token": CAMERA_TOKEN})

    app.router.add_get("/api/v1/printers/", printers)
    app.router.add_post("/api/v1/printers/camera/stream-token", stream_token)
    runner, url = await _start_server(app)
    try:
        async with ClientSession() as session:
            client = PrintbuddyClient(session, url, "api-token")
            printers_result = await client.async_get_printers()
            token = await client.async_create_camera_stream_token()
    finally:
        await runner.cleanup()

    printer = printers_result[0]
    assert printer.has_camera is True
    assert printer.external_camera_enabled is True
    assert printer.external_camera_type == "mjpeg"
    assert token == CAMERA_TOKEN
    assert client.camera_stream_url(printer.id, token) == f"{url}/api/v1/printers/7/camera/stream?token={CAMERA_TOKEN}"
    assert seen_auth_headers == ["Bearer api-token", "Bearer api-token"]


@pytest.mark.asyncio
async def test_missing_camera_stream_token_is_api_error() -> None:
    """Malformed camera token responses raise a client API error instead of producing broken URLs."""
    app = web.Application()

    async def stream_token(_: web.Request) -> web.Response:
        return web.json_response({"unexpected": "shape"})

    app.router.add_post("/api/v1/printers/camera/stream-token", stream_token)
    runner, url = await _start_server(app)
    try:
        async with ClientSession() as session:
            client = PrintbuddyClient(session, url)
            with pytest.raises(PrintbuddyApiError, match="camera stream token"):
                await client.async_create_camera_stream_token()
    finally:
        await runner.cleanup()


@pytest.mark.asyncio
async def test_auth_error() -> None:
    """401/403 responses become auth errors."""
    app = web.Application()

    async def printers(_: web.Request) -> web.Response:
        return web.json_response({"detail": "unauthorized"}, status=401)

    app.router.add_get("/api/v1/printers/", printers)
    runner, url = await _start_server(app)
    try:
        async with ClientSession() as session:
            client = PrintbuddyClient(session, url, "bad-token")
            with pytest.raises(PrintbuddyAuthError):
                await client.async_get_printers()
    finally:
        await runner.cleanup()


@pytest.mark.asyncio
async def test_camera_token_and_url_builders() -> None:
    """The client creates tokenized camera stream and snapshot URLs."""
    app = web.Application()
    seen_auth: list[str | None] = []

    async def stream_token(request: web.Request) -> web.Response:
        seen_auth.append(request.headers.get("Authorization"))
        return web.json_response({"token": "token with spaces"})

    async def snapshot(request: web.Request) -> web.Response:
        assert request.query["token"] == "token with spaces"
        return web.Response(body=b"jpeg-bytes", content_type="image/jpeg")

    app.router.add_post("/api/v1/printers/camera/stream-token", stream_token)
    app.router.add_get("/api/v1/printers/7/camera/snapshot", snapshot)
    runner, url = await _start_server(app)
    try:
        async with ClientSession() as session:
            client = PrintbuddyClient(session, url, "secret-token")
            stream_url = await client.async_get_camera_stream_url(7, fps=5)
            snapshot_url = await client.async_get_camera_snapshot_url(7)
            snapshot_bytes = await client.async_get_camera_snapshot(7)
    finally:
        await runner.cleanup()

    assert seen_auth == ["Bearer secret-token", "Bearer secret-token", "Bearer secret-token"]
    assert stream_url == f"{url}/api/v1/printers/7/camera/stream?fps=5&token=token+with+spaces"
    assert snapshot_url == f"{url}/api/v1/printers/7/camera/snapshot?token=token+with+spaces"
    assert snapshot_bytes == b"jpeg-bytes"


@pytest.mark.asyncio
async def test_optional_service_status_endpoints() -> None:
    """The client fetches Printbuddy service status endpoints used by HA entities."""
    app = web.Application()

    async def panda_breath(_: web.Request) -> web.Response:
        return web.json_response({"enabled": True, "devices": {"dev1": {"chamber_actual": 42}}})

    async def obico(_: web.Request) -> web.Response:
        return web.json_response({"enabled": True, "is_running": True, "per_printer": {"1": {"class": "safe"}}})

    async def mqtt(_: web.Request) -> web.Response:
        return web.json_response({"enabled": True, "connected": True})

    app.router.add_get("/api/v1/settings/panda-breath/status", panda_breath)
    app.router.add_get("/api/v1/obico/status", obico)
    app.router.add_get("/api/v1/settings/mqtt/status", mqtt)
    runner, url = await _start_server(app)
    try:
        async with ClientSession() as session:
            client = PrintbuddyClient(session, url)
            panda_result = await client.async_get_panda_breath_status()
            obico_result = await client.async_get_obico_status()
            mqtt_result = await client.async_get_mqtt_status()
    finally:
        await runner.cleanup()

    assert panda_result["devices"]["dev1"]["chamber_actual"] == 42
    assert obico_result["per_printer"]["1"]["class"] == "safe"
    assert mqtt_result["connected"] is True


@pytest.mark.asyncio
async def test_service_status_endpoint_must_return_object() -> None:
    """Non-object service status responses are treated as API errors."""
    from custom_components.printbuddy.api import PrintbuddyApiError

    app = web.Application()

    async def not_an_object(_: web.Request) -> web.Response:
        return web.json_response([])

    app.router.add_get("/api/v1/obico/status", not_an_object)
    runner, url = await _start_server(app)
    try:
        async with ClientSession() as session:
            client = PrintbuddyClient(session, url)
            with pytest.raises(PrintbuddyApiError):
                await client.async_get_obico_status()
    finally:
        await runner.cleanup()


def test_normalize_url() -> None:
    """Bare hostnames are normalized to HTTP URLs."""
    assert PrintbuddyClient.normalize_url("printbuddy.local:8000/") == "http://printbuddy.local:8000"
