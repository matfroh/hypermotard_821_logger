# Hypermotard 821 ECU/BBS Logger

This small project logs ECU and BBS data from a Ducati Hypermotard 821.

## Prerequisites

- Android device
- Reliable Bluetooth ELM327 adapter
  - Recommended: Lonelec
- Pydroid 3
- Pydroid repository plugin
- Pydroid permission plugin
- Location enabled

> To use this project on iOS, a BLE-compatible ELM327 adapter is required.

## Project Goal

The end goal is to log motorcycle data on an Android device for later analysis and potential virtual dyno visualization.

The streamlined, high-speed `DucatiFastLoggerApp` script for Pydroid 3 polls only the seven verified Engine ECU (`7E0`) channels required for both virtual road dyno and AFR/closed-loop fuel-trim analysis.

## Logged Data

Output filename:

```text
hypermotard_fastlog_YYYYMMDD_HHMMSS.csv
