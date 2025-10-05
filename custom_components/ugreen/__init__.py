import logging, contextlib

from datetime import timedelta
from typing import Any
from collections import defaultdict

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.device_registry import async_get as async_get_device_registry

from .const import (
    DOMAIN,
    PLATFORMS,
    CONF_UGREEN_HOST,
    CONF_UGREEN_PORT,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_USE_HTTPS,
    CONF_STATE_INTERVAL,
    DEFAULT_SCAN_INTERVAL_STATE,
    MANUFACTURER,
)

from .utils import get_entity_data_from_api

from .api import UgreenApiClient
from .entities import (
    ALL_NAS_COMMON_CONFIG_ENTITIES,
    ALL_NAS_COMMON_STATE_ENTITIES,
    ALL_NAS_COMMON_BUTTON_ENTITIES
)

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Setup and start the integration."""


    ### Preparations
    _LOGGER.debug("[UGREEN NAS] Setting up config entry: %s", entry.entry_id)
    hass.data.setdefault(DOMAIN, {})
    session = async_get_clientsession(hass)

    # Read configuration from entry (options override data)
    api = UgreenApiClient(
        ugreen_nas_host=entry.options.get(CONF_UGREEN_HOST, entry.data.get(CONF_UGREEN_HOST)),
        ugreen_nas_port=int(entry.options.get(CONF_UGREEN_PORT, entry.data.get(CONF_UGREEN_PORT))),
        username=entry.options.get(CONF_USERNAME, entry.data.get(CONF_USERNAME)),
        password=entry.options.get(CONF_PASSWORD, entry.data.get(CONF_PASSWORD)),
        use_https=bool(entry.options.get(CONF_USE_HTTPS, entry.data.get(CONF_USE_HTTPS, False))),
    )
    # keepalive_websocket = api.ws_keepalive(session, lang="de-DE")


    ### Initial authentication
    if not await api.authenticate(session):
        _LOGGER.error("[UGREEN NAS] Initial login failed. Aborting setup.")
        return False


    ### Create global counters for dynamic entities
    dynamic_entity_counts = await api.count_dynamic_entities(session)
    _LOGGER.debug("[UGREEN NAS] Entity counts done: %s", dynamic_entity_counts)


    ### Setup configuration entities (never or slowly changing, 60s polling)
    #   Build the entity list
    config_entities =  list(ALL_NAS_COMMON_CONFIG_ENTITIES)
    config_entities += await api.DISCOVER_NAS_SPECIFIC_CONFIG_ENTITIES(session)
    #   Group entities by endpoint to reduce number of API calls
    config_entities_grouped_by_endpoint = defaultdict(list)
    for entity in config_entities:
        config_entities_grouped_by_endpoint[entity.endpoint].append(entity)
    #   Create the update function for the corresponding coordinator
    async def update_configuration_data() -> dict[str, Any]:
        try:
            _LOGGER.debug("[UGREEN NAS] Updating configuration data...")
            endpoint_to_entities = hass.data[DOMAIN][entry.entry_id]["config_entities_grouped_by_endpoint"]
            return await get_entity_data_from_api(api, session, endpoint_to_entities)
        except Exception as err:
            raise UpdateFailed(f"[UGREEN NAS] Configuration entities update error: {err}") from err
    #   Create the coordinator
    config_coordinator = DataUpdateCoordinator( # data polling every 60s
        hass,
        _LOGGER,
        name="ugreen_configuration",
        update_method=update_configuration_data,
        update_interval=timedelta(seconds=60),
    )


    ### Setup state entities (changing rather quickly, 5s polling)
    #   Build the entity list
    state_entities =  list(ALL_NAS_COMMON_STATE_ENTITIES)
    state_entities += await api.DISCOVER_NAS_SPECIFIC_STATE_ENTITIES(session)
    #   Group entities by endpoint to reduce number of API calls
    state_entities_grouped_by_endpoint = defaultdict(list)
    for entity in state_entities: # reduce number of API calls
        state_entities_grouped_by_endpoint[entity.endpoint].append(entity)
    _LOGGER.debug("[UGREEN NAS] List of state entities prepared.")
    #   Create the update function for the corresponding coordinator
    async def update_state_data() -> dict[str, Any]: # update for coordinator
        try:
            _LOGGER.debug("[UGREEN NAS] Updating state data...")
            endpoint_to_entities = hass.data[DOMAIN][entry.entry_id]["state_entities_grouped_by_endpoint"]
            return await get_entity_data_from_api(api, session, endpoint_to_entities)
        except Exception as err:
            raise UpdateFailed(f"[UGREEN NAS] State entities update error: {err}") from err
    #   Create the coordinator
    state_coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="ugreen_state",
        update_method=update_state_data,
        update_interval=timedelta(
            seconds=entry.options.get(CONF_STATE_INTERVAL, entry.data.get(CONF_STATE_INTERVAL, DEFAULT_SCAN_INTERVAL_STATE))
        ),
    )


    ### Hand over all runtime objects to HA's data container
    hass.data[DOMAIN][entry.entry_id] = {
        "config_coordinator": config_coordinator,
        "config_entities": config_entities,
        "config_entities_grouped_by_endpoint": config_entities_grouped_by_endpoint,
        "state_coordinator": state_coordinator,
        "state_entities": state_entities,
        "state_entities_grouped_by_endpoint": state_entities_grouped_by_endpoint,
        "button_entities": ALL_NAS_COMMON_BUTTON_ENTITIES,
        "dynamic_entity_counts": dynamic_entity_counts,
        "api": api,
    }


    ### Initial entities refresh and start of keep-alive websocket
    await config_coordinator.async_config_entry_first_refresh()
    await state_coordinator.async_config_entry_first_refresh()
    await api.start_ws_keepalive_task(session, lang="de-DE", heartbeat=15)


    ### Build lightweight meta caches for Device Registry (disks/pools/volumes)
    pools_resp = await api.get(session, "/ugreen/v1/storage/pool/list")
    disks_resp = await api.get(session, "/ugreen/v2/storage/disk/list")

    pools = ((pools_resp or {}).get("data", {}) or {}).get("result", []) or []
    disks = ((disks_resp or {}).get("data", {}) or {}).get("result", []) or []

    # Map global disk list by dev_name for quick lookup
    dev_by_name = {}
    for d in disks:
        name = (d or {}).get("dev_name") or (d or {}).get("name")
        if name:
            dev_by_name[name] = d or {}

    disk_meta: dict[tuple[int, int], tuple[str | None, str | None]] = {}
    pool_meta: dict[int, tuple[str, str | None]] = {}
    volume_meta: dict[tuple[int, int], tuple[str, str | None]] = {}

    for p_idx, pool in enumerate(pools, start=1):
        # Pools: use UGREEN as manufacturer, RAID level as model
        raid = (pool or {}).get("level") or None
        pool_meta[p_idx] = (MANUFACTURER, raid)

        # Volumes: use UGREEN as manufacturer, filesystem as model
        for v_idx, vol in enumerate((pool or {}).get("volumes") or [], start=1):
            fs = (vol or {}).get("filesystem") or None
            volume_meta[(p_idx, v_idx)] = (MANUFACTURER, fs)

        # Disks: brand + model from global disk list via dev_name
        for d_idx, pd in enumerate((pool or {}).get("disks") or [], start=1):
            dev_name = (pd or {}).get("dev_name") or (pd or {}).get("name")
            info = dev_by_name.get(dev_name, {})
            brand = (info.get("brand") or info.get("manufacturer") or "").strip() or None
            model = (info.get("model") or info.get("name") or "").strip() or None
            disk_meta[(p_idx, d_idx)] = (brand, model)

    # Persist for device_info.py
    hass.data.setdefault(DOMAIN, {}).setdefault(entry.entry_id, {}).update({
        "disk_meta":   disk_meta,
        "pool_meta":   pool_meta,
        "volume_meta": volume_meta,
    })


    ### Device registration
    sys_info = await api.get(session, "/ugreen/v1/sysinfo/machine/common")
    common  = (sys_info or {}).get("data", {}).get("common", {})
    model   = common.get("model", "Unknown")
    version = common.get("system_version", "Unknown")
    name    = common.get("nas_name", "UGREEN NAS")
    serial  = (common.get("serial") or "").strip()
    brand = "UGREEN"
    model_display = f"{brand} {model}" if model and not model.upper().startswith(brand) else (model or brand)

    hass.data.setdefault(DOMAIN, {}).setdefault(entry.entry_id, {})["root_device_name"] = name
    device = None

    try:
        # Device registration (root)
        dev_reg = async_get_device_registry(hass)

        # Unique identifiers within the integration
        identifiers = {(DOMAIN, f"entry:{entry.entry_id}")}
        if serial:
            identifiers.add((DOMAIN, f"serial:{serial}"))

        # Create or get root device
        device = dev_reg.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers=identifiers,
            name=name,
            manufacturer=brand,
            model=model_display,
            sw_version=version,
            serial_number=serial or None,
        )

        # Enforce NAS DNS name as device name (only if not user-overridden)
        if device and not device.name_by_user and device.name != name:
            dev_reg.async_update_device(device.id, name=name)

    except Exception as e:
        _LOGGER.warning("[UGREEN NAS] Device registration failed: %s", e)


    ### Finalize init: Forward the setups to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _LOGGER.debug("[UGREEN NAS] Forwarded entry setups to platforms - setup complete.")

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the integration and stop all background schedulers."""

    data = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})

    ### Stop update intervals to prevent any further background work
    for key in ("ws_coordinator", "state_coordinator", "config_coordinator"):
        coord = data.get(key)
        if coord:
            coord.update_interval = None

    ### Stop the websocket for API keep-alive
    api: UgreenApiClient | None = data.get("api")
    if api:
        with contextlib.suppress(Exception):
            await api.stop_ws_keepalive_task()

    ### Unload platforms / entities and clean up data container
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return unload_ok
