from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from .const import DOMAIN


def build_device_info(hass: HomeAssistant, entry_id: str, key: str, model: str | None = None) -> DeviceInfo:
    """Build DeviceInfo anchored to the config entry root device."""

    root_id = f"entry:{entry_id}"
    ctx = hass.data.get(DOMAIN, {}).get(entry_id, {})  # cached meta from __init__.py
    root_name = ctx.get("root_device_name") or "UGREEN NAS"

    # Disks
    if key.startswith("disk") and "_pool" in key:
        part0, part1, *_ = key.split("_", 2)  # "disk2", "pool1", ...
        d = int(part0[4:])
        p = int(part1[4:])
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

    # volumes
    if key.startswith("volume") and "_pool" in key:
        part0, part1, *_ = key.split("_", 2)
        v = int(part0[6:]); p = int(part1[4:])
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

    # pools
    if key.startswith("pool"):
        part0, *_ = key.split("_", 1)
        p = int(part0[4:])
        mfg, raid = (ctx.get("pool_meta") or {}).get(p, ("Linux mdadm", None))
        mfg = mfg or "Linux mdadm"
        raid_up = (raid or "").upper()

        if raid_up:
            model_disp = raid_up if raid_up.lower().startswith(mfg.lower()) else f"{mfg} {raid_up}"
        else:
            model_disp = mfg

        return DeviceInfo(
            identifiers={(DOMAIN, f"ugreen_nas_pool_{p}")},
            name=f"{root_name} (Pool {p})",
            manufacturer=mfg,
            model=f"{model_disp} pool",
            via_device=(DOMAIN, root_id),
        )

    # Root device (details set in __init__.py)
    return DeviceInfo(identifiers={(DOMAIN, root_id)})
