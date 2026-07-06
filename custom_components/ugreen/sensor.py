import logging, re

from typing import List, Tuple
from datetime import date, datetime
from decimal import Decimal

from homeassistant.core import HomeAssistant
from homeassistant.const import MATCH_ALL
from homeassistant.config_entries import ConfigEntry
from homeassistant.util import slugify
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN, DEFAULT_ENTITY_PREFIX
from .device_info import build_device_info
from .entities import UgreenEntity
from .utils import (
    determine_unit,
    format_sensor_value,
    format_unix_timestamp,
    strip_parent_prefix,
)


_LOGGER = logging.getLogger(__name__)


# --------------------------------------------------------------------------------------
# Helpers for Multi-NAS feature
# --------------------------------------------------------------------------------------

def _get_entity_prefix(hass: HomeAssistant, entry_id: str) -> str:
    """Return the configured NAS prefix for entity names."""
    return (
        hass.data.get(DOMAIN, {}).get(entry_id, {}).get("root_device_name")
        or DEFAULT_ENTITY_PREFIX
    )


def _get_entity_prefix_slug(hass: HomeAssistant, entry_id: str) -> str:
    """Return a slugified NAS prefix for default entity_ids."""
    return slugify(_get_entity_prefix(hass, entry_id)) or "ugreen_nas"


# --------------------------------------------------------------------------------------
# Helpers for statistics metadata
# --------------------------------------------------------------------------------------

_DATA_RATE_UNITS = {"B/s", "kB/s", "MB/s", "GB/s", "TB/s", "PB/s"}

_RAM_SIZE_KEYS = {
    "ram_usage_total_usable",
    "ram_usage_free",
    "ram_usage_cache",
    "ram_usage_shared",
    "ram_usage_used_gb",
    "ram_total_size",
}


