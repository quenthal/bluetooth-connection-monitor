"""Shared read-only Bluetooth connection-allocation listener."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass
import logging
from typing import Any

from habluetooth import get_manager

from homeassistant.components.bluetooth import async_current_scanners
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN, ISSUE_INCOMPATIBLE_API

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

    @property
    def reports_slots(self) -> bool:
        """Return whether the source has reported connection-slot information.

        Home Assistant uses ``slots=0`` for sources that have not reported slot
        information (yet), such as passive scanners.
        """
        return self.slots > 0


def parse_allocation(allocation: Any) -> AllocationSource:
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
        raise TypeError(f"allocated addresses of {source_raw} are not a collection")

    source = str(source_raw).upper()
    slots = int(slots_raw)
    free = int(free_raw)
    allocated = tuple(str(item).upper() for item in allocated_raw)
    return AllocationSource(source, slots, free, allocated)


def parse_allocations(
    allocations: Any,
) -> tuple[dict[str, AllocationSource], list[str]]:
    """Parse a complete allocation snapshot.

    Returns the valid sources and one error message per entry that could not be
    parsed. A snapshot that is not a collection at all raises ``TypeError``.
    """
    if allocations is None:
        return {}, []
    if isinstance(allocations, (str, bytes, dict)) or not isinstance(
        allocations, Iterable
    ):
        raise TypeError("allocation snapshot is not an iterable of allocations")

    parsed: dict[str, AllocationSource] = {}
    errors: list[str] = []
    for allocation in allocations:
        try:
            item = parse_allocation(allocation)
        except (TypeError, ValueError) as err:
            errors.append(str(err))
            continue
        parsed[item.source] = item
    return parsed, errors


@callback
def async_source_names(hass: HomeAssistant) -> dict[str, str]:
    """Return friendly source names where Home Assistant exposes them."""
    names: dict[str, str] = {}
    try:
        scanners = async_current_scanners(hass)
    except Exception:
        # Called for every state write; names are cosmetic, so stay quiet.
        _LOGGER.debug("Unable to read Bluetooth scanner names", exc_info=True)
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
        resolved_name = str(name or source_raw)
        suffix = f" ({source})"
        if resolved_name.upper().endswith(suffix.upper()):
            resolved_name = resolved_name[: -len(suffix)].rstrip()
        names[source] = resolved_name or source
    return names


def format_source(source: str, source_name: str) -> str:
    """Format one source clearly while retaining its stable address."""
    if source_name.upper() == source.upper():
        return source
    return f"{source_name} ({source})"


def _unsubscribe_callable(remove: Any, name: str) -> Callable[[], None]:
    if not callable(remove):
        raise TypeError(f"{name} registration did not return an unsubscribe callable")
    return remove


class BluetoothConnectionMonitorHub:
    """Keep one shared subscription to Home Assistant Bluetooth allocations."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._manager: Any = None
        self._allocations: dict[str, AllocationSource] = {}
        self._invalid_entries: list[str] = []
        self._listeners: set[Callable[[], None]] = set()
        self._unsubscribers: list[Callable[[], None]] = []
        self._references = 0
        self._available = False
        self._last_error: str | None = None
        self._tracks_scanner_registrations = False

    @property
    def available(self) -> bool:
        """Return whether the allocation snapshot could be read."""
        return self._available

    @property
    def complete(self) -> bool:
        """Return whether every source in the snapshot could be parsed.

        When a source is unreadable, an address missing from the readable
        sources may still be allocated on the unreadable one.
        """
        return not self._invalid_entries

    @property
    def last_error(self) -> str | None:
        """Return the latest allocation processing error."""
        return self._last_error

    @callback
    def async_acquire(self) -> None:
        """Acquire the shared read-only allocation listener."""
        if self._unsubscribers:
            self._references += 1
            return

        manager = get_manager()
        missing = [
            method
            for method in _REQUIRED_MANAGER_METHODS
            if not hasattr(manager, method)
        ]
        if missing:
            methods = ", ".join(missing)
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                ISSUE_INCOMPATIBLE_API,
                is_fixable=False,
                severity=ir.IssueSeverity.ERROR,
                translation_key=ISSUE_INCOMPATIBLE_API,
                translation_placeholders={"methods": methods},
            )
            message = (
                "Home Assistant Bluetooth allocation API is incompatible; missing "
                f"manager method(s): {methods}"
            )
            raise ConfigEntryError(message)
        ir.async_delete_issue(self.hass, DOMAIN, ISSUE_INCOMPATIBLE_API)

        self._manager = manager
        try:
            # Subscribe before reading the snapshot so no change can slip in
            # between the two.
            self._unsubscribers.append(
                _unsubscribe_callable(
                    manager.async_register_allocation_callback(
                        self._async_allocations_changed, None
                    ),
                    "Bluetooth allocation callback",
                )
            )
            # Older Home Assistant releases drop a removed scanner's allocations
            # without an allocation callback; the scanner registration callback
            # is the only signal for that.
            self._tracks_scanner_registrations = hasattr(
                manager, "async_register_scanner_registration_callback"
            )
            if self._tracks_scanner_registrations:
                self._unsubscribers.append(
                    _unsubscribe_callable(
                        manager.async_register_scanner_registration_callback(
                            self._async_scanners_changed, None
                        ),
                        "Bluetooth scanner registration callback",
                    )
                )
            allocations, invalid = self._read_snapshot()
        except Exception as err:
            self._async_unsubscribe()
            # Home Assistant logs the message and retries the setup.
            _LOGGER.debug("Bluetooth allocation listener setup failed", exc_info=True)
            raise ConfigEntryNotReady(
                "Unable to initialize the read-only Bluetooth allocation listener: "
                f"{err}"
            ) from err

        self._references += 1
        self._apply_snapshot(allocations, invalid)
        _LOGGER.debug(
            "Bluetooth allocation listener initialized with %d source(s)",
            len(self._allocations),
        )

    @callback
    def async_release(self) -> None:
        """Release the shared listener when the final config entry unloads."""
        self._references = max(0, self._references - 1)
        if self._references:
            return
        self._async_unsubscribe()

    @callback
    def _async_unsubscribe(self) -> None:
        while self._unsubscribers:
            remove = self._unsubscribers.pop()
            try:
                remove()
            except Exception:
                _LOGGER.exception("Error while removing Bluetooth allocation listener")
        self._manager = None
        self._allocations = {}
        self._invalid_entries = []
        self._available = False
        self._last_error = None
        self._tracks_scanner_registrations = False

    @callback
    def async_add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Register a state listener."""
        self._listeners.add(listener)

        @callback
        def remove_listener() -> None:
            self._listeners.discard(listener)

        return remove_listener

    # Both callbacks ignore their payload and re-read the full snapshot: Home
    # Assistant updates its stored allocations before dispatching, and a full
    # snapshot also covers removed sources and recovers from earlier errors.
    @callback
    def _async_allocations_changed(self, _allocation: Any) -> None:
        self._async_refresh()

    @callback
    def _async_scanners_changed(self, _registration: Any) -> None:
        self._async_refresh()

    def _read_snapshot(self) -> tuple[dict[str, AllocationSource], list[str]]:
        return parse_allocations(self._manager.async_current_allocations(None))

    @callback
    def _async_refresh(self) -> None:
        """Re-read allocations without affecting Bluetooth Core state."""
        if self._manager is None:
            return
        try:
            allocations, invalid = self._read_snapshot()
        except Exception as err:
            if self._available:
                _LOGGER.exception("Unable to read the Bluetooth allocation snapshot")
            self._available = False
            self._last_error = f"Unable to read Bluetooth allocations: {err}"
        else:
            self._apply_snapshot(allocations, invalid)
        self._notify_listeners()

    @callback
    def _apply_snapshot(
        self, allocations: dict[str, AllocationSource], invalid: list[str]
    ) -> None:
        if invalid and invalid != self._invalid_entries:
            _LOGGER.warning(
                "Ignoring %d unexpected Bluetooth allocation entr%s: %s",
                len(invalid),
                "y" if len(invalid) == 1 else "ies",
                "; ".join(invalid),
            )
        self._allocations = allocations
        self._invalid_entries = invalid
        self._available = True
        self._last_error = (
            f"Unexpected Bluetooth allocation data: {'; '.join(invalid)}"
            if invalid
            else None
        )

    @callback
    def _notify_listeners(self) -> None:
        """Notify entities that allocation state or availability changed."""
        for listener in tuple(self._listeners):
            try:
                listener()
            except Exception:
                _LOGGER.exception("Bluetooth allocation entity listener failed")

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
    def allocation(self, source: str) -> AllocationSource | None:
        """Return the allocation details of one source."""
        return self._allocations.get(source.upper())

    @callback
    def slot_sources(self) -> list[AllocationSource]:
        """Return the sources that report connection-slot information."""
        return sorted(
            (a for a in self._allocations.values() if a.reports_slots),
            key=lambda allocation: allocation.source,
        )

    @callback
    def all_allocations(self) -> list[AllocationSource]:
        """Return every source in the current snapshot."""
        return sorted(self._allocations.values(), key=lambda a: a.source)

    @callback
    def as_diagnostics(self) -> dict[str, Any]:
        """Return the hub state for diagnostics."""
        source_names = async_source_names(self.hass)
        return {
            "listener_active": bool(self._unsubscribers),
            "tracks_scanner_registrations": self._tracks_scanner_registrations,
            "references": self._references,
            "available": self._available,
            "complete": self.complete,
            "last_error": self._last_error,
            "invalid_entries": list(self._invalid_entries),
            "sources": [
                {**asdict(allocation), "name": source_names.get(allocation.source)}
                for allocation in self.all_allocations()
            ],
        }
