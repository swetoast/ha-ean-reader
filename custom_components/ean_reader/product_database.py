"""Comprehensive product database for EAN Reader."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import UTC, datetime
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import STORAGE_KEY, STORAGE_VERSION


def _utcnow() -> str:
    """Return current UTC timestamp as ISO string."""
    return datetime.now(UTC).isoformat()


@dataclass
class ProductData:
    """Complete product information from OpenFoodFacts and local data."""
    
    # Core identification
    ean: str
    product_name: str
    source: str  # "openfoodfacts", "manual", "local"
    
    # Basic info
    brands: str | None = None
    quantity: str | None = None
    categories: str | None = None
    
    # Ingredients & allergens
    ingredients_text: str | None = None
    allergens: str | None = None
    traces: str | None = None
    additives: list[str] = field(default_factory=list)
    
    # Nutrition (per 100g/100ml)
    nutrition_grades: str | None = None  # Nutri-Score: a, b, c, d, e
    energy_kcal: float | None = None
    energy_kj: float | None = None
    fat: float | None = None
    saturated_fat: float | None = None
    carbohydrates: float | None = None
    sugars: float | None = None
    fiber: float | None = None
    proteins: float | None = None
    salt: float | None = None
    sodium: float | None = None
    
    # Serving information (how people actually consume)
    serving_size: str | None = None          # "150g", "1 cup (250ml)", "1 bottle"
    serving_quantity: float | None = None     # Numeric value for calculations
    
    # Detailed fats (per 100g)
    monounsaturated_fat: float | None = None
    polyunsaturated_fat: float | None = None
    trans_fat: float | None = None
    cholesterol: float | None = None
    omega_3_fat: float | None = None
    omega_6_fat: float | None = None
    
    # Vitamins (per 100g)
    vitamin_a: float | None = None
    vitamin_c: float | None = None
    vitamin_d: float | None = None
    vitamin_e: float | None = None
    vitamin_k: float | None = None
    vitamin_b1: float | None = None          # Thiamin
    vitamin_b2: float | None = None          # Riboflavin
    vitamin_b6: float | None = None
    vitamin_b9: float | None = None          # Folate
    vitamin_b12: float | None = None
    
    # Minerals (per 100g)
    calcium: float | None = None
    iron: float | None = None
    magnesium: float | None = None
    phosphorus: float | None = None
    potassium: float | None = None
    zinc: float | None = None
    
    # Special content (per 100g)
    alcohol: float | None = None              # % vol
    caffeine: float | None = None             # mg
    
    # Packaging & sustainability
    packaging: str | None = None              # "Plastic bottle", "Cardboard box"
    packaging_tags: list[str] = field(default_factory=list)
    recycling_instructions: str | None = None
    carbon_footprint: float | None = None     # CO2 equivalent per 100g
    
    # Additional metadata
    generic_name: str | None = None           # Generic product name
    ingredients_from_palm_oil: list[str] = field(default_factory=list)
    ingredients_analysis_vegan: str | None = None      # "yes", "no", "maybe"
    ingredients_analysis_vegetarian: str | None = None  # "yes", "no", "maybe"
    ingredients_analysis_palm_oil: str | None = None    # "yes", "no", "maybe"
    
    # Images
    image_url: str | None = None
    image_small_url: str | None = None
    image_front_url: str | None = None
    image_ingredients_url: str | None = None
    image_nutrition_url: str | None = None
    
    # Labels & certifications
    labels: list[str] = field(default_factory=list)
    eco_score_grade: str | None = None  # a, b, c, d, e
    nova_group: int | None = None  # 1-4 (food processing level)
    
    # Origins & manufacturing
    origins: str | None = None
    manufacturing_places: str | None = None
    countries: str | None = None
    stores: str | None = None
    
    # Multi-language names
    product_name_sv: str | None = None
    product_name_en: str | None = None
    product_name_de: str | None = None
    product_name_fr: str | None = None
    product_name_es: str | None = None
    
    # Local tracking data
    first_seen: str = field(default_factory=_utcnow)
    last_updated: str = field(default_factory=_utcnow)
    scan_count: int = 0
    
    # Price tracking (local)
    prices: list[dict[str, Any]] = field(default_factory=list)
    current_price: float | None = None
    price_currency: str = "SEK"
    
    # Expiry tracking (local)
    expiry_date: str | None = None
    expiry_set_at: str | None = None
    
    # User notes
    notes: str | None = None
    favorite: bool = False
    
    # Shopping list
    in_shopping_list: bool = False
    shopping_list_quantity: str | None = None  # "2", "500g", "3x"
    added_to_list_at: str | None = None
    
    # OpenFoodFacts metadata
    completeness: float | None = None  # 0-1 score
    last_modified_t: int | None = None  # Unix timestamp from OFF
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary, excluding None values."""
        data = asdict(self)
        return {k: v for k, v in data.items() if v is not None and v != [] and v != ""}


