# Intentio 🧠

**Intent-based automation for Home Assistant**

Instead of writing automations, you describe *goals*. Intentio uses AI to generate a coordinated bundle of automations that together achieve what you want — and you deploy them with one click.

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

---

## How it works

```
You write:   "I want the house to feel safe and cozy at night"
                          ↓
Intentio generates a bundle:
  → Dim hallway light on motion (23:00–06:00)
  → Simulate presence if nobody home (random lights 20:00–23:00)
  → Lock front door automatically at 23:00
  → Turn off non-essential lights at 23:30

You review → Deploy → Done
```

The system learns from your feedback. Rate bundles as good or bad, and use **Improve** to regenerate with that context.

---

## Features

- **Natural language goals** → multiple coordinated automations
- Works with **Groq** (free), **OpenRouter**, **Ollama**, **LM Studio**, **OpenAI**, **Anthropic**
- **Full review flow** — nothing is deployed without your approval
- **Feedback loop** — rate bundles, regenerate with improvements
- **Entity-aware** — only uses devices that actually exist in your home
- All generated automations are stored in `intentio_automations.yaml`

---

## Installation

### HACS (recommended)
1. HACS → Integrations → ⋮ → Custom repositories
2. Add `wizz666/homeassistant-intentio` as type **Integration**
3. Install **Intentio** and restart Home Assistant

### Manual
Copy `custom_components/intentio/` to your `config/custom_components/` directory and restart.

---

## One-time setup

Add this to your `configuration.yaml` so deployed automations take effect:

```yaml
automation intentio: !include intentio_automations.yaml
```

Then restart Home Assistant once. After that, deploying bundles only requires `automation.reload`.

---

## Usage

### 1. Describe a goal
Go to **Developer Tools → Services → `intentio.create`**:
```yaml
service: intentio.create
data:
  intention: "I want the house to feel safe and cozy at night"
```

### 2. Review the bundle
Check the `sensor.intentio_pending_bundles` attributes or the notification. The bundle contains the generated automations for your review.

### 3. Deploy
```yaml
service: intentio.deploy
data:
  bundle_id: "a1b2c3d4"
```

### 4. Give feedback
```yaml
service: intentio.feedback
data:
  bundle_id: "a1b2c3d4"
  rating: good  # or bad
```

### 5. Improve
```yaml
service: intentio.improve
data:
  bundle_id: "a1b2c3d4"
```

---

## Services

| Service | Description |
|---|---|
| `intentio.create` | Generate an automation bundle from a natural language intention |
| `intentio.deploy` | Deploy a pending bundle (writes to `intentio_automations.yaml` + reloads) |
| `intentio.reject` | Reject a pending bundle without deploying |
| `intentio.feedback` | Rate a bundle as `good` or `bad` |
| `intentio.improve` | Regenerate a bundle using feedback as context |
| `intentio.delete` | Remove a bundle and its automations |

---

## Sensors

| Entity | Description |
|---|---|
| `sensor.intentio_status` | `idle` / `thinking` / `error` |
| `sensor.intentio_pending_bundles` | Bundles waiting for review |
| `sensor.intentio_deployed_bundles` | Active deployed bundles |

---

## Getting a free API key

| Provider | Where | Free? |
|---|---|---|
| **Groq** | [console.groq.com](https://console.groq.com) | ✅ Generous free tier |
| **OpenRouter** | [openrouter.ai/keys](https://openrouter.ai/keys) | ✅ Several free models |
| **Ollama** | Run locally | ✅ Fully local |

---

## Notes

- Generated automations are stored in `/config/intentio_automations.yaml`
- Bundles are persisted in `/config/.intentio_bundles.json`
- Feedback is used as context for future `improve` calls — the more you use it, the better it gets
