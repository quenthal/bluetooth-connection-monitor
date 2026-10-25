"""Tests for diagnostics."""

from __future__ import annotations

from homeassistant.core import HomeAssistant

from custom_components.bluetooth_connection_monitor.diagnostics import (
    async_get_config_entry_diagnostics,
)

from .conftest import DEVICE, PROXY_A, PROXY_B, FakeManager, device_entry, setup_entry


async def test_diagnostics(hass: HomeAssistant, manager: FakeManager) -> None:
    """Diagnostics include the allocation snapshot and errors."""
    manager.set_allocation(PROXY_A, [DEVICE])
    manager.set_raw(PROXY_B, {"source": PROXY_B, "allocated": None})
    entry = device_entry()
    await setup_entry(hass, entry)

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics["device_links"] == {DEVICE: None}
    hub = diagnostics["hub"]
    assert hub["listener_active"] is True
    assert hub["tracks_scanner_registrations"] is True
    assert hub["available"] is True
    assert hub["complete"] is False
    assert PROXY_B in hub["last_error"]
    assert hub["sources"] == [
        {
            "source": PROXY_A,
            "slots": 3,
            "free": 2,
            "allocated": (DEVICE,),
            "name": "proxy-a",
        }
    ]
