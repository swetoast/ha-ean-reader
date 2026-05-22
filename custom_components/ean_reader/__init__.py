"""EAN Reader integration for Home Assistant."""
from __future__ import annotations

import asyncio
import logging
import re
from collections import deque
from datetime import UTC, datetime
from typing import Any

import openfoodfacts
import requests
from homeassistant.components import webhook
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, callback

from .const import (
    CONF_AUTO_ADD_TO_SHOPPING_LIST,
    CONF_CONTACT_EMAIL,
    CONF_ENABLE_WEBHOOK,
    CONF_LANGUAGE_PRIORITY,
    CONF_SHOW_IMAGES,
    CONF_SHOW_NOTIFICATIONS,
    CONF_TRACK_EXPIRY,
    CONF_TRACK_PRICES,
    DEFAULT_AUTO_ADD,
    DEFAULT_ENABLE_WEBHOOK,
    DEFAULT_LANGUAGE_PRIORITY,
    DEFAULT_SHOW_IMAGES,
    DEFAULT_SHOW_NOTIFICATIONS,
    DEFAULT_TRACK_EXPIRY,
    DEFAULT_TRACK_PRICES,
    DEFAULT_USER_EMAIL,
    DOMAIN,
    EVENT_LOOKUP_COMPLETED,
    EVENT_MAPPING_ADDED,
    EVENT_MAPPING_REMOVED,
    EVENT_MISSING_PRODUCT,
    EVENT_PRODUCT_SCANNED,
    EVENT_STATS_UPDATED,
    EVENT_TYPE,
    PLATFORMS,
    build_user_agent,
)
from .product_database import ProductData, ProductDatabase

_LOGGER = logging.getLogger(__name__)
EAN_RE = re.compile(r"^\d{8,14}$")
CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f-\x9f]")


