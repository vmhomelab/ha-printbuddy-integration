"""Tests for Printbuddy telemetry entity discovery helpers."""

from __future__ import annotations

from types import SimpleNamespace

from custom_components.printbuddy.api import PrintbuddyPrinter
from custom_components.printbuddy.telemetry import (
    ai_failure_detected,
    ai_printer_state_exists,
    ai_printer_value,
    ams_slots,
    binary_sensor_exists,
    camera_exists,
    hms_error_count,
    hms_has_error,
    loaded_spool_attributes,
    loaded_spool_summary,
    obico_enabled,
    obico_running,
    panda_breath_devices,
    panda_breath_state_value,
    scalar_value,
    temperature_exists,
    temperature_value,
)


def test_temperature_helpers_use_nested_values_and_aliases_without_raw_objects() -> None:
    """Temperature helpers expose scalar values and ignore raw Moonraker helper objects."""
    status = {
        "temperatures": {
            "nozzle": 215,
            "nozzle_target": 220,
            "extruder": {"temperature": 215},
        },
        "bed_temp": 60,
        "heater_bed": {"temperature": 60},
        "chamber_temperature": 0,
    }

    assert temperature_value(status, "nozzle") == 215
    assert temperature_value(status, "nozzle_target") == 220
    assert temperature_value(status, "bed") == 60
    assert temperature_value(status, "chamber") == 0
    assert temperature_value(status, "extruder") is None
    assert temperature_exists(status, "bed") is True
    assert temperature_exists(status, "extruder") is False


def test_loaded_spool_summary_prefers_virtual_tray_loaded_spool() -> None:
    """Single-spool/local loaded assignments are exposed from Printbuddy vt_tray data."""
    status = {
        "vt_tray": [
            {
                "id": 254,
                "tray_type": "PETG",
                "tray_sub_brands": "PETG HF",
                "tray_color": "FFFFFFFF",
                "tray_info_idx": "GFU99",
                "remain": 74,
            }
        ]
    }

    assert loaded_spool_summary(status) == "PETG HF (PETG)"
    assert loaded_spool_attributes(status) == {
        "source": "virtual_tray",
        "slot": 254,
        "material": "PETG",
        "name": "PETG HF",
        "color": "FFFFFFFF",
        "filament_id": "GFU99",
        "remaining_percent": 74,
    }


def test_loaded_spool_summary_uses_tray_now_for_ams() -> None:
    """AMS printers expose the loaded slot selected by tray_now."""
    status = {
        "tray_now": 1,
        "ams": [
            {
                "id": 0,
                "tray": [
                    {"id": 0, "tray_type": "PLA", "tray_sub_brands": "PLA Basic"},
                    {"id": 1, "tray_type": "ABS", "tray_sub_brands": "ABS-GF"},
                ],
            }
        ],
    }

    assert loaded_spool_summary(status) == "ABS-GF (ABS)"
    assert loaded_spool_attributes(status)["source"] == "ams"
    assert loaded_spool_attributes(status)["slot"] == 1


def test_camera_exists_from_external_camera_or_native_status() -> None:
    """Camera entities are created for configured external cameras or native camera status."""
    external = PrintbuddyPrinter.from_api(
        {
            "id": 1,
            "name": "Neptune",
            "provider": "fluidd",
            "external_camera_enabled": True,
            "external_camera_url": "http://cam.local/stream",
            "external_camera_type": "mjpeg",
        }
    )
    native = PrintbuddyPrinter.from_api({"id": 2, "name": "P1S", "provider": "bambu"})
    no_camera = PrintbuddyPrinter.from_api({"id": 3, "name": "Offline", "provider": "fluidd"})

    assert camera_exists(external, {}) is True
    assert camera_exists(native, {"ipcam": True}) is True
    assert camera_exists(no_camera, {"ipcam": False}) is False


def test_binary_sensor_exists_gates_bambu_only_false_defaults() -> None:
    """False Bambu-only placeholders do not create unsupported entities for Moonraker printers."""
    fluidd = SimpleNamespace(provider="fluidd")
    bambu = SimpleNamespace(provider="bambu")

    status = {
        "door_open": False,
        "chamber_light": False,
        "timelapse": False,
        "awaiting_plate_clear": False,
        "sdcard": False,
    }

    assert binary_sensor_exists("connected", status, fluidd) is True
    assert binary_sensor_exists("door_open", status, fluidd) is False
    assert binary_sensor_exists("chamber_light", status, fluidd) is False
    assert binary_sensor_exists("timelapse", status, fluidd) is False
    assert binary_sensor_exists("awaiting_plate_clear", status, fluidd) is True
    assert binary_sensor_exists("door_open", status, bambu) is True
    assert binary_sensor_exists("chamber_light", status, bambu) is True
    assert binary_sensor_exists("timelapse", status, bambu) is True


def test_zero_is_scalar_but_booleans_and_mappings_are_not() -> None:
    """Dynamic entity discovery treats 0 as present but ignores helper objects."""
    assert scalar_value(0) == 0
    assert scalar_value(0.0) == 0.0
    assert scalar_value("PLA") == "PLA"
    assert scalar_value(False) is None
    assert scalar_value({"temperature": 215}) is None
    assert scalar_value([215]) is None


def test_panda_breath_devices_support_native_and_singleton_payloads() -> None:
    """Panda Breath helpers expose native multi-device and legacy singleton state."""
    native = {
        "devices": {
            "9C139E456884": {
                "device_id": "9C139E456884",
                "availability": "online",
                "chamber_actual": 43.5,
                "target_temp": 45,
            }
        }
    }
    singleton = {"state": {"availability": "online", "chamber_actual": 41}}

    assert panda_breath_devices(native) == [("9C139E456884", native["devices"]["9C139E456884"])]
    assert panda_breath_devices(singleton) == [("panda_breath", singleton["state"])]
    assert panda_breath_state_value(native["devices"]["9C139E456884"], "chamber_actual") == 43.5
    assert panda_breath_state_value(native["devices"]["9C139E456884"], "chamber_target") == 45


def test_obico_helpers_expose_global_and_per_printer_ai_state() -> None:
    """Obico helpers normalize global service state and per-printer AI classification."""
    obico = {
        "enabled": True,
        "is_running": True,
        "per_printer": {"7": {"class": "failure", "score": 0.91, "frame_count": 12}},
    }

    assert obico_enabled(obico) is True
    assert obico_running(obico) is True
    assert ai_printer_state_exists(obico, 7) is True
    assert ai_printer_value(obico, 7, "class") == "failure"
    assert ai_printer_value(obico, 7, "score") == 0.91
    assert ai_failure_detected(obico, 7) is True
    assert ai_printer_state_exists(obico, 8) is False


def test_hms_and_ams_helpers_summarize_nested_printer_telemetry() -> None:
    """Error and AMS helpers expose automation-friendly values without entity-specific code."""
    status = {
        "hms_errors": [{"code": "0300_0A00", "severity": 2, "module": 3}],
        "ams": [
            {
                "id": 0,
                "humidity": 33,
                "temp": 26.5,
                "serial_number": "AMS123",
                "tray": [
                    {"id": 0, "tray_type": "PLA", "tray_sub_brands": "PLA Basic", "remain": 70, "state": 11},
                    {"id": 1, "state": 9},
                ],
            }
        ],
    }

    assert hms_error_count(status) == 1
    assert hms_has_error(status) is True
    slots = ams_slots(status)
    assert slots[0][0] == "0_0"
    assert slots[0][1]["tray_type"] == "PLA"
    assert slots[0][1]["ams_serial_number"] == "AMS123"
    assert slots[0][1]["global_tray_id"] == 0
