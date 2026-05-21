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
import voluptuous as vol

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
from .storage import MappingStore

_LOGGER = logging.getLogger(__name__)
EAN_RE = re.compile(r"^\d{8,14}$")
CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f-\x9f]")


class RateLimiter:
    """Rate limiter to comply with OpenFoodFacts API limits.
    
    OpenFoodFacts limits:
    - 15 requests per minute per IP for product queries
    - 10 requests per minute per IP for search queries
    
    We use a conservative limit of 12 requests per minute to stay safe.
    """

    def __init__(self, max_requests: int = 12, window_seconds: int = 60):
        """Initialize rate limiter.
        
        Args:
            max_requests: Maximum requests allowed in the time window
            window_seconds: Time window in seconds
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Wait until a request slot is available."""
        async with self._lock:
            now = datetime.now(UTC).timestamp()
            
            # Remove old requests outside the window
            while self.requests and self.requests[0] < now - self.window_seconds:
                self.requests.popleft()
            
            # If at limit, wait until oldest request expires
            if len(self.requests) >= self.max_requests:
                sleep_time = self.window_seconds - (now - self.requests[0]) + 0.1
                _LOGGER.debug(
                    "Rate limit reached (%d/%d), waiting %.1f seconds",
                    len(self.requests),
                    self.max_requests,
                    sleep_time,
                )
                await asyncio.sleep(sleep_time)
                
                # Clean up again after sleep
                now = datetime.now(UTC).timestamp()
                while self.requests and self.requests[0] < now - self.window_seconds:
                    self.requests.popleft()
            
            # Record this request
            self.requests.append(now)
            
            if len(self.requests) > self.max_requests * 0.8:
                _LOGGER.warning(
                    "Approaching rate limit: %d/%d requests in last %d seconds",
                    len(self.requests),
                    self.max_requests,
                    self.window_seconds,
                )


