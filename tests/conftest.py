"""Fixtures for Bluetooth Connection Monitor tests."""

from __future__ import annotations

from collections.abc import Callable, Generator
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from habluetooth import HaBluetoothSlotAllocations
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.core import HomeAssistant

from custom_components.bluetooth_connection_monitor.const import (
    CONF_ADDRESS,
    CONF_BLUETOOTH_NAME,
    CONF_ENTRY_TYPE,
    DOMAIN,
    ENTRY_TYPE_DEVICE,
    ENTRY_TYPE_SLOTS,
    SLOTS_UNIQUE_ID,
)

# Addresses from the IANA documentation range (RFC 7042).
DEVICE = "00:00:5E:00:53:01"
OTHER_DEVICE = "00:00:5E:00:53:02"
PROXY_A = "00:00:5E:00:53:A1"
PROXY_B = "00:00:5E:00:53:B2"


class FakeManager:
    """Minimal stand-in for the habluetooth manager allocation API."""

    def __init__(self) -> None:
        self.allocations: dict[str, Any] = {}
        self.allocation_callbacks: set[Callable[[Any], None]] = set()
        self.scanner_callbacks: set[Callable[[Any], None]] = set()
        self.fail_snapshot: Exception | None = None

    def async_current_allocations(self, source: str | None = None) -> list[Any]:
        if self.fail_snapshot is not None:
            raise self.fail_snapshot
        return list(self.allocations.values())

    def async_register_allocation_callback(
        self, callback: Callable[[Any], None], source: str | None = None
    ) -> Callable[[], None]:
        self.allocation_callbacks.add(callback)
        return lambda: self.allocation_callbacks.discard(callback)

    def async_register_scanner_registration_callback(
        self, callback: Callable[[Any], None], source: str | None
    ) -> Callable[[], None]:
        self.scanner_callbacks.add(callback)
        return lambda: self.scanner_callbacks.discard(callback)

    def set_allocation(
        self, source: str, allocated: list[str], slots: int = 3, free: int | None = None
    ) -> None:
        """Store an allocation and notify like Home Assistant does."""
        allocation = HaBluetoothSlotAllocations(
            source=source,
            slots=slots,
            free=slots - len(allocated) if free is None else free,
            allocated=allocated,
        )
        self.allocations[source] = allocation
        self.notify_allocation(allocation)

    def set_raw(self, source: str, raw: Any) -> None:
        """Store an arbitrary allocation entry and notify."""
        self.allocations[source] = raw
        self.notify_allocation(raw)

    def notify_allocation(self, allocation: Any) -> None:
        for callback in tuple(self.allocation_callbacks):
            callback(allocation)

    def remove_scanner(self, source: str, *, zeroed_allocation: bool) -> None:
        """Remove a scanner like current (zeroed) or older Home Assistant."""
        self.allocations.pop(source, None)
        if zeroed_allocation:
            self.notify_allocation(
                HaBluetoothSlotAllocations(source=source, slots=0, free=0, allocated=[])
            )
        for callback in tuple(self.scanner_callbacks):
            callback(SimpleNamespace(event="removed", source=source))


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable custom integrations in all tests."""


@pytest.fixture(autouse=True)
def bluetooth_loaded(hass: HomeAssistant) -> None:
    """Treat the Bluetooth dependency as set up; its API is patched instead."""
    hass.config.components.add("bluetooth")


@pytest.fixture
def scanners() -> list[SimpleNamespace]:
    """Return the patched Bluetooth scanners."""
    return [
        SimpleNamespace(source=PROXY_A, name=f"proxy-a ({PROXY_A})", details={}),
        SimpleNamespace(source=PROXY_B, name=None, details={"name": "proxy-b"}),
    ]


@pytest.fixture
def service_infos() -> list[SimpleNamespace]:
    """Return the patched Bluetooth discovery cache."""
    return [SimpleNamespace(address=DEVICE, name="Front door lock")]


@pytest.fixture
def manager(
    scanners: list[SimpleNamespace], service_infos: list[SimpleNamespace]
) -> Generator[FakeManager]:
    """Patch the Bluetooth manager and scanner helpers."""
    fake = FakeManager()
    with (
        patch(
            "custom_components.bluetooth_connection_monitor.hub.get_manager",
            return_value=fake,
        ),
        patch(
            "custom_components.bluetooth_connection_monitor.config_flow.get_manager",
            return_value=fake,
        ),
        patch(
            "custom_components.bluetooth_connection_monitor.hub.async_current_scanners",
            return_value=scanners,
        ),
        patch(
            "custom_components.bluetooth_connection_monitor.config_flow.async_discovered_service_info",
            return_value=service_infos,
        ),
    ):
        yield fake


def device_entry(address: str = DEVICE, title: str = "Front door") -> MockConfigEntry:
    """Return a device monitor config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=title,
        unique_id=address,
        data={
            CONF_ENTRY_TYPE: ENTRY_TYPE_DEVICE,
            CONF_ADDRESS: address,
            CONF_BLUETOOTH_NAME: "Front door lock",
        },
    )


def slots_entry() -> MockConfigEntry:
    """Return a connection-slot monitor config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Bluetooth connection slots",
        unique_id=SLOTS_UNIQUE_ID,
        data={CONF_ENTRY_TYPE: ENTRY_TYPE_SLOTS},
    )


async def setup_entry(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Add and set up a config entry."""
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
