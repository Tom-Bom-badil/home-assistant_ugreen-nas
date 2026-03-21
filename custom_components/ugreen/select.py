import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator
from homeassistant.util import slugify

from .const import (
    CONF_DASHBOARD_DISK_COLUMNS,
    CONF_DASHBOARD_IMAGE_FILE,
    CONF_DASHBOARD_POOL_COLUMNS,
    CONF_DASHBOARD_VOLUME_COLUMNS,
    CONF_ENTITY_PREFIX,
    DEFAULT_DASHBOARD_DISK_COLUMNS,
    DEFAULT_DASHBOARD_IMAGE_FILE,
    DEFAULT_DASHBOARD_POOL_COLUMNS,
    DEFAULT_DASHBOARD_VOLUME_COLUMNS,
    DOMAIN,
    LOVELACE_DEVICE_SELECT_NAME,
    LOVELACE_DEVICE_SELECT_UNIQUE_ID,
)

_LOGGER = logging.getLogger(__name__)


def _is_owner_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Only the first loaded config entry creates the global dashboard helpers."""
    entries = hass.config_entries.async_entries(DOMAIN)
    return bool(entries) and entries[0].entry_id == entry.entry_id


def _get_entry_label(entry: ConfigEntry) -> str:
    """Return the user-defined NAS label for the dropdown."""
    prefix = (
        entry.options.get(CONF_ENTITY_PREFIX, entry.data.get(CONF_ENTITY_PREFIX, ""))
        or ""
    ).strip()
    return prefix or "UGREEN NAS"


def _get_entry_slug(entry: ConfigEntry) -> str:
    """Return the technical slug used as entity_id prefix."""
    prefix = (
        entry.options.get(CONF_ENTITY_PREFIX, entry.data.get(CONF_ENTITY_PREFIX, ""))
        or ""
    ).strip()
    return slugify(prefix) or "ugreen_nas"


def _get_entry_value(entry: ConfigEntry, key: str, default):
    """Read a value from options first, then from data, else use default."""
    return entry.options.get(key, entry.data.get(key, default))


def _normalize_columns(value, default: int) -> int:
    """Convert dashboard columns to a safe integer range."""
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(0, min(10, number))


def _get_entry_disk_columns(entry: ConfigEntry) -> int:
    """Return the configured disk grid columns."""
    return _normalize_columns(
        _get_entry_value(entry, CONF_DASHBOARD_DISK_COLUMNS, DEFAULT_DASHBOARD_DISK_COLUMNS),
        DEFAULT_DASHBOARD_DISK_COLUMNS,
    )


def _get_entry_pool_columns(entry: ConfigEntry) -> int:
    """Return the configured pool grid columns."""
    return _normalize_columns(
        _get_entry_value(entry, CONF_DASHBOARD_POOL_COLUMNS, DEFAULT_DASHBOARD_POOL_COLUMNS),
        DEFAULT_DASHBOARD_POOL_COLUMNS,
    )


def _get_entry_volume_columns(entry: ConfigEntry) -> int:
    """Return the configured volume grid columns."""
    return _normalize_columns(
        _get_entry_value(entry, CONF_DASHBOARD_VOLUME_COLUMNS, DEFAULT_DASHBOARD_VOLUME_COLUMNS),
        DEFAULT_DASHBOARD_VOLUME_COLUMNS,
    )


def _get_entry_image_file(entry: ConfigEntry) -> str:
    """Return the configured dashboard image filename."""
    value = _get_entry_value(entry, CONF_DASHBOARD_IMAGE_FILE, DEFAULT_DASHBOARD_IMAGE_FILE)
    return str(value or "").strip()


def _build_devices(hass: HomeAssistant) -> list[dict[str, object]]:
    """Build the current NAS list for Lovelace selection."""
    devices: list[dict[str, object]] = []

    for entry in hass.config_entries.async_entries(DOMAIN):
        devices.append(
            {
                "entry_id": entry.entry_id,
                "label": _get_entry_label(entry),
                "slug": _get_entry_slug(entry),
                "disk_columns": _get_entry_disk_columns(entry),
                "pool_columns": _get_entry_pool_columns(entry),
                "volume_columns": _get_entry_volume_columns(entry),
                "image_file": _get_entry_image_file(entry),
            }
        )

    devices.sort(key=lambda item: str(item["label"]).lower())
    return devices


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the global Lovelace NAS selector."""
    if not _is_owner_entry(hass, entry):
        return

    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]["config_coordinator"]
    async_add_entities([UgreenLovelaceDeviceSelect(hass, coordinator)])


