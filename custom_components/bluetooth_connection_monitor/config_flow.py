"""Config flow for Bluetooth Connection Monitor."""

from __future__ import annotations

import re
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.bluetooth import (
    async_current_scanners,
    async_discovered_service_info,
)
from habluetooth import get_manager
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.helpers import selector

from .const import CONF_ADDRESS, CONF_BLUETOOTH_NAME, CONF_NAME, DOMAIN

_MAC_RE = re.compile(r"^(?:[0-9A-F]{2}:){5}[0-9A-F]{2}$")


class BluetoothConnectionMonitorConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Bluetooth Connection Monitor."""

    VERSION = 1

    def __init__(self) -> None:
        self._selected_address: str | None = None
        self._selected_bluetooth_name: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Offer detected allocations or manual entry."""
        return self.async_show_menu(
            step_id="user",
            menu_options=["detected", "manual"],
        )

    async def async_step_detected(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select from currently allocated Bluetooth devices."""
        choices = self._allocation_choices()
        if not choices:
            return self.async_abort(reason="no_allocated_devices")

        if user_input is not None:
            self._selected_address = str(user_input[CONF_ADDRESS]).upper()
            self._selected_bluetooth_name = self._bluetooth_names().get(
                self._selected_address
            )
            return await self.async_step_name()

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
            address = self._normalize_address(str(user_input[CONF_ADDRESS]))
            if not _MAC_RE.fullmatch(address):
                errors[CONF_ADDRESS] = "invalid_address"
            else:
                self._selected_address = address
                self._selected_bluetooth_name = self._bluetooth_names().get(address)
                return await self.async_step_name()

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

    async def async_step_name(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm a friendly name."""
        assert self._selected_address is not None
        await self.async_set_unique_id(self._selected_address)
        self._abort_if_unique_id_configured()

        suggested_name = self._suggested_name()
        errors: dict[str, str] = {}
        if user_input is not None:
            name = str(user_input[CONF_NAME]).strip()
            if not name:
                errors[CONF_NAME] = "empty_name"
            else:
                return self.async_create_entry(
                    title=name,
                    data={
                        CONF_ADDRESS: self._selected_address,
                        CONF_BLUETOOTH_NAME: self._selected_bluetooth_name,
                    },
                )

        return self.async_show_form(
            step_id="name",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_NAME,
                        default=suggested_name,
                    ): selector.TextSelector()
                }
            ),
            errors=errors,
            description_placeholders={
                "address": self._selected_address,
                "bluetooth_name": self._selected_bluetooth_name or "",
            },
        )

    def _allocation_choices(self) -> dict[str, str]:
        """Build user-friendly choices from current slot allocations."""
        names = self._bluetooth_names()
        source_names = self._source_names()
        sources_by_address: dict[str, list[str]] = {}
        manager = get_manager()
        if not hasattr(manager, "async_current_allocations"):
            return {}
        try:
            allocations = manager.async_current_allocations(None) or []
        except Exception:
            return {}

        for allocation in allocations:
            if isinstance(allocation, dict):
                source = str(allocation.get("source", "")).upper()
                allocated = allocation.get("allocated", [])
            else:
                source = str(getattr(allocation, "source", "")).upper()
                allocated = getattr(allocation, "allocated", [])
            if not source or allocated is None:
                continue
            for address in allocated:
                normalized = str(address).upper()
                sources_by_address.setdefault(normalized, []).append(source)

        choices: dict[str, str] = {}
        for address, sources in sources_by_address.items():
            name = names.get(address)
            readable_sources = [source_names.get(source, source) for source in sources]
            prefix = f"{name} — " if name else ""
            choices[address] = (
                f"{prefix}{address} — {', '.join(readable_sources)}"
            )
        return choices

    def _bluetooth_names(self) -> dict[str, str]:
        """Return the best currently known Bluetooth name per address."""
        names: dict[str, str] = {}
        for info in async_discovered_service_info(self.hass, connectable=True):
            address = str(info.address).upper()
            name = getattr(info, "name", None)
            if name and str(name).strip():
                names[address] = str(name).strip()
        return names

    def _source_names(self) -> dict[str, str]:
        """Return friendly names for Bluetooth sources."""
        names: dict[str, str] = {}
        try:
            scanners = async_current_scanners(self.hass)
        except Exception:
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

    def _suggested_name(self) -> str:
        """Choose a readable default while keeping it user-editable."""
        if self._selected_bluetooth_name:
            return self._selected_bluetooth_name
        assert self._selected_address is not None
        return f"Bluetooth device {self._selected_address}"

    @staticmethod
    def _normalize_address(address: str) -> str:
        """Normalize common MAC-address separators."""
        return address.strip().upper().replace("-", ":")
