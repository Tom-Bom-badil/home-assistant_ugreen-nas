import re

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN

_RE_STANDALONE_DISK = re.compile(r"^standalone_disk(?P<d>\d+)(?:_|$)")
_RE_DISK = re.compile(r"^disk(?P<d>\d+)_pool(?P<p>\d+)(?:_|$)")
_RE_CACHE_DISK = re.compile(r"^cache_disk(?P<d>\d+)_pool(?P<p>\d+)(?:_|$)")
_RE_CACHE = re.compile(r"^cache_pool(?P<p>\d+)(?:_|$)")
_RE_VOLUME = re.compile(r"^volume(?P<v>\d+)_pool(?P<p>\d+)(?:_|$)")
_RE_POOL = re.compile(r"^pool(?P<p>\d+)(?:_|$)")

def build_device_info(
    hass: HomeAssistant,
    entry_id: str,
    key: str,
    model: str | None = None,
) -> DeviceInfo:
    """Build DeviceInfo anchored to the config entry root device."""
    root_id = f"entry:{entry_id}"
    ctx = hass.data.get(DOMAIN, {}).get(entry_id, {})
    root_name = ctx.get("root_device_name") or "UGREEN NAS"
    def sub_id(kind: str, p: int, n: int | None = None) -> str:
        if n is None:
            return f"entry:{entry_id}:{kind}:{p}"
        return f"entry:{entry_id}:{kind}:{p}:{n}"
    def _via_device_id(identifier: str) -> str:
        try:
            return dr.async_get_device_id_by_identifier(
                hass,
                (DOMAIN, identifier),
                config_entry_id=entry_id,
            )
        except ValueError:
            match = re.fullmatch(
                rf"entry:{re.escape(entry_id)}:pool:(?P<p>\d+)", identifier
            )
            if not match:
                raise
            p = int(match.group("p"))
            mfg, raid = (ctx.get("pool_meta") or {}).get(
                p, ("Linux mdadm", None)
            )
            mfg = mfg or "Linux mdadm"
            raid_upper = (raid or "").upper()
            model_display = (
                raid_upper
                if raid_upper and raid_upper.lower().startswith(mfg.lower())
                else f"{mfg} {raid_upper}" if raid_upper else mfg
            )
            return dr.async_get(hass).async_get_or_create(
                config_entry_id=entry_id,
                identifiers={(DOMAIN, identifier)},
                name=f"{root_name} (Pool {p})",
                manufacturer=mfg,
                model=f"{model_display} pool",
                via_device_id=dr.async_get_device_id_by_identifier(
                    hass,
                    (DOMAIN, root_id),
                    config_entry_id=entry_id,
                ),
            ).id
    # Explicitly detected stand-alone disks.
    match = _RE_STANDALONE_DISK.match(key)
    if match:
        disk_number = int(match.group("d"))
        disk = next(
            (
                item
                for item in ctx.get("standalone_disks") or []
                if isinstance(item, dict)
                and str(item.get("number")) == str(disk_number)
            ),
            {},
        )
        brand = str(disk.get("brand") or disk.get("manufacturer") or "").strip()
        model_raw = str(disk.get("model") or disk.get("name") or "").strip()
        model_display = (
            f"{brand} {model_raw}"
            if brand and model_raw and not model_raw.lower().startswith(brand.lower())
            else model_raw or f"Stand-alone Disk {disk_number}"
        )
        serial = str(disk.get("serial") or "").strip()
        return DeviceInfo(
            identifiers={(DOMAIN, sub_id("standalone_disk", disk_number))},
            name=f"{root_name} (Stand-alone Disk {disk_number})",
            manufacturer=brand or "UGREEN",
            model=model_display,
            serial_number=serial or None,
            via_device_id=_via_device_id(root_id),
        )
    # Cache Disks (keys like "cache_disk1_pool2_*").
    match = _RE_CACHE_DISK.match(key)
    if match:
        d = int(match.group("d"))
        p = int(match.group("p"))
        brand, model_raw = (ctx.get("cache_disk_meta") or {}).get(
            (p, d), (None, None)
        )
        if brand and model_raw and not model_raw.lower().startswith(brand.lower()):
            model_display = f"{brand} {model_raw}"
        else:
            model_display = model_raw or f"Cache Disk {d}"
        return DeviceInfo(
            identifiers={(DOMAIN, sub_id("cache_disk", p, d))},
            name=f"{root_name} (Pool {p} | Cache Disk {d})",
            manufacturer=brand or "UGREEN",
            model=model_display,
            via_device_id=_via_device_id(root_id),
        )
    # Cache device per pool (keys like "cache_pool2_*").
    match = _RE_CACHE.match(key)
    if match:
        p = int(match.group("p"))
        mfg, lvl = (ctx.get("cache_meta") or {}).get(p, ("UGREEN", None))
        model_display = (lvl or "").upper() or mfg
        return DeviceInfo(
            identifiers={(DOMAIN, sub_id("cache", p))},
            name=f"{root_name} (Pool {p} | Cache)",
            manufacturer=mfg,
            model=model_display,
            via_device_id=_via_device_id(root_id),
        )
    # Disks.
    match = _RE_DISK.match(key)
    if match:
        d = int(match.group("d"))
        p = int(match.group("p"))
        brand, model_raw = (ctx.get("disk_meta") or {}).get((p, d), (None, None))
        if brand and model_raw and not model_raw.lower().startswith(brand.lower()):
            model_display = f"{brand} {model_raw}"
        else:
            model_display = model_raw or f"Disk {d}"
        return DeviceInfo(
            identifiers={(DOMAIN, sub_id("disk", p, d))},
            name=f"{root_name} (Pool {p} | Disk {d})",
            manufacturer=brand or "UGREEN",
            model=model_display,
            via_device_id=_via_device_id(sub_id("pool", p)),
        )
    # Volumes.
    match = _RE_VOLUME.match(key)
    if match:
        v = int(match.group("v"))
        p = int(match.group("p"))
        mfg, fs = (ctx.get("volume_meta") or {}).get(
            (p, v), ("Linux mdadm", None)
        )
        mfg = mfg or "Linux mdadm"
        if fs:
            model_display = fs if fs.lower().startswith(mfg.lower()) else f"{mfg} {fs}"
        else:
            model_display = mfg
        return DeviceInfo(
            identifiers={(DOMAIN, sub_id("volume", p, v))},
            name=f"{root_name} (Pool {p} | Volume {v})",
            manufacturer=mfg,
            model=f"{model_display} volume",
            via_device_id=_via_device_id(sub_id("pool", p)),
        )
    # Pools.
    match = _RE_POOL.match(key)
    if match:
        p = int(match.group("p"))
        mfg, raid = (ctx.get("pool_meta") or {}).get(
            p, ("Linux mdadm", None)
        )
        mfg = mfg or "Linux mdadm"
        raid_upper = (raid or "").upper()
        model_display = (
            raid_upper
            if raid_upper and raid_upper.lower().startswith(mfg.lower())
            else f"{mfg} {raid_upper}" if raid_upper else mfg
        )
        return DeviceInfo(
            identifiers={(DOMAIN, sub_id("pool", p))},
            name=f"{root_name} (Pool {p})",
            manufacturer=mfg,
            model=f"{model_display} pool",
            via_device_id=_via_device_id(root_id),
        )
    return DeviceInfo(identifiers={(DOMAIN, root_id)})
