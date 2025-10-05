import logging
from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from .device_info import build_device_info
from .const import DOMAIN
from .api import UgreenApiClient
from .entities import UgreenEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback
) -> None:
    """Set up UGREEN NAS buttons based on a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["config_coordinator"]
    entities: list[UgreenEntity] = hass.data[DOMAIN][entry.entry_id]["button_entities"]
    api = hass.data[DOMAIN][entry.entry_id]["api"]

    button_entities = [
        UgreenNasButton(hass, entry.entry_id, coordinator, entity, api)
        for entity in entities
    ]

    async_add_entities(button_entities)


class UgreenNasButton(CoordinatorEntity, ButtonEntity):
    """Representation of a UGREEN NAS button."""

    def __init__(self, hass: HomeAssistant, entry_id: str,
                coordinator: DataUpdateCoordinator,
                endpoint: UgreenEntity,
                api: UgreenApiClient) -> None:
        super().__init__(coordinator)
        self.hass = hass
        self._entry_id = entry_id
        self._endpoint = endpoint
        self._key = endpoint.description.key
        self._api = api

        self._attr_name = f"UGREEN NAS {endpoint.description.name}"
        self._attr_unique_id = f"{entry_id}_{endpoint.description.key}"
        self._attr_icon = endpoint.description.icon
        self._attr_native_unit_of_measurement = endpoint.description.unit_of_measurement

        self._attr_device_info = build_device_info(
            hass, self._entry_id, self._key
        )

    async def async_press(self) -> None:
        """Perform the button action."""
        try:
            session = async_get_clientsession(self.hass)
            await self._api.authenticate(session)

            method = str(self._endpoint.request_method or "GET").upper()
            path = self._endpoint.endpoint
    
            if method == "POST":
                await self._api.post(session, path)
            elif method == "GET":
                await self._api.get(session, path)
            else:
                _LOGGER.warning("Unsupported method: %s", method)

        except Exception as e:
            _LOGGER.error("Error pressing button %s: %s", self._key, e)
    
    def _handle_coordinator_update(self) -> None:
        """Update the button value from the coordinator."""
        self._attr_press = self.async_press
        super()._handle_coordinator_update()