# Global rate limiter instance
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
    """Look up product in OpenFoodFacts API using official SDK."""

    # Wait for rate limit slot
    await _RATE_LIMITER.acquire()

    # Get user agent with contact email
    config = hass.data[DOMAIN]["config"]
    email = config.get(CONF_CONTACT_EMAIL, DEFAULT_USER_EMAIL)
    user_agent = build_user_agent(email)

    def _sync_lookup():
        """Synchronous lookup using openfoodfacts library."""
        try:
            api = openfoodfacts.API(
                user_agent=user_agent,
                country="world",
                flavor="off",
                version="v2",
                environment="org",
            )

            fields = [
                "code",
                "product_name",
                "brands",
                "quantity",
                "categories",
                "ingredients_text",
                "allergens",
            ]

            for lang in lang_priority:
                fields.append(f"product_name_{lang}")

            if show_images:
                fields.extend(["image_url", "image_small_url"])

            product = api.product.get(ean, fields=fields)

            if not product:
                return None

            return product

        except requests.exceptions.HTTPError as err:
            # Handle rate limit exceeded (HTTP 503)
            if err.response.status_code == 503:
                _LOGGER.warning(
                    "OpenFoodFacts rate limit exceeded (HTTP 503). "
                    "The request for EAN %s will be retried later.",
                    ean,
                )
                # Return special marker to indicate rate limit
                return {"_rate_limited": True}
            raise
        except Exception as err:
            _LOGGER.debug("OpenFoodFacts lookup failed for %s: %s", ean, err)
            return None

    product = await hass.async_add_executor_job(_sync_lookup)

    # Check for rate limit marker
    if product and product.get("_rate_limited"):
        _LOGGER.info(
            "EAN %s lookup rate limited, will not cache as unknown", ean
        )
        return None

    if not product:
        return None

    name = _display_name(product, lang_priority)
    if not name:
        return None

    result = {
        "name": name,
        "source": "openfoodfacts",
        "product_name": _sanitize_text(product.get("product_name") or ""),
        "brands": _sanitize_text(product.get("brands") or ""),
        "quantity": _sanitize_text(product.get("quantity") or ""),
        "categories": _sanitize_text(product.get("categories") or ""),
        "ingredients": _sanitize_text(product.get("ingredients_text") or ""),
        "allergens": _sanitize_text(product.get("allergens") or ""),
    }

    for lang in lang_priority:
        key = f"product_name_{lang}"
        if product.get(key):
            result[key] = _sanitize_text(product[key])

    if show_images:
        if product.get("image_small_url"):
            result["image_small_url"] = product["image_small_url"]
        if product.get("image_url"):
            result["image_url"] = product["image_url"]

    return result


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
    store: MappingStore,
    ean: str,
    config: dict[str, Any],
) -> tuple[str | None, str]:
    """Resolve product name from local DB or OpenFoodFacts."""
    mapped = store.get_name(ean)
    if mapped:
        await store.async_increment_scan("local")
        return mapped, "local"

    if await store.async_is_known_missing(ean):
        _LOGGER.debug("EAN %s is known missing, skipping API call", ean)
        return None, "cached_missing"

    lang_priority = config.get(CONF_LANGUAGE_PRIORITY, DEFAULT_LANGUAGE_PRIORITY)
    show_images = config.get(CONF_SHOW_IMAGES, DEFAULT_SHOW_IMAGES)
    
    try:
        product = await _lookup_openfoodfacts(hass, ean, lang_priority, show_images)
    except requests.exceptions.HTTPError as err:
        if err.response.status_code == 503:
            # Rate limited - record and don't cache as unknown
            from datetime import UTC, datetime
            hass.data[DOMAIN]["diagnostics"]["last_error"] = "Rate limit exceeded (HTTP 503)"
            hass.data[DOMAIN]["diagnostics"]["last_error_time"] = datetime.now(UTC).isoformat()
            hass.data[DOMAIN]["diagnostics"]["rate_limited_count"] += 1
            _LOGGER.warning(
                "Rate limited by OpenFoodFacts API. Try again later. EAN: %s", ean
            )
            return None, "rate_limited"
        # Record other HTTP errors
        from datetime import UTC, datetime
        hass.data[DOMAIN]["diagnostics"]["last_error"] = f"HTTP {err.response.status_code}: {err}"
        hass.data[DOMAIN]["diagnostics"]["last_error_time"] = datetime.now(UTC).isoformat()
        hass.data[DOMAIN]["diagnostics"]["error_count"] += 1
        _LOGGER.error("HTTP error looking up EAN %s: %s", ean, err)
        return None, "error"
    except Exception as err:
        # Record unexpected errors
        from datetime import UTC, datetime
        hass.data[DOMAIN]["diagnostics"]["last_error"] = str(err)
        hass.data[DOMAIN]["diagnostics"]["last_error_time"] = datetime.now(UTC).isoformat()
        hass.data[DOMAIN]["diagnostics"]["error_count"] += 1
        _LOGGER.error("Unexpected error looking up EAN %s: %s", ean, err)
        return None, "error"

    if product:
        await store.async_set(ean, product["name"], product)
        await store.async_increment_scan("openfoodfacts")
        hass.bus.async_fire(
            EVENT_LOOKUP_COMPLETED,
            {
                "ean": ean,
                "found": True,
                "name": product["name"],
                "source": "openfoodfacts",
            },
        )
        hass.bus.async_fire(EVENT_STATS_UPDATED, {})
        return product["name"], "openfoodfacts"

    # Only mark as unknown if we got a definitive "not found" response
    unknown = await store.async_mark_unknown(ean)
    hass.bus.async_fire(
        EVENT_MISSING_PRODUCT,
        {"ean": ean, "source": "openfoodfacts", "seen_count": unknown.get("seen_count")},
    )
    hass.bus.async_fire(
        EVENT_LOOKUP_COMPLETED,
        {"ean": ean, "found": False, "name": None, "source": "openfoodfacts"},
    )

    show_notifications = config.get(CONF_SHOW_NOTIFICATIONS, DEFAULT_SHOW_NOTIFICATIONS)
    await _notify_missing_product(hass, ean, show_notifications)
    hass.bus.async_fire(EVENT_STATS_UPDATED, {})

    return None, "missing"


