"""Tests for deciding which Printbuddy entities should exist in Home Assistant."""

from __future__ import annotations

from custom_components.printbuddy.entity_availability import (
    is_binary_sensor_supported,
    is_present_value,
    supported_temperature_keys,
)


def test_moonraker_neptune_hides_unsupported_bambu_binary_sensors() -> None:
    """Generic Klipper/Moonraker printers should not get Bambu-only sensors from false defaults."""
    printer = {"provider": "fluidd", "model": "Elegoo Neptune 4 Pro"}
    status = {
        "connected": True,
        "door_open": False,
        "chamber_light": False,
        "sdcard": False,
        "timelapse": False,
        "awaiting_plate_clear": False,
    }

    assert is_binary_sensor_supported("connected", status, printer) is True
    assert is_binary_sensor_supported("door_open", status, printer) is False
    assert is_binary_sensor_supported("chamber_light", status, printer) is False
    assert is_binary_sensor_supported("sdcard", status, printer) is False
    assert is_binary_sensor_supported("timelapse", status, printer) is False
    assert is_binary_sensor_supported("awaiting_plate_clear", status, printer) is False


def test_bambu_keeps_supported_false_binary_sensors() -> None:
    """A false value still creates an entity when the printer class really supports that capability."""
    printer = {"provider": "bambu", "model": "P1S"}
    status = {"door_open": False, "chamber_light": False, "timelapse": False, "sdcard": False}

    assert is_binary_sensor_supported("door_open", status, printer) is True
    assert is_binary_sensor_supported("chamber_light", status, printer) is True
    assert is_binary_sensor_supported("timelapse", status, printer) is True
    assert is_binary_sensor_supported("sdcard", status, printer) is True


def test_supported_temperature_keys_are_named_current_and_target_channels() -> None:
    """Only scalar current/target temperature channels become HA sensors, with stable names."""
    status = {
        "temperatures": {
            "nozzle": 215,
            "nozzle_target": 220,
            "bed": 60,
            "bed_target": 65,
            "extruder": {"temperature": 215, "target": 220},
            "heater_bed": {"temperature": 60, "target": 65},
            "nozzle_heating": True,
            "bed_heating": True,
        }
    }

    assert supported_temperature_keys(status) == {
        "nozzle_temperature",
        "nozzle_target_temperature",
        "bed_temperature",
        "bed_target_temperature",
    }


def test_zero_temperature_is_present_but_none_and_nested_objects_are_not() -> None:
    """Do not drop valid zero readings, but ignore absent/object helper values."""
    assert is_present_value(0) is True
    assert is_present_value(0.0) is True
    assert is_present_value(None) is False
    assert is_present_value({"temperature": 42}) is False
    assert is_present_value(True) is False
