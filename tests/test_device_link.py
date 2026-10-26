"""Tests for choosing the device a sensor is shown on."""

from __future__ import annotations

from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    MockModule,
    mock_integration,
)

from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)

from custom_components.bluetooth_connection_monitor.const import (
    CONF_ADDRESS,
    CONF_DEVICE_ID,
    CONF_DEVICE_LINKS,
    CONF_NAME,
    DOMAIN,
    ISSUE_CHOSEN_DEVICE_MISSING,
)

from .conftest import (
    DEVICE,
    PROXY_A,
    PROXY_B,
    FakeManager,
    device_entry,
    setup_entry,
    slots_entry,
)


def _device(
    hass: HomeAssistant,
    domain: str,
    name: str,
    address: str | None = DEVICE,
) -> dr.DeviceEntry:
    entry = MockConfigEntry(domain=domain)
    entry.add_to_hass(hass)
    return dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(domain, name)},
        connections={(dr.CONNECTION_BLUETOOTH, address)} if address else set(),
        name=name,
    )


def _linked_device_id(hass: HomeAssistant, platform: str, unique_id: str) -> str:
    entity_registry = er.async_get(hass)
    entity_id = entity_registry.async_get_entity_id(platform, DOMAIN, unique_id)
    return entity_registry.async_get(entity_id).device_id


def _issue_id(entry: MockConfigEntry, address: str) -> str:
    return f"{ISSUE_CHOSEN_DEVICE_MISSING}_{entry.entry_id}_{address}"


async def test_prefers_bluetooth_integration(
    hass: HomeAssistant, manager: FakeManager
) -> None:
    """A lock's Bluetooth integration wins over its cloud integration."""
    mock_integration(
        hass, MockModule(domain="ble_lock", dependencies=["bluetooth_adapters"])
    )
    mock_integration(hass, MockModule(domain="cloud_lock"))
    # Several cloud devices make an accidental pass by device id order unlikely.
    for index in range(5):
        _device(hass, "cloud_lock", f"Cloud lock {index}")
    ble_device = _device(hass, "ble_lock", "Bluetooth lock")

    await setup_entry(hass, device_entry())

    assert _linked_device_id(hass, "binary_sensor", DEVICE) == ble_device.id


async def test_chosen_device_wins_and_survives_restart(
    hass: HomeAssistant, manager: FakeManager
) -> None:
    """A chosen device is kept, even over an automatic match."""
    _device(hass, "bluetooth_lock", "Automatic match")
    chosen = _device(hass, "esphome", "Door controller", address=None)
    entry = device_entry()
    entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(entry, options={CONF_DEVICE_ID: chosen.id})

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert _linked_device_id(hass, "binary_sensor", DEVICE) == chosen.id

    # Device registry changes and reloads keep the choice.
    _device(hass, "another_lock", "Another match")
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert _linked_device_id(hass, "binary_sensor", DEVICE) == chosen.id
    assert ir.async_get(hass).async_get_issue(DOMAIN, _issue_id(entry, DEVICE)) is None


async def test_removed_chosen_device_raises_issue(
    hass: HomeAssistant, manager: FakeManager
) -> None:
    """A removed chosen device is reported instead of silently replaced."""
    automatic = _device(hass, "bluetooth_lock", "Automatic match")
    chosen = _device(hass, "esphome", "Door controller", address=None)
    entry = device_entry()
    entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(entry, options={CONF_DEVICE_ID: chosen.id})
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    dr.async_get(hass).async_remove_device(chosen.id)
    await hass.async_block_till_done()

    assert _linked_device_id(hass, "binary_sensor", DEVICE) == automatic.id
    issue = ir.async_get(hass).async_get_issue(DOMAIN, _issue_id(entry, DEVICE))
    assert issue is not None
    assert issue.translation_placeholders == {"entry": "Front door", "address": DEVICE}

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert ir.async_get(hass).async_get_issue(DOMAIN, _issue_id(entry, DEVICE)) is None


async def test_config_flow_stores_chosen_device(
    hass: HomeAssistant, manager: FakeManager
) -> None:
    """A device chosen while adding the monitor is stored as an option."""
    chosen = _device(hass, "esphome", "Door controller", address=None)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "manual"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ADDRESS: DEVICE}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_NAME: "Front door", CONF_DEVICE_ID: chosen.id}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].options == {CONF_DEVICE_ID: chosen.id}
    await hass.async_block_till_done()
    assert _linked_device_id(hass, "binary_sensor", DEVICE) == chosen.id


async def test_options_flow_device(hass: HomeAssistant, manager: FakeManager) -> None:
    """The device can be chosen and cleared later; own devices are refused."""
    automatic = _device(hass, "bluetooth_lock", "Automatic match")
    chosen = _device(hass, "esphome", "Door controller", address=None)
    entry = device_entry()
    await setup_entry(hass, entry)
    assert _linked_device_id(hass, "binary_sensor", DEVICE) == automatic.id

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["step_id"] == "device"
    assert result["description_placeholders"] == {
        "address": DEVICE,
        "current_device": "Automatic match",
    }

    other_monitor = device_entry("00:00:5E:00:53:09", "Other")
    await setup_entry(hass, other_monitor)
    own_device = dr.async_entries_for_config_entry(
        dr.async_get(hass), other_monitor.entry_id
    )[0]
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_DEVICE_ID: own_device.id}
    )
    assert result["errors"] == {CONF_DEVICE_ID: "own_device"}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_DEVICE_ID: chosen.id}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.options == {CONF_DEVICE_ID: chosen.id}
    assert _linked_device_id(hass, "binary_sensor", DEVICE) == chosen.id

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()
    assert entry.options == {}
    assert _linked_device_id(hass, "binary_sensor", DEVICE) == automatic.id


async def test_options_flow_slots(hass: HomeAssistant, manager: FakeManager) -> None:
    """Each adapter or proxy sensor can be placed on a chosen device."""
    proxy_device = _device(hass, "esphome", "Proxy B", address=None)
    manager.set_allocation(PROXY_A, [], slots=3)
    manager.set_allocation(PROXY_B, [], slots=3)
    entry = slots_entry()
    await setup_entry(hass, entry)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["step_id"] == "slots"
    fields = [str(key) for key in result["data_schema"].schema]
    assert fields == [f"proxy-a ({PROXY_A})", f"proxy-b ({PROXY_B})"]

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {f"proxy-b ({PROXY_B})": proxy_device.id}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.options == {CONF_DEVICE_LINKS: {PROXY_B: proxy_device.id}}
    assert _linked_device_id(hass, "sensor", f"{PROXY_B}_free_slots") == (
        proxy_device.id
    )
    assert _linked_device_id(hass, "sensor", f"{PROXY_A}_free_slots") != (
        proxy_device.id
    )


async def test_options_flow_slots_without_sources(
    hass: HomeAssistant, manager: FakeManager
) -> None:
    """Without slot sources there is nothing to choose."""
    entry = slots_entry()
    await setup_entry(hass, entry)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_slot_sources"
