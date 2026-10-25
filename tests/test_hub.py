"""Tests for allocation parsing."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from custom_components.bluetooth_connection_monitor.hub import (
    AllocationSource,
    format_source,
    parse_allocation,
    parse_allocations,
)

from .conftest import DEVICE, PROXY_A, PROXY_B


def test_parse_allocation_object_and_mapping() -> None:
    """Objects and mappings parse to the same normalized model."""
    expected = AllocationSource(PROXY_A, 3, 2, (DEVICE,))
    as_object = SimpleNamespace(
        source=PROXY_A.lower(), slots=3, free="2", allocated=[DEVICE.lower()]
    )
    as_mapping = {"source": PROXY_A, "slots": 3, "free": 2, "allocated": (DEVICE,)}

    assert parse_allocation(as_object) == expected
    assert parse_allocation(as_mapping) == expected


@pytest.mark.parametrize(
    "allocation",
    [
        {"slots": 3, "allocated": []},
        {"source": PROXY_A, "allocated": None},
        {"source": PROXY_A, "allocated": DEVICE},
        {"source": PROXY_A, "slots": "many", "allocated": []},
    ],
)
def test_parse_allocation_rejects_unexpected_data(allocation: dict) -> None:
    """Unexpected entries raise instead of producing a wrong state."""
    with pytest.raises((TypeError, ValueError)):
        parse_allocation(allocation)


def test_parse_allocations_skips_invalid_entries() -> None:
    """One unreadable source does not hide the readable ones."""
    parsed, errors = parse_allocations(
        [
            {"source": PROXY_A, "slots": 3, "free": 3, "allocated": []},
            {"source": PROXY_B, "allocated": None},
        ]
    )

    assert list(parsed) == [PROXY_A]
    assert len(errors) == 1
    assert PROXY_B in errors[0]


@pytest.mark.parametrize("snapshot", ["text", {"source": PROXY_A}, 42])
def test_parse_allocations_rejects_non_collections(snapshot: object) -> None:
    """A snapshot that is not a collection of allocations is an error."""
    with pytest.raises(TypeError):
        parse_allocations(snapshot)


def test_parse_allocations_none_is_empty() -> None:
    """No snapshot means no allocations."""
    assert parse_allocations(None) == ({}, [])


def test_reports_slots() -> None:
    """slots=0 means that the source has not reported slot information."""
    assert AllocationSource(PROXY_A, 3, 3, ()).reports_slots
    assert not AllocationSource(PROXY_A, 0, 0, ()).reports_slots


def test_format_source() -> None:
    """Sources show their friendly name and keep the stable address."""
    assert format_source(PROXY_A, "proxy-a") == f"proxy-a ({PROXY_A})"
    assert format_source(PROXY_A, PROXY_A.lower()) == PROXY_A