async def _add_to_shopping_list(hass: HomeAssistant, name: str) -> bool:
    """Add item to Home Assistant shopping list."""
    if not hass.services.has_service("shopping_list", "add_item"):
        _LOGGER.warning(
            "shopping_list.add_item is not available. Enable the Shopping List integration."
        )
        return False

    await hass.services.async_call(
        "shopping_list", "add_item", {"name": name}, blocking=False
    )
    return True


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up EAN Reader from YAML configuration (legacy support)."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up EAN Reader from a config entry."""
    store = MappingStore(hass)
    await store.async_load()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["store"] = store
    hass.data[DOMAIN]["tasks"] = set()
    hass.data[DOMAIN]["config"] = entry.options.copy()
    hass.data[DOMAIN]["diagnostics"] = {
        "last_error": None,
        "last_error_time": None,
        "error_count": 0,
        "rate_limited_count": 0,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    await _async_register_services(hass, store, entry)

    @callback
    def _handle_share_event(event) -> None:
        """Handle mobile_app.share events for barcode scanning."""
        text = event.data.get("text") or event.data.get("url") or ""
        ean = _clean_ean(text)
        if not _valid_ean(ean):
            return

        async def _process_scan() -> None:
            config = hass.data[DOMAIN]["config"]
            name, source = await _resolve_name(hass, store, ean, config)

            hass.bus.async_fire(
                EVENT_PRODUCT_SCANNED,
                {"ean": ean, "name": name, "source": source},
            )

            if name and config.get(CONF_AUTO_ADD_TO_SHOPPING_LIST, DEFAULT_AUTO_ADD):
                success = await _add_to_shopping_list(hass, name)
                if success and config.get(CONF_SHOW_NOTIFICATIONS, DEFAULT_SHOW_NOTIFICATIONS):
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
        hass.data[DOMAIN].pop("store", None)
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

        store = hass.data[DOMAIN]["store"]
        config = hass.data[DOMAIN]["config"]

        name, source = await _resolve_name(hass, store, ean, config)

        result = {
            "status": "success",
            "ean": ean,
            "name": name,
            "source": source,
        }

        if name and config.get(CONF_AUTO_ADD_TO_SHOPPING_LIST, DEFAULT_AUTO_ADD):
            await _add_to_shopping_list(hass, name)
            result["added_to_list"] = True

        return result

    except Exception as err:  # pylint: disable=broad-except
        _LOGGER.error("Webhook error: %s", err)
        return {"status": "error", "message": str(err)}


async def _async_register_services(
    hass: HomeAssistant, store: MappingStore, entry: ConfigEntry
) -> None:
    """Register all services for EAN Reader."""

    async def svc_add_mapping(call: ServiceCall) -> None:
        """Add or update EAN mapping."""
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
        await store.async_set(ean, name, {"source": "manual"})

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
        """Map the last unknown scanned EAN."""
        ean = store.last_missing_ean
        name = str(call.data.get("name") or "").strip()
        add_to_list = bool(call.data.get("add_to_shopping_list", True))

        if not ean or not _valid_ean(ean) or not name:
            _LOGGER.warning("No valid last missing EAN to map, or name is empty")
            return

        name = _sanitize_text(name)
        await store.async_set(ean, name, {"source": "manual", "created_from": "last_missing"})

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
        """Remove an EAN mapping."""
        ean_raw = call.data.get("ean")
        if not ean_raw:
            _LOGGER.error("EAN is required for remove_mapping service")
            return

        ean = _clean_ean(ean_raw)
        if not _valid_ean(ean):
            _LOGGER.warning("Invalid EAN: ean=%r", ean)
            return

        await store.async_delete(ean)
        hass.bus.async_fire(EVENT_MAPPING_REMOVED, {"ean": ean})
        hass.bus.async_fire(EVENT_STATS_UPDATED, {})

    async def svc_lookup_product(call: ServiceCall) -> None:
        """Look up product in OpenFoodFacts."""
        ean_raw = call.data.get("ean")
        if not ean_raw:
            _LOGGER.error("EAN is required for lookup_product service")
            return

        ean = _clean_ean(ean_raw)
        if not _valid_ean(ean):
            _LOGGER.warning("Invalid EAN: ean=%r", ean)
            return

        config = hass.data[DOMAIN]["config"]
        await _resolve_name(hass, store, ean, config)

    async def svc_add_scanned(call: ServiceCall) -> None:
        """Add scanned EAN to shopping list."""
        ean_raw = call.data.get("ean")
        if not ean_raw:
            _LOGGER.error("EAN is required for add_scanned_to_shopping_list service")
            return

        ean = _clean_ean(ean_raw)
        if not _valid_ean(ean):
            _LOGGER.warning("Invalid EAN: ean=%r", ean)
            return

        config = hass.data[DOMAIN]["config"]
        name, _source = await _resolve_name(hass, store, ean, config)

        if name:
            await _add_to_shopping_list(hass, name)
        else:
            _LOGGER.info(
                "EAN %s is unknown. Add a mapping with ean_reader.add_last_missing_mapping.",
                ean,
            )

    async def svc_list_unknowns(call: ServiceCall) -> None:
        """List all unknown products."""
        unknowns = list(store.unknowns.values())
        hass.bus.async_fire(
            f"{DOMAIN}_unknowns_list",
            {"unknowns": unknowns, "count": len(unknowns)},
        )

    async def svc_export_mappings(call: ServiceCall) -> None:
        """Export all mappings to a file."""
        export_data = await store.async_export_mappings()
        hass.bus.async_fire(
            f"{DOMAIN}_export_complete",
            {"data": export_data, "count": len(export_data.get("mappings", {}))},
        )

    async def svc_import_mappings(call: ServiceCall) -> None:
        """Import mappings from data."""
        data = call.data.get("data")
        merge = bool(call.data.get("merge", True))

        if not data:
            _LOGGER.error("No data provided for import")
            return

        try:
            count = await store.async_import_mappings(data, merge)
            hass.bus.async_fire(
                f"{DOMAIN}_import_complete",
                {"imported_count": count},
            )
            hass.bus.async_fire(EVENT_STATS_UPDATED, {})
        except ValueError as err:
            _LOGGER.error("Import failed: %s", err)

    async def svc_add_price(call: ServiceCall) -> None:
        """Add price tracking entry."""
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

        if not _valid_ean(ean) or price is None:
            _LOGGER.warning("Invalid EAN or price: ean=%r price=%r", ean, price)
            return

        try:
            price_float = float(price)
            await store.async_add_price(ean, price_float, currency)
        except ValueError:
            _LOGGER.error("Invalid price value: %s", price)

    async def svc_set_expiry(call: ServiceCall) -> None:
        """Set expiry date for a product."""
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

        await store.async_set_expiry(ean, expiry_date)

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
