import logging
import re

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.button import ButtonEntity
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback


from .device_info import build_device_info
from .const import DOMAIN
from .api import UgreenApiClient
from .entities import UgreenEntity

_LOGGER = logging.getLogger(__name__)
_MAC_RE = re.compile(r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback
) -> None:
    """Set up UGREEN NAS buttons.."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["config_coordinator"]
    entities: list[UgreenEntity] = hass.data[DOMAIN][entry.entry_id]["button_entities"]
    api = hass.data[DOMAIN][entry.entry_id]["api"]
    # general (see entities.py)
    button_entities = [
        UgreenNasButton(hass, entry.entry_id, coordinator, entity, api)
        for entity in entities
    ]
    # specific (see below)
    button_entities.append(UgreenNasWakeOnLanButton(hass, entry.entry_id, coordinator))
    async_add_entities(button_entities)


class UgreenNasButton(CoordinatorEntity, ButtonEntity):
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
        self._attr_name = endpoint.description.name
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
                await self._api.post(session, path)
            elif method == "GET":
                await self._api.get(session, path)
            else:
                _LOGGER.warning("Unsupported method: %s", method)

        except Exception as e:
            _LOGGER.error("Error pressing button %s: %s", self._key, e)

    def _handle_coordinator_update(self) -> None:
        self._attr_press = self.async_press
        super()._handle_coordinator_update()


class UgreenNasWakeOnLanButton(CoordinatorEntity, ButtonEntity):
    """UGreen NAS wake_on_lan button (fire&forget method)."""

    def __init__(self, hass: HomeAssistant, entry_id: str, coordinator: DataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self.hass = hass
        self._entry_id = entry_id
        self._key = "wake_on_lan"

        self._attr_name = "Wake Up"
        self._attr_unique_id = f"{entry_id}_wake_on_lan"
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
                    if conn_type == dr.CONNECTION_NETWORK_MAC and isinstance(value, str):
                        mac = value.strip()
                        if _MAC_RE.match(mac):
                            macs.append(mac)
        except Exception as e:
            _LOGGER.debug("[UGREEN NAS] Failed to read MACs from device registry: %s", e)

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
        for m in macs:
            if m not in seen:
                seen.add(m)
                uniq.append(m)
        return uniq

    async def async_press(self) -> None:
        """Send WOL magic packets to all known NAS MACs (fire & forget)."""
        if not self.hass.services.has_service("wake_on_lan", "send_magic_packet"):
            _LOGGER.error("[UGREEN NAS] wake_on_lan service not available. Enable the wake_on_lan integration.")
            return

        macs = self._collect_all_macs()
        if not macs:
            _LOGGER.error("[UGREEN NAS] No valid MACs found (LAN*_mac) - cannot send WOL.")
            return

        broadcast = "255.255.255.255"

        for mac in macs:
            _LOGGER.info("[UGREEN NAS] Sending WOL packet to %s via %s:9", mac, broadcast)
            await self.hass.services.async_call(
                "wake_on_lan",
                "send_magic_packet",
                {"mac": mac, "broadcast_address": broadcast, "broadcast_port": 9},
                blocking=False,
            )

    def _handle_coordinator_update(self) -> None:
        self._attr_press = self.async_press
        super()._handle_coordinator_update()
