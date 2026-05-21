"""Constants for EAN Reader integration."""
from typing import Final

DOMAIN: Final = "ean_reader"
STORAGE_KEY: Final = "ean_reader_mappings"
STORAGE_VERSION: Final = 3
EVENT_TYPE: Final = "mobile_app.share"

# User agent format: AppName/Version (ContactEmail)
USER_AGENT_BASE: Final = "HomeAssistant-EANReader/1.0.0"
DEFAULT_USER_EMAIL: Final = "homeassistant@example.com"

# Cache duration
CACHE_UNKNOWN_DURATION: Final = 86400  # 24 hours before retrying unknown products

# Events
EVENT_LOOKUP_COMPLETED: Final = "ean_reader_lookup_completed"
EVENT_MISSING_PRODUCT: Final = "ean_reader_missing_product"
EVENT_MAPPING_ADDED: Final = "ean_reader_mapping_added"
EVENT_MAPPING_REMOVED: Final = "ean_reader_mapping_removed"
EVENT_PRODUCT_SCANNED: Final = "ean_reader_product_scanned"
EVENT_STATS_UPDATED: Final = "ean_reader_stats_updated"

# Configuration
CONF_CONTACT_EMAIL: Final = "contact_email"
CONF_LANGUAGE_PRIORITY: Final = "language_priority"
CONF_AUTO_ADD_TO_SHOPPING_LIST: Final = "auto_add_to_shopping_list"
CONF_SHOW_NOTIFICATIONS: Final = "show_notifications"
CONF_TRACK_PRICES: Final = "track_prices"
CONF_TRACK_EXPIRY: Final = "track_expiry"
CONF_ENABLE_WEBHOOK: Final = "enable_webhook"
CONF_SHOW_IMAGES: Final = "show_images"

# Defaults
DEFAULT_LANGUAGE_PRIORITY: Final = ["sv", "en", "de", "fr", "es"]
DEFAULT_AUTO_ADD: Final = True
DEFAULT_SHOW_NOTIFICATIONS: Final = True
DEFAULT_TRACK_PRICES: Final = False
DEFAULT_TRACK_EXPIRY: Final = False
DEFAULT_ENABLE_WEBHOOK: Final = False
DEFAULT_SHOW_IMAGES: Final = True

# Sensor attributes
ATTR_TOTAL_MAPPINGS: Final = "total_mappings"
ATTR_UNKNOWN_PRODUCTS: Final = "unknown_products"
ATTR_TOTAL_SCANS: Final = "total_scans"
ATTR_LAST_SCAN: Final = "last_scan"
ATTR_LAST_SCAN_TIME: Final = "last_scan_time"
ATTR_OPENFOODFACTS_HITS: Final = "openfoodfacts_hits"
ATTR_LOCAL_HITS: Final = "local_hits"

# Platforms
PLATFORMS: Final = ["sensor"]


def build_user_agent(email: str | None = None) -> str:
    """Build User-Agent string in OpenFoodFacts format.
    
    Format: AppName/Version (ContactEmail)
    Example: MyApp/1.0 (myapp@example.com)
    """
    email = email or DEFAULT_USER_EMAIL
    return f"{USER_AGENT_BASE} ({email})"
