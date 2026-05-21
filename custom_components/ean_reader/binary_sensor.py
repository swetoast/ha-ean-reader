"""Binary sensor platform for EAN Reader integration."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_API_AVAILABLE,
    ATTR_ERROR_COUNT,
    ATTR_LAST_ERROR,
    ATTR_LAST_ERROR_TIME,
    ATTR_RATE_LIMITED_COUNT,
    DOMAIN,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up EAN Reader binary sensor based on a config entry."""
    async_add_entities([EANReaderAPIDiagnostic(config_entry)], True)


class EANReaderAPIDiagnostic(BinarySensorEntity):
    """Binary sensor for OpenFoodFacts API health monitoring."""

    _attr_has_entity_name = True
    _attr_name = "API Problem"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = "diagnostic"

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize the diagnostic sensor."""
        self._attr_unique_id = f"{config_entry.entry_id}_api_diagnostic"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, config_entry.entry_id)},
            "name": "EAN Reader",
            "manufacturer": "Custom",
            "model": "EAN Reader",
        }

    @property
    def is_on(self) -> bool:
        """Return true if there's an API problem."""
        # ON means problem detected
        diagnostics = self.hass.data.get(DOMAIN, {}).get("diagnostics", {})
        error_count = diagnostics.get("error_count", 0)
        rate_limited = diagnostics.get("rate_limited_count", 0)
        return error_count > 0 or rate_limited > 0

    @property
    def extra_state_attributes(self) -> dict[str, any]:
        """Return diagnostic attributes."""
        diagnostics = self.hass.data.get(DOMAIN, {}).get("diagnostics", {})
        
        attrs = {
            ATTR_ERROR_COUNT: diagnostics.get("error_count", 0),
            ATTR_RATE_LIMITED_COUNT: diagnostics.get("rate_limited_count", 0),
            ATTR_API_AVAILABLE: not self.is_on,
        }

        last_error = diagnostics.get("last_error")
        if last_error:
            attrs[ATTR_LAST_ERROR] = last_error
            
        last_error_time = diagnostics.get("last_error_time")
        if last_error_time:
            attrs[ATTR_LAST_ERROR_TIME] = last_error_time

        return attrs
