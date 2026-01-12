# device_info.py
import re

from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from .const import DOMAIN


# _RE_DISK = re.compile(r"^disk(?P<d>\d+)_pool(?P<p>\d+)\b")
# _RE_CACHE_DISK = re.compile(r"^cache_disk(?P<d>\d+)_pool(?P<p>\d+)\b")
# _RE_CACHE = re.compile(r"^cache_pool(?P<p>\d+)\b")
# _RE_VOLUME = re.compile(r"^volume(?P<v>\d+)_pool(?P<p>\d+)\b")
# _RE_POOL = re.compile(r"^pool(?P<p>\d+)\b")

_RE_DISK = re.compile(r"^disk(?P<d>\d+)_pool(?P<p>\d+)(?:_|$)")
_RE_CACHE_DISK = re.compile(r"^cache_disk(?P<d>\d+)_pool(?P<p>\d+)(?:_|$)")
_RE_CACHE = re.compile(r"^cache_pool(?P<p>\d+)(?:_|$)")
_RE_VOLUME = re.compile(r"^volume(?P<v>\d+)_pool(?P<p>\d+)(?:_|$)")
_RE_POOL = re.compile(r"^pool(?P<p>\d+)(?:_|$)")


def build_device_info(hass: HomeAssistant, entry_id: str, key: str, model: str | None = None) -> DeviceInfo:
    """Build DeviceInfo anchored to the config entry root device."""
    root_id = f"entry:{entry_id}"
    ctx = hass.data.get(DOMAIN, {}).get(entry_id, {})
    root_name = ctx.get("root_device_name") or "UGREEN NAS"

    # Cache Disks (keys like "cache_disk1_pool2_*")
    if key.startswith("cache_disk") and "_pool" in key:
        part0, part1, *_ = key.split("_", 2)
        d_tail = part0[len("cache_disk"):] if len(part0) > len("cache_disk") else ""
        p_tail = part1[4:] if len(part1) > 4 else ""
        d = int(d_tail) if d_tail.isdigit() else 1
        p = int(p_tail) if p_tail.isdigit() else 1

        brand, model_raw = (ctx.get("cache_disk_meta") or {}).get((p, d), (None, None))
        if brand and model_raw and not model_raw.lower().startswith(brand.lower()):
            model_disp = f"{brand} {model_raw}"
        else:
            model_disp = model_raw or f"Cache Disk {d}"

        return DeviceInfo(
            identifiers={(DOMAIN, f"ugreen_nas_cache_disk_{p}_{d}")},
            name=f"{root_name} (Pool {p} | Cache Disk {d})",
            manufacturer=brand or "UGREEN",
            model=model_disp,
            via_device=(DOMAIN, root_id),  # root-level as requested
        )

    # Cache device per pool (keys like "cache_pool2_*")
    if key.startswith("cache_pool"):
        part0, *_ = key.split("_", 1)
        p_tail = part0[len("cache_pool"):] if len(part0) > len("cache_pool") else ""
        p = int(p_tail) if p_tail.isdigit() else 1

        mfg, lvl = (ctx.get("cache_meta") or {}).get(p, ("UGREEN", None))
        model_disp = (lvl or "").upper() or mfg

        return DeviceInfo(
            identifiers={(DOMAIN, f"ugreen_nas_cache_{p}")},
            name=f"{root_name} (Pool {p} | Cache)",
            manufacturer=mfg,
            model=model_disp,
            via_device=(DOMAIN, root_id),  # root-level as requested
        )

    # Disks
    m = _RE_DISK.match(key)
    if m:
        d = int(m.group("d"))
        p = int(m.group("p"))

        brand, model_raw = (ctx.get("disk_meta") or {}).get((p, d), (None, None))
        if brand and model_raw and not model_raw.lower().startswith(brand.lower()):
            model_disp = f"{brand} {model_raw}"
        else:
            model_disp = model_raw or f"Disk {d}"

        return DeviceInfo(
            identifiers={(DOMAIN, f"ugreen_nas_disk_{p}_{d}")},
            name=f"{root_name} (Pool {p} | Disk {d})",
            manufacturer=brand or "UGREEN",
            model=model_disp,
            via_device=(DOMAIN, f"ugreen_nas_pool_{p}"),
        )

    # Volumes
    m = _RE_VOLUME.match(key)
    if m:
        v = int(m.group("v"))
        p = int(m.group("p"))

        mfg, fs = (ctx.get("volume_meta") or {}).get((p, v), ("Linux mdadm", None))
        mfg = mfg or "Linux mdadm"
        if fs:
            model_disp = fs if fs.lower().startswith(mfg.lower()) else f"{mfg} {fs}"
        else:
            model_disp = mfg

        return DeviceInfo(
            identifiers={(DOMAIN, f"ugreen_nas_volume_{p}_{v}")},
            name=f"{root_name} (Pool {p} | Volume {v})",
            manufacturer=mfg,
            model=f"{model_disp} volume",
            via_device=(DOMAIN, f"ugreen_nas_pool_{p}"),
        )

    # Pools
    m = _RE_POOL.match(key)
    if m:
        p = int(m.group("p"))

        mfg, raid = (ctx.get("pool_meta") or {}).get(p, ("Linux mdadm", None))
        mfg = mfg or "Linux mdadm"
        raid_up = (raid or "").upper()
        model_disp = raid_up if raid_up and raid_up.lower().startswith(mfg.lower()) else (f"{mfg} {raid_up}" if raid_up else mfg)

        return DeviceInfo(
            identifiers={(DOMAIN, f"ugreen_nas_pool_{p}")},
            name=f"{root_name} (Pool {p})",
            manufacturer=mfg,
            model=f"{model_disp} pool",
            via_device=(DOMAIN, root_id),
        )

    return DeviceInfo(identifiers={(DOMAIN, root_id)})
