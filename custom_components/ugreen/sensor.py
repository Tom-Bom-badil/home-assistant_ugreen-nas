import logging, re

from typing import List, Tuple
from datetime import date, datetime
from decimal import Decimal

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import MATCH_ALL
from homeassistant.core import HomeAssistant, State
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN
from .device_info import build_device_info
from .entities import UgreenEntity
from .utils import determine_unit, format_sensor_value, strip_parent_prefix

_LOGGER = logging.getLogger(__name__)


# --------------------------------------------------------------------------------------
# Setup: regular sensors + root summary sensors
# --------------------------------------------------------------------------------------

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

    # --- get NAS DNS name once from "NAS Name" entity ---
    nas_device_id = ""
    for e in config_entities:
        if (e.description.name or "").lower() == "nas name":
            try:
                nas_device_id = str(config_coordinator.data.get(e.description.key) or "")
            except Exception:
                nas_device_id = ""
            break
    hass.data[DOMAIN][entry.entry_id]["nas_device_id"] = nas_device_id

    # Configuration sensors (60s)
    config_sensors = [
        UgreenNasSensor(hass, entry.entry_id, config_coordinator, entity)
        for entity in config_entities
    ]

    # State sensors (5s)
    state_sensors = [
        UgreenNasSensor(hass, entry.entry_id, state_coordinator, entity)
        for entity in state_entities
    ]

    async_add_entities(config_sensors + state_sensors)

    # --------------------------------------------------------------------------
    # One summary entity per Pool / Volume / Disk under NAS root
    # --------------------------------------------------------------------------
    data_ctx = hass.data[DOMAIN][entry.entry_id]
    status_coord: DataUpdateCoordinator = data_ctx["state_coordinator"]
    config_coord: DataUpdateCoordinator = data_ctx["config_coordinator"]

    pool_meta   = (data_ctx.get("pool_meta")   or {})
    volume_meta = (data_ctx.get("volume_meta") or {})
    disk_meta   = (data_ctx.get("disk_meta")   or {})
    cache_disk_meta = (data_ctx.get("cache_disk_meta") or {})

    summary_entities: list[UgreenNasRootObjectSummary] = []

    # Pools
    for p in sorted(pool_meta.keys()):
        summary_entities.append(
            UgreenNasRootObjectSummary(
                hass, entry.entry_id, status_coord, config_coord,
                title=f"Pool {p}", match_kind="pool", match_key=(p,)
            )
        )

    # Volumes (global order; running index 1..N)
    for i, (p, v) in enumerate(sorted(volume_meta.keys(), key=lambda t: (t[0], t[1])), start=1):
        summary_entities.append(
            UgreenNasRootObjectSummary(
                hass, entry.entry_id, status_coord, config_coord,
                title=f"Volume {i}",                 # <-- nur laufende Nummer
                match_kind="volume", match_key=(p, v)
            )
        )

    # Disks (global order: pool asc, disk asc)
    global_disk_pairs = sorted(disk_meta.keys(), key=lambda t: (t[0], t[1]))
    for i, _pd in enumerate(global_disk_pairs, start=1):
        summary_entities.append(
            UgreenNasRootObjectSummary(
                hass, entry.entry_id, status_coord, config_coord,
                title=f"Disk {i}", match_kind="disk", match_key=(i,)
            )
        )

    # Cache Disks (global order: pool asc, cache_disk asc)
    global_cache_disk_pairs = sorted(cache_disk_meta.keys(), key=lambda t: (t[0], t[1]))
    for i, _pcd in enumerate(global_cache_disk_pairs, start=1):
        summary_entities.append(
            UgreenNasRootObjectSummary(
                hass, entry.entry_id, status_coord, config_coord,
                title=f"Cache Disk {i}",
                match_kind="cache_disk",
                match_key=(i,)
            )
        )

    if summary_entities:
        async_add_entities(summary_entities, update_before_add=False)


# --------------------------------------------------------------------------------------
# Regular sensors
# --------------------------------------------------------------------------------------

