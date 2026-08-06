"""Binary sensor for Bluetooth connection allocations."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import CONF_ADDRESS, CONF_BLUETOOTH_NAME, DATA_HUB, DOMAIN
from .hub import AllocationSource, BluetoothConnectionMonitorHub


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the allocation binary sensor."""
    hub: BluetoothConnectionMonitorHub = hass.data[DOMAIN][DATA_HUB]
    async_add_entities([BluetoothConnectionAllocationSensor(entry, hub)])


class BluetoothConnectionAllocationSensor(BinarySensorEntity):
    """Report whether an address owns an active Bluetooth connection slot."""

    _attr_has_entity_name = True
    _attr_translation_key = "connection_allocated"
    _attr_icon = "mdi:bluetooth-connect"

    def __init__(
        self, entry: ConfigEntry, hub: BluetoothConnectionMonitorHub
    ) -> None:
        self._entry = entry
        self._hub = hub
        self._address = str(entry.data[CONF_ADDRESS]).upper()
        bluetooth_name = entry.data.get(CONF_BLUETOOTH_NAME)
        self._attr_unique_id = self._address
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._address)},
            name=entry.title,
            manufacturer="Bluetooth",
            model=str(bluetooth_name or "Connection allocation monitor"),
        )
        self._allocation_signature = self._signature(
            self._hub.allocations_for(self._address)
        )
        # Home Assistant cannot reconstruct an allocation change that happened
        # before this monitor was loaded. This timestamp therefore means the last
        # allocation state observed by this integration, beginning at setup.
        self._last_allocation_change: datetime = dt_util.utcnow()

    async def async_added_to_hass(self) -> None:
        """Subscribe to allocation changes."""
        self.async_on_remove(self._hub.async_add_listener(self._handle_update))

    @callback
    def _handle_update(self) -> None:
        allocations = self._hub.allocations_for(self._address)
        signature = self._signature(allocations)
        if signature != self._allocation_signature:
            self._allocation_signature = signature
            self._last_allocation_change = dt_util.utcnow()
        self.async_write_ha_state()

    @staticmethod
    def _signature(allocations: list[AllocationSource]) -> tuple[str, ...]:
        """Return the allocation identity relevant to this monitored device."""
        return tuple(allocation.source for allocation in allocations)

    @property
    def available(self) -> bool:
        """Return whether the Home Assistant allocation feed is usable."""
        return self._hub.available

    @property
    def is_on(self) -> bool:
        """Return true when the address is allocated on any source."""
        return bool(self._hub.allocations_for(self._address))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return a compact set of automation-friendly attributes."""
        allocations = self._hub.allocations_for(self._address)
        source_names = self._hub.source_names()
        connected_sources = [
            self._format_source(
                allocation.source,
                source_names.get(allocation.source, allocation.source),
            )
            for allocation in allocations
        ]

        return {
            "device_address": self._address,
            "connected_via": "; ".join(connected_sources) or None,
            "allocation_count": len(allocations),
            "last_allocation_change": self._last_allocation_change,
        }

    @staticmethod
    def _format_source(source: str, source_name: str) -> str:
        """Format one source clearly while retaining its stable address."""
        if source_name.upper() == source.upper():
            return source
        return f"{source_name} ({source})"
