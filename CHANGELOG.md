# Changelog

## 2026.10.2

### Added

- Choose the device a sensor is shown on, while adding a monitor or later in its options. Connection-slot sensors can be placed per adapter or proxy. A chosen device is kept across restarts.
- Repair issue when a chosen device has been removed; the sensor then falls back to automatic placement.
- Diagnostics include the chosen devices.

### Fixed

- When several integrations register the same Bluetooth address, the device of a Bluetooth integration is preferred. Previously a Yale lock's sensor could end up on the device of the Yale cloud integration instead of the Yale Bluetooth integration.

## 2026.10.1

### Fixed

- `last_allocation_change` and `allocated_addresses` are no longer stored in the recorder database. They changed with every allocation and created a new attribute row each time.
- The integration's own devices no longer show "Bluetooth" as the manufacturer.
- Free connection-slot sensors on the *Bluetooth connection slots* device are named after the adapter or proxy only, for example *Bluetooth connection slots proxy-a*, instead of repeating "free connection slots". Existing entity IDs are kept.
- An unreadable scanner name list is logged at debug level instead of as an error on every state update.

## 2026.10.0

Requires Home Assistant 2026.8.0 or newer.

### Breaking changes

- The binary sensor is now shown on the existing device of another integration that has the same Bluetooth address. The integration's own device is then removed. Entity IDs, history and automations are not affected, but dashboards or automations that target the old *device* need to be pointed at the new one.
- The binary sensor now uses the `connectivity` device class, so the UI shows *Connected* / *Disconnected* instead of *On* / *Off*. The state values stay `on` / `off`.
- Icons are defined in `icons.json`; a customized icon set on the entity keeps working.

### Added

- Optional free connection-slot sensors per Bluetooth adapter and proxy.
- Diagnostics download with the allocation snapshot, sensor placement and latest error.
- Repair issue when Home Assistant's allocation API is incompatible.
- Manual address entry accepts `AA-BB-CC-DD-EE-FF` and `AABBCCDDEEFF`.
- Test suite and Ruff linting in CI, run against the minimum and latest Home Assistant.

### Fixed

- A sensor no longer stays *on* after its Bluetooth proxy disappears on Home Assistant versions that do not send an allocation update for a removed proxy.
- One source with unexpected allocation data no longer makes every sensor unavailable; sensors stay available when their state is still known.
- A temporary error while starting the allocation listener is retried instead of failing permanently.
- Already monitored devices are no longer offered in the device list of the configuration flow.
- Source names in the device list and in `connected_via` are now formatted the same way.

## 2026.8.0

First calendar-versioned release.

- Exposes Home Assistant Bluetooth connection allocations as binary sensors.
- Supports selection from currently allocated devices and manual Bluetooth address entry.
- Uses a shared read-only allocation listener and does not generate Bluetooth traffic.
- Exposes compact `device_address`, `connected_via`, `allocation_count`, and `last_allocation_change` attributes.
- Documents that very brief allocation transitions are intentionally not filtered; automations can use Home Assistant's built-in `for:` handling.
- Includes English and Finnish custom-integration translations.
- Includes local brand assets and HACS-compatible repository metadata.
- Adds startup compatibility checks for Home Assistant's internal allocation API.
