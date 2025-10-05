import logging
import aiohttp
import voluptuous as vol
from typing import Any
from homeassistant import config_entries
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
        _LOGGER.info("[UGREEN NAS] Discovered device via zeroconf: %s", discovery_info)

        host = discovery_info.host
        port = discovery_info.port or 9999

        # Set unique ID to prevent duplicate entries
        await self.async_set_unique_id(f"ugreen_nas_{host}")
        self._abort_if_unique_id_configured()

        # Store discovered info for later use
        self._discovered_host = host
        self._discovered_port = port

        # Update context with discovered info
        self.context.update({
            "title_placeholders": {"name": f"UGREEN NAS ({host})"}
        })

        return await self.async_step_user()

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            _LOGGER.info("[UGREEN NAS] Received user input: %s", user_input)

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
                            sys_info = await api.get(session, "/ugreen/v1/sysinfo/machine/common")
                            common = (sys_info or {}).get("data", {}).get("common", {})
                            nas_name = common.get("nas_name", "UGREEN NAS")
                            _LOGGER.debug("[UGREEN NAS] Retrieved NAS name: %s", nas_name)
                        except Exception as e:
                            _LOGGER.warning("[UGREEN NAS] Failed to get NAS name, using default: %s", e)

                        return self.async_create_entry(
                            title=nas_name,
                            data={
                                CONF_UGREEN_HOST: user_input[CONF_UGREEN_HOST],
                                CONF_UGREEN_PORT: user_input[CONF_UGREEN_PORT],
                                CONF_USERNAME: user_input[CONF_USERNAME],
                                CONF_PASSWORD: user_input[CONF_PASSWORD],
                                CONF_USE_HTTPS: user_input.get(CONF_USE_HTTPS, False),
                            },
                        )

            except Exception as e:
                _LOGGER.exception("[UGREEN NAS] Connection/authentication failed: %s", e)
                errors["base"] = "cannot_connect"

        # Use discovered values as defaults if available
        default_host = self._discovered_host or ""
        default_port = self._discovered_port or 9999

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_UGREEN_HOST, default=default_host): str,
                vol.Required(CONF_UGREEN_PORT, default=default_port): int,
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Optional(CONF_USE_HTTPS, default=False): bool,
            }),
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        _LOGGER.debug("[UGREEN NAS] Starting options flow for config entry: %s", config_entry.entry_id)
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
                    self._entry,
                    title=device_name
                )

            return self.async_create_entry(title="", data=user_input)

        # Helper function to get value from options, falling back to data
        def _get_value(key: str, default: Any = None) -> Any:
            return self._entry.options.get(key, self._entry.data.get(key, default))

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional(CONF_UGREEN_HOST, default=_get_value(CONF_UGREEN_HOST, "")): str,
                vol.Optional(CONF_UGREEN_PORT, default=_get_value(CONF_UGREEN_PORT, 9999)): int,
                vol.Optional(CONF_USERNAME, default=_get_value(CONF_USERNAME, "")): str,
                vol.Optional(CONF_PASSWORD, default=_get_value(CONF_PASSWORD, "")): str,
                vol.Optional(CONF_USE_HTTPS, default=_get_value(CONF_USE_HTTPS, False)): bool,
            }),
        )
