import asyncio
import logging
import re

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from .api import UgreenApiClient
from .const import BACKUP_ENTITY_CATEGORY, CONF_STANDALONE_DISKS, DEFAULT_ENTITY_PREFIX, DOMAIN
from .device_info import build_device_info
from .entities import UgreenEntity

_LOGGER = logging.getLogger(__name__)

_MAC_RE = re.compile(r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")


def _get_entity_prefix(hass: HomeAssistant, entry_id: str) -> str:
    """Return the configured NAS prefix for entity names."""
    return (
        hass.data.get(DOMAIN, {}).get(entry_id, {}).get("root_device_name")
        or DEFAULT_ENTITY_PREFIX
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up UGREEN NAS buttons."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["config_coordinator"]
    entities: list[UgreenEntity] = hass.data[DOMAIN][entry.entry_id]["button_entities"]
    api = hass.data[DOMAIN][entry.entry_id]["api"]

    button_entities = [
        UgreenNasGenericButton(hass, entry.entry_id, coordinator, entity, api)
        for entity in entities
    ]

    # Special treatment (see below).
    button_entities.extend(
        (
            UgreenNasWakeOnLanButton(hass, entry.entry_id, coordinator),
            UgreenNasStandaloneDiskAdoptButton(hass, entry, coordinator, api),
        )
    )
    button_entities.extend(
        UgreenNasStandaloneDiskForgetButton(
            hass, entry, coordinator, disk_number
        )
        for disk_number in _get_standalone_disk_numbers(entry)
    )
    if hass.data[DOMAIN][entry.entry_id].get("backup_tasks"):
        backup_coordinator = hass.data[DOMAIN][entry.entry_id]["backup_coordinator"]
        button_entities.extend((
            UgreenNasBackupTaskActionButton(
                hass, entry, backup_coordinator, api, action="start"
            ),
            UgreenNasBackupTaskActionButton(
                hass, entry, backup_coordinator, api, action="stop"
            ),
        ))

    _remove_legacy_global_forget_button(hass, entry.entry_id)
    async_add_entities(button_entities)


class UgreenNasGenericButton(CoordinatorEntity, ButtonEntity):
    """UGREEN NAS action button backed by UGOS API calls - defined in entities.py."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        coordinator: DataUpdateCoordinator,
        endpoint: UgreenEntity,
        api: UgreenApiClient,
    ) -> None:
        super().__init__(coordinator)
        self.hass = hass
        self._entry_id = entry_id
        self._endpoint = endpoint
        self._api = api
        self._key = endpoint.description.key

        entity_prefix = _get_entity_prefix(hass, entry_id)
        self._attr_name = f"{entity_prefix} {endpoint.description.name}"
        self.entity_id = async_generate_entity_id(
            "button.{}", self._attr_name, hass=self.hass
        )
        self._attr_unique_id = f"{entry_id}_{self._key}"
        self._attr_icon = endpoint.description.icon
        self._attr_device_info = build_device_info(hass, entry_id, self._key)

    async def async_press(self) -> None:
        """Perform the button action."""
        try:
            session = async_get_clientsession(self.hass)
            await self._api.authenticate(session)
            method = str(self._endpoint.request_method or "GET").upper()
            path = self._endpoint.endpoint

            if method == "POST":
                await self._api.post(session, path, self._endpoint.payload)
            elif method == "GET":
                await self._api.get(session, path)
            else:
                _LOGGER.warning("Unsupported method: %s", method)
        except Exception as e:
            _LOGGER.error("Error pressing button %s: %s", self._key, e)

    def _handle_coordinator_update(self) -> None:
        self._attr_press = self.async_press
        super()._handle_coordinator_update()


def _get_standalone_disk_numbers(entry: ConfigEntry) -> list[int]:
    """Return stored stand-alone disk numbers in stable order."""
    stored = entry.data.get(CONF_STANDALONE_DISKS, [])
    if not isinstance(stored, list):
        return []

    numbers = {
        int(item["number"])
        for item in stored
        if isinstance(item, dict)
        and str(item.get("number", "")).isdigit()
        and int(item["number"]) > 0
    }
    return sorted(numbers)


def _remove_legacy_global_forget_button(
    hass: HomeAssistant, entry_id: str
) -> None:
    """Remove the superseded global stand-alone disk forget button."""
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id(
        "button", DOMAIN, f"{entry_id}_forget_stand_alone_disks"
    )
    if entity_id:
        registry.async_remove(entity_id)


class UgreenNasStandaloneDiskAdoptButton(CoordinatorEntity, ButtonEntity):
    """Adopt currently unassigned disks as explicitly managed devices."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        coordinator: DataUpdateCoordinator,
        api: UgreenApiClient,
    ) -> None:
        super().__init__(coordinator)
        self.hass = hass
        self._entry = entry
        self._entry_id = entry.entry_id
        self._api = api
        self._key = "detect_stand_alone_disks"

        self._attr_name = (
            f"{_get_entity_prefix(hass, entry.entry_id)} "
            "Stand-alone disks: Adopt"
        )
        self.entity_id = async_generate_entity_id(
            "button.{}", self._attr_name, hass=self.hass
        )
        self._attr_unique_id = f"{entry.entry_id}_{self._key}"
        self._attr_icon = "mdi:harddisk-plus"
        self._attr_device_info = build_device_info(
            hass, entry.entry_id, self._key
        )

    async def async_press(self) -> None:
        """Persist currently unassigned disks and reload the config entry."""
        try:
            session = async_get_clientsession(self.hass)
            if not await self._api.authenticate(session):
                _LOGGER.error(
                    "[UGREEN NAS] Stand-alone disk adoption failed: "
                    "authentication failed"
                )
                return

            detected = await self._api.get_unassigned_disks(session)
            stored = self._entry.data.get(CONF_STANDALONE_DISKS, [])
            stored = stored if isinstance(stored, list) else []
            merged = UgreenApiClient.merge_standalone_disks(stored, detected)

            if merged == stored:
                _LOGGER.info(
                    "[UGREEN NAS] Stand-alone disk adoption completed; "
                    "no new disks found"
                )
                return

            added = max(0, len(merged) - len(stored))
            data = dict(self._entry.data)
            data[CONF_STANDALONE_DISKS] = merged
            self.hass.config_entries.async_update_entry(self._entry, data=data)
            _LOGGER.info(
                "[UGREEN NAS] Stand-alone disk adoption stored %d disk(s), "
                "%d new",
                len(merged),
                added,
            )
            self.hass.async_create_task(
                self.hass.config_entries.async_reload(self._entry_id),
                "reload UGREEN NAS after stand-alone disk adoption",
            )
        except Exception as e:
            _LOGGER.error("[UGREEN NAS] Stand-alone disk adoption failed: %s", e)

    def _handle_coordinator_update(self) -> None:
        self._attr_press = self.async_press
        super()._handle_coordinator_update()


class UgreenNasStandaloneDiskForgetButton(CoordinatorEntity, ButtonEntity):
    """Forget one explicitly managed stand-alone disk."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        coordinator: DataUpdateCoordinator,
        disk_number: int,
    ) -> None:
        super().__init__(coordinator)
        self.hass = hass
        self._entry = entry
        self._entry_id = entry.entry_id
        self._disk_number = disk_number
        self._key = f"standalone_disk{disk_number}_forget"

        self._attr_name = (
            f"{_get_entity_prefix(hass, entry.entry_id)} "
            f"(Stand-alone Disk {disk_number}) Forget"
        )
        self.entity_id = async_generate_entity_id(
            "button.{}", self._attr_name, hass=self.hass
        )
        self._attr_unique_id = f"{entry.entry_id}_{self._key}"
        self._attr_icon = "mdi:harddisk-remove"
        self._attr_device_info = build_device_info(
            hass, entry.entry_id, self._key
        )

    async def async_press(self) -> None:
        """Forget this stand-alone disk and clean its registry entries."""
        stored = self._entry.data.get(CONF_STANDALONE_DISKS, [])
        stored = stored if isinstance(stored, list) else []
        remaining = [
            item
            for item in stored
            if not (
                isinstance(item, dict)
                and str(item.get("number")) == str(self._disk_number)
            )
        ]

        data = dict(self._entry.data)
        if remaining:
            data[CONF_STANDALONE_DISKS] = remaining
        else:
            data.pop(CONF_STANDALONE_DISKS, None)
        self.hass.config_entries.async_update_entry(self._entry, data=data)

        self.hass.async_create_task(
            self._reload_and_cleanup(),
            f"forget UGREEN NAS stand-alone disk {self._disk_number}",
        )

    async def _reload_and_cleanup(self) -> None:
        """Reload without this disk, then remove its registry entries."""
        try:
            if not await self.hass.config_entries.async_reload(self._entry_id):
                _LOGGER.error(
                    "[UGREEN NAS] Stand-alone disk %d was forgotten, but "
                    "config entry reload failed",
                    self._disk_number,
                )
                return

            entity_registry = er.async_get(self.hass)
            unique_id_prefix = (
                f"{self._entry_id}_standalone_disk{self._disk_number}_"
            )
            entity_ids = [
                item.entity_id
                for item in entity_registry.entities.values()
                if item.config_entry_id == self._entry_id
                and item.unique_id.startswith(unique_id_prefix)
            ]
            for entity_id in entity_ids:
                entity_registry.async_remove(entity_id)

            device_registry = dr.async_get(self.hass)
            identifier = (
                DOMAIN,
                f"entry:{self._entry_id}:standalone_disk:{self._disk_number}",
            )
            device = device_registry.async_get_device(identifiers={identifier})
            if device:
                device_registry.async_remove_device(device.id)

            _LOGGER.info(
                "[UGREEN NAS] Forgot stand-alone disk %d and removed "
                "%d entities and %d device",
                self._disk_number,
                len(entity_ids),
                int(device is not None),
            )
        except Exception as e:
            _LOGGER.error(
                "[UGREEN NAS] Failed to clean up stand-alone disk %d: %s",
                self._disk_number,
                e,
            )

    def _handle_coordinator_update(self) -> None:
        self._attr_press = self.async_press
        super()._handle_coordinator_update()


class UgreenNasBackupTaskActionButton(CoordinatorEntity, ButtonEntity):
    """Start or stop the currently selected UGOS backup task."""

    _ACTIONS = {
        "start": ("backup_task_start", "Backup: Start", "mdi:play-circle"),
        "stop": ("backup_task_stop", "Backup: Stop", "mdi:stop-circle"),
    }

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        coordinator: DataUpdateCoordinator,
        api: UgreenApiClient,
        *,
        action: str,
    ) -> None:
        super().__init__(coordinator)
        self.hass = hass
        self._entry = entry
        self._entry_id = entry.entry_id
        self._api = api
        self._action = action
        self._press_lock = asyncio.Lock()
        self._key, label, icon = self._ACTIONS[action]

        self._attr_name = f"{_get_entity_prefix(hass, entry.entry_id)} {label}"
        self.entity_id = async_generate_entity_id(
            "button.{}", self._attr_name, hass=self.hass
        )
        self._attr_unique_id = f"{entry.entry_id}_{self._key}"
        self._attr_icon = icon
        self._attr_device_info = build_device_info(hass, entry.entry_id, self._key)

    def _tasks(self) -> list[dict[str, object]]:
        """Return current backup tasks from the coordinator or setup cache."""
        data = self.coordinator.data or {}
        tasks = data.get("tasks") or self.hass.data[DOMAIN][self._entry_id].get("backup_tasks") or []
        return [task for task in tasks if isinstance(task, dict)]

    def _selected_task(self) -> dict[str, object] | None:
        """Return the selected backup task, falling back to the first task."""
        tasks = self._tasks()
        selected_key = self.hass.data[DOMAIN][self._entry_id].get("selected_backup_task_key")
        for task in tasks:
            if UgreenApiClient.backup_task_key(task) == selected_key:
                return task
        return tasks[0] if tasks else None

    @staticmethod
    def _task_running(task: dict[str, object]) -> bool:
        """Return whether UGOS currently reports this task as running."""
        try:
            status = int(task.get("status", -1))
        except (TypeError, ValueError):
            status = -1
        try:
            progress = int(task.get("progress") or 0)
        except (TypeError, ValueError):
            progress = 0
        return bool(task.get("execute_now")) or progress > 0 or status in {2, 3, 6, 7}

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        """Expose selected backup task metadata."""
        task = self._selected_task()
        attrs: dict[str, object] = {
            "UGNAS_global_id": "UGREEN NAS",
            "UGNAS_device_id": _get_entity_prefix(self.hass, self._entry_id),
            "UGNAS_part_category": BACKUP_ENTITY_CATEGORY,
        }
        if task:
            attrs.update({
                "selected_task": UgreenApiClient.backup_task_name(task),
                "selected_task_key": UgreenApiClient.backup_task_key(task),
                "selected_task_id": task.get("id"),
                "selected_protocol": task.get("protocol"),
            })
        return attrs

    async def async_press(self) -> None:
        """Start or stop the selected backup task."""
        async with self._press_lock:
            task = self._selected_task()
            if not task:
                _LOGGER.warning(
                    "[UGREEN NAS] No backup task selected for %s", self._action
                )
                return
            if self._action == "start" and self._task_running(task):
                return

            try:
                session = async_get_clientsession(self.hass)
                if not await self._api.authenticate(session):
                    _LOGGER.error(
                        "[UGREEN NAS] Backup task %s failed: authentication failed",
                        self._action,
                    )
                    return

                if self._action == "start":
                    resp = await self._api.start_backup_task(session, task)
                else:
                    resp = await self._api.stop_backup_task(session, task)

                if (resp or {}).get("code") != 200:
                    _LOGGER.warning(
                        "[UGREEN NAS] Backup task %s returned code=%s msg=%s",
                        self._action,
                        (resp or {}).get("code"),
                        (resp or {}).get("msg"),
                    )
                    return

                _LOGGER.info(
                    "[UGREEN NAS] Backup task %s requested for '%s'",
                    self._action,
                    UgreenApiClient.backup_task_name(task),
                )
                await self.coordinator.async_request_refresh()
            except Exception as e:
                _LOGGER.error(
                    "[UGREEN NAS] Backup task %s failed for '%s': %s",
                    self._action,
                    UgreenApiClient.backup_task_name(task),
                    e,
                )

    def _handle_coordinator_update(self) -> None:
        self._attr_press = self.async_press
        super()._handle_coordinator_update()


class UgreenNasWakeOnLanButton(CoordinatorEntity, ButtonEntity):
    """UGreen NAS wake_on_lan button (fire&forget method)."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        coordinator: DataUpdateCoordinator,
    ) -> None:
        super().__init__(coordinator)
        self.hass = hass
        self._entry_id = entry_id
        self._key = "power_action_wake_up"

        entity_prefix = _get_entity_prefix(hass, entry_id)
        self._attr_name = f"{entity_prefix} Power Action: Wake Up"
        self.entity_id = async_generate_entity_id(
            "button.{}", self._attr_name, hass=self.hass
        )
        self._attr_unique_id = f"{entry_id}_power_action_wake_up"
        self._attr_icon = "mdi:power"
        self._attr_device_info = build_device_info(hass, entry_id, self._key)

    def _collect_all_macs(self) -> list[str]:
        """Collect all valid LAN MACs."""
        macs: list[str] = []

        # 1) Device Registry (primary source, persistent)
        try:
            dev_reg = dr.async_get(self.hass)
            root_id = f"entry:{self._entry_id}"
            device = dev_reg.async_get_device(identifiers={(DOMAIN, root_id)})
            if device:
                for conn_type, value in device.connections:
                    if (
                        conn_type == dr.CONNECTION_NETWORK_MAC
                        and isinstance(value, str)
                    ):
                        mac = value.strip()
                        if _MAC_RE.match(mac):
                            macs.append(mac)
        except Exception as e:
            _LOGGER.debug(
                "[UGREEN NAS] Failed to read MACs from device registry: %s", e
            )

        # 2) Coordinator Data (fallback, volatile runtime cache)
        if not macs:
            data = self.coordinator.data or {}
            for i in range(1, 17):
                mac = data.get(f"LAN{i}_mac")
                if isinstance(mac, str):
                    mac = mac.strip()
                    if _MAC_RE.match(mac):
                        macs.append(mac)

        # 3) De-duplicate, but keep order
        seen: set[str] = set()
        uniq: list[str] = []
        for mac in macs:
            if mac not in seen:
                seen.add(mac)
                uniq.append(mac)
        return uniq

    async def async_press(self) -> None:
        """Send WOL magic packets to all known NAS MACs (fire & forget)."""
        if not self.hass.services.has_service("wake_on_lan", "send_magic_packet"):
            _LOGGER.error(
                "[UGREEN NAS] wake_on_lan service not available. "
                "Enable the wake_on_lan integration."
            )
            return

        macs = self._collect_all_macs()
        if not macs:
            _LOGGER.error(
                "[UGREEN NAS] No valid MACs found (LAN*_mac) - cannot send WOL."
            )
            return

        broadcast = "255.255.255.255"
        for mac in macs:
            _LOGGER.info(
                "[UGREEN NAS] Sending WOL packet to %s via %s:9", mac, broadcast
            )
            await self.hass.services.async_call(
                "wake_on_lan",
                "send_magic_packet",
                {
                    "mac": mac,
                    "broadcast_address": broadcast,
                    "broadcast_port": 9,
                },
                blocking=False,
            )

    def _handle_coordinator_update(self) -> None:
        self._attr_press = self.async_press
        super()._handle_coordinator_update()