class UgreenLovelaceDeviceSelect(CoordinatorEntity, RestoreEntity, SelectEntity):
    """Global NAS selector for the example dashboard."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: DataUpdateCoordinator,
    ) -> None:
        super().__init__(coordinator)
        self.hass = hass
        self._devices: list[dict[str, object]] = []
        self._selected_slug: str = ""

        self._attr_name = LOVELACE_DEVICE_SELECT_NAME
        self._attr_unique_id = LOVELACE_DEVICE_SELECT_UNIQUE_ID
        self._attr_icon = "mdi:nas"
        self._attr_entity_category = EntityCategory.CONFIG

    async def async_added_to_hass(self) -> None:
        """Restore the previous selection and build the initial list."""
        await super().async_added_to_hass()

        self._rebuild_devices()

        if last_state := await self.async_get_last_state():
            restored_slug = (last_state.attributes or {}).get("selected_slug")
            if isinstance(restored_slug, str) and restored_slug:
                self._selected_slug = restored_slug
            elif isinstance(last_state.state, str):
                selected = self._device_by_label(last_state.state)
                if selected:
                    self._selected_slug = str(selected["slug"])

        self._ensure_valid_selection()
        self.async_write_ha_state()

    def _rebuild_devices(self) -> None:
        """Rebuild the NAS mapping from current config entries."""
        self._devices = _build_devices(self.hass)

    def _ensure_valid_selection(self) -> None:
        """Keep the current selection valid after list changes."""
        if self._device_by_slug(self._selected_slug):
            return
        self._selected_slug = str(self._devices[0]["slug"]) if self._devices else ""

    def _device_by_slug(self, slug: str) -> dict[str, object] | None:
        """Find a device by technical slug."""
        for device in self._devices:
            if device["slug"] == slug:
                return device
        return None

    def _device_by_label(self, label: str) -> dict[str, object] | None:
        """Find a device by visible label."""
        for device in self._devices:
            if device["label"] == label:
                return device
        return None

    @property
    def options(self) -> list[str]:
        """Return visible options for the dropdown."""
        return [str(device["label"]) for device in self._devices]

    @property
    def current_option(self) -> str | None:
        """Return the currently selected visible label."""
        selected = self._device_by_slug(self._selected_slug)
        return str(selected["label"]) if selected else None

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        """Expose the selected NAS metadata for Lovelace."""
        selected = self._device_by_slug(self._selected_slug)

        if not selected:
            return {
                "selected_slug": "",
                "entity_prefix": "",
                "selected_entry_id": "",
                "selected_disk_columns": DEFAULT_DASHBOARD_DISK_COLUMNS,
                "selected_pool_columns": DEFAULT_DASHBOARD_POOL_COLUMNS,
                "selected_volume_columns": DEFAULT_DASHBOARD_VOLUME_COLUMNS,
                "selected_image_file": DEFAULT_DASHBOARD_IMAGE_FILE,
                "available_devices": [
                    {
                        "label": str(device["label"]),
                        "slug": str(device["slug"]),
                        "disk_columns": int(device["disk_columns"]),
                        "pool_columns": int(device["pool_columns"]),
                        "volume_columns": int(device["volume_columns"]),
                        "image_file": str(device["image_file"]),
                    }
                    for device in self._devices
                ],
            }

        return {
            "selected_slug": str(selected["slug"]),
            "entity_prefix": str(selected["slug"]),
            "selected_entry_id": str(selected["entry_id"]),
            "selected_disk_columns": int(selected["disk_columns"]),
            "selected_pool_columns": int(selected["pool_columns"]),
            "selected_volume_columns": int(selected["volume_columns"]),
            "selected_image_file": str(selected["image_file"]),
            "available_devices": [
                {
                    "label": str(device["label"]),
                    "slug": str(device["slug"]),
                    "disk_columns": int(device["disk_columns"]),
                    "pool_columns": int(device["pool_columns"]),
                    "volume_columns": int(device["volume_columns"]),
                    "image_file": str(device["image_file"]),
                }
                for device in self._devices
            ],
        }

    async def async_select_option(self, option: str) -> None:
        """Handle manual NAS selection from the UI."""
        selected = self._device_by_label(option)
        if not selected:
            _LOGGER.warning("[UGREEN NAS] Invalid dashboard NAS selection: %s", option)
            return

        self._selected_slug = str(selected["slug"])
        self.async_write_ha_state()

    def _handle_coordinator_update(self) -> None:
        """Refresh the NAS list every config coordinator cycle."""
        self._rebuild_devices()
        self._ensure_valid_selection()
        super()._handle_coordinator_update()