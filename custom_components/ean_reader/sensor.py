"""Sensor platform for EAN Reader integration."""
from __future__ import annotations

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
    store = hass.data[DOMAIN]["store"]

    async_add_entities([
        EANReaderStatsSensor(store, config_entry),
        EANReaderUnknownsSensor(store, config_entry),
    ])


class EANReaderStatsSensor(SensorEntity):
    """Sensor showing EAN Reader statistics."""

    _attr_has_entity_name = True
    _attr_name = "Statistics"
    _attr_icon = "mdi:barcode-scan"
    _attr_state_class = SensorStateClass.TOTAL

    def __init__(self, store, config_entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        self._store = store
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
        return self._store.statistics.get(ATTR_TOTAL_SCANS, 0)

    @property
    def extra_state_attributes(self) -> dict[str, any]:
        """Return additional attributes."""
        attrs = {
            ATTR_TOTAL_MAPPINGS: len(self._store.mappings),
            ATTR_UNKNOWN_PRODUCTS: len(self._store.unknowns),
            ATTR_TOTAL_SCANS: self._store.statistics.get(ATTR_TOTAL_SCANS, 0),
            ATTR_OPENFOODFACTS_HITS: self._store.statistics.get(
                ATTR_OPENFOODFACTS_HITS, 0
            ),
            ATTR_LOCAL_HITS: self._store.statistics.get(ATTR_LOCAL_HITS, 0),
            ATTR_LAST_SCAN: self._store.last_missing_ean,
        }

        last_scan_time = self._store.statistics.get(ATTR_LAST_SCAN_TIME)
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

    def __init__(self, store, config_entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        self._store = store
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
        return len(self._store.unknowns)

    @property
    def extra_state_attributes(self) -> dict[str, any]:
        """Return the list of unknown EANs."""
        unknowns_list = []
        for ean, data in self._store.unknowns.items():
            unknowns_list.append(
                {
                    "ean": ean,
                    "seen_count": data.get("seen_count", 0),
                    "first_seen": data.get("first_seen"),
                    "last_seen": data.get("last_seen"),
                }
            )

        unknowns_list.sort(key=lambda x: x["seen_count"], reverse=True)

        return {
            "unknowns": unknowns_list[:20],
            "total_unknown": len(self._store.unknowns),
            "last_missing_ean": self._store.last_missing_ean,
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