def _get_statistics_meta(
    endpoint: UgreenEntity,
) -> tuple[SensorStateClass | None, SensorDeviceClass | None]:
    """Return statistics metadata for numeric sensors."""

    key = endpoint.description.key
    unit = str(endpoint.description.unit_of_measurement or "")
    path = getattr(endpoint, "path", "")

    # Calculated bps (note: the human-readable transfer rate strings are not numeric).
    if isinstance(path, str) and path.startswith("calculated:scale_bytes_per_second"):
        return None, None

    # SMART schedule and history timestamps.
    if key.endswith(("_smart_last_test", "_smart_next_test")):
        return None, SensorDeviceClass.TIMESTAMP

    # Percentages: CPU / RAM usage.
    if key in {"cpu_usage", "mem_usage"}:
        return SensorStateClass.MEASUREMENT, None

    # RAM byte values.
    if key in _RAM_SIZE_KEYS:
        return SensorStateClass.MEASUREMENT, SensorDeviceClass.DATA_SIZE

    # Temperatures: CPU, disks, cache disks.
    if key == "cpu_temperature" or (
        key.endswith("_temperature") and "disk" in key
    ):
        return SensorStateClass.MEASUREMENT, SensorDeviceClass.TEMPERATURE

    # Fan RPM values.
    if key == "cpu_fan_speed" or (
        key.startswith("device_fan") and key.endswith("_speed")
    ):
        return SensorStateClass.MEASUREMENT, None

    # Raw transfer rates only, not formatted "123 MB/s" string sensors.
    if key.endswith("_raw") and unit in _DATA_RATE_UNITS:
        return SensorStateClass.MEASUREMENT, SensorDeviceClass.DATA_RATE

    return None, None


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
    # One summary entity per Pool / Volume / Disk / Cache under NAS root
    # --------------------------------------------------------------------------
    data_ctx = hass.data[DOMAIN][entry.entry_id]
    status_coord: DataUpdateCoordinator = data_ctx["state_coordinator"]
    config_coord: DataUpdateCoordinator = data_ctx["config_coordinator"]

    pool_meta   = (data_ctx.get("pool_meta")   or {})
    volume_meta = (data_ctx.get("volume_meta") or {})
    disk_meta   = (data_ctx.get("disk_meta")   or {})
    cache_disk_meta = (data_ctx.get("cache_disk_meta") or {})
    cache_meta = (data_ctx.get("cache_meta") or {})

    summary_entities: list[UgreenNasRootObjectSummary] = []

    # Pools
    for p in sorted(pool_meta.keys()):
        summary_entities.append(
            UgreenNasRootObjectSummary(
                hass, entry.entry_id, status_coord, config_coord,
                title=f"Pool {p}", match_kind="pool", match_key=(p,)
            )
        )

    # Cache (if present)
    for p in sorted(cache_meta.keys()):
        summary_entities.append(
            UgreenNasRootObjectSummary(
                hass, entry.entry_id, status_coord, config_coord,
                title=f"Cache {p}", match_kind="cache", match_key=(p,)
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
        entity_prefix = _get_entity_prefix(hass, entry_id)
        self._attr_name = f"{entity_prefix} {endpoint.description.name}"
        self.entity_id = async_generate_entity_id("sensor.{}", self._attr_name, hass=self.hass)
        self._attr_unique_id = f"{entry_id}_{endpoint.description.key}"
        self._attr_icon = endpoint.description.icon
        self._attr_state_class, self._attr_device_class = _get_statistics_meta(endpoint)
        self._attr_device_info = build_device_info(hass, entry_id, self._key)

    @property
    def native_value(self) -> StateType | date | datetime | Decimal:
        raw = self.coordinator.data.get(self._key)

        if self._attr_device_class == SensorDeviceClass.TIMESTAMP:
            return format_unix_timestamp(raw)

        return format_sensor_value(raw, self._endpoint)

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        base_attrs = dict(super().extra_state_attributes or {})
        base_attrs.update({
            "UGNAS_global_id": "UGREEN NAS",
            "UGNAS_device_id": _get_entity_prefix_slug(self.hass, self._entry_id),
            "UGNAS_part_category": self._endpoint.nas_part_category,
        })
        return base_attrs


    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the appropriate unit for the current sensor value."""
        raw = self.coordinator.data.get(self._key)
        unit = self._endpoint.description.unit_of_measurement
        name = self._endpoint.description.name or ""
        path = self._endpoint.path

        if raw == "":
            return None

        # Raw sensors keep their declared unit because their value is not scaled.
        if "(raw)" in name.lower():
            return unit

        # Human-readable calculated values already contain their unit.
        if path.startswith("calculated:scale_bytes_per_second:"):
            return None

        # Dynamic scaling for real numeric units (non-calculated)
        if unit in ("B/s", "kB/s", "MB/s", "GB/s", "TB/s", "PB/s"):
            return determine_unit(raw, unit, True)

        if unit in ("B", "kB", "MB", "GB", "TB", "PB"):
            return determine_unit(raw, unit, False)

        # Everything else: keep as-is (including None for text attributes)
        return unit



    def _handle_coordinator_update(self) -> None:
        self._attr_native_value = self.native_value
        self._attr_native_unit_of_measurement = self.native_unit_of_measurement
        super()._handle_coordinator_update()


# --------------------------------------------------------------------------------------
# Summary sensors: one per pool / volume / disk / cache, attached to NAS root device
# --------------------------------------------------------------------------------------

_TRANSFER_RATE_SUFFIXES = (
    "_read_rate",
    "_read_rate_raw",
    "_write_rate",
    "_write_rate_raw",
)


def _disk_display_name(slot: object, fallback: object = None) -> str | None:
    """Return a stable disk label derived from the physical slot."""
    slot_text = str(slot or "").strip()
    for pattern, prefix in (
        (r"^(?:s?ata)(\d+)$", "Disk"),
        (r"^nvme(\d+)$", "M.2 Disk"),
    ):
        if match := re.fullmatch(pattern, slot_text, re.IGNORECASE):
            return f"{prefix} {int(match.group(1))}"

    fallback_text = str(fallback or "").strip()
    if match := re.fullmatch(
        r"(M\.2\s+)?Hard Drive\s+(\d+)",
        fallback_text,
        re.IGNORECASE,
    ):
        prefix = "M.2 Disk" if match.group(1) else "Disk"
        return f"{prefix} {int(match.group(2))}"

    return fallback_text or None


class UgreenNasRootObjectSummary(CoordinatorEntity, SensorEntity):
    """One summary entity per Pool / Volume / Disk / Cache, attached to NAS root device."""

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
        self._nas_device_id = _get_entity_prefix_slug(hass, entry_id)

        # Friendly name (stable " Summary" suffix)
        self._attr_has_entity_name = False
        entity_prefix = _get_entity_prefix(hass, entry_id)
        base_name = f"{entity_prefix} {title} Summary"
        self._attr_name = base_name
        # Ensure entity_id contains "_summary" (generated from name)
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

            if self._kind == "cache":
                (p,) = self._mk
                if f"_cache_pool{p}_" in uid:
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

    # ---------- dynamic display name and summary helpers ----------

    def _entity_key(self, entity_id: str) -> str:
        """Return the integration key for a registered child entity."""
        registry_entry = er.async_get(self.hass).async_get(entity_id)
        unique_id = (registry_entry.unique_id or "") if registry_entry else ""
        prefix = f"{self._entry_id}_"
        return unique_id[len(prefix):] if unique_id.startswith(prefix) else unique_id

    def _coordinator_value(self, key: str) -> object:
        """Return the unformatted value from either coordinator."""
        for coordinator in (self._config, self._status):
            data = coordinator.data or {}
            if key in data:
                return data[key]
        return None

    def _find_key_value(
        self,
        pairs: List[Tuple[str, str]],
        suffix: str,
    ) -> str | None:
        """Return an unformatted child value selected by key suffix."""
        for _, ent_id in pairs:
            key = self._entity_key(ent_id)
            if not key.endswith(suffix):
                continue
            value = self._coordinator_value(key)
            if value not in (None, "", "unknown", "unavailable"):
                return str(value)
        return None

    def _capacity_attribute(self, key: str) -> tuple[bool, str | None]:
        """Map capacity keys to normalized summary attributes."""
        if self._kind in ("disk", "cache_disk"):
            return (True, "Size") if key.endswith("_size") else (False, None)

        if self._kind == "pool":
            for suffix, name in (
                ("_total", "Size"),
                ("_used", "Used"),
                ("_free", "Free"),
            ):
                if key.endswith(suffix):
                    return True, name
            return (True, None) if key.endswith("_available") else (False, None)

        if self._kind == "volume":
            if key.endswith(("_total_raw", "_used_raw", "_available_raw")):
                return True, None
            for suffix, name in (
                ("_total", "Size"),
                ("_used", "Used"),
                ("_available", "Free"),
            ):
                if key.endswith(suffix):
                    return True, name

        return False, None

    def _pool_members(self) -> tuple[list[str], list[str]]:
        """Return normalized disk names and technical slots for this pool."""
        if self._kind != "pool":
            return [], []

        pool_index = self._mk[0]
        reg = er.async_get(self.hass)
        members: dict[int, dict[str, str]] = {}

        for ent in er.async_entries_for_config_entry(reg, self._entry_id):
            if ent.platform != DOMAIN or ent.domain != "sensor":
                continue

            unique_id = ent.unique_id or ""
            prefix = f"{self._entry_id}_"
            key = unique_id[len(prefix):] if unique_id.startswith(prefix) else unique_id
            match = re.fullmatch(
                r"disk(\d+)_pool(\d+)_(slot|label|dev_name)",
                key,
            )
            if not match or int(match.group(2)) != pool_index:
                continue

            value = self._coordinator_value(key)
            if value in (None, ""):
                state = self.hass.states.get(ent.entity_id)
                value = state.state if state else None
            if value in (None, "", "unknown", "unavailable"):
                continue

            members.setdefault(int(match.group(1)), {})[match.group(3)] = str(value)

        names: list[str] = []
        slots: list[str] = []
        for disk_index in sorted(members):
            member = members[disk_index]
            slot = member.get("slot", "")
            fallback = member.get("label") or f"Disk {disk_index}"
            names.append(_disk_display_name(slot, fallback) or fallback)
            if slot:
                slots.append(slot)

        return names, slots

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
        """Flatten child states into stable summary attributes."""
        out: dict[str, object] = {}

        for hint, ent_id in pairs:
            key = self._entity_key(ent_id)
            st = self.hass.states.get(ent_id)
            friendly = (
                st.attributes.get("friendly_name") if st else None
            ) or hint or ent_id
            clean = strip_parent_prefix(str(friendly)).strip()

            if key.endswith(_TRANSFER_RATE_SUFFIXES) or clean.lower() in {
                "read rate",
                "read rate (raw)",
                "write rate",
                "write rate (raw)",
            }:
                continue

            handled, capacity_name = self._capacity_attribute(key)
            if handled:
                if capacity_name and st and st.state not in (
                    "unknown",
                    "unavailable",
                    "",
                ):
                    unit = st.attributes.get("unit_of_measurement")
                    out[capacity_name] = f"{st.state}{(' ' + unit) if unit else ''}"

                    raw = self._coordinator_value(key)
                    if raw not in (None, ""):
                        out[f"{capacity_name} (raw)"] = f"{raw} B"
                continue

            if not st or st.state in ("unknown", "unavailable", ""):
                continue

            unit = st.attributes.get("unit_of_measurement")
            out[clean] = f"{st.state}{(' ' + unit) if unit else ''}"

        if self._kind == "pool":
            member_disks, member_slots = self._pool_members()
            if member_disks:
                out["Member Disks"] = member_disks
            if member_slots:
                out["Member Slots"] = member_slots

        return out

    # ---------- build state & attributes (with no-op guard) ----------

    def _rebuild(self) -> None:
        pairs = self._collect_targets()

        # 1) dynamic entity name from Label (keep " Summary" suffix)
        label_val = self._find_label_value(pairs)
        if self._kind in ("disk", "cache_disk"):
            label_val = _disk_display_name(
                self._find_key_value(pairs, "_slot"),
                label_val,
            )
        if label_val:
            entity_prefix = _get_entity_prefix(self.hass, self._entry_id)
            new_name = f"{entity_prefix} {label_val} Summary"
            if getattr(self, "_attr_name", None) != new_name:
                self._attr_name = new_name

        # 2) attributes from children (labels stripped)
        attrs = self._flatten_states_as_attrs(pairs)

        # 3) state from Status (fallback: attribute count)
        status_val = self._find_status_value(pairs)
        new_state = status_val if status_val is not None else len(attrs)

        # 4) META attributes (not recorded)
        kind_map = {
            "pool": "Pool",
            "volume": "Volume",
            "disk": "Disk",
            "cache": "Cache",
            "cache_disk": "Cache Disk",
        }
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
        elif self._kind == "cache":
            meta["UGNAS_pool_index"] = self._mk[0]
        elif self._kind == "cache_disk":
            # if self._last_pd:
            if getattr(self, "_last_pd", None):
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
