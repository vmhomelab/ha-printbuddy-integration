# Printbuddy Home Assistant Integration

<p align="center">
  <img src="logo.png" alt="Printbuddy" width="180">
</p>

Custom Home Assistant integration for [Printbuddy](https://github.com/vmhomelab/Printbuddy).

It connects to a Printbuddy instance and exposes every configured Printbuddy printer as its own Home Assistant device with status, nozzle/bed/chamber temperatures, progress, fan, network, print-job sensors, loaded-spool telemetry, AMS/filament details, HMS/problem state, Obico AI detection state, Panda Breath telemetry, and a camera entity when Printbuddy has either a native printer camera or an assigned external camera.

## Features

- UI config flow; no YAML required.
- One Home Assistant device per Printbuddy printer.
- Discovers printers from `GET /api/v1/printers/`.
- Polls each printer via `GET /api/v1/printers/{id}/status`.
- Polls optional Printbuddy service health from MQTT relay, Panda Breath, and Obico status endpoints.
- Exposes Printbuddy camera streams through `GET /api/v1/printers/{id}/camera/stream` using Printbuddy stream tokens.
- Supports unauthenticated Printbuddy instances and Bearer/API-token protected instances.
- Creates stable entity unique IDs from the Printbuddy instance URL and printer ID.
- Creates camera entities for printers with a native Printbuddy camera or an assigned external camera.

## Entities

For each printer the integration can create:

- Connection binary sensor
- Door open binary sensor, when the printer/provider reports a real door capability
- Chamber light binary sensor, when supported
- Printing status sensor
- Current print sensor
- Loaded spool / currently loaded filament sensor, when Printbuddy reports virtual-tray or AMS loaded-slot data
- Nozzle temperature sensor
- Nozzle target temperature sensor
- Right nozzle temperature and target sensors, when reported
- Bed temperature sensor
- Bed target temperature sensor
- Chamber temperature and target sensors, when reported
- Print progress sensor
- Remaining time sensor
- Current layer sensor
- Total layers sensor
- Wi-Fi signal sensor
- Fan speed sensors for part cooling, auxiliary, chamber/exhaust, and heatbreak fans, when reported
- HMS error count, highest severity, last error, and problem binary sensors
- Firmware version, stage, speed level, airduct mode, current plate/archive, printable objects, active extruder, nozzle rack, and FilaSwitch telemetry when reported
- AMS unit, tray, slot, humidity, temperature, drying, firmware, serial, material, and loaded/empty telemetry when reported
- Obico/AI class, score, frame count, warning, and failure sensors when Printbuddy reports per-printer AI detection data
- Camera entity when Printbuddy reports a native camera or an assigned external camera for the printer

For the Printbuddy instance the integration can create:

- MQTT relay connection binary sensor
- Obico enabled/running binary sensors and configuration/status sensors
- Panda Breath bridge connection binary sensor
- Panda Breath device sensors for chamber/bed/filter/heater/drying/slicer temperatures, mode, drying state, firmware, bound printer, and availability/power/fan/working flags

## Installation

### HACS custom repository

1. In HACS, add this repository as a custom repository of type `Integration`.
2. Install **Printbuddy**.
3. Restart Home Assistant.
4. Go to **Settings → Devices & services → Add integration → Printbuddy**.

### Manual

Copy `custom_components/printbuddy` into your Home Assistant `custom_components` directory, restart Home Assistant, then add the integration from the UI.

## Configuration

The setup flow asks for:

- **Printbuddy URL**: for example `http://10.17.200.5:8000` or the add-on URL if reachable from Home Assistant.
- **API token**: optional. If Printbuddy authentication is enabled, provide a token accepted by Printbuddy's API as a Bearer token.
- **Scan interval**: polling interval in seconds. Default: 30 seconds.

## Notes

This integration is read-only in the first version. It intentionally does not expose printer or Panda Breath control buttons yet. That keeps the initial release safe and focused on reliable telemetry.

## Development

```bash
python -m pip install -r requirements-dev.txt
ruff check custom_components tests
pytest
```
