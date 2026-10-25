"""Tests for setup, the allocation binary sensor and device linking."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)

from custom_components.bluetooth_connection_monitor.const import (
    DOMAIN,
    ISSUE_INCOMPATIBLE_API,
)

from .conftest import (
    DEVICE,
    OTHER_DEVICE,
    PROXY_A,
    PROXY_B,
    FakeManager,
    device_entry,
    setup_entry,
)


def _entity_id(hass: HomeAssistant, address: str = DEVICE) -> str:
    entity_id = er.async_get(hass).async_get_entity_id("binary_sensor", DOMAIN, address)
    assert entity_id is not None
    return entity_id


def _other_integration_device(
    hass: HomeAssistant, address: str = DEVICE
) -> dr.DeviceEntry:
    other = MockConfigEntry(domain="test")
    other.add_to_hass(hass)
    return dr.async_get(hass).async_get_or_create(
        config_entry_id=other.entry_id,
        connections={(dr.CONNECTION_BLUETOOTH, address)},
        name="Front door lock",
    )


async def test_allocation_state_and_attributes(
    hass: HomeAssistant, manager: FakeManager
) -> None:
    """The sensor follows allocations on any source."""
    manager.set_allocation(PROXY_A, [])
    entry = device_entry()
    await setup_entry(hass, entry)
    entity_id = _entity_id(hass)

    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_DEVICE_CLASS] == BinarySensorDeviceClass.CONNECTIVITY
    assert state.attributes["connected_via"] is None
    assert state.attributes["allocation_count"] == 0
    first_change = state.attributes["last_allocation_change"]

    manager.set_allocation(PROXY_A, [DEVICE.lower()])
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    assert state.attributes["device_address"] == DEVICE
    assert state.attributes["connected_via"] == f"proxy-a ({PROXY_A})"
    assert state.attributes["allocation_count"] == 1
    assert state.attributes["last_allocation_change"] >= first_change

    manager.set_allocation(PROXY_B, [DEVICE])
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.attributes["connected_via"] == (
        f"proxy-a ({PROXY_A}); proxy-b ({PROXY_B})"
    )
    assert state.attributes["allocation_count"] == 2

    manager.set_allocation(PROXY_A, [OTHER_DEVICE])
    manager.set_allocation(PROXY_B, [])
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_OFF


async def test_removed_scanner_with_zeroed_allocation(
    hass: HomeAssistant, manager: FakeManager
) -> None:
    """Current Home Assistant dispatches a zeroed allocation on removal."""
    manager.set_allocation(PROXY_A, [DEVICE])
    await setup_entry(hass, device_entry())
    entity_id = _entity_id(hass)
    assert hass.states.get(entity_id).state == STATE_ON

    manager.remove_scanner(PROXY_A, zeroed_allocation=True)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_OFF


async def test_removed_scanner_without_allocation_callback(
    hass: HomeAssistant, manager: FakeManager
) -> None:
    """Older Home Assistant only reports removal as a scanner registration."""
    manager.set_allocation(PROXY_A, [DEVICE])
    await setup_entry(hass, device_entry())
    entity_id = _entity_id(hass)

    manager.remove_scanner(PROXY_A, zeroed_allocation=False)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_OFF


async def test_unreadable_source(hass: HomeAssistant, manager: FakeManager) -> None:
    """An unreadable source only hides states it could affect."""
    manager.set_allocation(PROXY_A, [DEVICE])
    await setup_entry(hass, device_entry())
    await setup_entry(hass, device_entry(OTHER_DEVICE, "Other"))
    entity_id = _entity_id(hass)
    other_entity_id = _entity_id(hass, OTHER_DEVICE)
    assert hass.states.get(other_entity_id).state == STATE_OFF

    manager.set_raw(PROXY_B, {"source": PROXY_B, "allocated": None})
    await hass.async_block_till_done()
    # Still known to be allocated through the readable source...
    assert hass.states.get(entity_id).state == STATE_ON
    # ...but "not allocated" can no longer be claimed.
    assert hass.states.get(other_entity_id).state == STATE_UNAVAILABLE

    manager.set_allocation(PROXY_B, [])
    await hass.async_block_till_done()
    assert hass.states.get(other_entity_id).state == STATE_OFF


async def test_snapshot_error_recovers(
    hass: HomeAssistant, manager: FakeManager
) -> None:
    """A failing snapshot makes sensors unavailable until it succeeds again."""
    manager.set_allocation(PROXY_A, [DEVICE])
    await setup_entry(hass, device_entry())
    entity_id = _entity_id(hass)

    manager.fail_snapshot = RuntimeError("boom")
    manager.notify_allocation(None)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    manager.fail_snapshot = None
    manager.notify_allocation(None)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_ON


async def test_incompatible_api_creates_issue(
    hass: HomeAssistant, manager: FakeManager
) -> None:
    """A missing allocation API is a permanent error with a repair issue."""
    old_manager = SimpleNamespace(async_current_allocations=lambda source=None: [])
    entry = device_entry()
    with patch(
        "custom_components.bluetooth_connection_monitor.hub.get_manager",
        return_value=old_manager,
    ):
        await setup_entry(hass, entry)

    assert entry.state is ConfigEntryState.SETUP_ERROR
    issue_registry = ir.async_get(hass)
    issue = issue_registry.async_get_issue(DOMAIN, ISSUE_INCOMPATIBLE_API)
    assert issue is not None
    assert issue.translation_placeholders == {
        "methods": "async_register_allocation_callback"
    }

    # A compatible API clears the issue.
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    assert issue_registry.async_get_issue(DOMAIN, ISSUE_INCOMPATIBLE_API) is None


async def test_initialization_error_retries(
    hass: HomeAssistant, manager: FakeManager
) -> None:
    """A failing first snapshot is retried by Home Assistant."""
    manager.fail_snapshot = RuntimeError("not ready")
    entry = device_entry()
    await setup_entry(hass, entry)

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert not manager.allocation_callbacks
    assert not manager.scanner_callbacks


async def test_shared_listener_lifecycle(
    hass: HomeAssistant, manager: FakeManager
) -> None:
    """All entries share one subscription, released with the last entry."""
    first = device_entry()
    second = device_entry(OTHER_DEVICE, "Other")
    await setup_entry(hass, first)
    await setup_entry(hass, second)
    assert len(manager.allocation_callbacks) == 1
    assert len(manager.scanner_callbacks) == 1

    assert await hass.config_entries.async_unload(first.entry_id)
    assert len(manager.allocation_callbacks) == 1

    assert await hass.config_entries.async_unload(second.entry_id)
    assert not manager.allocation_callbacks
    assert not manager.scanner_callbacks

    assert await hass.config_entries.async_setup(first.entry_id)
    await hass.async_block_till_done()
    assert len(manager.allocation_callbacks) == 1


async def test_own_device_without_match(
    hass: HomeAssistant, manager: FakeManager
) -> None:
    """Without a matching device, the monitor creates its own device."""
    entry = device_entry()
    await setup_entry(hass, entry)

    entity = er.async_get(hass).async_get(_entity_id(hass))
    device = dr.async_get(hass).async_get(entity.device_id)
    assert device.config_entry_id == entry.entry_id
    assert device.name == "Front door"
    assert device.model == "Front door lock"


async def test_links_to_existing_device(
    hass: HomeAssistant, manager: FakeManager
) -> None:
    """The sensor is shown on another integration's device with the address."""
    target = _other_integration_device(hass)
    entry = device_entry()
    await setup_entry(hass, entry)

    entity = er.async_get(hass).async_get(_entity_id(hass))
    assert entity.device_id == target.id
    assert not dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
    assert hass.states.get(entity.entity_id).name == (
        "Front door lock Connection allocated"
    )


