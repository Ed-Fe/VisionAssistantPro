# -*- coding: utf-8 -*-

import json
import logging

import addonHandler
import config

from .constants import DEFAULT_SYSTEM_PROMPTS, LEGACY_REFINER_TOKENS, REFINE_PROMPT_KEYS

addonHandler.initTranslation()
log = logging.getLogger(__name__)


def get_builtin_default_prompts():
    builtins = []
    for item in DEFAULT_SYSTEM_PROMPTS:
        p = str(item["prompt"]).strip()
        builtins.append({
            "key": item["key"],
            "section": item["section"],
            "label": item["label"],
            "display_label": f"{item['section']} - {item['label']}",
            "internal": bool(item.get("internal")),
            "prompt": p,
            "default": p,
        })
    return builtins


def get_builtin_default_prompt_map():
    return {item["key"]: item for item in get_builtin_default_prompts()}


def _normalize_custom_prompt_items(items):
    normalized = []
    if not isinstance(items, list):
        return normalized

    for item in items:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        content = item.get("content")
        if not isinstance(name, str) or not isinstance(content, str):
            continue
        name = name.strip()
        content = content.strip()
        if name and content:
            normalized.append({"name": name, "content": content})
    return normalized


def parse_custom_prompts_legacy(raw_value):
    items = []
    if not raw_value:
        return items

    normalized = raw_value.replace("\r\n", "\n").replace("\r", "\n")
    for line in normalized.split("\n"):
        for segment in line.split("|"):
            segment = segment.strip()
            if not segment or ":" not in segment:
                continue
            name, content = segment.split(":", 1)
            name = name.strip()
            content = content.strip()
            if name and content:
                items.append({"name": name, "content": content})
    return items


def parse_custom_prompts_v2(raw_value):
    if not isinstance(raw_value, str) or not raw_value.strip():
        return None
    try:
        data = json.loads(raw_value)
    except Exception as e:
        log.warning(f"Invalid custom_prompts_v2 config, falling back to legacy format: {e}")
        return None
    return _normalize_custom_prompt_items(data)


def serialize_custom_prompts_v2(items):
    normalized = _normalize_custom_prompt_items(items)
    if not normalized:
        return ""
    return json.dumps(normalized, ensure_ascii=False)


def load_configured_custom_prompts():
    try:
        raw_v2 = config.conf["VisionAssistant"]["custom_prompts_v2"]
    except Exception:
        raw_v2 = ""
    items_v2 = parse_custom_prompts_v2(raw_v2)
    if items_v2 is not None:
        return items_v2
    return parse_custom_prompts_legacy(config.conf["VisionAssistant"]["custom_prompts"])


def _sanitize_default_prompt_overrides(data):
    if not isinstance(data, dict):
        return {}, False

    changed = False
    mutable = dict(data)
    # Migrate old key used in previous versions.
    legacy_vision = mutable.pop("vision_image_analysis", None)
    if legacy_vision is not None:
        changed = True
    if isinstance(legacy_vision, str) and legacy_vision.strip():
        legacy_text = legacy_vision.strip()
        nav_value = mutable.get("vision_navigator_object")
        if not isinstance(nav_value, str) or not nav_value.strip():
            mutable["vision_navigator_object"] = legacy_text
            changed = True
        full_value = mutable.get("vision_fullscreen")
        if not isinstance(full_value, str) or not full_value.strip():
            mutable["vision_fullscreen"] = legacy_text
            changed = True

    valid_keys = set(get_builtin_default_prompt_map().keys())
    sanitized = {}
    for key, value in mutable.items():
        if key not in valid_keys or not isinstance(value, str):
            changed = True
            continue
        prompt_text = value.strip()
        if not prompt_text:
            changed = True
            continue
        if key in LEGACY_REFINER_TOKENS and prompt_text == LEGACY_REFINER_TOKENS[key]:
            # Drop old token-only overrides and fallback to current built-ins.
            changed = True
            continue
        if prompt_text != value:
            changed = True
        sanitized[key] = prompt_text
    return sanitized, changed