class UgreenNasSensor(CoordinatorEntity, SensorEntity):
    """Representation of each UGREEN NAS sensor."""

    def __init__(self, hass: HomeAssistant, entry_id: str,
                coordinator: DataUpdateCoordinator, endpoint: UgreenEntity) -> None:
        super().__init__(coordinator)

        self.hass = hass
        self._entry_id = entry_id
        self._endpoint = endpoint
        self._key = endpoint.description.key
        self._nas_device_id = hass.data[DOMAIN][self._entry_id].get("nas_device_id", "")

        self._attr_name = f"UGREEN NAS {endpoint.description.name}"
        self._attr_unique_id = f"{entry_id}_{endpoint.description.key}"
        self._attr_icon = endpoint.description.icon
        self._attr_device_info = build_device_info(hass, entry_id, self._key)

    @property
    def native_value(self) -> StateType | date | datetime | Decimal:
        raw = self.coordinator.data.get(self._key)
        return format_sensor_value(raw, self._endpoint)

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        base_attrs = dict(super().extra_state_attributes or {})
        base_attrs.update({
            "UGNAS_global_id": "UGREEN NAS",
            "UGNAS_device_id": self._nas_device_id,
            "UGNAS_part_category": self._endpoint.nas_part_category,
        })
        return base_attrs

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit, keeping raw unscaled and leaving calculated values unitless."""
        raw = self.coordinator.data.get(self._key)
        unit = self._endpoint.description.unit_of_measurement
        name = self._endpoint.description.name or ""
        path = getattr(self._endpoint, "path", "")

        # 1) Explicit RAW sensors: keep declared unit (e.g., "B/s")
        if isinstance(name, str) and "(raw)" in name.lower():
            return unit

        # 2) Calculated, human-readable strings (unit embedded in state): no unit attribute
        if isinstance(path, str) and path.startswith("calculated:scale_bytes_per_second"):
            return None

        # 3) Dynamic scaling for real numeric units (non-calculated)
        if unit in ("B/s", "kB/s", "MB/s", "GB/s", "TB/s", "PB/s"):
            return determine_unit(raw, str(unit), True)
        if unit in ("B", "kB", "MB", "GB", "TB", "PB"):
            return determine_unit(raw, str(unit), False)

        # 4) Everything else: keep as-is (including None for text attributes)
        return unit


    def _handle_coordinator_update(self) -> None:
        self._attr_native_value = self.native_value
        self._attr_native_unit_of_measurement = self.native_unit_of_measurement
        super()._handle_coordinator_update()


# --------------------------------------------------------------------------------------
# Summary sensors: one per pool / volume / disk, available under the NAS root device
# --------------------------------------------------------------------------------------

class UgreenNasRootObjectSummary(CoordinatorEntity, SensorEntity):
    """One summary entity per Pool / Volume / Disk attached to the NAS root device."""

    _attr_icon = "mdi:clipboard-text-outline"
    _unrecorded_attributes = frozenset({MATCH_ALL}) # Exclude ALL attributes from recorder

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        status_coord: DataUpdateCoordinator,
        config_coord: DataUpdateCoordinator,
        *,
        title: str,
        match_kind: str,
        match_key: tuple[int, ...],
    ) -> None:
        super().__init__(status_coord)
        self.hass = hass
        self._entry_id = entry_id
        self._status = status_coord
        self._config = config_coord
        self._kind = match_kind                   # "pool" | "volume" | "disk"
        self._mk = match_key                      # (p,) | (p,v) | (global_index,)
        self._nas_device_id = hass.data[DOMAIN][entry_id].get("nas_device_id", "")

        # Friendly name (stable " Summary" suffix)
        self._attr_has_entity_name = False
        base_name = f"UGREEN NAS {title} Summary"
        self._attr_name = base_name

        # Ensure entity_id contains "_summary" (generated from name)
        # e.g. "sensor.ugreen_nas_disk_1_summary"
        self.entity_id = async_generate_entity_id("sensor.{}", self._attr_name, hass=self.hass)

        # Make unique_id explicitly end with "_summary" to separate from older IDs
        # e.g. "<entry>_root_summary_disk_1_summary"
        uid_title = re.sub(r"\s+", "_", title.strip()).lower()
        self._attr_unique_id = f"{entry_id}_root_summary_{uid_title}_summary"

        # attach to NAS root device (fallback)
        self._attr_device_info = build_device_info(hass, entry_id, key="root")

    async def async_added_to_hass(self) -> None:
        # refresh on BOTH coordinators
        self.async_on_remove(self._status.async_add_listener(self._refresh))
        self.async_on_remove(self._config.async_add_listener(self._refresh))
        self._rebuild()
        self.async_write_ha_state()

    # ---------- collect target entities (without calling API) -----------------

    def _collect_targets(self) -> List[Tuple[str, str]]:
        reg = er.async_get(self.hass)
        items: list[tuple[str, str]] = []

        for ent in er.async_entries_for_config_entry(reg, self._entry_id):
            if ent.platform != DOMAIN or ent.domain not in ("sensor",):
                continue
            friendly = ent.original_name or ent.name or ""
            nm = (friendly or "").lower()
            uid = ent.unique_id or ""
            eid = ent.entity_id

            if self._kind == "pool":
                (p,) = self._mk
                if f"(pool {p})" in nm:
                    items.append((friendly, eid))
                continue

            if self._kind == "volume":
                p, v = self._mk
                if f"(pool {p} | volume {v})" in nm:
                    items.append((friendly, eid))
                continue

            if self._kind == "disk":
                # collect candidates; determine target pair later
                if "_disk" in uid and "_pool" in uid:
                    items.append((friendly, eid))
                continue

            if self._kind == "cache_disk":
                # collect candidates; determine target pair later
                if "_cache_disk" in uid and "_pool" in uid:
                    items.append((friendly, eid))
                continue

        # if self._kind != "disk":
        if self._kind not in ("disk", "cache_disk"):
            return items

        # Determine the (pool, disk) pair for the global index
        pairs: list[tuple[int, int]] = []
        for hint, _ in items:
            nm = (hint or "").lower()
            # if "(pool " in nm and " | disk " in nm:
            if self._kind == "disk" and "(pool " in nm and " | disk " in nm:
                try:
                    inside = nm.split("(")[1].split(")")[0]  # "pool x | disk y"
                    parts = [s.strip() for s in inside.split("|")]
                    p = int(parts[0].split(" ")[1])
                    d = int(parts[1].split(" ")[1])
                    pairs.append((p, d))
                except Exception:
                    continue

            if self._kind == "cache_disk" and "(pool " in nm and " | cache disk " in nm:
                try:
                    inside = nm.split("(")[1].split(")")[0]  # "pool x | cache disk y"
                    parts = [s.strip() for s in inside.split("|")]
                    p = int(parts[0].split(" ")[1])
                    d = int(parts[1].split(" ")[2])  # "cache disk y" -> ["cache","disk","y"]
                    pairs.append((p, d))
                except Exception:
                    continue

        pairs = sorted(set(pairs), key=lambda t: (t[0], t[1]))
        idx = self._mk[0]  # 1..N
        if not (1 <= idx <= len(pairs)):
            return []
        p, d = pairs[idx - 1]
        self._last_pd = (p, d)

        filtered: list[tuple[str, str]] = []
        for hint, eid in items:
            nm = (hint or "").lower()
            # if f"(pool {p} | disk {d})" in nm:
            if self._kind == "disk" and f"(pool {p} | disk {d})" in nm:
                filtered.append((hint, eid))
            if self._kind == "cache_disk" and f"(pool {p} | cache disk {d})" in nm:
                filtered.append((hint, eid))
        return filtered

    # ---------- dynamic display name from Label ----------

    def _find_label_value(self, pairs: List[Tuple[str, str]]) -> str | None:
        for hint, ent_id in pairs:
            st = self.hass.states.get(ent_id)
            if not st:
                continue
            friendly = st.attributes.get("friendly_name") or hint or ent_id
            clean = strip_parent_prefix(str(friendly)).lower()
            if clean == "label" or clean.endswith(" label") or ent_id.endswith("_label"):
                val = st.state
                if val and val not in ("unknown", "unavailable"):
                    return str(val)
        return None

    def _find_status_value(self, pairs: List[Tuple[str, str]]) -> str | None:
        for hint, ent_id in pairs:
            st = self.hass.states.get(ent_id)
            if not st:
                continue
            friendly = st.attributes.get("friendly_name") or hint or ent_id
            clean = strip_parent_prefix(str(friendly)).lower()
            if clean == "status" or clean.endswith(" status") or ent_id.endswith("_status"):
                val = st.state
                if val and val not in ("unknown", "unavailable"):
                    return str(val)
        return None

    # ---------- local helper for Summary Entities ----------

    def _flatten_states_as_attrs(self, pairs: list[tuple[str, str]]) -> dict[str, object]:
        out: dict[str, object] = {}
        for hint, ent_id in pairs:
            if ent_id.endswith("_raw"):   # exclude *_raw entities, we only want formatted values
                continue
            st = self.hass.states.get(ent_id)
            if not st:
                continue
            friendly = st.attributes.get("friendly_name") or hint or ent_id
            clean = strip_parent_prefix(str(friendly)).strip()
            unit  = st.attributes.get("unit_of_measurement")
            val   = st.state
            if val not in ("unknown", "unavailable", None, ""):
                out[clean] = f"{val}{(' ' + unit) if unit else ''}"
        return out

    # ---------- build state & attributes (with no-op guard) ----------

    def _rebuild(self) -> None:
        pairs = self._collect_targets()

        # 1) dynamic entity name from Label (keep " Summary" suffix)
        label_val = self._find_label_value(pairs)
        if label_val:
            new_name = f"UGREEN NAS {label_val} Summary"
            if getattr(self, "_attr_name", None) != new_name:
                self._attr_name = new_name

        # 2) attributes from children (labels stripped)
        attrs = self._flatten_states_as_attrs(pairs)

        # 3) state from Status (fallback: attribute count)
        status_val = self._find_status_value(pairs)
        new_state = status_val if status_val is not None else len(attrs)

        # 4) META attributes (not recorded)
        kind_map = {"pool": "Pool", "volume": "Volume", "disk": "Disk", "cache_disk": "Cache Disk"}
        meta = {
            "UGNAS_global_id": "UGREEN NAS",
            "UGNAS_device_id": self._nas_device_id,
            "UGNAS_summary_entity_for": kind_map.get(self._kind, self._kind),
            "UGNAS_part_category": "Summary",
        }
        if self._kind == "pool":
            meta["UGNAS_pool_index"] = self._mk[0]
        elif self._kind == "volume":
            p, v = self._mk
            meta["UGNAS_pool_index"] = p
            meta["UGNAS_volume_index"] = v
        elif self._kind == "disk":
            meta["UGNAS global disk number"] = self._mk[0]
            if getattr(self, "_last_pd", None):
                p, d = self._last_pd
                meta["UGNAS member of pool"] = p
                meta["UGNAS disk number in pool"] = d
        elif self._kind == "cache_disk":
            if self._last_pd:
                p, d = self._last_pd
                meta["UGNAS member of pool"] = p
                meta["UGNAS cache disk number in pool"] = d
                meta["UGNAS global cache disk number"] = self._mk[0]

        attrs.update(meta)

        # 5) no-op guard
        if getattr(self, "_attr_native_value", None) == new_state and getattr(self, "_attr_extra_state_attributes", None) == attrs:
            return
        self._attr_native_value = new_state
        self._attr_extra_state_attributes = attrs

    def _refresh(self) -> None:
        self._rebuild()
        self.async_write_ha_state()