async def test_moves_to_device_added_later(
    hass: HomeAssistant, manager: FakeManager
) -> None:
    """An upgraded or earlier monitor moves to a matching device and back."""
    entry = device_entry()
    await setup_entry(hass, entry)
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    entity_id = _entity_id(hass)
    own_device_id = entity_registry.async_get(entity_id).device_id

    target = _other_integration_device(hass)
    await hass.async_block_till_done()

    assert entity_registry.async_get(entity_id).device_id == target.id
    assert device_registry.async_get(own_device_id) is None
    assert entry.runtime_data.links == {DEVICE: target.id}

    device_registry.async_remove_device(target.id)
    await hass.async_block_till_done()

    entity = entity_registry.async_get(entity_id)
    assert entity is not None
    device = device_registry.async_get(entity.device_id)
    assert device.config_entry_id == entry.entry_id
    assert entry.runtime_data.links == {DEVICE: None}


async def test_unrelated_device_changes_do_not_reload(
    hass: HomeAssistant, manager: FakeManager
) -> None:
    """Devices with other addresses leave the monitor alone."""
    entry = device_entry()
    await setup_entry(hass, entry)
    entity_id = _entity_id(hass)
    device_id = er.async_get(hass).async_get(entity_id).device_id

    _other_integration_device(hass, OTHER_DEVICE)
    await hass.async_block_till_done()

    assert er.async_get(hass).async_get(entity_id).device_id == device_id
    assert entry.state is ConfigEntryState.LOADED