def migrate_prompt_config_if_needed():
    changed = False

    try:
        raw_v2 = config.conf["VisionAssistant"]["custom_prompts_v2"]
    except Exception:
        raw_v2 = ""
    raw_legacy = config.conf["VisionAssistant"]["custom_prompts"]

    v2_items = parse_custom_prompts_v2(raw_v2)
    if v2_items is None:
        target_items = parse_custom_prompts_legacy(raw_legacy)
    else:
        target_items = v2_items

    serialized_v2 = serialize_custom_prompts_v2(target_items)
    if serialized_v2 != (raw_v2 or ""):
        config.conf["VisionAssistant"]["custom_prompts_v2"] = serialized_v2
        changed = True

    # Legacy mirror is disabled. Clear old storage to prevent stale fallback data.
    if raw_legacy:
        config.conf["VisionAssistant"]["custom_prompts"] = ""
        changed = True

    try:
        raw_defaults = config.conf["VisionAssistant"]["default_refine_prompts"]
    except Exception:
        raw_defaults = ""
    if isinstance(raw_defaults, str) and raw_defaults.strip():
        try:
            defaults_data = json.loads(raw_defaults)
        except Exception:
            defaults_data = None
        if isinstance(defaults_data, dict):
            sanitized, migrated = _sanitize_default_prompt_overrides(defaults_data)
            if migrated:
                config.conf["VisionAssistant"]["default_refine_prompts"] = (
                    json.dumps(sanitized, ensure_ascii=False) if sanitized else ""
                )
                changed = True

    return changed


def load_default_prompt_overrides():
    try:
        raw = config.conf["VisionAssistant"]["default_refine_prompts"]
    except Exception:
        raw = ""
    if not isinstance(raw, str) or not raw.strip():
        return {}

    try:
        data = json.loads(raw)
    except Exception as e:
        log.warning(f"Invalid default_refine_prompts config, using built-ins: {e}")
        return {}

    overrides, _ = _sanitize_default_prompt_overrides(data)
    return overrides


def get_configured_default_prompt_map():
    prompt_map = get_builtin_default_prompt_map()
    overrides = load_default_prompt_overrides()
    for key, override in overrides.items():
        if key not in prompt_map:
            continue
        if key in LEGACY_REFINER_TOKENS and override == LEGACY_REFINER_TOKENS[key]:
            continue
        prompt_map[key]["prompt"] = override
    return prompt_map


def get_configured_default_prompts():
    prompt_map = get_configured_default_prompt_map()
    items = []
    for item in DEFAULT_SYSTEM_PROMPTS:
        if item.get("internal"):
            continue
        key = item["key"]
        if key in prompt_map:
            items.append(dict(prompt_map[key]))
    items.sort(key=lambda item: item.get("display_label", "").casefold())
    return items


def get_prompt_text(prompt_key):
    prompt_map = get_configured_default_prompt_map()
    item = prompt_map.get(prompt_key)
    if item:
        return item["prompt"]
    return ""


def serialize_default_prompt_overrides(items):
    if not items:
        return ""

    base_map = {item["key"]: item["prompt"] for item in get_builtin_default_prompts()}
    overrides = {}
    for item in items:
        key = item.get("key")
        prompt_text = item.get("prompt", "")
        if key not in base_map:
            continue
        if not isinstance(prompt_text, str):
            continue
        prompt_text = prompt_text.strip()
        if prompt_text and prompt_text != base_map[key]:
            overrides[key] = prompt_text

    if not overrides:
        return ""
    return json.dumps(overrides, ensure_ascii=False)


def get_refine_menu_options():
    options = []
    prompt_map = get_configured_default_prompt_map()
    for key in REFINE_PROMPT_KEYS:
        item = prompt_map.get(key)
        if item:
            options.append((item["label"], item["prompt"]))

    for item in load_configured_custom_prompts():
        # Translators: Prefix for custom prompts in the Refine menu
        options.append((_("Custom: ") + item["name"], item["content"]))
    return options


def apply_prompt_template(template, replacements):
    if not isinstance(template, str):
        return ""

    text = template
    for key, value in replacements:
        text = text.replace("{" + key + "}", str(value))

    return text.strip()
