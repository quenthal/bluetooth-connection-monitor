"""Diagnostics for Bluetooth Connection Monitor."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from .const import DATA_HUB
from .device_link import BluetoothConnectionMonitorConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: BluetoothConnectionMonitorConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return {
        "entry": {
            "title": entry.title,
            "data": dict(entry.data),
        },
        "device_links": dict(entry.runtime_data.links),
        "hub": hass.data[DATA_HUB].as_diagnostics(),
    }
