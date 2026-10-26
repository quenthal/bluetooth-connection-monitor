"""Link monitor entities to Bluetooth devices owned by other integrations."""

from __future__ import annotations

from dataclasses import dataclass, field
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.loader import IntegrationNotLoaded, async_get_loaded_integration

from .const import DOMAIN, ISSUE_CHOSEN_DEVICE_MISSING

_LOGGER = logging.getLogger(__name__)

_BLUETOOTH_DEPENDENCIES = {"bluetooth", "bluetooth_adapters"}


@dataclass(slots=True)
class MonitorRuntimeData:
    """Runtime data of one config entry."""

    # Bluetooth address -> id of the other integration's device the entity is
    # linked to, or None when the entity uses this integration's own device.
    links: dict[str, str | None] = field(default_factory=dict)
    # Bluetooth address -> device chosen by the user.
    chosen_devices: dict[str, str] = field(default_factory=dict)


type BluetoothConnectionMonitorConfigEntry = ConfigEntry[MonitorRuntimeData]


@callback
def _device_domain(hass: HomeAssistant, device: dr.AnyDeviceEntry) -> str | None:
    owner = hass.config_entries.async_get_entry(device.config_entry_id)
    return owner.domain if owner else None


@callback
def async_is_own_device(hass: HomeAssistant, device_id: str) -> bool:
    """Return whether the device belongs to this integration."""
    device = dr.async_get(hass).async_get(device_id)
    return device is not None and _device_domain(hass, device) == DOMAIN


@callback
def _is_bluetooth_integration(hass: HomeAssistant, domain: str) -> bool:
    """Return whether the integration talks to its devices over Bluetooth."""
    if domain == "bluetooth":
        return True
    try:
        integration = async_get_loaded_integration(hass, domain)
    except IntegrationNotLoaded:
        return False
    return bool(integration.manifest.get("bluetooth")) or bool(
        _BLUETOOTH_DEPENDENCIES & set(integration.dependencies)
    )


@callback
def async_find_linked_device(
    hass: HomeAssistant, address: str, chosen_device_id: str | None = None
) -> dr.AnyDeviceEntry | None:
    """Return the other integration's device to show the entity on.

    A device chosen by the user wins. Otherwise the device is found by its
    Bluetooth address; when several integrations register the same address
    (for example a lock's Bluetooth and cloud integrations), a Bluetooth
    integration is preferred.
    """
    device_registry = dr.async_get(hass)
    if chosen_device_id is not None:
        device = device_registry.async_get(chosen_device_id)
        if device is not None and _device_domain(hass, device) != DOMAIN:
            return device

    connections = {
        (dr.CONNECTION_BLUETOOTH, address.upper()),
        (dr.CONNECTION_BLUETOOTH, address.lower()),
    }
    candidates: list[tuple[bool, bool, str, dr.DeviceEntry]] = []
    for device in device_registry.async_get_devices(connections=connections):
        domain = _device_domain(hass, device)
        if domain is None or domain == DOMAIN:
            continue
        candidates.append(
            (
                device.disabled,
                not _is_bluetooth_integration(hass, domain),
                device.id,
                device,
            )
        )
    if not candidates:
        return None
    # Prefer an enabled device of a Bluetooth integration and keep the choice
    # stable between restarts.
    return min(candidates, key=lambda candidate: candidate[:3])[3]


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
        runtime_data = entry.runtime_data
        for address, linked_device_id in runtime_data.links.items():
            device = async_find_linked_device(
                hass, address, runtime_data.chosen_devices.get(address)
            )
            if (device.id if device else None) != linked_device_id:
                _LOGGER.debug("Device link of %s changed; reloading", address)
                hass.config_entries.async_schedule_reload(entry.entry_id)
                return

    return hass.bus.async_listen(
        dr.EVENT_DEVICE_REGISTRY_UPDATED, _async_device_registry_updated
    )


@callback
def async_link_entity_device(
    hass: HomeAssistant,
    entry: BluetoothConnectionMonitorConfigEntry,
    address: str,
    chosen_device_id: str | None,
) -> dr.AnyDeviceEntry | None:
    """Find the device for an entity and remember the link for tracking.

    A chosen device that no longer exists raises a repair issue, so the
    sensor does not move to another device unnoticed.
    """
    if chosen_device_id is not None:
        entry.runtime_data.chosen_devices[address] = chosen_device_id
    device = async_find_linked_device(hass, address, chosen_device_id)
    issue_id = _chosen_device_issue_id(entry, address)
    if chosen_device_id is not None and (
        device is None or device.id != chosen_device_id
    ):
        _LOGGER.warning(
            "The device chosen for %s no longer exists; finding one by its "
            "Bluetooth address instead",
            address,
        )
        ir.async_create_issue(
            hass,
            DOMAIN,
            issue_id,
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key=ISSUE_CHOSEN_DEVICE_MISSING,
            translation_placeholders={"entry": entry.title, "address": address},
        )
    else:
        ir.async_delete_issue(hass, DOMAIN, issue_id)
    entry.runtime_data.links[address] = device.id if device else None
    return device


def _chosen_device_issue_id(entry: ConfigEntry, address: str) -> str:
    return f"{ISSUE_CHOSEN_DEVICE_MISSING}_{entry.entry_id}_{address}"


@callback
def async_delete_entry_issues(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Delete the repair issues of a removed config entry."""
    prefix = f"{ISSUE_CHOSEN_DEVICE_MISSING}_{entry.entry_id}_"
    for domain, issue_id in list(ir.async_get(hass).issues):
        if domain == DOMAIN and issue_id.startswith(prefix):
            ir.async_delete_issue(hass, DOMAIN, issue_id)


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
