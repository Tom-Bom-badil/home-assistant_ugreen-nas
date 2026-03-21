import logging
from typing import Any, Optional

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import NumberSelector, NumberSelectorConfig
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
from homeassistant.util import slugify

from .api import UgreenApiClient
from .const import (
    DOMAIN,
    CONF_DEVICE_NAME,
    CONF_UGREEN_HOST,
    CONF_UGREEN_PORT,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_USE_HTTPS,
    CONF_STATE_INTERVAL,
    CONF_CONFIG_INTERVAL,
    CONF_WS_INTERVAL,
    CONF_ENTITY_PREFIX,
    CONF_DASHBOARD_DISK_COLUMNS,
    CONF_DASHBOARD_POOL_COLUMNS,
    CONF_DASHBOARD_VOLUME_COLUMNS,
    CONF_DASHBOARD_IMAGE_FILE,
    DEFAULT_ENTITY_PREFIX,
    DEFAULT_SCAN_INTERVAL_STATE,
    DEFAULT_SCAN_INTERVAL_CONFIG,
    DEFAULT_SCAN_INTERVAL_WS,
    DEFAULT_DASHBOARD_DISK_COLUMNS,
    DEFAULT_DASHBOARD_POOL_COLUMNS,
    DEFAULT_DASHBOARD_VOLUME_COLUMNS,
    DEFAULT_DASHBOARD_IMAGE_FILE,
)

_LOGGER = logging.getLogger(__name__)
HEARTBEAT_PATH = "/ugreen/v1/verify/heartbeat"


def _build_entry_unique_id(serial: str) -> str:
    """Build the config entry unique id from NAS serial."""
    return f"ugreen_{serial.strip()}"


def _normalize_entity_prefix(value: str) -> str:
    """Normalize the user-visible prefix value."""
    return (value or "").strip()


def _build_entity_prefix_slug(value: str) -> str:
    """Build a normalized slug from the user-visible prefix."""
    return slugify(_normalize_entity_prefix(value))


def _get_saved_entity_prefix(entry: config_entries.ConfigEntry) -> str:
    """Return the stored prefix from options or data."""
    return _normalize_entity_prefix(
        entry.options.get(CONF_ENTITY_PREFIX, entry.data.get(CONF_ENTITY_PREFIX, ""))
    )


def _is_entity_prefix_in_use(
    entries: list[config_entries.ConfigEntry],
    prefix: str,
    current_entry_id: str | None = None,
) -> bool:
    """Check if the normalized prefix slug is already used by another entry."""
    candidate_slug = _build_entity_prefix_slug(prefix)
    if not candidate_slug:
        return False

    for entry in entries:
        if current_entry_id and entry.entry_id == current_entry_id:
            continue

        existing_prefix = _get_saved_entity_prefix(entry)
        if not existing_prefix:
            continue

        if _build_entity_prefix_slug(existing_prefix) == candidate_slug:
            return True

    return False


def _normalize_dashboard_columns(value: Any, default: int) -> int:
    """Normalize dashboard column values to a safe integer range."""
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(0, min(10, number))


def _normalize_dashboard_image_file(value: Any) -> str:
    """Normalize the optional dashboard image filename."""
    return str(value or "").strip()


async def _is_ugreen_device(hass, host: Optional[str], port: int) -> bool:
    """
    Probe the unauthenticated heartbeat endpoint to verify a UGREEN NAS.
    Return True only if the endpoint responds with code=200 and msg='success'.
    """
    if not host:
        return False

    netloc = f"[{host}]" if ":" in host and not host.startswith("[") else host
    url = f"http://{netloc}:{port}{HEARTBEAT_PATH}"

    session = async_get_clientsession(hass)

    try:
        async with session.get(url, timeout=3) as resp:
            if resp.status != 200:
                return False
            data = await resp.json(content_type=None)
    except Exception:
        return False

    return data.get("code") == 200 and data.get("msg") == "success"


class UgreenNasConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for UGREEN NAS."""

    VERSION = 1

    def __init__(self):
        """Initialize the config flow."""
        self._discovered_host = None
        self._discovered_port = None

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> config_entries.ConfigFlowResult:
        """Handle zeroconf discovery."""
        _LOGGER.debug("[UGREEN NAS] Discovered device via zeroconf: %s", discovery_info)

        host = discovery_info.host
        port = discovery_info.port or 9999

        for configured_entry in self._async_current_entries():
            configured_host = configured_entry.options.get(
                CONF_UGREEN_HOST,
                configured_entry.data.get(CONF_UGREEN_HOST),
            )
            if configured_host == host:
                return self.async_abort(reason="already_configured")

        if not await _is_ugreen_device(self.hass, host, port):
            _LOGGER.debug(
                "[UGREEN NAS] Zeroconf candidate at %s:%s did not respond as UGREEN NAS",
                host,
                port,
            )
            return self.async_abort(reason="not_ugreen_nas")

        self._discovered_host = host
        self._discovered_port = port

        hostname = (discovery_info.hostname or "").rstrip(".")
        instance = ""
        if discovery_info.name:
            instance = discovery_info.name.split("._", 1)[0].rstrip(".")

        display_name = hostname or instance or host
        self.context.update(
            {"title_placeholders": {"name": f"UGREEN NAS ({display_name})"}}
        )

        return await self.async_step_user()

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial setup step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            _LOGGER.debug("[UGREEN NAS] Received user input: %s", user_input)

            entity_prefix = _normalize_entity_prefix(
                user_input.get(CONF_ENTITY_PREFIX, "")
            )
            entity_prefix_slug = _build_entity_prefix_slug(entity_prefix)

            disk_columns = _normalize_dashboard_columns(
                user_input.get(
                    CONF_DASHBOARD_DISK_COLUMNS,
                    DEFAULT_DASHBOARD_DISK_COLUMNS,
                ),
                DEFAULT_DASHBOARD_DISK_COLUMNS,
            )
            pool_columns = _normalize_dashboard_columns(
                user_input.get(
                    CONF_DASHBOARD_POOL_COLUMNS,
                    DEFAULT_DASHBOARD_POOL_COLUMNS,
                ),
                DEFAULT_DASHBOARD_POOL_COLUMNS,
            )
            volume_columns = _normalize_dashboard_columns(
                user_input.get(
                    CONF_DASHBOARD_VOLUME_COLUMNS,
                    DEFAULT_DASHBOARD_VOLUME_COLUMNS,
                ),
                DEFAULT_DASHBOARD_VOLUME_COLUMNS,
            )
            image_file = _normalize_dashboard_image_file(
                user_input.get(
                    CONF_DASHBOARD_IMAGE_FILE,
                    DEFAULT_DASHBOARD_IMAGE_FILE,
                )
            )

            if not entity_prefix or not entity_prefix_slug:
                errors["base"] = "invalid_entity_prefix"
            elif _is_entity_prefix_in_use(
                self._async_current_entries(),
                entity_prefix,
            ):
                errors["base"] = "entity_prefix_in_use"
            else:
                try:
                    api = UgreenApiClient(
                        ugreen_nas_host=user_input[CONF_UGREEN_HOST],
                        ugreen_nas_port=int(user_input[CONF_UGREEN_PORT]),
                        username=user_input[CONF_USERNAME],
                        password=user_input[CONF_PASSWORD],
                        use_https=user_input.get(CONF_USE_HTTPS, False),
                    )

                    async with aiohttp.ClientSession() as session:
                        success = await api.authenticate(session)
                        if not success:
                            errors["base"] = "invalid_auth"
                        else:
                            _LOGGER.info("[UGREEN NAS] Successfully authenticated")

                            nas_name = "UGREEN NAS"
                            serial = ""

                            try:
                                sys_info = await api.get(
                                    session, "/ugreen/v1/sysinfo/machine/common"
                                )
                                common = (sys_info or {}).get("data", {}).get("common", {})
                                nas_name = common.get("nas_name", "UGREEN NAS")
                                serial = (common.get("serial") or "").strip()
                                _LOGGER.debug("[UGREEN NAS] Retrieved NAS name: %s", nas_name)
                                _LOGGER.debug("[UGREEN NAS] Retrieved NAS serial: %s", serial)
                            except Exception as e:
                                _LOGGER.warning("[UGREEN NAS] Failed to get NAS info: %s", e)

                            if not serial:
                                _LOGGER.error(
                                    "[UGREEN NAS] Missing serial number after successful authentication"
                                )
                                errors["base"] = "cannot_connect"
                            else:
                                await self.async_set_unique_id(
                                    _build_entry_unique_id(serial)
                                )
                                self._abort_if_unique_id_configured()

                                return self.async_create_entry(
                                    title=nas_name,
                                    data={
                                        CONF_UGREEN_HOST: user_input[CONF_UGREEN_HOST],
                                        CONF_UGREEN_PORT: user_input[CONF_UGREEN_PORT],
                                        CONF_USERNAME: user_input[CONF_USERNAME],
                                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                                        CONF_USE_HTTPS: user_input.get(CONF_USE_HTTPS, False),
                                        CONF_ENTITY_PREFIX: entity_prefix,
                                        CONF_DASHBOARD_DISK_COLUMNS: disk_columns,
                                        CONF_DASHBOARD_POOL_COLUMNS: pool_columns,
                                        CONF_DASHBOARD_VOLUME_COLUMNS: volume_columns,
                                        CONF_DASHBOARD_IMAGE_FILE: image_file,
                                    },
                                )

                except Exception as e:
                    _LOGGER.exception(
                        "[UGREEN NAS] Connection/authentication failed: %s", e
                    )
                    errors["base"] = "cannot_connect"

        default_host = self._discovered_host or ""
        default_port = self._discovered_port or 9999

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_UGREEN_HOST, default=default_host): str,
                    vol.Required(CONF_UGREEN_PORT, default=default_port): int,
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Required(
                        CONF_ENTITY_PREFIX,
                        default=DEFAULT_ENTITY_PREFIX,
                    ): str,
                    vol.Optional(CONF_USE_HTTPS, default=False): bool,
                }
            ),
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        _LOGGER.debug(
            "[UGREEN NAS] Starting options flow for config entry: %s",
            config_entry.entry_id,
        )
        return UgreenNasOptionsFlowHandler(config_entry)


class UgreenNasOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle UGREEN NAS options."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        self._entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """Handle the single-page options form."""
        errors: dict[str, str] = {}

        if user_input is not None:
            _LOGGER.debug("[UGREEN NAS] Options updated: %s", user_input)

            entity_prefix = _normalize_entity_prefix(
                user_input.get(CONF_ENTITY_PREFIX, "")
            )
            entity_prefix_slug = _build_entity_prefix_slug(entity_prefix)

            disk_columns = _normalize_dashboard_columns(
                user_input.get(
                    CONF_DASHBOARD_DISK_COLUMNS,
                    DEFAULT_DASHBOARD_DISK_COLUMNS,
                ),
                DEFAULT_DASHBOARD_DISK_COLUMNS,
            )
            pool_columns = _normalize_dashboard_columns(
                user_input.get(
                    CONF_DASHBOARD_POOL_COLUMNS,
                    DEFAULT_DASHBOARD_POOL_COLUMNS,
                ),
                DEFAULT_DASHBOARD_POOL_COLUMNS,
            )
            volume_columns = _normalize_dashboard_columns(
                user_input.get(
                    CONF_DASHBOARD_VOLUME_COLUMNS,
                    DEFAULT_DASHBOARD_VOLUME_COLUMNS,
                ),
                DEFAULT_DASHBOARD_VOLUME_COLUMNS,
            )
            image_file = _normalize_dashboard_image_file(
                user_input.get(
                    CONF_DASHBOARD_IMAGE_FILE,
                    DEFAULT_DASHBOARD_IMAGE_FILE,
                )
            )

            if not entity_prefix or not entity_prefix_slug:
                errors["base"] = "invalid_entity_prefix"
            elif _is_entity_prefix_in_use(
                self.hass.config_entries.async_entries(DOMAIN),
                entity_prefix,
                current_entry_id=self._entry.entry_id,
            ):
                errors["base"] = "entity_prefix_in_use"
            else:
                user_input[CONF_ENTITY_PREFIX] = entity_prefix
                user_input[CONF_DASHBOARD_DISK_COLUMNS] = disk_columns
                user_input[CONF_DASHBOARD_POOL_COLUMNS] = pool_columns
                user_input[CONF_DASHBOARD_VOLUME_COLUMNS] = volume_columns
                user_input[CONF_DASHBOARD_IMAGE_FILE] = image_file

                if CONF_DEVICE_NAME in user_input and user_input[CONF_DEVICE_NAME]:
                    device_name = user_input[CONF_DEVICE_NAME]
                    self.hass.config_entries.async_update_entry(
                        self._entry,
                        title=device_name,
                    )

                return self.async_create_entry(title="", data=user_input)

        def _get_value(key: str, default: Any = None) -> Any:
            return self._entry.options.get(key, self._entry.data.get(key, default))

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_UGREEN_HOST,
                        default=_get_value(CONF_UGREEN_HOST, ""),
                    ): str,
                    vol.Required(
                        CONF_UGREEN_PORT,
                        default=_get_value(CONF_UGREEN_PORT, 9999),
                    ): int,
                    vol.Required(
                        CONF_USERNAME,
                        default=_get_value(CONF_USERNAME, ""),
                    ): str,
                    vol.Required(
                        CONF_PASSWORD,
                        default=_get_value(CONF_PASSWORD, ""),
                    ): str,
                    vol.Required(
                        CONF_STATE_INTERVAL,
                        default=_get_value(
                            CONF_STATE_INTERVAL,
                            DEFAULT_SCAN_INTERVAL_STATE,
                        ),
                    ): NumberSelector(
                        NumberSelectorConfig(min=5, max=3600, step=1, mode="box")
                    ),
                    vol.Required(
                        CONF_CONFIG_INTERVAL,
                        default=_get_value(
                            CONF_CONFIG_INTERVAL,
                            DEFAULT_SCAN_INTERVAL_CONFIG,
                        ),
                    ): NumberSelector(
                        NumberSelectorConfig(min=60, max=3600, step=1, mode="box")
                    ),
                    # Uncomment to show API ping frequency in configuration window
                    # vol.Optional(
                    #     CONF_WS_INTERVAL,
                    #     default=_get_value(CONF_WS_INTERVAL, DEFAULT_SCAN_INTERVAL_WS),
                    # ): NumberSelector(NumberSelectorConfig(min=20, max=60, step=1, mode="box")),
                    vol.Required(
                        CONF_ENTITY_PREFIX,
                        default=_get_value(
                            CONF_ENTITY_PREFIX,
                            DEFAULT_ENTITY_PREFIX,
                        ),
                    ): str,
                    vol.Required(
                        CONF_DASHBOARD_DISK_COLUMNS,
                        default=_get_value(
                            CONF_DASHBOARD_DISK_COLUMNS,
                            DEFAULT_DASHBOARD_DISK_COLUMNS,
                        ),
                    ): NumberSelector(
                        NumberSelectorConfig(min=1, max=6, step=1, mode="box")
                    ),
                    vol.Required(
                        CONF_DASHBOARD_POOL_COLUMNS,
                        default=_get_value(
                            CONF_DASHBOARD_POOL_COLUMNS,
                            DEFAULT_DASHBOARD_POOL_COLUMNS,
                        ),
                    ): NumberSelector(
                        NumberSelectorConfig(min=1, max=3, step=1, mode="box")
                    ),
                    vol.Required(
                        CONF_DASHBOARD_VOLUME_COLUMNS,
                        default=_get_value(
                            CONF_DASHBOARD_VOLUME_COLUMNS,
                            DEFAULT_DASHBOARD_VOLUME_COLUMNS,
                        ),
                    ): NumberSelector(
                        NumberSelectorConfig(min=1, max=3, step=1, mode="box")
                    ),
                    vol.Optional(
                        CONF_DASHBOARD_IMAGE_FILE,
                        default=_get_value(
                            CONF_DASHBOARD_IMAGE_FILE,
                            DEFAULT_DASHBOARD_IMAGE_FILE,
                        ),
                    ): str,
                    vol.Optional(
                        CONF_USE_HTTPS,
                        default=_get_value(CONF_USE_HTTPS, False),
                    ): bool,
                }
            ),
            errors=errors,
        )