class RateLimiter:
    """Rate limiter for OpenFoodFacts API compliance."""

    def __init__(self, max_requests: int = 12, window_seconds: int = 60):
        """Initialize rate limiter."""
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Wait until a request slot is available."""
        async with self._lock:
            now = datetime.now(UTC).timestamp()
            
            while self.requests and self.requests[0] < now - self.window_seconds:
                self.requests.popleft()
            
            if len(self.requests) >= self.max_requests:
                sleep_time = self.window_seconds - (now - self.requests[0]) + 0.1
                _LOGGER.debug(
                    "Rate limit reached (%d/%d), waiting %.1f seconds",
                    len(self.requests),
                    self.max_requests,
                    sleep_time,
                )
                await asyncio.sleep(sleep_time)
                
                now = datetime.now(UTC).timestamp()
                while self.requests and self.requests[0] < now - self.window_seconds:
                    self.requests.popleft()
            
            self.requests.append(now)
            
            if len(self.requests) > self.max_requests * 0.8:
                _LOGGER.warning(
                    "Approaching rate limit: %d/%d requests in last %d seconds",
                    len(self.requests),
                    self.max_requests,
                    self.window_seconds,
                )


_RATE_LIMITER = RateLimiter(max_requests=12, window_seconds=60)


def _clean_ean(value: Any) -> str:
    """Remove non-digit characters from EAN."""
    return re.sub(r"\D", "", str(value or ""))


def _valid_ean(ean: str) -> bool:
    """Check if EAN format is valid (8-14 digits)."""
    return bool(EAN_RE.match(ean))


def _sanitize_text(text: str) -> str:
    """Remove potentially harmful characters from text."""
    if not isinstance(text, str):
        return ""
    cleaned = CONTROL_CHARS_RE.sub("", text)
    return " ".join(cleaned.split())


def _first_text(*values: Any) -> str | None:
    """Return first non-empty string value."""
    for value in values:
        if isinstance(value, str):
            cleaned = _sanitize_text(value)
            if cleaned:
                return cleaned
    return None


def _display_name(product: dict[str, Any], lang_priority: list[str]) -> str | None:
    """Build display name from product data with language priority."""
    name_keys = [f"product_name_{lang}" for lang in lang_priority]
    name_keys.extend(["product_name", "generic_name"])

    name = _first_text(*[product.get(key) for key in name_keys])
    if not name:
        return None

    brand = _first_text(product.get("brands"))
    quantity = _first_text(product.get("quantity"))

    if brand and brand.lower() not in name.lower():
        name = f"{brand} - {name}"

    if quantity and quantity.lower() not in name.lower():
        name = f"{name} ({quantity})"

    return name


async def _lookup_openfoodfacts(
    hass: HomeAssistant, ean: str, lang_priority: list[str], show_images: bool = True
) -> dict[str, Any] | None:
    """Look up product in OpenFoodFacts using official library."""
    await _RATE_LIMITER.acquire()

    config = hass.data[DOMAIN]["config"]
    email = config.get(CONF_CONTACT_EMAIL, DEFAULT_USER_EMAIL)
    user_agent = build_user_agent(email)

    fields = [
        "code", "product_name", "generic_name", "brands", "quantity",
        "categories", "categories_tags",
        "ingredients_text", "allergens", "traces", "additives_tags",
        "nutrition_grades", "nutriments",
        "image_url", "image_small_url", "image_front_url", 
        "image_ingredients_url", "image_nutrition_url",
        "labels", "labels_tags", "eco_score_grade", "nova_group",
        "origins", "manufacturing_places", "countries", "stores",
        "completeness", "last_modified_t",
        # Serving & packaging
        "serving_size", "serving_quantity",
        "packaging", "packaging_tags",
        "recycling_instructions_to_recycle",
        # Ingredients analysis
        "ingredients_from_palm_oil_tags",
        "ingredients_analysis_tags",
        # Environmental
        "carbon-footprint_100g",
    ]
    
    for lang in lang_priority:
        fields.append(f"product_name_{lang}")

    def _sync_lookup():
        try:
            api = openfoodfacts.API(
                user_agent=user_agent,
                country="world",
                flavor="off",
                version="v2",
                environment="org",
            )
            
            product = api.product.get(ean, fields=fields)
            return product

        except requests.exceptions.HTTPError as err:
            if err.response.status_code == 503:
                _LOGGER.warning("OpenFoodFacts rate limit (HTTP 503). EAN: %s", ean)
                return {"_rate_limited": True}
            raise
        except Exception as err:
            _LOGGER.debug("OpenFoodFacts lookup failed for %s: %s", ean, err)
            return None

    product = await hass.async_add_executor_job(_sync_lookup)

    if product and product.get("_rate_limited"):
        return None

    return product


async def _notify_missing_product(
    hass: HomeAssistant, ean: str, show_notifications: bool
) -> None:
    """Create persistent notification for missing product."""
    if not show_notifications or not hass.services.has_service(
        "persistent_notification", "create"
    ):
        return

    message = (
        f"OpenFoodFacts had no product name for EAN `{ean}`.\n\n"
        "Add it to your local database with:\n\n"
        "```yaml\n"
        "service: ean_reader.add_last_missing_mapping\n"
        "data:\n"
        "  name: \"Product name here\"\n"
        "  add_to_shopping_list: true\n"
        "```"
    )

    await hass.services.async_call(
        "persistent_notification",
        "create",
        {
            "title": "EAN Reader: Unknown product",
            "message": message,
            "notification_id": f"{DOMAIN}_missing_{ean}",
        },
        blocking=False,
    )


async def _notify_success(
    hass: HomeAssistant, name: str, show_notifications: bool
) -> None:
    """Create success notification."""
    if not show_notifications or not hass.services.has_service(
        "persistent_notification", "create"
    ):
        return

    await hass.services.async_call(
        "persistent_notification",
        "create",
        {
            "title": "EAN Reader",
            "message": f"Added '{name}' to shopping list",
            "notification_id": f"{DOMAIN}_success",
        },
        blocking=False,
    )


async def _resolve_name(
    hass: HomeAssistant,
    db: ProductDatabase,
    ean: str,
    config: dict[str, Any],
) -> tuple[str | None, str]:
    """Resolve product name from local DB or OpenFoodFacts."""
    product = db.get_product(ean)
    if product:
        await db.async_increment_scan("local")
        return product.product_name, "local"

    if await db.async_is_known_missing(ean):
        _LOGGER.debug("EAN %s is known missing, skipping API call", ean)
        return None, "cached_missing"

    lang_priority = config.get(CONF_LANGUAGE_PRIORITY, DEFAULT_LANGUAGE_PRIORITY)
    show_images = config.get(CONF_SHOW_IMAGES, DEFAULT_SHOW_IMAGES)
    
    try:
        api_data = await _lookup_openfoodfacts(hass, ean, lang_priority, show_images)
    except requests.exceptions.HTTPError as err:
        if err.response.status_code == 503:
            hass.data[DOMAIN]["diagnostics"]["last_error"] = "Rate limit exceeded (HTTP 503)"
            hass.data[DOMAIN]["diagnostics"]["last_error_time"] = datetime.now(UTC).isoformat()
            hass.data[DOMAIN]["diagnostics"]["rate_limited_count"] += 1
            _LOGGER.warning("Rate limited by OpenFoodFacts API. EAN: %s", ean)
            return None, "rate_limited"
        hass.data[DOMAIN]["diagnostics"]["last_error"] = f"HTTP {err.response.status_code}: {err}"
        hass.data[DOMAIN]["diagnostics"]["last_error_time"] = datetime.now(UTC).isoformat()
        hass.data[DOMAIN]["diagnostics"]["error_count"] += 1
        _LOGGER.error("HTTP error looking up EAN %s: %s", ean, err)
        return None, "error"
    except Exception as err:
        hass.data[DOMAIN]["diagnostics"]["last_error"] = str(err)
        hass.data[DOMAIN]["diagnostics"]["last_error_time"] = datetime.now(UTC).isoformat()
        hass.data[DOMAIN]["diagnostics"]["error_count"] += 1
        _LOGGER.error("Unexpected error looking up EAN %s: %s", ean, err)
        return None, "error"

    if not api_data:
        unknown = await db.async_mark_unknown(ean)
        hass.bus.async_fire(
            EVENT_MISSING_PRODUCT,
            {"ean": ean, "source": "openfoodfacts", "seen_count": unknown.seen_count},
        )
        hass.bus.async_fire(
            EVENT_LOOKUP_COMPLETED,
            {"ean": ean, "found": False, "name": None, "source": "openfoodfacts"},
        )
        show_notifications = config.get(CONF_SHOW_NOTIFICATIONS, DEFAULT_SHOW_NOTIFICATIONS)
        await _notify_missing_product(hass, ean, show_notifications)
        hass.bus.async_fire(EVENT_STATS_UPDATED, {})
        return None, "missing"

    name = _display_name(api_data, lang_priority)
    if not name:
        await db.async_mark_unknown(ean)
        return None, "missing"
    
    nutriments = api_data.get("nutriments", {})
    labels_tags = api_data.get("labels_tags", [])
    additives_tags = api_data.get("additives_tags", [])
    packaging_tags = api_data.get("packaging_tags", [])
    palm_oil_tags = api_data.get("ingredients_from_palm_oil_tags", [])
    
    # Parse ingredients analysis
    ingredients_analysis = api_data.get("ingredients_analysis_tags", [])
    vegan = "maybe"
    vegetarian = "maybe"
    palm_oil_free = "maybe"
    
    for tag in ingredients_analysis:
        if "vegan" in tag:
            vegan = "yes" if "en:vegan" in tag else "no"
        if "vegetarian" in tag:
            vegetarian = "yes" if "en:vegetarian" in tag else "no"
        if "palm" in tag:
            palm_oil_free = "no" if "en:palm-oil" in tag else "yes"
    
    product_data = ProductData(
        ean=ean,
        product_name=name,
        source="openfoodfacts",
        brands=api_data.get("brands"),
        quantity=api_data.get("quantity"),
        categories=api_data.get("categories"),
        generic_name=api_data.get("generic_name"),
        ingredients_text=api_data.get("ingredients_text"),
        allergens=api_data.get("allergens"),
        traces=api_data.get("traces"),
        additives=additives_tags if isinstance(additives_tags, list) else [],
        nutrition_grades=api_data.get("nutrition_grades"),
        
        # Basic nutrition (per 100g)
        energy_kcal=nutriments.get("energy-kcal_100g"),
        energy_kj=nutriments.get("energy-kj_100g"),
        fat=nutriments.get("fat_100g"),
        saturated_fat=nutriments.get("saturated-fat_100g"),
        carbohydrates=nutriments.get("carbohydrates_100g"),
        sugars=nutriments.get("sugars_100g"),
        fiber=nutriments.get("fiber_100g"),
        proteins=nutriments.get("proteins_100g"),
        salt=nutriments.get("salt_100g"),
        sodium=nutriments.get("sodium_100g"),
        
        # Serving information
        serving_size=api_data.get("serving_size"),
        serving_quantity=api_data.get("serving_quantity"),
        
        # Detailed fats (per 100g)
        monounsaturated_fat=nutriments.get("monounsaturated-fat_100g"),
        polyunsaturated_fat=nutriments.get("polyunsaturated-fat_100g"),
        trans_fat=nutriments.get("trans-fat_100g"),
        cholesterol=nutriments.get("cholesterol_100g"),
        omega_3_fat=nutriments.get("omega-3-fat_100g"),
        omega_6_fat=nutriments.get("omega-6-fat_100g"),
        
        # Vitamins (per 100g)
        vitamin_a=nutriments.get("vitamin-a_100g"),
        vitamin_c=nutriments.get("vitamin-c_100g"),
        vitamin_d=nutriments.get("vitamin-d_100g"),
        vitamin_e=nutriments.get("vitamin-e_100g"),
        vitamin_k=nutriments.get("vitamin-k_100g"),
        vitamin_b1=nutriments.get("vitamin-b1_100g"),
        vitamin_b2=nutriments.get("vitamin-b2_100g"),
        vitamin_b6=nutriments.get("vitamin-b6_100g"),
        vitamin_b9=nutriments.get("vitamin-b9_100g"),
        vitamin_b12=nutriments.get("vitamin-b12_100g"),
        
        # Minerals (per 100g)
        calcium=nutriments.get("calcium_100g"),
        iron=nutriments.get("iron_100g"),
        magnesium=nutriments.get("magnesium_100g"),
        phosphorus=nutriments.get("phosphorus_100g"),
        potassium=nutriments.get("potassium_100g"),
        zinc=nutriments.get("zinc_100g"),
        
        # Special content
        alcohol=nutriments.get("alcohol_100g"),
        caffeine=nutriments.get("caffeine_100g"),
        
        # Packaging & sustainability
        packaging=api_data.get("packaging"),
        packaging_tags=packaging_tags if isinstance(packaging_tags, list) else [],
        recycling_instructions=api_data.get("recycling_instructions_to_recycle"),
        carbon_footprint=nutriments.get("carbon-footprint_100g"),
        
        # Ingredients analysis
        ingredients_from_palm_oil=palm_oil_tags if isinstance(palm_oil_tags, list) else [],
        ingredients_analysis_vegan=vegan,
        ingredients_analysis_vegetarian=vegetarian,
        ingredients_analysis_palm_oil=palm_oil_free,
        
        # Images
        image_url=api_data.get("image_url"),
        image_small_url=api_data.get("image_small_url"),
        image_front_url=api_data.get("image_front_url"),
        image_ingredients_url=api_data.get("image_ingredients_url"),
        image_nutrition_url=api_data.get("image_nutrition_url"),
        
        # Labels & scores
        labels=labels_tags if isinstance(labels_tags, list) else [],
        eco_score_grade=api_data.get("eco_score_grade"),
        nova_group=api_data.get("nova_group"),
        
        # Origins
        origins=api_data.get("origins"),
        manufacturing_places=api_data.get("manufacturing_places"),
        countries=api_data.get("countries"),
        stores=api_data.get("stores"),
        
        # Metadata
        completeness=api_data.get("completeness"),
        last_modified_t=api_data.get("last_modified_t"),
    )
    
    for lang in lang_priority:
        key = f"product_name_{lang}"
        if api_data.get(key):
            setattr(product_data, key, api_data[key])
    
    await db.async_add_product(product_data)
    await db.async_increment_scan("openfoodfacts")
    
    hass.bus.async_fire(
        EVENT_LOOKUP_COMPLETED,
        {
            "ean": ean,
            "found": True,
            "name": name,
            "source": "openfoodfacts",
        },
    )
    hass.bus.async_fire(EVENT_STATS_UPDATED, {})
    
    return name, "openfoodfacts"


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up EAN Reader from YAML configuration."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up EAN Reader from a config entry."""
    db = ProductDatabase(hass)
    await db.async_load()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["db"] = db
    hass.data[DOMAIN]["tasks"] = set()
    hass.data[DOMAIN]["config"] = entry.options.copy()
    hass.data[DOMAIN]["diagnostics"] = {
        "last_error": None,
        "last_error_time": None,
        "error_count": 0,
        "rate_limited_count": 0,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await _async_register_services(hass, db, entry)

    @callback
    def _handle_share_event(event) -> None:
        text = event.data.get("text") or event.data.get("url") or ""
        ean = _clean_ean(text)
        if not _valid_ean(ean):
            return

        async def _process_scan() -> None:
            config = hass.data[DOMAIN]["config"]
            name, source = await _resolve_name(hass, db, ean, config)

            hass.bus.async_fire(
                EVENT_PRODUCT_SCANNED,
                {"ean": ean, "name": name, "source": source},
            )

            if name and config.get(CONF_AUTO_ADD_TO_SHOPPING_LIST, DEFAULT_AUTO_ADD):
                await db.async_add_to_shopping_list(ean)
                if config.get(CONF_SHOW_NOTIFICATIONS, DEFAULT_SHOW_NOTIFICATIONS):
                    await _notify_success(hass, name, True)
            elif not name:
                _LOGGER.info("EAN %s is unknown. Waiting for local mapping.", ean)

        task = hass.async_create_task(_process_scan())
        hass.data[DOMAIN]["tasks"].add(task)
        task.add_done_callback(lambda t: hass.data[DOMAIN]["tasks"].discard(t))

    hass.bus.async_listen(EVENT_TYPE, _handle_share_event)

    if entry.options.get(CONF_ENABLE_WEBHOOK, DEFAULT_ENABLE_WEBHOOK):
        webhook_id = webhook.async_generate_id()
        webhook.async_register(
            hass,
            DOMAIN,
            "EAN Scanner Webhook",
            webhook_id,
            _handle_webhook,
        )
        hass.data[DOMAIN]["webhook_id"] = webhook_id
        _LOGGER.info("Webhook registered with ID: %s", webhook_id)

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    tasks = hass.data[DOMAIN].get("tasks", set())
    for task in tasks:
        task.cancel()

    webhook_id = hass.data[DOMAIN].get("webhook_id")
    if webhook_id:
        webhook.async_unregister(hass, webhook_id)

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop("db", None)
        hass.data[DOMAIN].pop("config", None)
        hass.data[DOMAIN].pop("tasks", None)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)


