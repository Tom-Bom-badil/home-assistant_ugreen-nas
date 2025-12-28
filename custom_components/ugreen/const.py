DOMAIN = "ugreen"
PLATFORMS = ["sensor", "button"]

CONF_DEVICE_NAME = "device_name"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"

CONF_UGREEN_HOST = "ugreen_host"
CONF_UGREEN_PORT = "ugreen_port"
CONF_USE_HTTPS = "use_https"

CONF_STATE_INTERVAL = "state_interval"
CONF_CONFIG_INTERVAL = "config_interval"
CONF_WS_INTERVAL = "ws_interval"

DEFAULT_SCAN_INTERVAL_CONFIG = 60   # config entities = 60 seconds
DEFAULT_SCAN_INTERVAL_STATE = 5     # status entities =  5 seconds
DEFAULT_SCAN_INTERVAL_WS = 20       # keep-alive ping for websocket = 20 seconds

MANUFACTURER = "UGREEN"
STORAGE_TECHNOLOGY = "Linux mdadm"
CACHE_TECHNOLOGY = "Linux lvm-v1"
