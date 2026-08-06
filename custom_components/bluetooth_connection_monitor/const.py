"""Constants for Bluetooth Connection Monitor."""

from homeassistant.const import Platform

DOMAIN = "bluetooth_connection_monitor"
PLATFORMS = [Platform.BINARY_SENSOR]

CONF_ADDRESS = "address"
CONF_BLUETOOTH_NAME = "bluetooth_name"
CONF_NAME = "name"

DATA_HUB = "hub"
