"""Constants for Intentio."""

DOMAIN = "intentio"
VERSION = "1.0.0"

CONF_AI_PROVIDER = "ai_provider"
CONF_AI_KEY = "ai_key"
CONF_AI_BASE_URL = "ai_base_url"
CONF_AI_MODEL = "ai_model"

DEFAULT_PROVIDER = "groq"

PROVIDERS = ["groq", "openrouter", "ollama", "lmstudio", "openai", "anthropic", "custom"]

PROVIDER_PRESETS = {
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "model": "llama-3.3-70b-versatile",
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "model": "meta-llama/llama-3.3-70b-instruct:free",
    },
    "ollama": {
        "base_url": "http://localhost:11434/v1",
        "model": "llama3.2:latest",
        "api_key": "ollama",
    },
    "lmstudio": {
        "base_url": "http://localhost:1234/v1",
        "model": "local-model",
        "api_key": "lm-studio",
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
    },
}

# Entity domains to expose to the LLM
RELEVANT_DOMAINS = (
    "light", "switch", "lock", "sensor", "binary_sensor",
    "climate", "media_player", "cover", "alarm_control_panel",
    "input_boolean", "fan", "scene",
)

SYSTEM_PROMPT = """You are a Home Assistant automation expert. The user describes a home automation GOAL or INTENTION in plain language. You generate a coordinated bundle of 2-6 Home Assistant automations that together achieve that goal.

Available entities are provided as a JSON list. Only use entity_ids from that list.

ALWAYS respond with valid JSON in exactly this format:
{
  "bundle_name": "Short descriptive name (max 40 chars)",
  "description": "What this bundle does in 1-2 sentences",
  "automations": [
    {
      "id": "intentio_<snake_case_id>",
      "alias": "Intentio: <Human readable name>",
      "description": "What this specific automation does",
      "trigger": [ ... ],
      "condition": [ ... ],
      "action": [ ... ],
      "mode": "single"
    }
  ]
}

Rules:
- Generate 2-6 complementary automations that work together as a system
- Each automation must be complete and immediately deployable in Home Assistant
- Use only entity_ids from the provided entity list
- All automation IDs must start with "intentio_"
- All aliases must start with "Intentio: "
- Use proper HA automation YAML structure (trigger/condition/action arrays)
- For time-based triggers use platform: time or platform: sun
- Keep each automation focused on one specific behavior
- Prefer robust patterns: use for: delays on motion, use conditions to prevent conflicts"""
