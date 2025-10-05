import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from datetime import date, datetime
from decimal import Decimal

from .device_info import build_device_info
from .const import DOMAIN
from .entities import UgreenEntity
from .utils import determine_unit, format_sensor_value

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback
) -> None:
    """Set up UGREEN NAS sensors based on a config entry."""
    config_coordinator = hass.data[DOMAIN][entry.entry_id]["config_coordinator"]
    config_entities = hass.data[DOMAIN][entry.entry_id]["config_entities"]
    state_coordinator = hass.data[DOMAIN][entry.entry_id]["state_coordinator"]
    state_entities = hass.data[DOMAIN][entry.entry_id]["state_entities"]
    nas_model = hass.data[DOMAIN][entry.entry_id].get("nas_model")

    # Configuration sensors (60s)
    config_sensors = [
        UgreenNasSensor(hass, entry.entry_id, config_coordinator, entity, nas_model)
        for entity in config_entities
    ]

    # State sensors (5s)
    state_sensors = [
        UgreenNasSensor(hass, entry.entry_id, state_coordinator, entity, nas_model)
        for entity in state_entities
    ]

    async_add_entities(config_sensors + state_sensors)


class UgreenNasSensor(CoordinatorEntity, SensorEntity):
    """Representation of the UgreenNasSensor class."""

    def __init__(self, hass: HomeAssistant, entry_id: str,
                coordinator: DataUpdateCoordinator,
                endpoint: UgreenEntity,
                nas_model: str | None = None) -> None:
        super().__init__(coordinator)

        self.hass = hass
        self._entry_id = entry_id
        self._endpoint = endpoint
        self._key = endpoint.description.key

        self._attr_name = f"UGREEN NAS {endpoint.description.name}"
        self._attr_unique_id = f"{entry_id}_{endpoint.description.key}"
        self._attr_icon = endpoint.description.icon

        base_device_info = build_device_info(hass, self._entry_id, self._key, nas_model)

        if "disk" in self._key and "brand" in self._key:
            try:
                base_device_info.manufacturer = str(self.coordinator.data.get(self._key))
            except Exception:
                pass

        if "disk" in self._key and "model" in self._key:
            try:
                base_device_info.model = str(self.coordinator.data.get(self._key))
            except Exception:
                pass

        self._attr_device_info = base_device_info

    @property
    def native_value(self) -> StateType | date | datetime | Decimal:
        """Return the formatted value of the sensor."""
        raw = self.coordinator.data.get(self._key)
        return format_sensor_value(raw, self._endpoint)

    @property
    def extra_state_attributes(self):
        base_attrs = super().extra_state_attributes or {}
        base_attrs.update({
            "nas_device_type": "UGreen NAS",
            "nas_device_id": "",
            "nas_part_category": self._endpoint.nas_part_category,
        })
        return base_attrs

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit, dynamically determined."""
        raw = self.coordinator.data.get(self._key)
        unit = self._endpoint.description.unit_of_measurement or ""

        if self._endpoint.description.unit_of_measurement in ("B/s", "kB/s", "MB/s", "GB/s", "TB/s", "PB/s"):
            return determine_unit(raw, unit, True)
        elif self._endpoint.description.unit_of_measurement in ("B", "kB", "MB", "GB", "TB", "PB"):
            return determine_unit(raw, unit, False)

        return self._endpoint.description.unit_of_measurement

    def _handle_coordinator_update(self) -> None:
        """Update the sensor value from the coordinator."""
        self._attr_native_value = self.native_value
        self._attr_native_unit_of_measurement = self.native_unit_of_measurement
        super()._handle_coordinator_update()
