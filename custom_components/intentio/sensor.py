"""Intentio sensors."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import IntentioCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: IntentioCoordinator = hass.data[DOMAIN][entry.entry_id]
    await coordinator.async_load()
    async_add_entities([
        IntentioStatusSensor(coordinator, entry),
        IntenzioPendingSensor(coordinator, entry),
        IntentioDeployedSensor(coordinator, entry),
    ])


class _IntentioBaseSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, coordinator: IntentioCoordinator, entry: ConfigEntry) -> None:
        self._coordinator = coordinator
        self._entry = entry

    async def async_added_to_hass(self) -> None:
        self._coordinator.async_add_listener(self._handle_update)

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()

    @property
    def device_info(self) -> dict:
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": "Intentio",
            "manufacturer": "Intentio",
            "model": "Intent-based Automation",
            "entry_type": "service",
        }


class IntentioStatusSensor(_IntentioBaseSensor):
    _attr_icon = "mdi:brain"

    def __init__(self, coordinator: IntentioCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_status"
        self._attr_name = "Status"

    @property
    def native_value(self) -> str:
        return self._coordinator.status

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "total_bundles": len(self._coordinator.bundles),
            "pending": len(self._coordinator.pending_bundles),
            "deployed": len(self._coordinator.deployed_bundles),
        }


class IntenzioPendingSensor(_IntentioBaseSensor):
    _attr_icon = "mdi:lightbulb-auto-outline"
    _attr_native_unit_of_measurement = "bundles"

    def __init__(self, coordinator: IntentioCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_pending"
        self._attr_name = "Pending bundles"

    @property
    def native_value(self) -> int:
        return len(self._coordinator.pending_bundles)

    @property
    def extra_state_attributes(self) -> dict:
        pending = self._coordinator.pending_bundles
        result = {"bundles": []}
        for b in pending:
            result["bundles"].append({
                "id": b["id"],
                "bundle_name": b["bundle_name"],
                "intention": b["intention"],
                "description": b["description"],
                "automation_count": len(b.get("automations", [])),
                "created_at": b["created_at"],
                "automations": b.get("automations", []),
            })
        return result


class IntentioDeployedSensor(_IntentioBaseSensor):
    _attr_icon = "mdi:robot-happy-outline"
    _attr_native_unit_of_measurement = "bundles"

    def __init__(self, coordinator: IntentioCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_deployed"
        self._attr_name = "Deployed bundles"

    @property
    def native_value(self) -> int:
        return len(self._coordinator.deployed_bundles)

    @property
    def extra_state_attributes(self) -> dict:
        deployed = self._coordinator.deployed_bundles
        result = {"bundles": []}
        for b in deployed:
            result["bundles"].append({
                "id": b["id"],
                "bundle_name": b["bundle_name"],
                "intention": b["intention"],
                "description": b["description"],
                "automation_count": len(b.get("automations", [])),
                "deployed_at": b.get("deployed_at"),
                "feedback": b.get("feedback"),
            })
        return result
