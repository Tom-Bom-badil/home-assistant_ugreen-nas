# device_info.py
import re

from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from .const import DOMAIN


_RE_DISK = re.compile(r"^disk(?P<d>\d+)_pool(?P<p>\d+)\b")
_RE_CACHE_DISK = re.compile(r"^cache_disk(?P<d>\d+)_pool(?P<p>\d+)\b")
_RE_CACHE = re.compile(r"^cache_pool(?P<p>\d+)\b")
_RE_VOLUME = re.compile(r"^volume(?P<v>\d+)_pool(?P<p>\d+)\b")
_RE_POOL = re.compile(r"^pool(?P<p>\d+)\b")


def build_device_info(hass: HomeAssistant, entry_id: str, key: str, model: str | None = None) -> DeviceInfo:
    """Build DeviceInfo anchored to the config entry root device."""
    root_id = f"entry:{entry_id}"
    ctx = hass.data.get(DOMAIN, {}).get(entry_id, {})
    root_name = ctx.get("root_device_name") or "UGREEN NAS"

    # Cache Disks
    m = _RE_CACHE_DISK.match(key)
    if m:
        d = int(m.group("d"))
        p = int(m.group("p"))

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
            via_device=(DOMAIN, f"ugreen_nas_cache_{p}"),
        )

    # Cache (Pool-level)
    m = _RE_CACHE.match(key)
    if m:
        p = int(m.group("p"))

        mfg, lvl = (ctx.get("cache_meta") or {}).get(p, ("UGREEN", None))
        mfg = mfg or "UGREEN"
        lvl_up = (lvl or "").upper()
        model_disp = f"{lvl_up} cache" if lvl_up else "SSD cache"

        return DeviceInfo(
            identifiers={(DOMAIN, f"ugreen_nas_cache_{p}")},
            name=f"{root_name} (Pool {p} | Cache)",
            manufacturer=mfg,
            model=model_disp,
            via_device=(DOMAIN, f"ugreen_nas_pool_{p}"),
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




# from homeassistant.core import HomeAssistant
# from homeassistant.helpers.device_registry import DeviceInfo
# from .const import DOMAIN


# def build_device_info(hass: HomeAssistant, entry_id: str, key: str, model: str | None = None) -> DeviceInfo:
#     """Build DeviceInfo anchored to the config entry root device."""

#     root_id = f"entry:{entry_id}"
#     ctx = hass.data.get(DOMAIN, {}).get(entry_id, {})  # cached meta from __init__.py
#     root_name = ctx.get("root_device_name") or "UGREEN NAS"

#     # Disks (keys like "disk2_pool1_*" or compact "disk_pool")
#     if key.startswith("disk") and "_pool" in key:
#         part0, part1, *_ = key.split("_", 2)
#         # Be tolerant: default to 1 if no numeric suffix is present
#         d_tail = part0[4:] if len(part0) > 4 else ""
#         p_tail = part1[4:] if len(part1) > 4 else ""
#         d = int(d_tail) if d_tail.isdigit() else 1
#         p = int(p_tail) if p_tail.isdigit() else 1

#         brand, model_raw = (ctx.get("disk_meta") or {}).get((p, d), (None, None))

#         if brand and model_raw and not model_raw.lower().startswith(brand.lower()):
#             model_disp = f"{brand} {model_raw}"
#         else:
#             model_disp = model_raw or f"Disk {d}"

#         return DeviceInfo(
#             identifiers={(DOMAIN, f"ugreen_nas_disk_{p}_{d}")},
#             name=f"{root_name} (Pool {p} | Disk {d})",
#             manufacturer=brand or "UGREEN",
#             model=model_disp,
#             via_device=(DOMAIN, f"ugreen_nas_pool_{p}"),
#         )

#     # Cache Disks (keys like "cache_disk2_pool1_*")
#     if key.startswith("cache_disk") and "_pool" in key:
#         part0, part1, *_ = key.split("_", 2)
#         d_tail = part0[9:] if len(part0) > 9 else ""  # len("cache_disk") == 9
#         p_tail = part1[4:] if len(part1) > 4 else ""
#         d = int(d_tail) if d_tail.isdigit() else 1
#         p = int(p_tail) if p_tail.isdigit() else 1

#         brand, model_raw = (ctx.get("cache_disk_meta") or {}).get((p, d), (None, None))

#         if brand and model_raw and not model_raw.lower().startswith(brand.lower()):
#             model_disp = f"{brand} {model_raw}"
#         else:
#             model_disp = model_raw or f"Cache Disk {d}"

#         return DeviceInfo(
#             identifiers={(DOMAIN, f"ugreen_nas_cache_disk_{p}_{d}")},
#             name=f"{root_name} (Pool {p} | Cache Disk {d})",
#             manufacturer=brand or "UGREEN",
#             model=model_disp,
#             via_device=(DOMAIN, f"ugreen_nas_cache_{p}"),
#         )

#     # Cache (keys like "cache_pool1_*")
#     if key.startswith("cache_pool"):
#         part0, *_ = key.split("_", 1)
#         p_tail = part0[10:] if len(part0) > 10 else ""  # len("cache_pool") == 10
#         p = int(p_tail) if p_tail.isdigit() else 1

#         mfg, lvl = (ctx.get("cache_meta") or {}).get(p, ("UGREEN", None))
#         mfg = mfg or "UGREEN"
#         lvl_up = (lvl or "").upper()

#         model_disp = f"{lvl_up} cache" if lvl_up else "SSD cache"

#         return DeviceInfo(
#             identifiers={(DOMAIN, f"ugreen_nas_cache_{p}")},
#             name=f"{root_name} (Pool {p} | Cache)",
#             manufacturer=mfg,
#             model=model_disp,
#             via_device=(DOMAIN, f"ugreen_nas_pool_{p}"),
#         )

#     # Volumes (keys like "volume1_pool1_*" or compact "volume_pool")
#     if key.startswith("volume") and "_pool" in key:
#         part0, part1, *_ = key.split("_", 2)
#         # Be tolerant: default to 1 if no numeric suffix is present
#         v_tail = part0[6:] if len(part0) > 6 else ""
#         p_tail = part1[4:] if len(part1) > 4 else ""
#         v = int(v_tail) if v_tail.isdigit() else 1
#         p = int(p_tail) if p_tail.isdigit() else 1

#         mfg, fs = (ctx.get("volume_meta") or {}).get((p, v), ("Linux mdadm", None))
#         mfg = mfg or "Linux mdadm"

#         if fs:
#             model_disp = fs if fs.lower().startswith(mfg.lower()) else f"{mfg} {fs}"
#         else:
#             model_disp = mfg

#         return DeviceInfo(
#             identifiers={(DOMAIN, f"ugreen_nas_volume_{p}_{v}")},
#             name=f"{root_name} (Pool {p} | Volume {v})",
#             manufacturer=mfg,
#             model=f"{model_disp} volume",
#             via_device=(DOMAIN, f"ugreen_nas_pool_{p}"),
#         )

#     # Pools (keys like "pool1_*" or compact "pool_*")
#     if key.startswith("pool"):
#         part0, *_ = key.split("_", 1)
#         # Be tolerant: default to 1 if no numeric suffix is present
#         p_tail = part0[4:] if len(part0) > 4 else ""
#         p = int(p_tail) if p_tail.isdigit() else 1

#         mfg, raid = (ctx.get("pool_meta") or {}).get(p, ("Linux mdadm", None))
#         mfg = mfg or "Linux mdadm"
#         raid_up = (raid or "").upper()

#         if raid_up:
#             model_disp = raid_up if raid_up.lower().startswith(mfg.lower()) else f"{mfg} {raid_up}"
#         else:
#             model_disp = mfg

#         return DeviceInfo(
#             identifiers={(DOMAIN, f"ugreen_nas_pool_{p}")},
#             name=f"{root_name} (Pool {p})",
#             manufacturer=mfg,
#             model=f"{model_disp} pool",
#             via_device=(DOMAIN, root_id),
#         )

#     # Root device (details set in __init__.py)
#     return DeviceInfo(identifiers={(DOMAIN, root_id)})
