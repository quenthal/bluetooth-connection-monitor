"""Sensors for free Bluetooth connection slots per source."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DATA_HUB, DOMAIN, SLOTS_UNIQUE_ID
from .device_link import BluetoothConnectionMonitorConfigEntry, async_find_linked_device
from .hub import BluetoothConnectionMonitorHub, async_source_names


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BluetoothConnectionMonitorConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up one free-slot sensor per source that reports connection slots."""
    hub = hass.data[DATA_HUB]
    known_sources: set[str] = set()

    @callback
    def _async_add_new_sources() -> None:
        new_entities = [
            BluetoothFreeSlotsSensor(hass, entry, hub, allocation.source)
            for allocation in hub.slot_sources()
            if allocation.source not in known_sources
        ]
        if new_entities:
            known_sources.update(entity.source for entity in new_entities)
            async_add_entities(new_entities)

    _async_add_new_sources()
    entry.async_on_unload(hub.async_add_listener(_async_add_new_sources))


class BluetoothFreeSlotsSensor(SensorEntity):
    """Report the free connection slots of one Bluetooth adapter or proxy."""

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        hass: HomeAssistant,
        entry: BluetoothConnectionMonitorConfigEntry,
        hub: BluetoothConnectionMonitorHub,
        source: str,
    ) -> None:
        self._hub = hub
        self.source = source
        self._attr_unique_id = f"{source}_free_slots"

        # Home Assistant registers adapters and proxies as devices with their
        # Bluetooth address; show the sensor there when possible.
        if (device := async_find_linked_device(hass, source)) is not None:
            self.device_entry = device
            self._attr_translation_key = "free_slots"
        else:
            self._attr_translation_key = "free_slots_source"
            self._attr_translation_placeholders = {
                "source": async_source_names(hass).get(source, source)
            }
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, SLOTS_UNIQUE_ID)},
                name=entry.title,
                entry_type=DeviceEntryType.SERVICE,
            )
        entry.runtime_data.links[source] = device.id if device else None

    async def async_added_to_hass(self) -> None:
        """Subscribe to allocation changes."""
        self.async_on_remove(self._hub.async_add_listener(self.async_write_ha_state))

    @property
    def available(self) -> bool:
        """Return whether the source currently reports connection slots."""
        allocation = self._hub.allocation(self.source)
        return (
            self._hub.available and allocation is not None and allocation.reports_slots
        )

    @property
    def native_value(self) -> int | None:
        """Return the number of free connection slots."""
        if (allocation := self._hub.allocation(self.source)) is None:
            return None
        return allocation.free

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return slot details of the source."""
        attributes: dict[str, Any] = {"source_address": self.source}
        if (allocation := self._hub.allocation(self.source)) is not None:
            attributes["connection_slots"] = allocation.slots
            attributes["allocated_addresses"] = list(allocation.allocated)
        return attributes
