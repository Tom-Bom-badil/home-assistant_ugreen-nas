import logging, asyncio, base64, time, contextlib, aiohttp, async_timeout, ssl

from typing import List, Any
from uuid import uuid4
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding

from homeassistant.helpers.entity import EntityDescription
from homeassistant.const import (
    PERCENTAGE, REVOLUTIONS_PER_MINUTE, UnitOfDataRate, UnitOfTemperature,
    UnitOfInformation, UnitOfTime, UnitOfFrequency
)

from .utils import make_entities, apply_templates
from .entities import (
    UgreenEntity,
    NAS_SPECIFIC_CONFIG_TEMPLATES_USB,
    NAS_SPECIFIC_STATUS_TEMPLATES_USB,
    NAS_SPECIFIC_CONFIG_TEMPLATES_LAN,
    NAS_SPECIFIC_STATUS_TEMPLATES_LAN,
    NAS_SPECIFIC_CONFIG_TEMPLATES_RAM,
    NAS_SPECIFIC_STATUS_TEMPLATES_RAM,
    NAS_SPECIFIC_CONFIG_TEMPLATES_UPS,
    NAS_SPECIFIC_STATUS_TEMPLATES_UPS,
    NAS_SPECIFIC_CONFIG_TEMPLATES_FANS,
    NAS_SPECIFIC_STATUS_TEMPLATES_FANS_CHASSIS,
    NAS_SPECIFIC_STATUS_TEMPLATES_FAN_CPU,
    NAS_SPECIFIC_CONFIG_TEMPLATES_STORAGE_POOL,
    NAS_SPECIFIC_STATUS_TEMPLATES_STORAGE_POOL,
    NAS_SPECIFIC_CONFIG_TEMPLATES_STORAGE_VOLUME,
    NAS_SPECIFIC_STATUS_TEMPLATES_STORAGE_VOLUME,
    NAS_SPECIFIC_CONFIG_TEMPLATES_STORAGE_DISK,
    NAS_SPECIFIC_STATUS_TEMPLATES_STORAGE_DISK
)

_LOGGER = logging.getLogger(__name__)


