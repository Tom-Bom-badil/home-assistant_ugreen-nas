import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import EntityCategory, async_generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator
from homeassistant.util import slugify
from .api import backup_task_key, backup_task_name
from .device_info import build_device_info

from .const import (
    CONF_DASHBOARD_DISK_COLUMNS,
    CONF_DASHBOARD_IMAGE_FILE,
    CONF_DASHBOARD_POOL_COLUMNS,
    CONF_DASHBOARD_VOLUME_COLUMNS,
    BACKUP_ENTITY_CATEGORY,
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


POWER_MODE_OPTIONS = {
    "High Performance": "power_mode_high_performance",
    "Balanced": "power_mode_balanced",
    "Energy Saving": "power_mode_energy_saving",
}

POWER_MODE_STATE = {
    0: "High Performance",
    1: "Balanced",
    2: "Energy Saving",
}

FAN_MODE_OPTIONS = {
    "Quiet": "fan_mode_quiet",
    "Default": "fan_mode_default",
    "Full Power": "fan_mode_full_power",
}

FAN_MODE_STATE = {
    1: "Quiet",
    2: "Default",
    3: "Full Power",
}

POWER_ACTION_OPTIONS = {
    "Shutdown": "power_action_shutdown",
    "Wake Up": "power_action_wake_up",
    "Reboot": "power_action_reboot",
}


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
    """Set up UGREEN NAS select entities."""

    data = hass.data[DOMAIN][entry.entry_id]
    entities: list[SelectEntity] = [
        UgreenPowerModeSelect(hass, entry, data["state_coordinator"]),
        UgreenFanModeSelect(hass, entry, data["state_coordinator"]),
    ]
    if data.get("backup_tasks"):
        entities.append(UgreenBackupTaskSelect(hass, entry, data["backup_coordinator"]))
    if _is_owner_entry(hass, entry):
        entities.append(UgreenLovelaceDeviceSelect(hass, data["config_coordinator"]))
    async_add_entities(entities)


class UgreenBackupTaskSelect(CoordinatorEntity, RestoreEntity, SelectEntity):
    """Select one configured UGOS backup task for global backup controls."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        coordinator: DataUpdateCoordinator,
    ) -> None:
        super().__init__(coordinator)
        self.hass = hass
        self._entry = entry
        self._entry_id = entry.entry_id
        self._selected_key = ""

        self._attr_name = f"{_get_entry_label(entry)} Backup Task"
        self.entity_id = async_generate_entity_id(
            "select.{}", self._attr_name, hass=self.hass
        )
        self._attr_unique_id = f"{entry.entry_id}_backup_task_select"
        self._attr_icon = "mdi:backup-restore"
        self._attr_device_info = build_device_info(hass, entry.entry_id, "backup_task_select")

    async def async_added_to_hass(self) -> None:
        """Restore the previous backup task selection."""
        await super().async_added_to_hass()
        if last_state := await self.async_get_last_state():
            restored_key = (last_state.attributes or {}).get("selected_task_key")
            if isinstance(restored_key, str) and restored_key:
                self._selected_key = restored_key
            elif isinstance(last_state.state, str):
                task = self._task_by_option(last_state.state)
                if task:
                    self._selected_key = backup_task_key(task)
        self._ensure_valid_selection()
        self._store_selection()
        self.async_write_ha_state()

    def _tasks(self) -> list[dict[str, object]]:
        """Return current backup tasks from the coordinator or setup cache."""
        data = self.coordinator.data or {}
        tasks = data.get("tasks") or self.hass.data[DOMAIN][self._entry_id].get("backup_tasks") or []
        return [task for task in tasks if isinstance(task, dict)]

    def _option_map(self) -> dict[str, dict[str, object]]:
        """Return visible option labels mapped to tasks."""
        tasks = self._tasks()
        names = [backup_task_name(task) for task in tasks]
        duplicate_names = {name for name in names if names.count(name) > 1}
        options: dict[str, dict[str, object]] = {}

        for task in tasks:
            name = backup_task_name(task)
            key = backup_task_key(task)
            label = f"{name} ({key})" if name in duplicate_names else name
            options[label] = task
        return options

    def _task_by_key(self, key: str) -> dict[str, object] | None:
        """Find a backup task by stable key."""
        for task in self._tasks():
            if backup_task_key(task) == key:
                return task
        return None

    def _task_by_option(self, option: str) -> dict[str, object] | None:
        """Find a backup task by visible option label."""
        return self._option_map().get(option)

    def _option_for_key(self, key: str) -> str | None:
        """Return the visible option label for a stable key."""
        for option, task in self._option_map().items():
            if backup_task_key(task) == key:
                return option
        return None

    def _ensure_valid_selection(self) -> None:
        """Keep the selected task valid after task list changes."""
        if self._task_by_key(self._selected_key):
            return
        tasks = self._tasks()
        self._selected_key = backup_task_key(tasks[0]) if tasks else ""

    def _store_selection(self) -> None:
        """Store the selected task key for global backup buttons."""
        self.hass.data[DOMAIN][self._entry_id]["selected_backup_task_key"] = self._selected_key

    @property
    def options(self) -> list[str]:
        """Return selectable backup task names."""
        return list(self._option_map())

    @property
    def current_option(self) -> str | None:
        """Return the currently selected backup task name."""
        self._ensure_valid_selection()
        return self._option_for_key(self._selected_key)

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        """Expose selected backup task metadata."""
        selected = self._task_by_key(self._selected_key)
        attrs: dict[str, object] = {
            "UGNAS_global_id": "UGREEN NAS",
            "UGNAS_device_id": _get_entry_slug(self._entry),
            "UGNAS_part_category": BACKUP_ENTITY_CATEGORY,
            "selected_task_key": self._selected_key,
            "available_tasks": [
                {
                    "name": backup_task_name(task),
                    "task_id": task.get("id"),
                    "protocol": task.get("protocol"),
                }
                for task in self._tasks()
            ],
        }
        if selected:
            attrs.update({
                "selected_task_id": selected.get("id"),
                "selected_protocol": selected.get("protocol"),
            })
        return attrs

    async def async_select_option(self, option: str) -> None:
        """Handle manual backup task selection from the UI."""
        task = self._task_by_option(option)
        if not task:
            _LOGGER.warning("[UGREEN NAS] Invalid backup task selection: %s", option)
            return

        self._selected_key = backup_task_key(task)
        self._store_selection()
        self.async_write_ha_state()

    def _handle_coordinator_update(self) -> None:
        """Refresh the task list and keep the selection valid."""
        self._ensure_valid_selection()
        self._store_selection()
        super()._handle_coordinator_update()


class UgreenLovelaceDeviceSelect(CoordinatorEntity, RestoreEntity, SelectEntity):
    """Select for choosing one from all knwon NASes (e.g. example dashboard)."""

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


class UgreenPowerModeSelect(CoordinatorEntity, SelectEntity):
    """Select for triggering power mode buttons."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        coordinator: DataUpdateCoordinator,
    ) -> None:
        super().__init__(coordinator)
        self.hass = hass
        self._entry = entry
        self._current: str | None = None

        self._attr_name = f"{_get_entry_label(entry)} Power Mode"
        self._attr_unique_id = f"{entry.entry_id}_power_mode_select"
        self._attr_icon = "mdi:speedometer"
        self._attr_device_info = build_device_info(hass, entry.entry_id, "power_mode_select")

    @property
    def options(self) -> list[str]:
        """Return selectable power modes."""
        return list(POWER_MODE_OPTIONS)

    @property
    def current_option(self) -> str | None:
        """Return the current power mode."""
        raw = (self.coordinator.data or {}).get("power_mode")
        try:
            self._current = POWER_MODE_STATE.get(int(raw), self._current)
        except (TypeError, ValueError):
            pass
        return self._current

    async def async_select_option(self, option: str) -> None:
        """Press the mapped button and refresh the current mode."""
        button_key = POWER_MODE_OPTIONS.get(option)
        entity_id = er.async_get(self.hass).async_get_entity_id(
            "button",
            DOMAIN,
            f"{self._entry.entry_id}_{button_key}",
        ) if button_key else None

        if not entity_id:
            _LOGGER.warning("[UGREEN NAS] Power mode button not found for option: %s", option)
            return

        self._current = option
        self.async_write_ha_state()

        await self.hass.services.async_call(
            "button",
            "press",
            {"entity_id": entity_id},
            blocking=True,
        )

        await self.coordinator.async_request_refresh()


