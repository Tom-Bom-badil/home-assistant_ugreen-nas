from homeassistant.components.text import TextEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    DOMAIN,
    LOVELACE_ENTITY_FILTER_NAME,
    LOVELACE_ENTITY_FILTER_UNIQUE_ID,
)


def _is_owner_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Only the first loaded config entry creates the global dashboard helpers."""
    entries = hass.config_entries.async_entries(DOMAIN)
    return bool(entries) and entries[0].entry_id == entry.entry_id


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the global Lovelace text filter."""
    if not _is_owner_entry(hass, entry):
        return

    async_add_entities([UgreenLovelaceEntityFilter()])


class UgreenLovelaceEntityFilter(RestoreEntity, TextEntity):
    """Global free-text filter for the example dashboard."""

    def __init__(self) -> None:
        self._attr_name = LOVELACE_ENTITY_FILTER_NAME
        self._attr_unique_id = LOVELACE_ENTITY_FILTER_UNIQUE_ID
        self._attr_icon = "mdi:filter-variant"
        self._attr_entity_category = EntityCategory.CONFIG
        self._attr_native_value = ""
        self._attr_mode = "text"

    async def async_added_to_hass(self) -> None:
        """Restore the previous filter text."""
        await super().async_added_to_hass()

        if last_state := await self.async_get_last_state():
            if isinstance(last_state.state, str):
                self._attr_native_value = last_state.state

        self.async_write_ha_state()

    async def async_set_value(self, value: str) -> None:
        """Store the current free-text filter."""
        self._attr_native_value = value
        self.async_write_ha_state()