class UgreenApiClient:

    ### Initialization
    
    def __init__(
        self,
        ugreen_nas_host: str,
        ugreen_nas_port: int,
        username: str = "",
        password: str = "",
        token: str = "",
        use_https: bool = False,
        otp: bool = False,
    ):

        # Derived connection attributes for HTTP/WS usage
        self.scheme = "https" if use_https else "http"
        self.host = ugreen_nas_host
        self.port = int(ugreen_nas_port)
        self.base_url = f"{self.scheme}://{self.host}:{self.port}"

        # Credentials & connection
        self.username = username
        self.password = password
        self.token = token
        self.otp = otp

        # Auth state
        self._login_lock = asyncio.Lock()
        self._authed = bool(token)

        # Dynamic entity caches (used in count_* and DISCOVER_NAS_SPECIFIC_*)
        self._dynamic_entity_counts: dict[str, Any] | None = None
        self._dynamic_entity_counts_lock = asyncio.Lock()

        # Disable SSL certificate checking
        self._ssl = (False if self.scheme == "https" else None)


    ### "The API" - public entrypoints (e.g. used by __init__.py)

    async def authenticate(self, session) -> bool:
        """Call once during setup; afterwards rely on on-demand login in _request()"""
        if self._authed:
            return True
        ok = await self._login(session)
        self._authed = ok
        return ok


    async def get(self, session, endpoint: str) -> dict[str, Any]:
        """HTTP GET wrapper, uses _request."""
        return await self._request(session, "GET", endpoint)


    async def post(self, session, endpoint: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        """HTTP POST wrapper, uses _request."""
        return await self._request(session, "POST", endpoint, payload)


    async def DISCOVER_NAS_SPECIFIC_CONFIG_ENTITIES(self, session) -> list[UgreenEntity]:
        """Build NAS-specific config entities (volumes, disks, raid levels etc) - 60s read."""
        return await self._build_from_registry(session, self._config_definitions(), for_status=False)


    async def DISCOVER_NAS_SPECIFIC_STATE_ENTITIES(self, session) -> list[UgreenEntity]:
        """Build NAS-specific status entities (disk temperatures, fan speeds etc) - 5s read."""
        return await self._build_from_registry(session, self._status_definitions(), for_status=True)


    async def count_dynamic_entities(self, session: aiohttp.ClientSession) -> dict:
        """Return counted numbers of dynamic, NAS-specific entities."""
        return await self._count_dynamic_entities(session)


    def get_dynamic_entity_counts(self) -> dict:
        """Return above counted number of dynamic entities on request."""
        return self._dynamic_entity_counts or {}


    def ws_keepalive(self, session: aiohttp.ClientSession, *, lang: str = "de-DE"):
        """Return coroutine that keeps the desktop websocket alive (public wrapper)."""
        return self._ws_keepalive(session, lang=lang)


    ### Internally used functions ##############################################


    async def _login(self, session) -> bool:
        """Fetch RSA pubkey from header, encrypt password, request token"""
        async with self._login_lock:
            try:
                # 1) public key
                url_pk = f"{self.base_url}/ugreen/v1/verify/check?token="
                payload_pk = {"username": self.username}
                _LOGGER.debug("[UGREEN] login: fetch public key")
                async with async_timeout.timeout(10):
                    async with session.post(url_pk, json=payload_pk, ssl=self._ssl) as resp:
                        resp.raise_for_status()
                        hdr = resp.headers.get("x-rsa-token", "")
                if not hdr:
                    _LOGGER.debug("[UGREEN] login: missing x-rsa-token header")
                    return False
                try:
                    pub_bytes = base64.b64decode(hdr)
                except Exception:
                    pub_bytes = hdr.encode("utf-8")

                # 2) encrypt password (PKCS#1 v1.5) and login
                try:
                    pub = serialization.load_der_public_key(pub_bytes)
                except Exception:
                    pub = serialization.load_pem_public_key(pub_bytes)
                enc = base64.b64encode(pub.encrypt(self.password.encode("utf-8"), padding.PKCS1v15())).decode("ascii")

                url_login = f"{self.base_url}/ugreen/v1/verify/login"
                payload = {
                    "is_simple": True,
                    "keepalive": True,
                    "otp": bool(self.otp),
                    "username": self.username,
                    "password": enc,
                }
                _LOGGER.debug("[UGREEN] login POST (otp=%s)", self.otp)
                async with async_timeout.timeout(10):
                    async with session.post(url_login, json=payload, ssl=self._ssl) as resp:
                        resp.raise_for_status()
                        data = await resp.json()

                if data.get("code") != 200:
                    msg = data.get("msg") or data.get("debug") or ""
                    _LOGGER.error("[UGREEN] login failed code=%s msg=%s", data.get("code"), msg)
                    return False

                token = (data.get("data") or {}).get("token")
                if not token:
                    _LOGGER.error("[UGREEN] login ok but token missing")
                    return False

                self.token = token
                self._authed = True
                _LOGGER.debug("[UGREEN] token stored")
                return True

            except Exception as e:
                _LOGGER.error("[UGREEN] login error: %s", e)
                return False


    async def _request(self, session, method: str, endpoint: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        """Single request helper with 1024-refresh; keeps noise low"""
        payload = payload or {}

        async def _do() -> dict[str, Any]:
            url = f"{self.base_url}{endpoint}"
            url = f"{url}{'&' if '?' in url else '?'}token={self.token}"
            _LOGGER.debug("[UGREEN] %s %s payload=%s", method, url, payload if method == "POST" else None)
            async with async_timeout.timeout(10):
                async with session.request(method, url, json=payload if method == "POST" else None, ssl=self._ssl) as resp:
                    resp.raise_for_status()
                    return await resp.json()

        try:
            if not self.token and not await self._login(session):
                _LOGGER.error("[UGREEN] %s: no token and login failed", method)
                return {}

            data = await _do()
            if data.get("code") == 1024:
                _LOGGER.error("[UGREEN] token expired (1024) -> relogin")
                if await self._login(session):
                    data = await _do()
                else:
                    _LOGGER.error("[UGREEN] relogin failed")
                    return {}
            return data
        except Exception as e:
            _LOGGER.error("[UGREEN] %s error on %s: %s", method, endpoint, e)
            return {}


    async def _count_dynamic_entities(self, session: aiohttp.ClientSession) -> dict:
        """Counts number of dynamic entities for central accessibility"""
        if self._dynamic_entity_counts is not None:
            return self._dynamic_entity_counts
        async with self._dynamic_entity_counts_lock:
            if self._dynamic_entity_counts is not None:
                return self._dynamic_entity_counts
            try:
                counts: dict[str, Any] = {}

                # 1) RAM / USB / UPS (sysinfo)
                sysinfo = await self.get(session, "/ugreen/v1/sysinfo/machine/common")
                if isinstance(sysinfo, dict):
                    hw = (sysinfo.get("data", {}) or {}).get("hardware", {}) or {}
                    counts["num_rams"] = len(hw.get("mem", []) or [])
                    counts["num_usbs"] = len(hw.get("usb", []) or [])
                    counts["has_ups"] = bool(hw.get("ups", []) or [])

                # 2) Storage: Disks / Pools / Volumes
                disks_resp = await self.get(session, "/ugreen/v2/storage/disk/list")
                if isinstance(disks_resp, dict):
                    counts["num_disks"] = len((disks_resp.get("data", {}) or {}).get("result", []) or [])

                pools_resp = await self.get(session, "/ugreen/v1/storage/pool/list")
                if isinstance(pools_resp, dict):
                    pools = (pools_resp.get("data", {}) or {}).get("result", []) or []
                    counts["num_pools"] = len(pools)
                    counts["num_volumes"] = sum(len(p.get("volumes", []) or []) for p in pools)

                # 3) NICs / Fans / GPU (stat/get_all)
                stat = await self.get(session, "/ugreen/v1/taskmgr/stat/get_all")
                if isinstance(stat, dict) and stat.get("code") == 200:
                    sdata = (stat.get("data", {}) or {})

                    # NICs (without element[0]="overview")
                    net_series = ((sdata.get("net", {}) or {}).get("series", []) or [])
                    non_overview = [x for x in net_series if x.get("name") not in ("overview", "Overview", "Übersicht")]
                    counts["num_nics"] = len(non_overview)

                    # Fans (overview can be dict or list)
                    overview = (sdata.get("overview", {}) or {})
                    cpu_fans = overview.get("cpu_fan") or []
                    dev_fans = overview.get("device_fan") or []
                    if isinstance(cpu_fans, dict):
                        cpu_fans = [cpu_fans]
                    if isinstance(dev_fans, dict):
                        dev_fans = [dev_fans]

                    counts["has_cpu_fan"] = len(cpu_fans) > 0
                    counts["num_device_fans"] = len(dev_fans)
                    counts["has_device_fan"] = counts["num_device_fans"] > 0

                    # GPU
                    gpu_series = ((sdata.get("gpu", {}) or {}).get("series", []) or [])
                    counts["has_gpu"] = any((g.get("gpu_name") or "").strip() for g in gpu_series)

                self._dynamic_entity_counts = counts
            except Exception as e:
                _LOGGER.warning("[UGREEN NAS] count_dynamic_entities failed: %s", e)
                self._dynamic_entity_counts = {}
            return self._dynamic_entity_counts


    def _ws_keepalive(self, session: aiohttp.ClientSession, *, lang: str = "de-DE"):
        """Return an update coroutine that keeps the desktop websocket alive."""
        ws: aiohttp.ClientWebSocketResponse | None = None
        subscribed = False

        def _url() -> str:
            ws_scheme = "wss" if self.scheme == "https" else "ws"
            return (
                f"{ws_scheme}://{self.host}:{self.port}/ugreen/v1/desktop/ws"
                f"?client_id={uuid4()}-WEB&lang={lang}&token={self.token}"
            )

        async def _update() -> dict:
            nonlocal ws, subscribed
            if not self.token:
                if ws and not ws.closed:
                    with contextlib.suppress(Exception):
                        await ws.close()
                ws, subscribed = None, False
                return {"connected": False, "reason": "no_token"}

            try:
                if ws is None or ws.closed:
                    headers = {
                        "Origin": f"{self.scheme}://{self.host}:{self.port}",
                        "Pragma": "no-cache",
                        "Cache-Control": "no-cache",
                    }
                    ws = await session.ws_connect(_url(), headers=headers, heartbeat=None, ssl=self._ssl)
                    subscribed = False

                if not subscribed:
                    await ws.send_json({"op": "subscribe", "topics": ["cpu_temp"], "ts": int(time.time() * 1000)})
                    subscribed = True

                with contextlib.suppress(Exception):
                    await ws.ping()

                return {"connected": True}

            except Exception as e:
                if ws:
                    with contextlib.suppress(Exception):
                        await ws.close()
                ws, subscribed = None, False
                return {"connected": False, "reason": str(e)}

        return _update


    def _config_definitions(self) -> list[dict]:
        """Registry for dynamic CONFIG entities."""
        return [
            # List-driven sections (fetch + list_path)
            dict(
                key="LAN",
                kind="list",
                templates=NAS_SPECIFIC_CONFIG_TEMPLATES_LAN,
                endpoint="/ugreen/v1/sysinfo/machine/common",
                list_path="data.hardware.net",
                prefix_key_base="LAN",
                prefix_name_base="LAN Port",
                category="Network",
            ),
            dict(
                key="USB",
                kind="list",
                templates=NAS_SPECIFIC_CONFIG_TEMPLATES_USB,
                endpoint="/ugreen/v1/sysinfo/machine/common",
                list_path="data.hardware.usb",
                prefix_key_base="USB_device",
                prefix_name_base="USB Device",
                category="USB",
            ),
            dict(
                key="UPS",
                kind="list",
                templates=NAS_SPECIFIC_CONFIG_TEMPLATES_UPS,
                endpoint="/ugreen/v1/sysinfo/machine/common",
                list_path="data.hardware.ups",
                prefix_key_base="UPS",
                prefix_name_base="UPS",
                category="UPS",
            ),

            # Count-driven sections (no list_path)
            dict(
                key="RAM",
                kind="count",
                templates=NAS_SPECIFIC_CONFIG_TEMPLATES_RAM,
                endpoint="/ugreen/v1/sysinfo/machine/common",
                count=lambda c: int(c.get("num_rams", 0)),
                prefix_key_base="RAM",
                prefix_name_base="RAM Module",
                category="Hardware",
                post="ram_total",  # add virtual total sensor after creation
            ),
            dict(
                key="FANS",
                kind="count",
                templates=NAS_SPECIFIC_CONFIG_TEMPLATES_FANS,
                endpoint="/ugreen/v1/sysinfo/machine/common",
                count=lambda c: int(c.get("num_device_fans", 0)) + (1 if c.get("has_cpu_fan") else 0),
                prefix_key_base="fan",
                prefix_name_base="Fan",
                category="Hardware",
            ),

            # Custom builder (special logic for storage tree building)
            dict(
                key="STORAGE",
                kind="custom",
                builder="_get_dynamic_config_entities_storage",
            ),
        ]


    def _status_definitions(self) -> list[dict]:
        """Registry for dynamic STATUS entities."""
        return [
            dict(
                key="LAN",
                kind="count",
                templates=NAS_SPECIFIC_STATUS_TEMPLATES_LAN,
                endpoint="/ugreen/v1/taskmgr/stat/get_all",
                count=lambda c: int(c.get("num_nics", 0)),
                prefix_key_base="lan",
                prefix_name_base="LAN",
                category="LAN",
                index_start=1,
                single_compact=False,
            ),
            dict(
                key="USB",
                kind="count",
                templates=NAS_SPECIFIC_STATUS_TEMPLATES_USB,
                endpoint="/ugreen/v1/taskmgr/stat/get_all",
                count=lambda c: int(c.get("num_usbs", 0)),
                prefix_key_base="usb_device",
                prefix_name_base="USB Device",
                category="Status",
            ),
            dict(
                key="UPS",
                kind="count",
                templates=NAS_SPECIFIC_STATUS_TEMPLATES_UPS,
                endpoint="/ugreen/v1/taskmgr/stat/get_all",
                count=lambda c: 1 if c.get("has_ups") else 0,
                prefix_key_base="ups",
                prefix_name_base="UPS",
                category="Status",
            ),
            dict(
                key="RAM",
                kind="count",
                templates=NAS_SPECIFIC_STATUS_TEMPLATES_RAM,
                endpoint="/ugreen/v1/taskmgr/stat/get_all",
                count=lambda c: int(c.get("num_rams", 0)),
                prefix_key_base="ram",
                prefix_name_base="RAM Module",
                category="Status",
            ),
            dict(
                key="STORAGE_DISK",
                kind="count",
                templates=NAS_SPECIFIC_STATUS_TEMPLATES_STORAGE_DISK,
                endpoint="/ugreen/v1/taskmgr/stat/get_all",
                count=lambda c: int(c.get("num_disks", 0)),
                prefix_key_base="disk",
                prefix_name_base="Disk",
                category="Status",
                index_start=1,
                single_compact=False,
            ),
            dict(
                key="FAN_CPU",
                kind="count",
                templates=NAS_SPECIFIC_STATUS_TEMPLATES_FAN_CPU,
                endpoint="/ugreen/v1/taskmgr/stat/get_all",
                count=lambda c: 1 if c.get("has_cpu_fan") else 0,
                prefix_key_base="cpu_fan",
                prefix_name_base="CPU Fan",
                category="Status",
            ),
            dict(
                key="FAN_CHASSIS",
                kind="count",
                templates=NAS_SPECIFIC_STATUS_TEMPLATES_FANS_CHASSIS,
                endpoint="/ugreen/v1/taskmgr/stat/get_all",
                count=lambda c: int(c.get("num_device_fans", 0)),
                prefix_key_base="device_fan",
                prefix_name_base="Device Fan",
                category="Status",
                single_compact=True, 
            ),
        ]


    async def _build_from_registry(self, session, registry: list[dict], *, for_status: bool) -> list[UgreenEntity]:
        """Single loop over registry entries; supports list/count/custom + post hooks."""
        out: list[UgreenEntity] = []
        counts: dict | None = None

        for d in registry:
            kind = d.get("kind", "count")
            # custom builder
            if kind == "custom":
                builder_name = d["builder"]
                builder = getattr(self, builder_name)
                out.extend(await builder(session))
                continue

            endpoint = d.get("endpoint") or ("/ugreen/v1/taskmgr/stat/get_all" if for_status else "/ugreen/v1/sysinfo/machine/common")

            if kind == "list":
                async def _fetch(ep: str) -> dict:
                    return await self.get(session, ep)
                ents = await make_entities(
                    fetch=_fetch,
                    templates=d["templates"],
                    endpoint=endpoint,
                    list_path=d["list_path"],
                    prefix_key_base=d["prefix_key_base"],
                    prefix_name_base=d["prefix_name_base"],
                    category=d["category"],
                    index_start=d.get("index_start", 1),
                    single_compact=d.get("single_compact", True),
                )
            else:
                # count-based
                if counts is None:
                    counts = await self.count_dynamic_entities(session) or {}
                n = int(d["count"](counts)) if callable(d.get("count")) else 0
                ents = await make_entities(
                    fetch=None,
                    templates=d["templates"],
                    endpoint=endpoint,
                    count=n,
                    prefix_key_base=d["prefix_key_base"],
                    prefix_name_base=d["prefix_name_base"],
                    category=d["category"],
                    index_start=d.get("index_start", 1),
                    single_compact=d.get("single_compact", not for_status),
                )

            # optional post-processing (e.g., RAM total)
            if d.get("post") == "ram_total" and ents:
                ents.append(UgreenEntity(
                    description=EntityDescription(
                        key="ram_total_size",
                        name="RAM Total Size",
                        icon="mdi:memory",
                        unit_of_measurement=UnitOfInformation.BYTES,
                    ),
                    endpoint="/ugreen/v1/sysinfo/machine/common",
                    path="calculated:ram_total_size",
                    decimal_places=0,
                    nas_part_category="Hardware",
                ))

            out.extend(ents)

        return out


    async def _get_dynamic_config_entities_storage(self, session: aiohttp.ClientSession) -> List[UgreenEntity]:
        """Create STORAGE config entities (templated): Pools, Disks inside Pools, Volumes inside Pools."""

        endpoint_pools = "/ugreen/v1/storage/pool/list"
        endpoint_disk  = "/ugreen/v2/storage/disk/list"

        # Get response on pools (main response)
        pools_resp = await self.get(session, endpoint_pools)
        results = ((pools_resp or {}).get("data", {}) or {}).get("result", []) or []
        if not results:
            _LOGGER.debug("[UGREEN NAS] No pools in %s response", endpoint_pools)
            return []

        entities: List[UgreenEntity] = []

        # 1) Create entities for pools
        async def _fetch_cached(_: str) -> dict:
            return pools_resp
        entities.extend(await make_entities(
            fetch=_fetch_cached,
            templates=NAS_SPECIFIC_CONFIG_TEMPLATES_STORAGE_POOL,
            endpoint=endpoint_pools,
            list_path="data.result",
            prefix_key_base="pool",
            prefix_name_base="Pool",
            category="Pools",
        ))

        # 2) Create a global disk list
        disk_resp = await self.get(session, endpoint_disk)
        disk_list = ((disk_resp or {}).get("data", {}) or {}).get("result", []) or []
        dev_index: dict[str, int] = {}
        for idx, d in enumerate(disk_list):
            name = (d or {}).get("dev_name") or (d or {}).get("name")
            if isinstance(name, str) and name:
                dev_index[name] = idx

        # 3) Create entities for disks
        for p_i, pool in enumerate(results):
            disks = (pool or {}).get("disks") or []
            for d_i, disk in enumerate(disks):
                dev_name = (disk or {}).get("dev_name") or (disk or {}).get("name")
                if dev_name not in dev_index:
                    _LOGGER.debug("[UGREEN NAS] dev_name '%s' not found in global disk list", dev_name)
                    continue
                global_idx = dev_index[dev_name]

                entities.extend(apply_templates(
                    NAS_SPECIFIC_CONFIG_TEMPLATES_STORAGE_DISK,
                    series_index=global_idx,
                    prefix_key=f"disk{d_i+1}_pool{p_i+1}",
                    prefix_name=f"(Pool {p_i+1} | Disk {d_i+1})",
                    endpoint=endpoint_disk,
                    category="Disks",
                ))

            # 4) Create entities for volumes, based on pools
            volumes = (pool or {}).get("volumes") or []
            for v_i, _ in enumerate(volumes):
                entities.extend(apply_templates(
                    NAS_SPECIFIC_CONFIG_TEMPLATES_STORAGE_VOLUME,
                    pool_index=p_i,
                    i=v_i,
                    prefix_key=f"volume{v_i+1}_pool{p_i+1}",
                    prefix_name=f"(Pool {p_i+1} | Volume {v_i+1})",
                    endpoint=endpoint_pools,
                    category="Volumes",
                ))

        return entities




### preserved for future programming ###

# obsolete
    # async def get_dynamic_status_entities_storage(self, session) -> List[UgreenEntity]:
    #     """Create STORAGE status entities (templated)."""
    #     counts = await self.count_dynamic_entities(session) or {}
    #     return await make_entities(
    #         fetch=None,
    #         templates=NAS_SPECIFIC_STATUS_TEMPLATES_STORAGE_DISK,
    #         endpoint="/ugreen/v1/taskmgr/stat/get_all",
    #         count=counts.get("num_disks", 0),
    #         prefix_key_base="disk",
    #         prefix_name_base="Disk",
    #         category="Status",
    #         index_start=0,
    #         single_compact=False,
    #     )

# undecided
    # async def get_dynamic_status_entities_storage_pool(self, session) -> list[UgreenEntity]:
    #     """Create STORAGE POOL status entities (templated) – currently none."""
    #     return []

    # async def get_dynamic_status_entities_storage_volume(self, session) -> list[UgreenEntity]:
    #     """Create STORAGE VOLUME status entities (templated) – currently none."""
    #     return []
