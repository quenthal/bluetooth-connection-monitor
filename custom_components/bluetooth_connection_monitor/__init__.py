"""Bluetooth Connection Monitor integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DATA_HUB, DOMAIN, PLATFORMS
from .hub import BluetoothConnectionMonitorHub


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Bluetooth Connection Monitor from a config entry."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    hub: BluetoothConnectionMonitorHub = domain_data.setdefault(
        DATA_HUB, BluetoothConnectionMonitorHub(hass)
    )

    hub.async_acquire()
    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except Exception:
        hub.async_release()
        raise
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False

    hub: BluetoothConnectionMonitorHub = hass.data[DOMAIN][DATA_HUB]
    hub.async_release()
    return True
