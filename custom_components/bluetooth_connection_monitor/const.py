"""Constants for Bluetooth Connection Monitor."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.const import Platform
from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from .hub import BluetoothConnectionMonitorHub

DOMAIN = "bluetooth_connection_monitor"

CONF_ADDRESS = "address"
CONF_BLUETOOTH_NAME = "bluetooth_name"
CONF_ENTRY_TYPE = "entry_type"
CONF_NAME = "name"

# Entries created before connection-slot monitoring have no entry type and are
# device monitors.
ENTRY_TYPE_DEVICE = "device"
ENTRY_TYPE_SLOTS = "connection_slots"

SLOTS_UNIQUE_ID = "connection_slots"

PLATFORMS_BY_ENTRY_TYPE = {
    ENTRY_TYPE_DEVICE: [Platform.BINARY_SENSOR],
    ENTRY_TYPE_SLOTS: [Platform.SENSOR],
}

ISSUE_INCOMPATIBLE_API = "incompatible_api"

DATA_HUB: HassKey[BluetoothConnectionMonitorHub] = HassKey(DOMAIN)
