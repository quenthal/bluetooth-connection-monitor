"""Shared read-only Bluetooth connection-allocation listener."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.components.bluetooth import async_current_scanners
from habluetooth import get_manager
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryError

_LOGGER = logging.getLogger(__name__)

_REQUIRED_MANAGER_METHODS = (
    "async_current_allocations",
    "async_register_allocation_callback",
)


@dataclass(frozen=True, slots=True)
class AllocationSource:
    """Allocation details for one Bluetooth source."""

    source: str
    slots: int
    free: int
    allocated: tuple[str, ...]


class BluetoothConnectionMonitorHub:
    """Keep one shared subscription to Home Assistant Bluetooth allocations."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._allocations: dict[str, AllocationSource] = {}
        self._listeners: set[Callable[[], None]] = set()
        self._remove_callback: Callable[[], None] | None = None
        self._references = 0
        self._available = False
        self._last_error: str | None = None

    @property
    def available(self) -> bool:
        """Return whether allocation data is currently usable."""
        return self._available

    @property
    def last_error(self) -> str | None:
        """Return the latest allocation processing error."""
        return self._last_error

    @callback
    def async_acquire(self) -> None:
        """Acquire the shared read-only allocation listener."""
        self._references += 1
        if self._remove_callback is not None:
            return

        manager = get_manager()
        missing = [
            method for method in _REQUIRED_MANAGER_METHODS if not hasattr(manager, method)
        ]
        if missing:
            self._references = max(0, self._references - 1)
            message = (
                "Home Assistant Bluetooth allocation API is incompatible; missing "
                f"manager method(s): {', '.join(missing)}"
            )
            _LOGGER.error(message)
            raise ConfigEntryError(message)

        try:
            current_allocations = manager.async_current_allocations(None)
            parsed = self._parse_all(current_allocations)
            remove_callback = manager.async_register_allocation_callback(
                self._allocation_changed, None
            )
            if not callable(remove_callback):
                raise TypeError(
                    "Bluetooth allocation callback registration did not return an "
                    "unsubscribe callable"
                )
        except Exception as err:
            self._references = max(0, self._references - 1)
            message = (
                "Unable to initialize the read-only Bluetooth allocation listener: "
                f"{err}"
            )
            _LOGGER.exception(message)
            raise ConfigEntryError(message) from err

        self._allocations = parsed
        self._remove_callback = remove_callback
        self._available = True
        self._last_error = None
        _LOGGER.debug(
            "Bluetooth allocation listener initialized with %d source(s)",
            len(self._allocations),
        )

    @callback
    def async_release(self) -> None:
        """Release the shared listener when the final config entry unloads."""
        self._references = max(0, self._references - 1)
        if self._references or self._remove_callback is None:
            return

        try:
            self._remove_callback()
        except Exception:
            _LOGGER.exception("Error while removing Bluetooth allocation listener")
        finally:
            self._remove_callback = None
            self._allocations.clear()
            self._available = False
            self._last_error = None

    @callback
    def async_add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Register a state listener."""
        self._listeners.add(listener)

        @callback
        def remove_listener() -> None:
            self._listeners.discard(listener)

        return remove_listener

    @callback
    def _allocation_changed(self, allocation: Any) -> None:
        """Handle one allocation update without affecting Bluetooth Core state."""
        try:
            parsed = self._parse(allocation)
        except Exception as err:
            self._available = False
            self._last_error = f"Unexpected Bluetooth allocation data: {err}"
            _LOGGER.exception(
                "Ignoring an unexpected Bluetooth allocation update; existing "
                "allocation data was left unchanged"
            )
            self._notify_listeners()
            return

        self._allocations[parsed.source] = parsed
        self._available = True
        self._last_error = None
        self._notify_listeners()

    @callback
    def _notify_listeners(self) -> None:
        """Notify entities that allocation state or availability changed."""
        for listener in tuple(self._listeners):
            try:
                listener()
            except Exception:
                _LOGGER.exception("Bluetooth allocation entity listener failed")

    @classmethod
    def _parse_all(cls, allocations: Any) -> dict[str, AllocationSource]:
        """Parse a complete allocation snapshot."""
        if allocations is None:
            return {}
        if isinstance(allocations, (str, bytes, dict)):
            raise TypeError("allocation snapshot is not an iterable of allocations")
        if not isinstance(allocations, Iterable):
            raise TypeError("allocation snapshot is not iterable")

        parsed_allocations: dict[str, AllocationSource] = {}
        for allocation in allocations:
            parsed = cls._parse(allocation)
            parsed_allocations[parsed.source] = parsed
        return parsed_allocations

    @staticmethod
    def _parse(allocation: Any) -> AllocationSource:
        """Convert allocation objects or mappings to a stable local model."""
        if isinstance(allocation, dict):
            source_raw = allocation.get("source")
            slots_raw = allocation.get("slots", 0)
            free_raw = allocation.get("free", 0)
            allocated_raw = allocation.get("allocated", [])
        else:
            source_raw = getattr(allocation, "source", None)
            slots_raw = getattr(allocation, "slots", 0)
            free_raw = getattr(allocation, "free", 0)
            allocated_raw = getattr(allocation, "allocated", [])

        if not source_raw:
            raise ValueError("allocation source is missing")
        if allocated_raw is None or isinstance(allocated_raw, (str, bytes)):
            raise TypeError("allocated addresses are not a collection")

        source = str(source_raw).upper()
        slots = int(slots_raw)
        free = int(free_raw)
        allocated = tuple(str(item).upper() for item in allocated_raw)
        return AllocationSource(source, slots, free, allocated)

    @callback
    def allocations_for(self, address: str) -> list[AllocationSource]:
        """Return all sources currently allocating the address."""
        normalized = address.upper()
        return sorted(
            (
                allocation
                for allocation in self._allocations.values()
                if normalized in allocation.allocated
            ),
            key=lambda allocation: allocation.source,
        )

    @callback
    def source_names(self) -> dict[str, str]:
        """Return friendly source names where Home Assistant exposes them."""
        names: dict[str, str] = {}
        try:
            scanners = async_current_scanners(self.hass)
        except Exception:
            _LOGGER.exception("Unable to read Bluetooth scanner names")
            return names

        for scanner in scanners:
            source_raw = getattr(scanner, "source", None)
            if not source_raw:
                continue
            source = str(source_raw).upper()
            details = getattr(scanner, "details", None)
            name = getattr(scanner, "name", None)
            if not name and isinstance(details, dict):
                name = details.get("name") or details.get("adapter")
            names[source] = str(name or source_raw)
        return names
