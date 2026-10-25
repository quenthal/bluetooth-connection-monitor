# Bluetooth Connection Monitor

A lightweight Home Assistant custom integration that exposes Home Assistant's existing Bluetooth connection allocations as binary sensors for automations, and optionally the free connection slots of each Bluetooth adapter and proxy.

The integration is completely read-only. It does **not** scan, connect, poll, reserve Bluetooth slots, or generate Bluetooth traffic. It only reads the allocation state already maintained by Home Assistant Core and subscribes to allocation changes.

Requires Home Assistant 2026.8.0 or newer.

## Features

- One binary sensor per monitored Bluetooth address
- The sensor is shown on the device's own page when another integration already has a device with the same Bluetooth address
- Optional free connection-slot sensor per Bluetooth adapter or proxy
- UI configuration flow
- Choose from currently allocated devices or enter an address manually
- Editable device-name suggestion from Home Assistant's Bluetooth discovery cache
- Shows the current Bluetooth proxy/adapter in a compact `connected_via` attribute
- One shared, read-only allocation listener for all configured monitors
- Diagnostics download and a repair issue if Home Assistant's allocation API changes
- English and Finnish UI translations
- HACS compatible

## Sensor state

The binary sensor uses the `connectivity` device class, so the UI shows it as *Connected* / *Disconnected*. It is:

- **On**: the Bluetooth address appears in at least one active connection allocation
- **Off**: the Bluetooth address does not appear in any current allocation
- **Unavailable**: the allocation feed could not be read, or one source returned unexpected data and the address was not found on the readable sources

An allocation is a strong diagnostic signal, but it is not an absolute guarantee that an individual GATT operation will succeed at that exact moment.

### Very brief allocation changes

Normal Bluetooth connection management can occasionally produce very brief allocation changes, including transitions lasting only tens or hundreds of milliseconds. Bluetooth Connection Monitor intentionally exposes these changes without debounce or filtering.

If an automation should ignore short interruptions, use Home Assistant's built-in `for:` option in the trigger or condition, for example:

```yaml
trigger:
  - platform: state
    entity_id: binary_sensor.front_door_lock_connection_allocated
    to: "off"
    for:
      milliseconds: 500
```

This keeps the integration a faithful read-only view of Home Assistant's allocation state while allowing each automation to choose its own stability requirement.

## Attributes

The sensor intentionally exposes only a compact set of attributes:

```yaml
device_address: 00:00:5E:00:53:01
connected_via: esp-bt-front-door (00:00:5E:00:53:A1)
allocation_count: 1
last_allocation_change: 2026-10-25T20:32:11+00:00
```

| Attribute | Description |
| --- | --- |
| `device_address` | Bluetooth address being monitored |
| `connected_via` | Friendly source name and stable source address; multiple sources are separated with `; ` |
| `allocation_count` | Number of current allocation sources; normally `0` or `1` |
| `last_allocation_change` | When this integration last observed the allocation source set change |

After a Home Assistant restart, `last_allocation_change` starts at integration setup because allocation history from before startup is not available.

## Device placement

When another integration already has a device with the monitored Bluetooth address (for example a lock or a sensor integration), the binary sensor is shown on that device, next to the device's own entities. The name entered during setup is then only used as the config entry title.

Otherwise the integration creates its own device with the entered name. If a matching device appears later, for example when the device's own integration is set up afterwards, the sensor moves to it automatically and the integration's own device is removed. If the matching device is removed, the sensor moves back to its own device. The entity ID does not change in either case.

## Connection slots

Choose **Monitor free connection slots of Bluetooth adapters and proxies** in the configuration flow to add one sensor per adapter or proxy that reports connection slots:

```yaml
state: 2
source_address: 00:00:5E:00:53:A1
connection_slots: 3
allocated_addresses:
  - 00:00:5E:00:53:01
```

The sensor is placed on the adapter's or proxy's Bluetooth device when Home Assistant has one; otherwise on a *Bluetooth connection slots* service device. New adapters and proxies get a sensor as soon as they report slots. A sensor is unavailable while its adapter or proxy is gone.

