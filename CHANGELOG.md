# Changelog

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
