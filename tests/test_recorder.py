"""Tests for what the recorder stores."""

from __future__ import annotations

from datetime import timedelta

import pytest
from pytest_homeassistant_custom_component.components.recorder.common import (
    async_wait_recording_done,
)

from homeassistant.components.recorder import Recorder, history
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from custom_components.bluetooth_connection_monitor.const import DOMAIN

from .conftest import (
    DEVICE,
    PROXY_A,
    FakeManager,
    device_entry,
    setup_entry,
    slots_entry,
)


# The recorder must be set up before hass, so these override the autouse
# fixtures of conftest.py, which both need hass.
@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(
    recorder_mock: Recorder, enable_custom_integrations: None
) -> None:
    """Enable custom integrations after the recorder."""


@pytest.fixture(autouse=True)
def bluetooth_loaded(recorder_mock: Recorder, hass: HomeAssistant) -> None:
    """Mark Bluetooth as loaded after the recorder."""
    hass.config.components.add("bluetooth")


async def test_volatile_attributes_not_recorded(
    recorder_mock: Recorder, hass: HomeAssistant, manager: FakeManager
) -> None:
    """Attributes that change with every allocation stay out of the database."""
    start = dt_util.utcnow() - timedelta(minutes=1)
    manager.set_allocation(PROXY_A, [DEVICE])
    await setup_entry(hass, device_entry())
    await setup_entry(hass, slots_entry())
    manager.set_allocation(PROXY_A, [])
    await hass.async_block_till_done()
    await async_wait_recording_done(hass)

    entity_registry = er.async_get(hass)
    binary_sensor = entity_registry.async_get_entity_id("binary_sensor", DOMAIN, DEVICE)
    sensor = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{PROXY_A}_free_slots"
    )
    states = await recorder_mock.async_add_executor_job(
        history.get_significant_states,
        hass,
        start,
        None,
        [binary_sensor, sensor],
        None,
        True,
        False,
    )

    assert [state.state for state in states[binary_sensor]] == ["on", "off"]
    for state in states[binary_sensor]:
        assert "last_allocation_change" not in state.attributes
        assert "connected_via" in state.attributes
    assert [state.state for state in states[sensor]] == ["2", "3"]
    for state in states[sensor]:
        assert "allocated_addresses" not in state.attributes
        assert state.attributes["connection_slots"] == 3
