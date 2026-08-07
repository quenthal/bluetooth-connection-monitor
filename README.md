# Bluetooth Connection Monitor

A lightweight Home Assistant custom integration that exposes Home Assistant's existing Bluetooth connection allocations as binary sensors for automations.

The integration is completely read-only. It does **not** scan, connect, poll, reserve Bluetooth slots, or generate Bluetooth traffic. It only reads the allocation state already maintained by Home Assistant Core and subscribes to allocation changes.

## Features

- One binary sensor per monitored Bluetooth address
- UI configuration flow
- Choose from currently allocated devices or enter an address manually
- Editable device-name suggestion from Home Assistant's Bluetooth discovery cache
- Shows the current Bluetooth proxy/adapter in a compact `connected_via` attribute
- One shared, read-only allocation listener for all configured monitors
- English and Finnish UI translations
- HACS compatible

## Sensor state

The binary sensor is:

- **On**: the Bluetooth address appears in at least one active connection allocation
- **Off**: the Bluetooth address does not appear in any current allocation
- **Unavailable**: the allocation feed could not be initialized or returned an unexpected payload

An allocation is a strong diagnostic signal, but it is not an absolute guarantee that an individual GATT operation will succeed at that exact moment.

### Very brief allocation changes

Normal Bluetooth connection management can occasionally produce very brief allocation changes, including transitions lasting only tens or hundreds of milliseconds. Bluetooth Connection Monitor intentionally exposes these changes without debounce or filtering.

If an automation should ignore short interruptions, use Home Assistant's built-in `for:` option in the trigger or condition, for example:

```yaml
trigger:
  - platform: state
    entity_id: binary_sensor.etuovi_connection_allocated
    to: "off"
    for:
      milliseconds: 500
```

This keeps the integration a faithful read-only view of Home Assistant's allocation state while allowing each automation to choose its own stability requirement.

## Attributes

The sensor intentionally exposes only a compact set of attributes:

```yaml
device_address: 78:9C:85:0B:73:FD
connected_via: esp-bt-etuovi (A8:42:E3:91:72:C2)
allocation_count: 1
last_allocation_change: 2026-08-06T20:32:11+00:00
```

| Attribute | Description |
| --- | --- |
| `device_address` | Bluetooth address being monitored |
| `connected_via` | Friendly source name and stable source address; multiple sources are separated with `; ` |
| `allocation_count` | Number of current allocation sources; normally `0` or `1` |
| `last_allocation_change` | When this integration last observed the allocation source set change |

After a Home Assistant restart, `last_allocation_change` starts at integration setup because allocation history from before startup is not available.

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

Require one unambiguous allocation through a particular proxy:

```yaml
condition:
  - condition: state
    entity_id: binary_sensor.etuovi_connection_allocated
    state: "on"

  - condition: template
    value_template: >
      {{ state_attr(
           'binary_sensor.etuovi_connection_allocated',
           'allocation_count'
         ) == 1
         and state_attr(
           'binary_sensor.etuovi_connection_allocated',
           'connected_via'
         ) == 'esp-bt-etuovi (A8:42:E3:91:72:C2)' }}
```

Check how recently the allocation changed:

```jinja
{{ now() - as_datetime(
     state_attr(
       'binary_sensor.etuovi_connection_allocated',
       'last_allocation_change'
     )
   ) }}
```

## Read-only operation

Bluetooth Connection Monitor never creates Bluetooth connections or reserves Bluetooth slots. It only:

- reads the current allocation snapshot
- subscribes to allocation changes
- updates Home Assistant entities

## Compatibility

The integration follows the same Bluetooth allocation information used internally by Home Assistant's Bluetooth connection monitor UI.

The allocation methods are currently internal Home Assistant implementation details rather than part of the documented public Bluetooth integration API. A future Home Assistant release may therefore occasionally require a small compatibility update. The integration validates the expected API during startup and logs a clear error if it is unavailable.

## Versioning

Bluetooth Connection Monitor uses calendar versioning in the form:

```text
YYYY.M.PATCH
```

For example, `2026.8.0` is the first release made in August 2026. Additional compatible fixes in the same month become `2026.8.1`, `2026.8.2`, and so on.

The calendar version identifies this integration's release date. It does **not** mean that the integration requires the matching Home Assistant release unless a minimum Home Assistant version is explicitly documented.

GitHub Release tags use the same version prefixed with `v`, for example `v2026.8.0`.

## License

MIT
