import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from .const import DOMAIN, STORAGE_TECHNOLOGY, MANUFACTURER

from typing import Any, Dict, Tuple, Optional

_LOGGER = logging.getLogger(__name__)

def build_device_info(hass: HomeAssistant, entry_id: str, key: str) -> DeviceInfo:
    """Build DeviceInfo anchored to the config entry root device."""
    root_id = f"entry:{entry_id}"
    ctx: Dict[str, Any] = hass.data.get(DOMAIN, {}).get(entry_id, {})  # cached meta from __init__.py
    root_name: str = ctx.get("root_device_name") or "UGREEN NAS"

    # Disks
    if key.startswith("disk") and "_pool" in key:
        part0, part1, *_ = key.split("_", 2)
        d = int(part0[4:])
        p = int(part1[4:])
        disk_meta: Dict[Tuple[int, int], Tuple[Optional[str], Optional[str]]] = ctx.get("disk_meta") or {}
        brand: Optional[str]
        model_raw: Optional[str]
        brand, model_raw = disk_meta.get((p, d), ("Unknown", None))

        if brand and model_raw and not model_raw.lower().startswith(brand.lower()):
            model_disp = f"{brand} {model_raw}"
        else:
            model_disp = model_raw or f"Disk {d}"

        return DeviceInfo(
            identifiers={(DOMAIN, f"ugreen_nas_disk_{p}_{d}")},
            name=f"{root_name} (Pool {p} | Disk {d})",
            manufacturer=brand or MANUFACTURER,
            model=model_disp,
            via_device=(DOMAIN, f"ugreen_nas_pool_{p}"),
        )

    # volumes
    if key.startswith("volume") and "_pool" in key:
        part0, part1, *_ = key.split("_", 2)
        v = int(part0[6:]); p = int(part1[4:])
        volume_meta: Dict[Tuple[int, int], Tuple[Optional[str], Optional[str]]] = ctx.get("volume_meta") or {}
        mfg_raw, fs_raw = volume_meta.get((p, v), (STORAGE_TECHNOLOGY, None))
        mfg: str = str(mfg_raw) if mfg_raw is not None else STORAGE_TECHNOLOGY
        fs: Optional[str] = str(fs_raw) if fs_raw is not None else None

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

    # pools
    if key.startswith("pool"):
        pool_index: str = key.split('_')[0][4:]
        meta: Dict[str, Any] = (ctx.get("pool_meta") or {}).get(pool_index, {})
        mfg: str = meta.get("mfg", "Linux mdadm")
        raid: Optional[str] = meta.get("raid")
        raid_name: str = raid.upper() if raid else ""
        model: str = raid_name if raid_name.lower().startswith(mfg.lower()) else f"{mfg} {raid_name}" if raid_name else mfg
        return DeviceInfo(
            identifiers={(DOMAIN, f"ugreen_nas_pool_{pool_index}")},
            name=f"{root_name} (Pool {pool_index})",
            manufacturer=mfg,
            model=f"{model} pool",
            via_device=(DOMAIN, root_id),
        )

    # Root device (details set in __init__.py)
    return DeviceInfo(identifiers={(DOMAIN, root_id)})
