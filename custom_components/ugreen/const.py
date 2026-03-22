DOMAIN = "ugreen"
MANUFACTURER = "UGREEN"
PLATFORMS = ["sensor", "button", "select", "text"]

STORAGE_TECHNOLOGY = "Linux mdadm"
CACHE_TECHNOLOGY = "Linux lvm-v1"

CONF_UGREEN_HOST = "ugreen_host"
CONF_UGREEN_PORT = "ugreen_port"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_USE_HTTPS = "use_https"

CONF_STATE_INTERVAL = "state_interval"
CONF_CONFIG_INTERVAL = "config_interval"
CONF_WS_INTERVAL = "ws_interval"
CONF_ENTITY_PREFIX = "entity_prefix"

DEFAULT_SCAN_INTERVAL_CONFIG = 60   # config entities = 60 seconds
DEFAULT_SCAN_INTERVAL_STATE = 5     # status entities =  5 seconds
DEFAULT_SCAN_INTERVAL_WS = 20       # keep-alive ping for websocket = 20 seconds
DEFAULT_ENTITY_PREFIX = "UGREEN NAS"

LOVELACE_DEVICE_SELECT_NAME = "UGREEN NAS Lovelace Device Select"
LOVELACE_DEVICE_SELECT_UNIQUE_ID = "ugreen_nas_lovelace_device_select"

LOVELACE_ENTITY_FILTER_NAME = "UGREEN NAS Lovelace Entity Filter"
LOVELACE_ENTITY_FILTER_UNIQUE_ID = "ugreen_nas_lovelace_entity_filter"

CONF_DASHBOARD_DISK_COLUMNS = "dashboard_disk_columns"
CONF_DASHBOARD_POOL_COLUMNS = "dashboard_pool_columns"
CONF_DASHBOARD_VOLUME_COLUMNS = "dashboard_volume_columns"
CONF_DASHBOARD_IMAGE_FILE = "dashboard_image_file"

DEFAULT_DASHBOARD_DISK_COLUMNS = 5
DEFAULT_DASHBOARD_POOL_COLUMNS = 2
DEFAULT_DASHBOARD_VOLUME_COLUMNS = 2
DEFAULT_DASHBOARD_IMAGE_FILE = "default_picture.png"
