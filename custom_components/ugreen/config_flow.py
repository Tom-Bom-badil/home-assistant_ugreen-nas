import logging
import asyncio
from typing import Any, Optional

import aiohttp
from aiohttp import ClientError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import (
    DOMAIN,
    CONF_DEVICE_NAME,
    CONF_UGREEN_HOST,
    CONF_UGREEN_PORT,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_USE_HTTPS,
)
from .api import UgreenApiClient

_LOGGER = logging.getLogger(__name__)

HEARTBEAT_PATH = "/ugreen/v1/verify/heartbeat"


def _normalize_discovery_id(discovery_info: ZeroconfServiceInfo) -> str:
    """
    Build a stable unique id from zeroconf data.
    Normalize hostname and instance name, strip '.local' and ignore IPv4/IPv6
    address changes as much as possible.
    """
    host = (discovery_info.host or "").strip().lower()
    hostname = (discovery_info.hostname or "").strip().rstrip(".")
    name = (discovery_info.name or "").strip().rstrip(".")

    def clean(value: str) -> str:
        v = value.strip().lower()
        if v.endswith(".local"):
            v = v[: -len(".local")]
        return v

    hostname_id = clean(hostname) if hostname else ""
    instance_raw = name.split("._", 1)[0] if name else ""
    instance_id = clean(instance_raw) if instance_raw else ""

    base = hostname_id or instance_id or host
    return f"ugreen_nas_{base}"


async def _is_ugreen_device(hass, host: Optional[str], port: int) -> bool:
    """
    Probe the unauthenticated heartbeat endpoint to verify a UGREEN NAS.
    Return True only if the endpoint responds with code=200 and msg='success'.
    """
    if not host:
        return False

    # Handle IPv6 literal addresses
    netloc = f"[{host}]" if ":" in host and not host.startswith("[") else host
    url = f"http://{netloc}:{port}{HEARTBEAT_PATH}"

    session = async_get_clientsession(hass)

    try:
        async with session.get(url, timeout=3) as resp:
            if resp.status != 200:
                return False
            data = await resp.json(content_type=None)
    # except (ClientError, asyncio.TimeoutError, ValueError):   # --> use for degugging
        ## Network error, timeout, or invalid JSON → not a UGREEN NAS
        # return false
    except:
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

        # Build a stable unique id that does not change with IPv4/IPv6 or .local suffixes
        unique_id = _normalize_discovery_id(discovery_info)

        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        # New potential device: verify that it is really a UGREEN NAS.
        if not await _is_ugreen_device(self.hass, host, port):
            _LOGGER.debug(
                "[UGREEN NAS] Zeroconf candidate at %s:%s did not respond as UGREEN NAS",
                host,
                port,
            )
            return self.async_abort(reason="not_ugreen_nas")

        # Store discovered info for later use
        self._discovered_host = host
        self._discovered_port = port

        # Update context with discovered info
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
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            _LOGGER.debug("[UGREEN NAS] Received user input: %s", user_input)

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

                        # Get NAS name from API
                        nas_name = "UGREEN NAS"
                        try:
                            sys_info = await api.get(
                                session, "/ugreen/v1/sysinfo/machine/common"
                            )
                            common = (sys_info or {}).get("data", {}).get("common", {})
                            nas_name = common.get("nas_name", "UGREEN NAS")
                            _LOGGER.debug(
                                "[UGREEN NAS] Retrieved NAS name: %s", nas_name
                            )
                        except Exception as e:  # pylint: disable=broad-except
                            _LOGGER.warning(
                                "[UGREEN NAS] Failed to get NAS name, using default: %s",
                                e,
                            )

                        return self.async_create_entry(
                            title=nas_name,
                            data={
                                CONF_UGREEN_HOST: user_input[CONF_UGREEN_HOST],
                                CONF_UGREEN_PORT: user_input[CONF_UGREEN_PORT],
                                CONF_USERNAME: user_input[CONF_USERNAME],
                                CONF_PASSWORD: user_input[CONF_PASSWORD],
                                CONF_USE_HTTPS: user_input.get(
                                    CONF_USE_HTTPS, False
                                ),
                            },
                        )

            except Exception as e:  # pylint: disable=broad-except
                _LOGGER.exception(
                    "[UGREEN NAS] Connection/authentication failed: %s", e
                )
                errors["base"] = "cannot_connect"

        # Use discovered values as defaults if available
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
        if user_input is not None:
            _LOGGER.info("[UGREEN NAS] Options updated: %s", user_input)

            # Update device name if changed
            if CONF_DEVICE_NAME in user_input and user_input[CONF_DEVICE_NAME]:
                device_name = user_input[CONF_DEVICE_NAME]
                self.hass.config_entries.async_update_entry(
                    self._entry, title=device_name
                )

            return self.async_create_entry(title="", data=user_input)

        # Helper function to get value from options, falling back to data
        def _get_value(key: str, default: Any = None) -> Any:
            return self._entry.options.get(key, self._entry.data.get(key, default))

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_UGREEN_HOST,
                        default=_get_value(CONF_UGREEN_HOST, ""),
                    ): str,
                    vol.Optional(
                        CONF_UGREEN_PORT,
                        default=_get_value(CONF_UGREEN_PORT, 9999),
                    ): int,
                    vol.Optional(
                        CONF_USERNAME, default=_get_value(CONF_USERNAME, "")
                    ): str,
                    vol.Optional(
                        CONF_PASSWORD, default=_get_value(CONF_PASSWORD, "")
                    ): str,
                    vol.Optional(
                        CONF_USE_HTTPS, default=_get_value(CONF_USE_HTTPS, False)
                    ): bool,
                }
            ),
        )
