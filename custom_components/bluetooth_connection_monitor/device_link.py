"""Link monitor entities to Bluetooth devices owned by other integrations."""

from __future__ import annotations

from dataclasses import dataclass, field
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class MonitorRuntimeData:
    """Runtime data of one config entry."""

    # Bluetooth address -> id of the other integration's device the entity is
    # linked to, or None when the entity uses this integration's own device.
    links: dict[str, str | None] = field(default_factory=dict)


type BluetoothConnectionMonitorConfigEntry = ConfigEntry[MonitorRuntimeData]


@callback
def async_find_linked_device(
    hass: HomeAssistant, address: str
) -> dr.DeviceEntry | None:
    """Return another integration's device that has this Bluetooth address."""
    device_registry = dr.async_get(hass)
    connections = {
        (dr.CONNECTION_BLUETOOTH, address.upper()),
        (dr.CONNECTION_BLUETOOTH, address.lower()),
    }
    candidates = []
    for device in device_registry.async_get_devices(connections=connections):
        owner = hass.config_entries.async_get_entry(device.config_entry_id)
        if owner is None or owner.domain == DOMAIN:
            continue
        candidates.append(device)
    if not candidates:
        return None
    # Prefer an enabled device and keep the choice stable between restarts.
    return min(candidates, key=lambda device: (device.disabled, device.id))


@callback
def async_track_device_links(
    hass: HomeAssistant, entry: BluetoothConnectionMonitorConfigEntry
) -> CALLBACK_TYPE:
    """Reload the entry when the device an entity should link to changes.

    This covers a matching device that is added after the monitor, for example
    when the device's own integration is set up later, and a linked device
    that is removed.
    """

    @callback
    def _async_device_registry_updated(
        event: Event[dr.EventDeviceRegistryUpdatedData],
    ) -> None:
        data = event.data
        if data["action"] == "update" and "connections" not in data["changes"]:
            return
        for address, linked_device_id in entry.runtime_data.links.items():
            device = async_find_linked_device(hass, address)
            if (device.id if device else None) != linked_device_id:
                _LOGGER.debug("Device link of %s changed; reloading", address)
                hass.config_entries.async_schedule_reload(entry.entry_id)
                return

    return hass.bus.async_listen(
        dr.EVENT_DEVICE_REGISTRY_UPDATED, _async_device_registry_updated
    )


@callback
def async_remove_unused_devices(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove this entry's own devices whose entities moved to a linked device."""
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)
    for device in dr.async_entries_for_config_entry(device_registry, entry.entry_id):
        if not er.async_entries_for_device(
            entity_registry, device.id, include_disabled_entities=True
        ):
            _LOGGER.debug("Removing unused device %s", device.id)
            device_registry.async_remove_device(device.id)
