"""Storage management for EAN Reader integration."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import STORAGE_KEY, STORAGE_VERSION


def _utcnow() -> str:
    """Return current UTC timestamp as ISO string."""
    return datetime.now(UTC).isoformat()


@dataclass
class MappingStore:
    """Store for EAN mappings, unknowns, and statistics."""

    hass: HomeAssistant
    _store: Store = field(init=False)
    mappings: dict[str, dict[str, Any]] = field(default_factory=dict)
    unknowns: dict[str, dict[str, Any]] = field(default_factory=dict)
    last_missing_ean: str | None = None
    statistics: dict[str, Any] = field(default_factory=dict)
    price_history: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    expiry_tracking: dict[str, dict[str, Any]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Initialize the store."""
        self._store = Store(self.hass, STORAGE_VERSION, STORAGE_KEY)
        if not self.statistics:
            self.statistics = {
                "total_scans": 0,
                "openfoodfacts_hits": 0,
                "local_hits": 0,
                "last_scan_time": None,
            }

    async def async_load(self) -> None:
        """Load data from storage."""
        loaded = await self._store.async_load()
        if not loaded:
            return

        # Handle migration from old format
        if "mappings" not in loaded and isinstance(loaded, dict):
            self.mappings = dict(loaded)
            self.unknowns = {}
            self.last_missing_ean = None
            self.statistics = {
                "total_scans": 0,
                "openfoodfacts_hits": 0,
                "local_hits": 0,
                "last_scan_time": None,
            }
            await self.async_save()
            return

        self.mappings = loaded.get("mappings") or {}
        self.unknowns = loaded.get("unknowns") or {}
        self.last_missing_ean = loaded.get("last_missing_ean")
        self.statistics = loaded.get("statistics") or {
            "total_scans": 0,
            "openfoodfacts_hits": 0,
            "local_hits": 0,
            "last_scan_time": None,
        }
        self.price_history = loaded.get("price_history") or {}
        self.expiry_tracking = loaded.get("expiry_tracking") or {}

    async def async_save(self) -> None:
        """Save data to storage."""
        await self._store.async_save(
            {
                "mappings": self.mappings,
                "unknowns": self.unknowns,
                "last_missing_ean": self.last_missing_ean,
                "statistics": self.statistics,
                "price_history": self.price_history,
                "expiry_tracking": self.expiry_tracking,
            }
        )

    def get(self, ean: str) -> dict[str, Any] | None:
        """Get mapping for an EAN."""
        return self.mappings.get(ean)

    def get_name(self, ean: str) -> str | None:
        """Get product name for an EAN, if it exists."""
        return self.mappings.get(ean, {}).get("name")

    async def async_set(
        self,
        ean: str,
        name: str,
        extra: dict[str, Any] | None = None,
    ) -> None:
        """Set or update a mapping."""
        now = _utcnow()
        previous = self.mappings.get(ean) or {}
        self.mappings[ean] = {
            **previous,
            "name": name,
            "updated_at": now,
            **(extra or {}),
        }

        # Clean up from unknowns if it was there
        self.unknowns.pop(ean, None)
        if self.last_missing_ean == ean:
            self.last_missing_ean = None

        await self.async_save()

    async def async_delete(self, ean: str) -> None:
        """Delete a mapping, unknown, and related data."""
        changed = False
        if ean in self.mappings:
            self.mappings.pop(ean)
            changed = True
        if ean in self.unknowns:
            self.unknowns.pop(ean)
            changed = True
        if self.last_missing_ean == ean:
            self.last_missing_ean = None
            changed = True
        if ean in self.price_history:
            self.price_history.pop(ean)
            changed = True
        if ean in self.expiry_tracking:
            self.expiry_tracking.pop(ean)
            changed = True

        if changed:
            await self.async_save()

    async def async_mark_unknown(self, ean: str) -> dict[str, Any]:
        """Mark an EAN as unknown (not found in OpenFoodFacts)."""
        now = _utcnow()
        item = self.unknowns.get(ean) or {
            "ean": ean,
            "first_seen": now,
            "seen_count": 0,
        }
        item["last_seen"] = now
        item["seen_count"] = int(item.get("seen_count") or 0) + 1
        item["source"] = "openfoodfacts"
        item["status"] = "missing"
        self.unknowns[ean] = item
        self.last_missing_ean = ean
        await self.async_save()
        return item

    async def async_is_known_missing(self, ean: str) -> bool:
        """Check if EAN is recently known to be missing from OpenFoodFacts."""
        unknown = self.unknowns.get(ean)
        if not unknown:
            return False

        # Don't retry API calls for cached unknowns within 24 hours
        try:
            last_seen = datetime.fromisoformat(unknown["last_seen"])
            from .const import CACHE_UNKNOWN_DURATION

            age = (datetime.now(UTC) - last_seen).total_seconds()
            return age < CACHE_UNKNOWN_DURATION
        except (ValueError, KeyError):
            return False

    async def async_increment_scan(self, source: str = "unknown") -> None:
        """Increment scan statistics."""
        self.statistics["total_scans"] = self.statistics.get("total_scans", 0) + 1
        self.statistics["last_scan_time"] = _utcnow()

        if source == "openfoodfacts":
            self.statistics["openfoodfacts_hits"] = (
                self.statistics.get("openfoodfacts_hits", 0) + 1
            )
        elif source == "local":
            self.statistics["local_hits"] = self.statistics.get("local_hits", 0) + 1

        await self.async_save()

    async def async_add_price(
        self, ean: str, price: float, currency: str = "SEK"
    ) -> None:
        """Add price tracking entry."""
        if ean not in self.price_history:
            self.price_history[ean] = []

        self.price_history[ean].append(
            {
                "price": price,
                "currency": currency,
                "timestamp": _utcnow(),
            }
        )

        # Keep only last 50 entries per product
        if len(self.price_history[ean]) > 50:
            self.price_history[ean] = self.price_history[ean][-50:]

        await self.async_save()

    async def async_set_expiry(self, ean: str, expiry_date: str) -> None:
        """Set expiry date for a product."""
        self.expiry_tracking[ean] = {
            "expiry_date": expiry_date,
            "set_at": _utcnow(),
        }
        await self.async_save()

    def get_expiry(self, ean: str) -> str | None:
        """Get expiry date for a product."""
        return self.expiry_tracking.get(ean, {}).get("expiry_date")

    def get_price_history(self, ean: str) -> list[dict[str, Any]]:
        """Get price history for a product."""
        return self.price_history.get(ean, [])

    def get_latest_price(self, ean: str) -> dict[str, Any] | None:
        """Get latest price for a product."""
        history = self.price_history.get(ean, [])
        return history[-1] if history else None

    async def async_export_mappings(self) -> dict[str, Any]:
        """Export all mappings for backup."""
        return {
            "version": STORAGE_VERSION,
            "exported_at": _utcnow(),
            "mappings": self.mappings,
            "statistics": self.statistics,
        }

    async def async_import_mappings(
        self, data: dict[str, Any], merge: bool = True
    ) -> int:
        """Import mappings from backup. Returns count of imported items."""
        if not isinstance(data, dict) or "mappings" not in data:
            raise ValueError("Invalid import data format")

        imported_mappings = data["mappings"]
        count = 0

        for ean, mapping in imported_mappings.items():
            if not merge or ean not in self.mappings:
                self.mappings[ean] = mapping
                count += 1

        if count > 0:
            await self.async_save()

        return count
