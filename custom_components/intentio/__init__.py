"""Intentio — Intent-based automation for Home Assistant."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .coordinator import IntentioCoordinator

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    coordinator = IntentioCoordinator(hass, entry)
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    _register_services(hass, coordinator)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        _unregister_services(hass)
    return unloaded


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


def _register_services(hass: HomeAssistant, coordinator: IntentioCoordinator) -> None:

    async def handle_create(call: ServiceCall) -> None:
        intention = call.data["intention"]
        try:
            bundle_id = await coordinator.async_generate(intention)
            hass.components.persistent_notification.async_create(
                title="Intentio: Bundle ready for review",
                message=(
                    f"**Intention:** {intention}\n\n"
                    f"A bundle of automations has been generated. "
                    f"Review it in the Intentio dashboard and deploy when ready.\n\n"
                    f"Bundle ID: `{bundle_id}`"
                ),
                notification_id=f"intentio_{bundle_id}_ready",
            )
        except Exception as e:
            hass.components.persistent_notification.async_create(
                title="Intentio: Generation failed",
                message=f"Could not generate automations: {e}",
                notification_id="intentio_error",
            )

    async def handle_deploy(call: ServiceCall) -> None:
        bundle_id = call.data["bundle_id"]
        await coordinator.async_deploy(bundle_id)

    async def handle_reject(call: ServiceCall) -> None:
        bundle_id = call.data["bundle_id"]
        await coordinator.async_reject(bundle_id)

    async def handle_feedback(call: ServiceCall) -> None:
        bundle_id = call.data["bundle_id"]
        rating = call.data["rating"]
        await coordinator.async_feedback(bundle_id, rating)

    async def handle_improve(call: ServiceCall) -> None:
        bundle_id = call.data["bundle_id"]
        try:
            new_id = await coordinator.async_improve(bundle_id)
            hass.components.persistent_notification.async_create(
                title="Intentio: Improved bundle ready",
                message=(
                    f"An improved bundle has been generated based on your feedback.\n\n"
                    f"New bundle ID: `{new_id}`"
                ),
                notification_id=f"intentio_{new_id}_ready",
            )
        except Exception as e:
            hass.components.persistent_notification.async_create(
                title="Intentio: Improvement failed",
                message=str(e),
                notification_id="intentio_error",
            )

    async def handle_delete(call: ServiceCall) -> None:
        bundle_id = call.data["bundle_id"]
        await coordinator.async_delete(bundle_id)

    hass.services.async_register(
        DOMAIN, "create",
        handle_create,
        schema=vol.Schema({vol.Required("intention"): cv.string}),
    )
    hass.services.async_register(
        DOMAIN, "deploy",
        handle_deploy,
        schema=vol.Schema({vol.Required("bundle_id"): cv.string}),
    )
    hass.services.async_register(
        DOMAIN, "reject",
        handle_reject,
        schema=vol.Schema({vol.Required("bundle_id"): cv.string}),
    )
    hass.services.async_register(
        DOMAIN, "feedback",
        handle_feedback,
        schema=vol.Schema({
            vol.Required("bundle_id"): cv.string,
            vol.Required("rating"): vol.In(["good", "bad"]),
        }),
    )
    hass.services.async_register(
        DOMAIN, "improve",
        handle_improve,
        schema=vol.Schema({vol.Required("bundle_id"): cv.string}),
    )
    hass.services.async_register(
        DOMAIN, "delete",
        handle_delete,
        schema=vol.Schema({vol.Required("bundle_id"): cv.string}),
    )


def _unregister_services(hass: HomeAssistant) -> None:
    for svc in ("create", "deploy", "reject", "feedback", "improve", "delete"):
        hass.services.async_remove(DOMAIN, svc)
