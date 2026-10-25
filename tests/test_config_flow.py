"""Tests for the config flow."""

from __future__ import annotations

import pytest

from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.bluetooth_connection_monitor.const import (
    CONF_ADDRESS,
    CONF_BLUETOOTH_NAME,
    CONF_ENTRY_TYPE,
    CONF_NAME,
    DOMAIN,
    ENTRY_TYPE_DEVICE,
    ENTRY_TYPE_SLOTS,
)

from .conftest import (
    DEVICE,
    OTHER_DEVICE,
    PROXY_A,
    FakeManager,
    device_entry,
    slots_entry,
)


async def _start(hass: HomeAssistant, step: str) -> dict:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": step}
    )


async def test_detected_device(hass: HomeAssistant, manager: FakeManager) -> None:
    """A currently allocated device can be chosen and named."""
    manager.set_allocation(PROXY_A, [DEVICE, OTHER_DEVICE])
    device_entry(OTHER_DEVICE, "Other").add_to_hass(hass)

    result = await _start(hass, "detected")
    assert result["type"] is FlowResultType.FORM
    options = result["data_schema"].schema[CONF_ADDRESS].config["options"]
    assert options == [
        {"value": DEVICE, "label": f"Front door lock — {DEVICE} — proxy-a"}
    ]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ADDRESS: DEVICE}
    )
    assert result["step_id"] == "name"
    assert result["description_placeholders"] == {
        "address": DEVICE,
        "bluetooth_name": "Front door lock",
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_NAME: " Front door "}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Front door"
    assert result["data"] == {
        CONF_ENTRY_TYPE: ENTRY_TYPE_DEVICE,
        CONF_ADDRESS: DEVICE,
        CONF_BLUETOOTH_NAME: "Front door lock",
    }
    assert result["result"].unique_id == DEVICE


async def test_detected_without_unmonitored_devices(
    hass: HomeAssistant, manager: FakeManager
) -> None:
    """The detected step aborts when every allocated device is monitored."""
    manager.set_allocation(PROXY_A, [DEVICE])
    device_entry().add_to_hass(hass)

    result = await _start(hass, "detected")
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_allocated_devices"


@pytest.mark.parametrize(
    "address",
    [
        "00:00:5e:00:53:01",
        " 00-00-5E-00-53-01 ",
        "00005e005301",
    ],
)
async def test_manual_address_notations(
    hass: HomeAssistant, manager: FakeManager, address: str
) -> None:
    """Common MAC notations are normalized."""
    result = await _start(hass, "manual")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ADDRESS: address}
    )
    assert result["step_id"] == "name"
    assert result["description_placeholders"]["address"] == DEVICE


async def test_manual_errors(hass: HomeAssistant, manager: FakeManager) -> None:
    """Invalid addresses and empty names are rejected."""
    result = await _start(hass, "manual")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ADDRESS: "not a mac"}
    )
    assert result["errors"] == {CONF_ADDRESS: "invalid_address"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ADDRESS: OTHER_DEVICE}
    )
    assert result["step_id"] == "name"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_NAME: "  "}
    )
    assert result["errors"] == {CONF_NAME: "empty_name"}


async def test_manual_already_configured(
    hass: HomeAssistant, manager: FakeManager
) -> None:
    """Each address can be configured once."""
    device_entry().add_to_hass(hass)
    result = await _start(hass, "manual")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ADDRESS: DEVICE}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_connection_slots(hass: HomeAssistant, manager: FakeManager) -> None:
    """Connection-slot monitoring is a single entry."""
    result = await _start(hass, "connection_slots")
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_ENTRY_TYPE: ENTRY_TYPE_SLOTS}


async def test_connection_slots_already_configured(
    hass: HomeAssistant, manager: FakeManager
) -> None:
    """A second connection-slot entry is refused."""
    slots_entry().add_to_hass(hass)
    result = await _start(hass, "connection_slots")
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "slots_already_configured"
