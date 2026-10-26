"""Bluetooth Connection Monitor integration."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import (
    CONF_ENTRY_TYPE,
    DATA_HUB,
    ENTRY_TYPE_DEVICE,
    PLATFORMS_BY_ENTRY_TYPE,
)
from .device_link import (
    BluetoothConnectionMonitorConfigEntry,
    MonitorRuntimeData,
    async_delete_entry_issues,
    async_remove_unused_devices,
    async_track_device_links,
)
from .hub import BluetoothConnectionMonitorHub


def _platforms(entry: BluetoothConnectionMonitorConfigEntry) -> list[Platform]:
    return PLATFORMS_BY_ENTRY_TYPE[entry.data.get(CONF_ENTRY_TYPE, ENTRY_TYPE_DEVICE)]


async def async_setup_entry(
    hass: HomeAssistant, entry: BluetoothConnectionMonitorConfigEntry
) -> bool:
    """Set up Bluetooth Connection Monitor from a config entry."""
    hub = hass.data.setdefault(DATA_HUB, BluetoothConnectionMonitorHub(hass))

    hub.async_acquire()
    entry.runtime_data = MonitorRuntimeData()
    try:
        await hass.config_entries.async_forward_entry_setups(entry, _platforms(entry))
    except Exception:
        hub.async_release()
        raise

    async_remove_unused_devices(hass, entry)
    entry.async_on_unload(async_track_device_links(hass, entry))
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: BluetoothConnectionMonitorConfigEntry
) -> bool:
    """Unload a config entry."""
    if not await hass.config_entries.async_unload_platforms(entry, _platforms(entry)):
        return False

    hass.data[DATA_HUB].async_release()
    return True


async def async_remove_entry(
    hass: HomeAssistant, entry: BluetoothConnectionMonitorConfigEntry
) -> None:
    """Clean up after a removed config entry."""
    async_delete_entry_issues(hass, entry)
