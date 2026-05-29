"""Sensor platform for EAN Reader integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_LAST_SCAN,
    ATTR_LAST_SCAN_TIME,
    ATTR_LOCAL_HITS,
    ATTR_OPENFOODFACTS_HITS,
    ATTR_TOTAL_MAPPINGS,
    ATTR_TOTAL_SCANS,
    ATTR_UNKNOWN_PRODUCTS,
    DOMAIN,
    EVENT_STATS_UPDATED,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up EAN Reader sensor based on a config entry."""
    db = hass.data[DOMAIN]["db"]

    async_add_entities([
        EANReaderStatsSensor(db, config_entry),
        EANReaderUnknownsSensor(db, config_entry),
        EANReaderShoppingListSensor(db, config_entry),
    ])


class EANReaderStatsSensor(SensorEntity):
    """Sensor showing EAN Reader statistics."""

    _attr_has_entity_name = True
    _attr_name = "Statistics"
    _attr_icon = "mdi:barcode-scan"
    _attr_state_class = SensorStateClass.TOTAL

    def __init__(self, db, config_entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        self._db = db
        self._attr_unique_id = f"{config_entry.entry_id}_stats"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, config_entry.entry_id)},
            "name": "EAN Reader",
            "manufacturer": "Custom",
            "model": "EAN Reader",
        }

    @property
    def native_value(self) -> int:
        """Return the total number of scans."""
        return self._db.statistics.get("total_scans", 0)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        attrs = {
            ATTR_TOTAL_MAPPINGS: len(self._db.products),
            ATTR_UNKNOWN_PRODUCTS: len(self._db.unknowns),
            ATTR_TOTAL_SCANS: self._db.statistics.get("total_scans", 0),
            ATTR_OPENFOODFACTS_HITS: self._db.statistics.get("openfoodfacts_hits", 0),
            ATTR_LOCAL_HITS: self._db.statistics.get("local_hits", 0),
            ATTR_LAST_SCAN: self._db.statistics.get("last_scan"),
        }

        last_scan_time = self._db.statistics.get("last_scan_time")
        if last_scan_time:
            attrs[ATTR_LAST_SCAN_TIME] = last_scan_time

        return attrs

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""

        @callback
        def _handle_event(event):
            """Handle stat update events."""
            self.async_schedule_update_ha_state()

        self.async_on_remove(
            self.hass.bus.async_listen(EVENT_STATS_UPDATED, _handle_event)
        )


class EANReaderUnknownsSensor(SensorEntity):
    """Sensor showing count of unknown products."""

    _attr_has_entity_name = True
    _attr_name = "Unknown Products"
    _attr_icon = "mdi:help-circle"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, db, config_entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        self._db = db
        self._attr_unique_id = f"{config_entry.entry_id}_unknowns"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, config_entry.entry_id)},
            "name": "EAN Reader",
            "manufacturer": "Custom",
            "model": "EAN Reader",
        }

    @property
    def native_value(self) -> int:
        """Return the count of unknown products."""
        return len(self._db.unknowns)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the list of unknown EANs."""
        unknowns_list = []
        for ean, unknown in self._db.unknowns.items():
            unknowns_list.append({
                "ean": ean,
                "seen_count": unknown.seen_count,
                "first_seen": unknown.first_seen,
                "last_seen": unknown.last_seen,
            })

        unknowns_list.sort(key=lambda x: x["seen_count"], reverse=True)

        return {
            "unknowns": unknowns_list[:20],
            "total_unknown": len(self._db.unknowns),
            "last_missing_ean": self._db.last_missing_ean,
        }

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""

        @callback
        def _handle_event(event):
            """Handle stat update events."""
            self.async_schedule_update_ha_state()

        self.async_on_remove(
            self.hass.bus.async_listen(EVENT_STATS_UPDATED, _handle_event)
        )


class EANReaderShoppingListSensor(SensorEntity):
    """Sensor showing shopping list with all products."""

    _attr_has_entity_name = True
    _attr_name = "Shopping List"
    _attr_icon = "mdi:cart"

    def __init__(self, db, config_entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        self._db = db
        self._attr_unique_id = f"{config_entry.entry_id}_shopping_list"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, config_entry.entry_id)},
            "name": "EAN Reader",
            "manufacturer": "Custom",
            "model": "EAN Reader",
        }

    @property
    def native_value(self) -> int:
        """Return the count of items in shopping list."""
        return sum(1 for p in self._db.products.values() if p.in_shopping_list)

    @property
    def extra_state_attributes(self) -> dict:
        """Return the shopping list products as attributes."""
        shopping_products = []
        
        for product in self._db.products.values():
            if product.in_shopping_list:
                shopping_products.append({
                    "ean": product.ean,
                    "product_name": product.product_name,
                    "brands": product.brands,
                    "quantity": product.quantity,
                    "shopping_list_quantity": product.shopping_list_quantity,
                    "image_url": product.image_url,
                    "nutrition_grades": product.nutrition_grades,
                    "eco_score_grade": product.eco_score_grade,
                    "nova_group": product.nova_group,
                    "ingredients_analysis_vegan": product.ingredients_analysis_vegan,
                    "ingredients_analysis_vegetarian": product.ingredients_analysis_vegetarian,
                    "energy_kcal": product.energy_kcal,
                    "fat": product.fat,
                    "carbohydrates": product.carbohydrates,
                    "proteins": product.proteins,
                    "serving_size": product.serving_size,
                    "calcium": product.calcium,
                    "iron": product.iron,
                    "vitamin_c": product.vitamin_c,
                    "packaging": product.packaging,
                    "carbon_footprint": product.carbon_footprint,
                    "alcohol": product.alcohol,
                    "caffeine": product.caffeine,
                })
        
        return {
            "products": shopping_products,
            "count": len(shopping_products),
        }

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""

        @callback
        def _handle_event(event):
            """Handle stat update events."""
            self.async_schedule_update_ha_state()

        self.async_on_remove(
            self.hass.bus.async_listen(EVENT_STATS_UPDATED, _handle_event)
        )