async def _handle_webhook(
    hass: HomeAssistant, webhook_id: str, request
) -> dict[str, Any]:
    """Handle webhook callback for external barcode scanners."""
    try:
        data = await request.json()
        ean = _clean_ean(data.get("ean") or data.get("barcode") or data.get("code", ""))

        if not _valid_ean(ean):
            return {"status": "error", "message": "Invalid EAN format"}

        db = hass.data[DOMAIN]["db"]
        config = hass.data[DOMAIN]["config"]

        name, source = await _resolve_name(hass, db, ean, config)

        result = {
            "status": "success",
            "ean": ean,
            "name": name,
            "source": source,
        }

        if name and config.get(CONF_AUTO_ADD_TO_SHOPPING_LIST, DEFAULT_AUTO_ADD):
            await db.async_add_to_shopping_list(ean)
            result["added_to_list"] = True

        return result

    except Exception as err:
        _LOGGER.error("Webhook error: %s", err)
        return {"status": "error", "message": str(err)}


async def _async_register_services(
    hass: HomeAssistant, db: ProductDatabase, entry: ConfigEntry
) -> None:
    """Register all services for EAN Reader."""

    async def svc_add_mapping(call: ServiceCall) -> None:
        ean_raw = call.data.get("ean")
        if not ean_raw:
            _LOGGER.error("EAN is required for add_mapping service")
            return

        ean = _clean_ean(ean_raw)
        name = str(call.data.get("name") or "").strip()
        add_to_list = bool(call.data.get("add_to_shopping_list", False))

        if not _valid_ean(ean) or not name:
            _LOGGER.warning("Invalid EAN or name: ean=%r name=%r", ean, name)
            return

        name = _sanitize_text(name)
        product = await db.async_add_manual_product(ean, name)

        hass.bus.async_fire(
            EVENT_MAPPING_ADDED, {"ean": ean, "name": name, "source": "manual"}
        )
        hass.bus.async_fire(EVENT_STATS_UPDATED, {})

        if add_to_list:
            await _add_to_shopping_list(hass, name)

        if hass.services.has_service("persistent_notification", "dismiss"):
            await hass.services.async_call(
                "persistent_notification",
                "dismiss",
                {"notification_id": f"{DOMAIN}_missing_{ean}"},
                blocking=False,
            )

    async def svc_add_last_missing_mapping(call: ServiceCall) -> None:
        ean = db.last_missing_ean
        name = str(call.data.get("name") or "").strip()
        add_to_list = bool(call.data.get("add_to_shopping_list", True))

        if not ean or not _valid_ean(ean) or not name:
            _LOGGER.warning("No valid last missing EAN to map, or name is empty")
            return

        name = _sanitize_text(name)
        await db.async_add_manual_product(ean, name)

        hass.bus.async_fire(
            EVENT_MAPPING_ADDED, {"ean": ean, "name": name, "source": "manual"}
        )
        hass.bus.async_fire(EVENT_STATS_UPDATED, {})

        if hass.services.has_service("persistent_notification", "dismiss"):
            await hass.services.async_call(
                "persistent_notification",
                "dismiss",
                {"notification_id": f"{DOMAIN}_missing_{ean}"},
                blocking=False,
            )

        if add_to_list:
            await _add_to_shopping_list(hass, name)

    async def svc_remove_mapping(call: ServiceCall) -> None:
        ean_raw = call.data.get("ean")
        if not ean_raw:
            _LOGGER.error("EAN is required for remove_mapping service")
            return

        ean = _clean_ean(ean_raw)
        if not _valid_ean(ean):
            _LOGGER.warning("Invalid EAN: ean=%r", ean)
            return

        await db.async_delete_product(ean)
        hass.bus.async_fire(EVENT_MAPPING_REMOVED, {"ean": ean})
        hass.bus.async_fire(EVENT_STATS_UPDATED, {})

    async def svc_lookup_product(call: ServiceCall) -> None:
        ean_raw = call.data.get("ean")
        if not ean_raw:
            _LOGGER.error("EAN is required for lookup_product service")
            return

        ean = _clean_ean(ean_raw)
        if not _valid_ean(ean):
            _LOGGER.warning("Invalid EAN: ean=%r", ean)
            return

        config = hass.data[DOMAIN]["config"]
        await _resolve_name(hass, db, ean, config)

    async def svc_add_scanned(call: ServiceCall) -> None:
        ean_raw = call.data.get("ean")
        quantity = call.data.get("quantity")
        
        if not ean_raw:
            _LOGGER.error("EAN is required for add_scanned_to_shopping_list service")
            return

        ean = _clean_ean(ean_raw)
        if not _valid_ean(ean):
            _LOGGER.warning("Invalid EAN: ean=%r", ean)
            return

        config = hass.data[DOMAIN]["config"]
        name, _source = await _resolve_name(hass, db, ean, config)

        if name:
            await db.async_add_to_shopping_list(ean, quantity)
            hass.bus.async_fire(EVENT_STATS_UPDATED, {})
            _LOGGER.info("Added %s to shopping list", name)
        else:
            _LOGGER.info(
                "EAN %s is unknown. Add a mapping with ean_reader.add_last_missing_mapping.",
                ean,
            )
    
    async def svc_remove_from_list(call: ServiceCall) -> None:
        ean_raw = call.data.get("ean")
        if not ean_raw:
            _LOGGER.error("EAN is required for remove_from_shopping_list service")
            return
        
        ean = _clean_ean(ean_raw)
        if not _valid_ean(ean):
            _LOGGER.warning("Invalid EAN: ean=%r", ean)
            return
        
        product = await db.async_remove_from_shopping_list(ean)
        if product:
            hass.bus.async_fire(EVENT_STATS_UPDATED, {})
            _LOGGER.info("Removed %s from shopping list", product.product_name)
    
    async def svc_update_list_quantity(call: ServiceCall) -> None:
        ean_raw = call.data.get("ean")
        quantity = call.data.get("quantity", "")
        
        if not ean_raw:
            _LOGGER.error("EAN is required for update_shopping_list_quantity service")
            return
        
        ean = _clean_ean(ean_raw)
        if not _valid_ean(ean):
            _LOGGER.warning("Invalid EAN: ean=%r", ean)
            return
        
        await db.async_update_shopping_list_quantity(ean, quantity)
        hass.bus.async_fire(EVENT_STATS_UPDATED, {})
    
    async def svc_clear_shopping_list(call: ServiceCall) -> None:
        count = await db.async_clear_shopping_list()
        hass.bus.async_fire(EVENT_STATS_UPDATED, {})
        _LOGGER.info("Cleared %d items from shopping list", count)
    
    async def svc_get_shopping_list(call: ServiceCall) -> None:
        items = db.get_shopping_list()
        hass.bus.async_fire(
            f"{DOMAIN}_shopping_list",
            {
                "items": [item.to_dict() for item in items],
                "count": len(items)
            },
        )

    async def svc_list_unknowns(call: ServiceCall) -> None:
        unknowns = [u.to_dict() for u in db.unknowns.values()]
        hass.bus.async_fire(
            f"{DOMAIN}_unknowns_list",
            {"unknowns": unknowns, "count": len(unknowns)},
        )

    async def svc_export_mappings(call: ServiceCall) -> None:
        export_data = await db.async_export()
        hass.bus.async_fire(
            f"{DOMAIN}_export_complete",
            {"data": export_data, "count": len(export_data.get("products", {}))},
        )

    async def svc_import_mappings(call: ServiceCall) -> None:
        data = call.data.get("data")
        merge = bool(call.data.get("merge", True))

        if not data:
            _LOGGER.error("No data provided for import")
            return

        try:
            count = await db.async_import(data, merge)
            hass.bus.async_fire(
                f"{DOMAIN}_import_complete",
                {"imported_count": count},
            )
            hass.bus.async_fire(EVENT_STATS_UPDATED, {})
        except ValueError as err:
            _LOGGER.error("Import failed: %s", err)

    async def svc_add_price(call: ServiceCall) -> None:
        if not entry.options.get(CONF_TRACK_PRICES, DEFAULT_TRACK_PRICES):
            _LOGGER.warning("Price tracking is not enabled")
            return

        ean_raw = call.data.get("ean")
        if not ean_raw:
            _LOGGER.error("EAN is required for add_price service")
            return

        ean = _clean_ean(ean_raw)
        price = call.data.get("price")
        currency = call.data.get("currency", "SEK")
        store = call.data.get("store")

        if not _valid_ean(ean) or price is None:
            _LOGGER.warning("Invalid EAN or price: ean=%r price=%r", ean, price)
            return

        try:
            price_float = float(price)
            await db.async_add_price(ean, price_float, currency, store)
        except ValueError:
            _LOGGER.error("Invalid price value: %s", price)

    async def svc_set_expiry(call: ServiceCall) -> None:
        if not entry.options.get(CONF_TRACK_EXPIRY, DEFAULT_TRACK_EXPIRY):
            _LOGGER.warning("Expiry tracking is not enabled")
            return

        ean_raw = call.data.get("ean")
        if not ean_raw:
            _LOGGER.error("EAN is required for set_expiry service")
            return

        ean = _clean_ean(ean_raw)
        expiry_date = call.data.get("expiry_date")

        if not _valid_ean(ean) or not expiry_date:
            _LOGGER.warning("Invalid EAN or expiry_date: ean=%r expiry=%r", ean, expiry_date)
            return

        await db.async_set_expiry(ean, expiry_date)

    hass.services.async_register(DOMAIN, "add_mapping", svc_add_mapping)
    hass.services.async_register(DOMAIN, "add_last_missing_mapping", svc_add_last_missing_mapping)
    hass.services.async_register(DOMAIN, "remove_mapping", svc_remove_mapping)
    hass.services.async_register(DOMAIN, "lookup_product", svc_lookup_product)
    hass.services.async_register(DOMAIN, "add_scanned_to_shopping_list", svc_add_scanned)
    hass.services.async_register(DOMAIN, "list_unknowns", svc_list_unknowns)
    hass.services.async_register(DOMAIN, "export_mappings", svc_export_mappings)
    hass.services.async_register(DOMAIN, "import_mappings", svc_import_mappings)
    hass.services.async_register(DOMAIN, "add_price", svc_add_price)
    hass.services.async_register(DOMAIN, "set_expiry", svc_set_expiry)
    
    # Shopping list services
    hass.services.async_register(DOMAIN, "remove_from_shopping_list", svc_remove_from_list)
    hass.services.async_register(DOMAIN, "update_shopping_list_quantity", svc_update_list_quantity)
    hass.services.async_register(DOMAIN, "clear_shopping_list", svc_clear_shopping_list)
    hass.services.async_register(DOMAIN, "get_shopping_list", svc_get_shopping_list)
