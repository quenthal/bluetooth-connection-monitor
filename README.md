# Bluetooth Connection Monitor

A lightweight Home Assistant custom integration that exposes Home Assistant's existing Bluetooth connection-slot allocations as binary sensors.

It does **not** scan, connect, poll, reserve slots, or send Bluetooth traffic. It only reads the current allocation snapshot and subscribes to allocation changes already maintained by Home Assistant Core.

## Features

- One binary sensor per monitored Bluetooth address
- UI configuration flow
- Choose from currently allocated devices or enter an address manually
- Editable name suggestion from Home Assistant's Bluetooth discovery cache
- Shows the current Bluetooth proxy/adapter source as attributes
- Supports the uncommon case where an address appears allocated on multiple sources
- One shared, read-only allocation listener for all configured monitors
- English and Finnish UI translations
- HACS-compatible repository layout

## Sensor meaning

The binary sensor is:

- **On**: the Bluetooth address appears in at least one source's active connection-slot allocation
- **Off**: the address does not appear in any current allocation
- **Unavailable**: the allocation feed could not be initialized or an unexpected allocation payload was received

An allocation is a strong diagnostic signal, but it is not an absolute proof that a GATT operation will succeed at that exact moment.

## Attributes

Example:

```yaml
device_address: 78:9C:85:0B:73:FD
allocation_count: 1
sources:
  - A8:42:E3:91:72:C2
source_names:
  - esp-bt-etuovi
source_count: 1
connected_via:
  - address: A8:42:E3:91:72:C2
    name: esp-bt-etuovi
connected_via_address: A8:42:E3:91:72:C2
connected_via_name: esp-bt-etuovi
total_slots: 1
total_free_slots: 0
allocations:
  - source: A8:42:E3:91:72:C2
    source_name: esp-bt-etuovi
    slots: 1
    free: 0
```

`connected_via_address` and `connected_via_name` are populated only when exactly one allocation source matches. The full `connected_via` and `sources` lists are always available.

## Installation with HACS

1. Open HACS.
2. Open the menu and choose **Custom repositories**.
3. Add this GitHub repository as category **Integration**.
4. Install **Bluetooth Connection Monitor**.
5. Restart Home Assistant.

## Manual installation

Copy:

```text
custom_components/bluetooth_connection_monitor
```

into:

```text
/config/custom_components/bluetooth_connection_monitor
```

Restart Home Assistant.

## Configuration

Open:

**Settings → Devices & services → Add integration → Bluetooth Connection Monitor**

Choose either:

- **Choose an actively allocated Bluetooth device**
- **Enter a Bluetooth address manually**

The detected Bluetooth name is suggested as the Home Assistant device name and remains editable. Each Bluetooth address can be configured once.

## Automation examples

Require an allocation on any source:

```yaml
condition:
  - condition: state
    entity_id: binary_sensor.etuovi_connection_allocated
    state: "on"
```

Require that a particular proxy is one of the current allocation sources:

```yaml
condition:
  - condition: template
    value_template: >
      {{ 'A8:42:E3:91:72:C2' in
         (state_attr('binary_sensor.etuovi_connection_allocated', 'sources') or []) }}
```

Require an unambiguous allocation on exactly one expected proxy:

```yaml
condition:
  - condition: template
    value_template: >
      {{ state_attr(
           'binary_sensor.etuovi_connection_allocated',
           'connected_via_address'
         ) == 'A8:42:E3:91:72:C2' }}
```

## Read-only behavior

The integration only calls Home Assistant's current-allocation reader and registers a callback for allocation changes. It does not request a scanner, connect to a device, reserve a slot, or modify Bluetooth manager state.

## Compatibility note

Home Assistant exposes allocation subscriptions through its Bluetooth manager and WebSocket API. This integration follows the same manager snapshot-and-callback path used by Home Assistant's Bluetooth connection monitor UI.

The allocation methods are internal implementation details rather than part of Home Assistant's documented public Bluetooth integration API. A future Home Assistant release may therefore require a small compatibility update. The integration checks the expected API during setup and logs a clear error instead of silently failing.

## Repository publishing

Before publishing, replace `YOUR_GITHUB_USERNAME` in:

```text
custom_components/bluetooth_connection_monitor/manifest.json
```

with the GitHub account or organization that owns the repository. See [PUBLISHING.md](PUBLISHING.md).

## License

MIT