@dataclass
class UnknownProduct:
    """Product not found in any database."""
    
    ean: str
    first_seen: str = field(default_factory=_utcnow)
    last_seen: str = field(default_factory=_utcnow)
    seen_count: int = 1
    source: str = "openfoodfacts"  # Where we tried to look it up
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class ProductDatabase:
    """Comprehensive product database with full OpenFoodFacts data."""
    
    def __init__(self, hass: HomeAssistant):
        """Initialize product database."""
        self.hass = hass
        self._store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self.products: dict[str, ProductData] = {}
        self.unknowns: dict[str, UnknownProduct] = {}
        self.last_missing_ean: str | None = None
        self.statistics: dict[str, Any] = {
            "total_scans": 0,
            "openfoodfacts_hits": 0,
            "local_hits": 0,
            "last_scan_time": None,
        }
    
    async def async_load(self) -> None:
        """Load database from storage."""
        loaded = await self._store.async_load()
        if not loaded:
            return
        
        # Load products
        products_data = loaded.get("products", {})
        for ean, data in products_data.items():
            try:
                # Convert dict to ProductData
                self.products[ean] = ProductData(**data)
            except TypeError:
                # Old format - migrate
                self.products[ean] = self._migrate_old_product(ean, data)
        
        # Load unknowns
        unknowns_data = loaded.get("unknowns", {})
        for ean, data in unknowns_data.items():
            try:
                self.unknowns[ean] = UnknownProduct(**data)
            except TypeError:
                # Old format
                self.unknowns[ean] = UnknownProduct(
                    ean=ean,
                    first_seen=data.get("first_seen", _utcnow()),
                    last_seen=data.get("last_seen", _utcnow()),
                    seen_count=data.get("seen_count", 1),
                    source=data.get("source", "openfoodfacts"),
                )
        
        # Load metadata
        self.last_missing_ean = loaded.get("last_missing_ean")
        self.statistics = loaded.get("statistics", self.statistics)
    
    def _migrate_old_product(self, ean: str, data: dict[str, Any]) -> ProductData:
        """Migrate old product format to new ProductData."""
        return ProductData(
            ean=ean,
            product_name=data.get("name", "Unknown"),
            source=data.get("source", "manual"),
            brands=data.get("brands"),
            quantity=data.get("quantity"),
            categories=data.get("categories"),
            ingredients_text=data.get("ingredients"),
            allergens=data.get("allergens"),
            image_url=data.get("image_url"),
            image_small_url=data.get("image_small_url"),
            first_seen=data.get("updated_at", _utcnow()),
            last_updated=data.get("updated_at", _utcnow()),
        )
    
    async def async_save(self) -> None:
        """Save database to storage."""
        await self._store.async_save({
            "products": {
                ean: product.to_dict()
                for ean, product in self.products.items()
            },
            "unknowns": {
                ean: unknown.to_dict()
                for ean, unknown in self.unknowns.items()
            },
            "last_missing_ean": self.last_missing_ean,
            "statistics": self.statistics,
        })
    
    def get_product(self, ean: str) -> ProductData | None:
        """Get product by EAN."""
        return self.products.get(ean)
    
    def get_product_name(self, ean: str) -> str | None:
        """Get product name by EAN."""
        product = self.products.get(ean)
        return product.product_name if product else None
    
    async def async_add_product(self, product: ProductData) -> None:
        """Add or update a product."""
        existing = self.products.get(product.ean)
        if existing:
            # Update scan count and last updated
            product.scan_count = existing.scan_count + 1
            product.first_seen = existing.first_seen
            # Preserve local data
            product.prices = existing.prices
            product.current_price = existing.current_price
            product.price_currency = existing.price_currency
            product.expiry_date = existing.expiry_date
            product.expiry_set_at = existing.expiry_set_at
            product.notes = existing.notes
            product.favorite = existing.favorite
        
        product.last_updated = _utcnow()
        self.products[product.ean] = product
        
        # Remove from unknowns if it was there
        self.unknowns.pop(product.ean, None)
        if self.last_missing_ean == product.ean:
            self.last_missing_ean = None
        
        await self.async_save()
    
    async def async_add_manual_product(
        self, ean: str, name: str, **kwargs
    ) -> ProductData:
        """Add a manually entered product."""
        product = ProductData(
            ean=ean,
            product_name=name,
            source="manual",
            **kwargs
        )
        await self.async_add_product(product)
        return product

    # Fields a user is allowed to edit directly on a product.
    EDITABLE_FIELDS: tuple[str, ...] = (
        "product_name", "brands", "quantity", "categories",
        "ingredients_text", "allergens", "traces", "labels",
        "stores", "origins", "packaging", "notes",
    )

    async def async_update_product_fields(
        self, ean: str, fields: dict[str, Any]
    ) -> ProductData:
        """Apply a partial edit to a product, creating it if needed.

        Only the keys present in ``fields`` (and non-None) are written, so
        existing OpenFoodFacts-derived data is preserved. An EAN that was in
        the unknowns list is promoted to a real product.
        """
        product = self.products.get(ean)
        created = product is None
        if product is None:
            product = ProductData(
                ean=ean,
                product_name=str(fields.get("product_name") or "Unknown Product"),
                source="manual",
            )

        for key, value in fields.items():
            if value is None or key not in self.EDITABLE_FIELDS:
                continue
            setattr(product, key, value)

        # If a user edits an OFF product, keep provenance but note local edits.
        if not created and product.source == "openfoodfacts":
            product.source = "openfoodfacts+manual"

        product.last_updated = _utcnow()
        self.products[ean] = product

        # Promote out of unknowns.
        self.unknowns.pop(ean, None)
        if self.last_missing_ean == ean:
            self.last_missing_ean = None

        await self.async_save()
        return product
    
    async def async_delete_product(self, ean: str) -> None:
        """Delete a product and all associated data."""
        self.products.pop(ean, None)
        self.unknowns.pop(ean, None)
        if self.last_missing_ean == ean:
            self.last_missing_ean = None
        await self.async_save()
    
    async def async_mark_unknown(self, ean: str) -> UnknownProduct:
        """Mark an EAN as unknown (not found)."""
        unknown = self.unknowns.get(ean)
        if unknown:
            unknown.last_seen = _utcnow()
            unknown.seen_count += 1
        else:
            unknown = UnknownProduct(ean=ean)
            self.unknowns[ean] = unknown
        
        self.last_missing_ean = ean
        await self.async_save()
        return unknown
    
    async def async_is_known_missing(self, ean: str) -> bool:
        """Check if EAN is recently known to be missing."""
        unknown = self.unknowns.get(ean)
        if not unknown:
            return False
        
        try:
            last_seen = datetime.fromisoformat(unknown.last_seen)
            from .const import CACHE_UNKNOWN_DURATION
            age = (datetime.now(UTC) - last_seen).total_seconds()
            return age < CACHE_UNKNOWN_DURATION
        except (ValueError, KeyError):
            return False
    
    async def async_add_price(
        self, ean: str, price: float, currency: str = "SEK", store: str | None = None
    ) -> None:
        """Add a price entry for a product."""
        product = self.products.get(ean)
        if not product:
            # Create minimal product if it doesn't exist
            product = ProductData(
                ean=ean,
                product_name="Unknown Product",
                source="local",
            )
            self.products[ean] = product
        
        # Add to price history
        product.prices.append({
            "price": price,
            "currency": currency,
            "store": store,
            "timestamp": _utcnow(),
        })
        
        # Keep only last 50 prices
        if len(product.prices) > 50:
            product.prices = product.prices[-50:]
        
        # Update current price
        product.current_price = price
        product.price_currency = currency
        
        await self.async_save()
    
    async def async_set_expiry(self, ean: str, expiry_date: str) -> None:
        """Set expiry date for a product."""
        product = self.products.get(ean)
        if not product:
            product = ProductData(
                ean=ean,
                product_name="Unknown Product",
                source="local",
            )
            self.products[ean] = product
        
        product.expiry_date = expiry_date
        product.expiry_set_at = _utcnow()
        
        await self.async_save()
    
    async def async_set_notes(self, ean: str, notes: str) -> None:
        """Set user notes for a product."""
        product = self.products.get(ean)
        if product:
            product.notes = notes
            await self.async_save()
    
    async def async_set_favorite(self, ean: str, favorite: bool = True) -> None:
        """Mark a product as favorite."""
        product = self.products.get(ean)
        if product:
            product.favorite = favorite
            await self.async_save()
    
    async def async_increment_scan(
        self, source: str = "unknown", ean: str | None = None
    ) -> None:
        """Increment scan statistics."""
        self.statistics["total_scans"] = self.statistics.get("total_scans", 0) + 1
        self.statistics["last_scan_time"] = _utcnow()
        if ean:
            self.statistics["last_scan"] = ean
        
        if source == "openfoodfacts":
            self.statistics["openfoodfacts_hits"] = (
                self.statistics.get("openfoodfacts_hits", 0) + 1
            )
        elif source == "local":
            self.statistics["local_hits"] = (
                self.statistics.get("local_hits", 0) + 1
            )
        
        await self.async_save()
    
    async def async_export(self) -> dict[str, Any]:
        """Export database for backup."""
        return {
            "version": STORAGE_VERSION,
            "exported_at": _utcnow(),
            "products": {
                ean: product.to_dict()
                for ean, product in self.products.items()
            },
            "statistics": self.statistics,
        }
    
    async def async_import(
        self, data: dict[str, Any], merge: bool = True
    ) -> int:
        """Import products from backup."""
        if not isinstance(data, dict) or "products" not in data:
            raise ValueError("Invalid import data format")
        
        imported_products = data["products"]
        count = 0
        
        for ean, product_data in imported_products.items():
            try:
                if not merge or ean not in self.products:
                    product = ProductData(**product_data)
                    self.products[ean] = product
                    count += 1
            except TypeError:
                # Old format - migrate
                if not merge or ean not in self.products:
                    product = self._migrate_old_product(ean, product_data)
                    self.products[ean] = product
                    count += 1
        
        if count > 0:
            await self.async_save()
        
        return count
    
    def get_favorites(self) -> list[ProductData]:
        """Get all favorite products."""
        return [p for p in self.products.values() if p.favorite]
    
    def search_products(self, query: str) -> list[ProductData]:
        """Search products by name, brand, or category."""
        query_lower = query.lower()
        results = []
        
        for product in self.products.values():
            if (
                query_lower in product.product_name.lower()
                or (product.brands and query_lower in product.brands.lower())
                or (product.categories and query_lower in product.categories.lower())
            ):
                results.append(product)
        
        return results
    
    def get_products_expiring_soon(self, days: int = 7) -> list[ProductData]:
        """Get products expiring within specified days."""
        if days <= 0:
            return []
        
        now = datetime.now(UTC)
        cutoff = now.timestamp() + (days * 86400)
        results = []
        
        for product in self.products.values():
            if product.expiry_date:
                try:
                    expiry = datetime.fromisoformat(product.expiry_date).timestamp()
                    if expiry <= cutoff:
                        results.append(product)
                except ValueError:
                    continue
        
        return sorted(results, key=lambda p: p.expiry_date or "")
    
    async def async_add_to_shopping_list(
        self, ean: str, quantity: str | None = None
    ) -> ProductData | None:
        """Add product to shopping list."""
        product = self.products.get(ean)
        if not product:
            return None
        
        product.in_shopping_list = True
        product.shopping_list_quantity = quantity
        product.added_to_list_at = _utcnow()
        
        await self.async_save()
        return product
    
    async def async_remove_from_shopping_list(self, ean: str) -> ProductData | None:
        """Remove product from shopping list."""
        product = self.products.get(ean)
        if not product:
            return None
        
        product.in_shopping_list = False
        product.shopping_list_quantity = None
        product.added_to_list_at = None
        
        await self.async_save()
        return product
    
    async def async_update_shopping_list_quantity(
        self, ean: str, quantity: str
    ) -> ProductData | None:
        """Update quantity for item in shopping list."""
        product = self.products.get(ean)
        if not product or not product.in_shopping_list:
            return None
        
        product.shopping_list_quantity = quantity
        await self.async_save()
        return product
    
    async def async_clear_shopping_list(self) -> int:
        """Clear all items from shopping list."""
        count = 0
        for product in self.products.values():
            if product.in_shopping_list:
                product.in_shopping_list = False
                product.shopping_list_quantity = None
                product.added_to_list_at = None
                count += 1
        
        if count > 0:
            await self.async_save()
        
        return count
    
    def get_shopping_list(self) -> list[ProductData]:
        """Get all products in shopping list."""
        return [
            p for p in self.products.values() 
            if p.in_shopping_list
        ]
    
    def get_shopping_list_count(self) -> int:
        """Get count of items in shopping list."""
        return sum(1 for p in self.products.values() if p.in_shopping_list)
