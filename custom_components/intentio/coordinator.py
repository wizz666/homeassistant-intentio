"""Intentio coordinator — entity discovery, LLM generation, bundle management."""
from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
from datetime import datetime
from pathlib import Path

import aiohttp
import yaml

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .const import (
    CONF_AI_KEY,
    CONF_AI_PROVIDER,
    CONF_AI_BASE_URL,
    CONF_AI_MODEL,
    PROVIDER_PRESETS,
    RELEVANT_DOMAINS,
    SYSTEM_PROMPT,
)

_LOGGER = logging.getLogger(__name__)

BUNDLE_STATUS_PENDING = "pending"
BUNDLE_STATUS_DEPLOYED = "deployed"
BUNDLE_STATUS_REJECTED = "rejected"


class IntentioCoordinator:
    """Manages intention bundles: generate, deploy, feedback, improve."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.status: str = "idle"
        self.bundles: list[dict] = []
        self._bundles_file = Path(hass.config.path(".intentio_bundles.json"))
        self._automations_file = Path(hass.config.path("intentio_automations.yaml"))
        self._listeners: list = []

    # ── Listeners ─────────────────────────────────────────────────────────────

    def async_add_listener(self, cb) -> None:
        self._listeners.append(cb)

    def _notify(self) -> None:
        for cb in self._listeners:
            cb()

    # ── Persistence ───────────────────────────────────────────────────────────

    async def async_load(self) -> None:
        try:
            text = await asyncio.get_event_loop().run_in_executor(
                None, self._bundles_file.read_text
            )
            self.bundles = json.loads(text)
        except Exception:
            self.bundles = []

    async def _save(self) -> None:
        data = json.dumps(self.bundles, ensure_ascii=False, indent=2)
        await asyncio.get_event_loop().run_in_executor(
            None, lambda: self._bundles_file.write_text(data, encoding="utf-8")
        )

    # ── Entity discovery ──────────────────────────────────────────────────────

    def _get_entity_summary(self) -> dict[str, list[dict]]:
        """Return relevant entities grouped by domain for the LLM."""
        result: dict[str, list[dict]] = {}
        for state in self.hass.states.async_all():
            domain = state.entity_id.split(".")[0]
            if domain not in RELEVANT_DOMAINS:
                continue
            result.setdefault(domain, []).append({
                "entity_id": state.entity_id,
                "name": state.attributes.get("friendly_name", state.entity_id),
                "state": state.state,
            })
        return result

    # ── AI calls ──────────────────────────────────────────────────────────────

    def _resolve_provider(self) -> tuple[str, str, str, str]:
        data = self.entry.data
        opts = self.entry.options
        provider = opts.get(CONF_AI_PROVIDER, data.get(CONF_AI_PROVIDER, "groq"))
        api_key = opts.get(CONF_AI_KEY, data.get(CONF_AI_KEY, ""))
        base_url = opts.get(CONF_AI_BASE_URL, data.get(CONF_AI_BASE_URL, ""))
        model = opts.get(CONF_AI_MODEL, data.get(CONF_AI_MODEL, ""))
        preset = PROVIDER_PRESETS.get(provider, {})
        if not base_url:
            base_url = preset.get("base_url", "")
        if not model:
            model = preset.get("model", "llama-3.3-70b-versatile")
        if not api_key and "api_key" in preset:
            api_key = preset["api_key"]
        return provider, api_key, base_url, model

    async def _call_llm(self, prompt: str) -> str:
        provider, api_key, base_url, model = self._resolve_provider()

        if provider == "anthropic":
            return await self._call_anthropic(api_key, prompt)

        if not base_url:
            raise ValueError(f"No base URL for provider '{provider}'")

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        body = {
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.3,
            "max_tokens": 3000,
            "response_format": {"type": "json_object"},
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(
                base_url.rstrip("/") + "/chat/completions",
                headers=headers,
                json=body,
                timeout=aiohttp.ClientTimeout(total=90),
            ) as resp:
                data = await resp.json()
        return data["choices"][0]["message"]["content"]

    async def _call_anthropic(self, api_key: str, prompt: str) -> str:
        headers = {
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        }
        body = {
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 3000,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": prompt}],
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=body,
                timeout=aiohttp.ClientTimeout(total=90),
            ) as resp:
                data = await resp.json()
        return data["content"][0]["text"]

    @staticmethod
    def _extract_json(text) -> dict:
        if isinstance(text, dict):
            return text
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            pass
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group())
        raise ValueError(f"No JSON in response: {text[:300]}")

    # ── Main: generate bundle from intention ──────────────────────────────────

    async def async_generate(self, intention: str) -> str:
        """Generate a bundle from a natural language intention. Returns bundle_id."""
        self.status = "thinking"
        self._notify()

        entities = self._get_entity_summary()
        entity_count = sum(len(v) for v in entities.values())

        prompt = (
            f"User intention: {intention}\n\n"
            f"Available entities ({entity_count} total):\n"
            f"{json.dumps(entities, ensure_ascii=False, indent=2)}"
        )

        # Add feedback context if any bundles have feedback
        feedback_context = self._build_feedback_context()
        if feedback_context:
            prompt += f"\n\nPrevious automation feedback from this home:\n{feedback_context}"

        try:
            raw = await self._call_llm(prompt)
            parsed = self._extract_json(raw)
        except Exception as e:
            _LOGGER.error("Intentio: LLM call failed: %s", e)
            self.status = "error"
            self._notify()
            raise

        bundle_id = str(uuid.uuid4())[:8]
        bundle = {
            "id": bundle_id,
            "intention": intention,
            "bundle_name": parsed.get("bundle_name", intention[:40]),
            "description": parsed.get("description", ""),
            "automations": parsed.get("automations", []),
            "status": BUNDLE_STATUS_PENDING,
            "feedback": None,
            "created_at": datetime.now().isoformat(),
            "deployed_at": None,
        }

        self.bundles.insert(0, bundle)
        await self._save()
        self.status = "idle"
        _LOGGER.info(
            "Intentio: generated bundle '%s' with %d automations",
            bundle["bundle_name"],
            len(bundle["automations"]),
        )
        self._notify()
        return bundle_id

    # ── Deploy ────────────────────────────────────────────────────────────────

    async def async_deploy(self, bundle_id: str) -> None:
        """Write automations to file and reload."""
        bundle = self._get_bundle(bundle_id)
        if not bundle:
            _LOGGER.warning("Intentio: bundle %s not found", bundle_id)
            return

        # Build YAML for all deployed bundles
        await self._rewrite_automations_file()

        bundle["status"] = BUNDLE_STATUS_DEPLOYED
        bundle["deployed_at"] = datetime.now().isoformat()
        await self._save()

        # Reload automations
        await self.hass.services.async_call("automation", "reload")

        self.hass.components.persistent_notification.async_create(
            title=f"Intentio: '{bundle['bundle_name']}' deployed",
            message=(
                f"{bundle['description']}\n\n"
                f"**{len(bundle['automations'])} automations** added.\n\n"
                f"ℹ️ Make sure `intentio_automations.yaml` is included in your "
                f"`configuration.yaml` for the automations to be active. "
                f"See the [README](https://github.com/wizz666/homeassistant-intentio) for setup."
            ),
            notification_id=f"intentio_{bundle_id}_deployed",
        )
        self._notify()

    async def _rewrite_automations_file(self) -> None:
        """Rebuild the automations YAML file from all deployed bundles."""
        all_automations = []
        for bundle in self.bundles:
            if bundle["status"] == BUNDLE_STATUS_DEPLOYED:
                for auto in bundle.get("automations", []):
                    # Ensure the automation has the bundle ID in metadata
                    auto_copy = dict(auto)
                    auto_copy["description"] = (
                        f"[Intentio:{bundle['id']}] {auto_copy.get('description', '')}"
                    )
                    all_automations.append(auto_copy)

        yaml_text = yaml.dump(
            all_automations,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
        ) if all_automations else "# No Intentio automations deployed yet\n"

        header = (
            "# Intentio Automations — auto-generated, do not edit manually\n"
            "# Managed by the Intentio integration\n\n"
        )
        content = header + yaml_text
        await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self._automations_file.write_text(content, encoding="utf-8"),
        )

    # ── Reject ────────────────────────────────────────────────────────────────

    async def async_reject(self, bundle_id: str) -> None:
        bundle = self._get_bundle(bundle_id)
        if not bundle:
            return
        bundle["status"] = BUNDLE_STATUS_REJECTED
        await self._save()
        self._notify()

    # ── Feedback ──────────────────────────────────────────────────────────────

    async def async_feedback(self, bundle_id: str, rating: str) -> None:
        """Rate a deployed bundle: 'good' or 'bad'."""
        bundle = self._get_bundle(bundle_id)
        if not bundle:
            return
        bundle["feedback"] = rating
        await self._save()
        self._notify()
        _LOGGER.info("Intentio: feedback '%s' for bundle %s", rating, bundle_id)

    # ── Improve ───────────────────────────────────────────────────────────────

    async def async_improve(self, bundle_id: str) -> str:
        """Regenerate a bundle using original intention + feedback context."""
        bundle = self._get_bundle(bundle_id)
        if not bundle:
            raise ValueError(f"Bundle {bundle_id} not found")

        intention = bundle["intention"]
        original_automations = bundle.get("automations", [])
        feedback = bundle.get("feedback", "")

        improve_prompt = (
            f"Original intention: {intention}\n\n"
            f"Previous automations generated:\n"
            f"{json.dumps(original_automations, ensure_ascii=False, indent=2)}\n\n"
            f"User feedback: {feedback or 'needs improvement'}\n\n"
            f"Generate an improved bundle. Keep what worked, fix what didn't."
        )

        entities = self._get_entity_summary()
        entity_count = sum(len(v) for v in entities.values())
        improve_prompt += (
            f"\n\nAvailable entities ({entity_count} total):\n"
            f"{json.dumps(entities, ensure_ascii=False, indent=2)}"
        )

        # Mark old bundle as rejected
        bundle["status"] = BUNDLE_STATUS_REJECTED
        await self._save()
        await self._rewrite_automations_file()
        await self.hass.services.async_call("automation", "reload")

        # Generate new bundle with original intention
        new_id = await self.async_generate(intention)
        return new_id

    # ── Delete ────────────────────────────────────────────────────────────────

    async def async_delete(self, bundle_id: str) -> None:
        """Remove a bundle and redeploy remaining automations."""
        self.bundles = [b for b in self.bundles if b["id"] != bundle_id]
        await self._save()
        await self._rewrite_automations_file()
        await self.hass.services.async_call("automation", "reload")
        self._notify()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _get_bundle(self, bundle_id: str) -> dict | None:
        return next((b for b in self.bundles if b["id"] == bundle_id), None)

    def _build_feedback_context(self) -> str:
        lines = []
        for b in self.bundles:
            if b.get("feedback"):
                lines.append(
                    f"- '{b['intention']}' → {b['feedback']} "
                    f"({b['bundle_name']})"
                )
        return "\n".join(lines[:5])  # max 5 examples

    @property
    def pending_bundles(self) -> list[dict]:
        return [b for b in self.bundles if b["status"] == BUNDLE_STATUS_PENDING]

    @property
    def deployed_bundles(self) -> list[dict]:
        return [b for b in self.bundles if b["status"] == BUNDLE_STATUS_DEPLOYED]