A typical use is an alert when a proxy runs out of free slots:

```yaml
trigger:
  - platform: numeric_state
    entity_id: sensor.esp_bt_front_door_free_connection_slots
    below: 1
    for:
      minutes: 5
```

## Installation with HACS

1. Open HACS.
2. Open **Custom repositories**.
3. Add `https://github.com/quenthal/bluetooth-connection-monitor` as category **Integration**.
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

**Settings -> Devices & services -> Add integration -> Bluetooth Connection Monitor**

Choose one of:

- **Choose an actively allocated Bluetooth device** – lists devices that currently own a connection slot and are not monitored yet
- **Enter a Bluetooth address manually** – accepts `AA:BB:CC:DD:EE:FF`, `AA-BB-CC-DD-EE-FF` and `AABBCCDDEEFF`
- **Monitor free connection slots of Bluetooth adapters and proxies** – can be added once

The detected Bluetooth name is suggested as the Home Assistant device name and remains editable. Each Bluetooth address can be configured once.

## Automation examples

Require an allocation on any source:

```yaml
condition:
  - condition: state
    entity_id: binary_sensor.front_door_lock_connection_allocated
    state: "on"
```

Require one unambiguous allocation through a particular proxy:

```yaml
condition:
  - condition: state
    entity_id: binary_sensor.front_door_lock_connection_allocated
    state: "on"

  - condition: template
    value_template: >
      {{ state_attr(
           'binary_sensor.front_door_lock_connection_allocated',
           'allocation_count'
         ) == 1
         and state_attr(
           'binary_sensor.front_door_lock_connection_allocated',
           'connected_via'
         ) == 'esp-bt-front-door (00:00:5E:00:53:A1)' }}
```

Check how recently the allocation changed:

```jinja
{{ now() - as_datetime(
     state_attr(
       'binary_sensor.front_door_lock_connection_allocated',
       'last_allocation_change'
     )
   ) }}
```

## Read-only operation

Bluetooth Connection Monitor never creates Bluetooth connections or reserves Bluetooth slots. It only:

- reads the current allocation snapshot
- subscribes to allocation and adapter/proxy registration changes
- updates Home Assistant entities

## Troubleshooting

**Settings -> Devices & services -> Bluetooth Connection Monitor -> ⋮ -> Download diagnostics** returns the current allocation snapshot, the device placement of the sensors and the latest allocation error. The file contains Bluetooth addresses; review it before sharing it publicly.

## Compatibility

The integration follows the same Bluetooth allocation information used internally by Home Assistant's Bluetooth connection monitor UI.

The allocation methods are currently internal Home Assistant implementation details rather than part of the documented public Bluetooth integration API. A future Home Assistant release may therefore occasionally require a small compatibility update. The integration validates the expected API during startup; if it is unavailable, it logs a clear error and raises a repair issue under **Settings -> System -> Repairs**.

## Versioning

Bluetooth Connection Monitor uses calendar versioning in the form:

```text
YYYY.M.PATCH
```

For example, `2026.8.0` is the first release made in August 2026. Additional compatible fixes in the same month become `2026.8.1`, `2026.8.2`, and so on.

The calendar version identifies this integration's release date. It does **not** mean that the integration requires the matching Home Assistant release; the minimum Home Assistant version is stated above and in `hacs.json`. Breaking changes are listed in the changelog.

GitHub Release tags use the same version prefixed with `v`, for example `v2026.8.0`.

## Development

```bash
python -m venv .venv
.venv/bin/pip install pytest-homeassistant-custom-component ruff
.venv/bin/pip install $(.venv/bin/python scripts/install_test_deps.py)
.venv/bin/pytest
.venv/bin/ruff check . && .venv/bin/ruff format --check .
```

The tests replace Home Assistant's Bluetooth manager with a small fake, so no Bluetooth hardware is needed. CI runs them against the minimum supported and the latest Home Assistant version.

## License

MIT
