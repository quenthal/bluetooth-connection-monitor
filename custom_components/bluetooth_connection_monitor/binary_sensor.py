"""Binary sensor for Bluetooth connection allocations."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_ADDRESS, CONF_BLUETOOTH_NAME, DATA_HUB, DOMAIN
from .hub import BluetoothConnectionMonitorHub


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

    async def async_added_to_hass(self) -> None:
        """Subscribe to allocation changes."""
        self.async_on_remove(self._hub.async_add_listener(self._handle_update))

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()

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
        """Return source and slot diagnostics."""
        allocations = self._hub.allocations_for(self._address)
        source_names = self._hub.source_names()
        sources = [allocation.source for allocation in allocations]
        named_sources = [source_names.get(source, source) for source in sources]
        connected_via = [
            {
                "address": allocation.source,
                "name": source_names.get(allocation.source, allocation.source),
            }
            for allocation in allocations
        ]

        attributes: dict[str, Any] = {
            "device_address": self._address,
            "allocation_count": len(allocations),
            "sources": sources,
            "source_names": named_sources,
            "source_count": len(sources),
            "connected_via": connected_via,
            "total_slots": sum(allocation.slots for allocation in allocations),
            "total_free_slots": sum(allocation.free for allocation in allocations),
            "allocations": [
                {
                    "source": allocation.source,
                    "source_name": source_names.get(
                        allocation.source, allocation.source
                    ),
                    "slots": allocation.slots,
                    "free": allocation.free,
                }
                for allocation in allocations
            ],
        }
        if len(allocations) == 1:
            allocation = allocations[0]
            attributes["connected_via_address"] = allocation.source
            attributes["connected_via_name"] = source_names.get(
                allocation.source, allocation.source
            )
        else:
            attributes["connected_via_address"] = None
            attributes["connected_via_name"] = None

        if self._hub.last_error:
            attributes["last_error"] = self._hub.last_error
        return attributes
