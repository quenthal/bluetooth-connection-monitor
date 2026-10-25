"""Tests for the free connection-slot sensors."""

from __future__ import annotations

from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from custom_components.bluetooth_connection_monitor.const import DOMAIN

from .conftest import DEVICE, PROXY_A, PROXY_B, FakeManager, setup_entry, slots_entry


def _entity_id(hass: HomeAssistant, source: str) -> str | None:
    return er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{source}_free_slots"
    )


async def test_free_slot_sensors(hass: HomeAssistant, manager: FakeManager) -> None:
    """Sources that report slots get a sensor, also when they appear later."""
    manager.set_allocation(PROXY_A, [DEVICE], slots=3)
    manager.set_allocation("hci0-passive", [], slots=0)
    entry = slots_entry()
    await setup_entry(hass, entry)

    entity_id = _entity_id(hass, PROXY_A)
    state = hass.states.get(entity_id)
    assert state.state == "2"
    assert state.attributes["source_address"] == PROXY_A
    assert state.attributes["connection_slots"] == 3
    assert state.attributes["allocated_addresses"] == [DEVICE]
    assert state.name == "Bluetooth connection slots proxy-a free connection slots"
    assert _entity_id(hass, "HCI0-PASSIVE") is None

    manager.set_allocation(PROXY_B, [], slots=4)
    await hass.async_block_till_done()
    assert hass.states.get(_entity_id(hass, PROXY_B)).state == "4"

    manager.remove_scanner(PROXY_A, zeroed_allocation=True)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    manager.set_allocation(PROXY_A, [], slots=3)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "3"


async def test_free_slot_sensor_links_to_adapter_device(
    hass: HomeAssistant, manager: FakeManager
) -> None:
    """The sensor is placed on the adapter's device when one exists."""
    bluetooth = MockConfigEntry(domain="bluetooth")
    bluetooth.add_to_hass(hass)
    adapter = dr.async_get(hass).async_get_or_create(
        config_entry_id=bluetooth.entry_id,
        connections={(dr.CONNECTION_BLUETOOTH, PROXY_A)},
        name="proxy-a",
    )
    manager.set_allocation(PROXY_A, [], slots=3)
    manager.set_allocation(PROXY_B, [], slots=3)
    entry = slots_entry()
    await setup_entry(hass, entry)

    entity_registry = er.async_get(hass)
    linked = entity_registry.async_get(_entity_id(hass, PROXY_A))
    assert linked.device_id == adapter.id
    assert hass.states.get(linked.entity_id).name == "proxy-a Free connection slots"

    unlinked = entity_registry.async_get(_entity_id(hass, PROXY_B))
    own_device = dr.async_get(hass).async_get(unlinked.device_id)
    assert own_device.config_entry_id == entry.entry_id
    assert own_device.entry_type is dr.DeviceEntryType.SERVICE