class UgreenFanModeSelect(CoordinatorEntity, SelectEntity):
    """Select for triggering fan mode buttons."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        coordinator: DataUpdateCoordinator,
    ) -> None:
        super().__init__(coordinator)
        self.hass = hass
        self._entry = entry
        self._current: str | None = None

        self._attr_name = f"{_get_entry_label(entry)} Fan Mode"
        self._attr_unique_id = f"{entry.entry_id}_fan_mode_select"
        self._attr_icon = "mdi:fan"
        self._attr_device_info = build_device_info(hass, entry.entry_id, "fan_mode_select")

    @property
    def options(self) -> list[str]:
        """Return selectable fan modes."""
        return list(FAN_MODE_OPTIONS)

    @property
    def current_option(self) -> str | None:
        """Return the current fan mode."""
        raw = (self.coordinator.data or {}).get("fan_mode")

        try:
            self._current = FAN_MODE_STATE.get(int(raw), self._current)
        except (TypeError, ValueError):
            if isinstance(raw, str):
                self._current = {
                    "quiet": "Quiet",
                    "default": "Default",
                    "full power": "Full Power",
                }.get(raw.lower(), self._current)

        return self._current

    async def async_select_option(self, option: str) -> None:
        """Press the mapped button and refresh the current fan mode."""
        button_key = FAN_MODE_OPTIONS.get(option)
        entity_id = er.async_get(self.hass).async_get_entity_id(
            "button",
            DOMAIN,
            f"{self._entry.entry_id}_{button_key}",
        ) if button_key else None

        if not entity_id:
            _LOGGER.warning("[UGREEN NAS] Fan mode button not found for option: %s", option)
            return

        self._current = option
        self.async_write_ha_state()

        await self.hass.services.async_call(
            "button",
            "press",
            {"entity_id": entity_id},
            blocking=True,
        )

        await self.coordinator.async_request_refresh()
