"""Config flow for Bluetooth Connection Monitor."""

from __future__ import annotations

import logging
import re
from typing import Any

from habluetooth import get_manager
import voluptuous as vol

from homeassistant.components.bluetooth import async_discovered_service_info
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, selector
from homeassistant.helpers.device_registry import format_mac

from .const import (
    CONF_ADDRESS,
    CONF_BLUETOOTH_NAME,
    CONF_DEVICE_ID,
    CONF_DEVICE_LINKS,
    CONF_ENTRY_TYPE,
    CONF_NAME,
    DATA_HUB,
    DOMAIN,
    ENTRY_TYPE_DEVICE,
    ENTRY_TYPE_SLOTS,
    SLOTS_UNIQUE_ID,
)
from .device_link import async_is_own_device
from .hub import (
    AllocationSource,
    async_source_names,
    format_source,
    parse_allocations,
)

_LOGGER = logging.getLogger(__name__)

_MAC_RE = re.compile(r"^(?:[0-9A-F]{2}:){5}[0-9A-F]{2}$")

SLOTS_TITLE = "Bluetooth connection slots"


@callback
def _async_current_allocations() -> list[AllocationSource]:
    """Return the current allocation snapshot, or nothing when unavailable."""
    manager = get_manager()
    if not hasattr(manager, "async_current_allocations"):
        return []
    try:
        allocations, _invalid = parse_allocations(
            manager.async_current_allocations(None)
        )
    except Exception:
        _LOGGER.exception("Unable to read the Bluetooth allocation snapshot")
        return []
    return list(allocations.values())


@callback
def _async_bluetooth_names(hass: HomeAssistant) -> dict[str, str]:
    """Return the best currently known Bluetooth name per address."""
    names: dict[str, str] = {}
    for info in async_discovered_service_info(hass, connectable=True):
        address = str(info.address).upper()
        name = getattr(info, "name", None)
        if name and str(name).strip():
            names[address] = str(name).strip()
    return names


def _device_schema_field(key: str) -> dict[vol.Optional, selector.DeviceSelector]:
    return {vol.Optional(key): selector.DeviceSelector()}


def _validate_device(
    hass: HomeAssistant, device_id: str | None, key: str, errors: dict[str, str]
) -> None:
    if device_id and async_is_own_device(hass, device_id):
        errors[key] = "own_device"


def _normalize_address(address: str) -> str:
    """Normalize common MAC-address notations to AA:BB:CC:DD:EE:FF."""
    return format_mac(address.strip()).upper()


class BluetoothConnectionMonitorConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Bluetooth Connection Monitor."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> BluetoothConnectionMonitorOptionsFlow:
        """Return the options flow."""
        return BluetoothConnectionMonitorOptionsFlow()

    def __init__(self) -> None:
        self._selected_address: str | None = None
        self._selected_bluetooth_name: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Offer detected allocations, manual entry or slot monitoring."""
        return self.async_show_menu(
            step_id="user",
            menu_options=["detected", "manual", "connection_slots"],
        )

    async def async_step_detected(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select from currently allocated Bluetooth devices."""
        if user_input is not None:
            return await self._async_select_address(str(user_input[CONF_ADDRESS]))

        choices = self._allocation_choices()
        if not choices:
            return self.async_abort(reason="no_allocated_devices")

        return self.async_show_form(
            step_id="detected",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(value=address, label=label)
                                for address, label in choices.items()
                            ],
                            mode=selector.SelectSelectorMode.DROPDOWN,
                            sort=True,
                        )
                    )
                }
            ),
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Enter a Bluetooth address manually."""
        errors: dict[str, str] = {}
        if user_input is not None:
            address = _normalize_address(str(user_input[CONF_ADDRESS]))
            if _MAC_RE.fullmatch(address):
                return await self._async_select_address(address)
            errors[CONF_ADDRESS] = "invalid_address"

        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.TEXT,
                            autocomplete="off",
                        )
                    )
                }
            ),
            errors=errors,
        )

    async def async_step_connection_slots(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Monitor the free connection slots of every Bluetooth source."""
        await self.async_set_unique_id(SLOTS_UNIQUE_ID)
        self._abort_if_unique_id_configured(error="slots_already_configured")

        if user_input is not None:
            return self.async_create_entry(
                title=SLOTS_TITLE,
                data={CONF_ENTRY_TYPE: ENTRY_TYPE_SLOTS},
            )
        return self.async_show_form(step_id="connection_slots")

    async def _async_select_address(self, address: str) -> ConfigFlowResult:
        self._selected_address = address.upper()
        self._selected_bluetooth_name = _async_bluetooth_names(self.hass).get(
            self._selected_address
        )
        return await self.async_step_name()

    async def async_step_name(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm a friendly name."""
        assert self._selected_address is not None
        await self.async_set_unique_id(self._selected_address)
        self._abort_if_unique_id_configured()

        errors: dict[str, str] = {}
        if user_input is not None:
            name = str(user_input[CONF_NAME]).strip()
            device_id = user_input.get(CONF_DEVICE_ID)
            if not name:
                errors[CONF_NAME] = "empty_name"
            _validate_device(self.hass, device_id, CONF_DEVICE_ID, errors)
            if not errors:
                return self.async_create_entry(
                    title=name,
                    data={
                        CONF_ENTRY_TYPE: ENTRY_TYPE_DEVICE,
                        CONF_ADDRESS: self._selected_address,
                        CONF_BLUETOOTH_NAME: self._selected_bluetooth_name,
                    },
                    options={CONF_DEVICE_ID: device_id} if device_id else {},
                )

        return self.async_show_form(
            step_id="name",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_NAME,
                        default=self._suggested_name(),
                    ): selector.TextSelector(),
                    **_device_schema_field(CONF_DEVICE_ID),
                }
            ),
            errors=errors,
            description_placeholders={
                "address": self._selected_address,
                "bluetooth_name": self._selected_bluetooth_name or "",
            },
        )

    def _allocation_choices(self) -> dict[str, str]:
        """Build user-friendly choices from current slot allocations.

        Addresses that are already monitored are left out.
        """
        configured = self._async_current_ids(include_ignore=False)
        names = _async_bluetooth_names(self.hass)
        source_names = async_source_names(self.hass)
        sources_by_address: dict[str, list[str]] = {}
        for allocation in _async_current_allocations():
            for address in allocation.allocated:
                if address not in configured:
                    sources_by_address.setdefault(address, []).append(allocation.source)

        choices: dict[str, str] = {}
        for address, sources in sources_by_address.items():
            name = names.get(address)
            readable_sources = [source_names.get(source, source) for source in sources]
            prefix = f"{name} — " if name else ""
            choices[address] = f"{prefix}{address} — {', '.join(readable_sources)}"
        return choices

    def _suggested_name(self) -> str:
        """Choose a readable default while keeping it user-editable."""
        if self._selected_bluetooth_name:
            return self._selected_bluetooth_name
        assert self._selected_address is not None
        return f"Bluetooth device {self._selected_address}"


class BluetoothConnectionMonitorOptionsFlow(OptionsFlowWithReload):
    """Choose the devices the sensors are shown on."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the options of the entry type."""
        if self.config_entry.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_SLOTS:
            return await self.async_step_slots()
        return await self.async_step_device()

    async def async_step_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose the device of a monitored Bluetooth address."""
        errors: dict[str, str] = {}
        if user_input is not None:
            device_id = user_input.get(CONF_DEVICE_ID)
            _validate_device(self.hass, device_id, CONF_DEVICE_ID, errors)
            if not errors:
                return self.async_create_entry(
                    data={CONF_DEVICE_ID: device_id} if device_id else {}
                )

        address = str(self.config_entry.data[CONF_ADDRESS])
        return self.async_show_form(
            step_id="device",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(_device_schema_field(CONF_DEVICE_ID)),
                user_input or self.config_entry.options,
            ),
            errors=errors,
            description_placeholders={
                "address": address,
                "current_device": self._current_device_name(address),
            },
        )

    async def async_step_slots(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose the device of each Bluetooth adapter or proxy."""
        current: dict[str, str] = dict(
            self.config_entry.options.get(CONF_DEVICE_LINKS, {})
        )
        sources = set(current)
        if (hub := self.hass.data.get(DATA_HUB)) is not None:
            sources.update(allocation.source for allocation in hub.slot_sources())
        if not sources:
            return self.async_abort(reason="no_slot_sources")

        # Field keys are shown as labels; the sources are only known at runtime,
        # so they cannot have translations.
        names = async_source_names(self.hass)
        fields = {
            format_source(source, names.get(source, source)): source
            for source in sorted(sources)
        }

        errors: dict[str, str] = {}
        if user_input is not None:
            links: dict[str, str] = {}
            for key, source in fields.items():
                if device_id := user_input.get(key):
                    _validate_device(self.hass, device_id, key, errors)
                    links[source] = device_id
            if not errors:
                return self.async_create_entry(
                    data={CONF_DEVICE_LINKS: links} if links else {}
                )

        schema: dict[vol.Optional, selector.DeviceSelector] = {}
        for key in fields:
            schema.update(_device_schema_field(key))
        suggested = user_input or {
            key: current[source] for key, source in fields.items() if source in current
        }
        return self.async_show_form(
            step_id="slots",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(schema), suggested
            ),
            errors=errors,
        )

    @callback
    def _current_device_name(self, address: str) -> str:
        """Return the name of the device the sensor is currently shown on."""
        runtime_data = getattr(self.config_entry, "runtime_data", None)
        linked_device_id = (
            runtime_data.links.get(address.upper()) if runtime_data else None
        )
        if linked_device_id is None:
            return "-"
        device = dr.async_get(self.hass).async_get(linked_device_id)
        if device is None:
            return "-"
        return device.name_by_user or device.name or linked_device_id
