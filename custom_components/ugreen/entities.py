# ==============================================================================
# UGREEN ENTITIES
# ==============================================================================
#    │
#    ├─ ALL_NAS_COMMON    (always present in any NAS)
#    │  ├─ CONFIG         (60s polling: name, model etc)
#    │  ├─ STATUS         (5s polling: temps, cpu usage etc)
#    │  └─ BUTTONS        (actions; shutdown, restart)
#    │
#    └─ NAS_SPECIFIC      (presence 1..n is depending on your NAS & setup)
#       ├─ LAN
#       ├─ USB
#       ├─ RAM
#       ├─ UPS
#       ├─ FANS
#       |  ├─ CHASSIS (=DEVICE)
#       |  └─ CPU
#       └─ STORAGE
#          ├─ POOLS
#          ├─ VOLUMES
#          └─ DISKS
#
# Note: All NAS_SPECIFIC items are split further into CONFIG (60s) and STATUS (5s).


from dataclasses import dataclass
from typing import List
from homeassistant.helpers.entity import EntityDescription
from homeassistant.const import (
    PERCENTAGE, REVOLUTIONS_PER_MINUTE, UnitOfDataRate, UnitOfTemperature,
    UnitOfInformation, UnitOfTime, UnitOfFrequency
)

@dataclass
class UgreenEntity:
    description: EntityDescription
    endpoint: str
    path: str
    request_method: str = "GET"
    decimal_places: int = 2
    nas_part_category: str = ""


# Common sensors available in all models - name, serial etc. Updated every 60s.
ALL_NAS_COMMON_CONFIG_ENTITIES: List[UgreenEntity] = [  # -- common config entities --

    ### Device Info
    UgreenEntity(
        description=EntityDescription(
            key="type",
            name="NAS Type",
            icon="mdi:nas",
            unit_of_measurement=None,
        ),
        endpoint="/ugreen/v1/desktop/components/data?id=desktop.component.SystemStatus",
        path="data.type",
        nas_part_category="Device",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="owner",
            name="NAS Owner",
            icon="mdi:account",
            unit_of_measurement=None,
        ),
        endpoint="/ugreen/v1/sysinfo/machine/common",
        path="data.common.nas_owner",
        nas_part_category="Device",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="device_name",
            name="NAS Name",
            icon="mdi:nas",
            unit_of_measurement=None,
        ),
        endpoint="/ugreen/v1/desktop/components/data?id=desktop.component.SystemStatus",
        path="data.dev_name",
        nas_part_category="Device",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="ugos_version",
            name="NAS UGOS Version",
            icon="mdi:information-outline",
            unit_of_measurement=None,
        ),
        endpoint="/ugreen/v1/sysinfo/machine/common",
        path="data.common.system_version",
        nas_part_category="Device",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="model",
            name="NAS Model",
            icon="mdi:nas",
            unit_of_measurement=None,
        ),
        endpoint="/ugreen/v1/sysinfo/machine/common",
        path="data.common.model",
        nas_part_category="Device",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="serial",
            name="NAS Serial",
            icon="mdi:barcode",
            unit_of_measurement=None,
        ),
        endpoint="/ugreen/v1/sysinfo/machine/common",
        path="data.common.serial",
        nas_part_category="Device",
    ),

    ### Hardware Info
    UgreenEntity(
        description=EntityDescription(
            key="cpu_model",
            name="CPU Model",
            icon="mdi:chip",
            unit_of_measurement=None,
        ),
        endpoint="/ugreen/v1/sysinfo/machine/common",
        path="data.hardware.cpu[0].model",
        nas_part_category="Hardware",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="cpu_ghz",
            name="CPU Speed",
            icon="mdi:speedometer",
            unit_of_measurement=UnitOfFrequency.MEGAHERTZ,
        ),
        endpoint="/ugreen/v1/sysinfo/machine/common",
        path="data.hardware.cpu[0].ghz",
        decimal_places=0,
        nas_part_category="Hardware",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="cpu_core",
            name="CPU Cores",
            icon="mdi:chip",
            unit_of_measurement="Cores",
        ),
        endpoint="/ugreen/v1/sysinfo/machine/common",
        path="data.hardware.cpu[0].core",
        decimal_places=0,
        nas_part_category="Hardware",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="cpu_thread",
            name="CPU Threads",
            icon="mdi:chip",
            unit_of_measurement="Threads",
        ),
        endpoint="/ugreen/v1/sysinfo/machine/common",
        path="data.hardware.cpu[0].thread",
        decimal_places=0,
        nas_part_category="Hardware",
    ),

    ### Runtime info
    UgreenEntity(
        description=EntityDescription(
            key="last_boot_date",
            name="Last Boot",
            icon="mdi:calendar",
            unit_of_measurement=None,
        ),
        endpoint="/ugreen/v1/desktop/components/data?id=desktop.component.SystemStatus",
        path="data.last_boot_date",
        nas_part_category="Status",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="last_boot_time",
            name="Last Boot Timestamp",
            icon="mdi:clock",
            unit_of_measurement=None,
        ),
        endpoint="/ugreen/v1/desktop/components/data?id=desktop.component.SystemStatus",
        path="data.last_boot_time",
        nas_part_category="Status",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="total_run_time",
            name="Total Runtime",
            icon="mdi:timer-outline",
            unit_of_measurement=UnitOfTime.SECONDS,
        ),
        endpoint="/ugreen/v1/desktop/components/data?id=desktop.component.SystemStatus",
        path="data.total_run_time",
        nas_part_category="Status",
    ),

    ### System Status
    UgreenEntity(
        description=EntityDescription(
            key="server_status",
            name="Server Status",
            icon="mdi:server",
            unit_of_measurement=None,
        ),
        endpoint="/ugreen/v1/desktop/components/data?id=desktop.component.SystemStatus",
        path="data.server_status",
        nas_part_category="Status",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="status",
            name="System Status Code",
            icon="mdi:information",
            unit_of_measurement=None,
        ),
        endpoint="/ugreen/v1/desktop/components/data?id=desktop.component.SystemStatus",
        path="data.status",
        nas_part_category="Status",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="cpu_status",
            name="CPU Temperature Status",
            icon="mdi:alert",
            unit_of_measurement=None,
        ),
        endpoint="/ugreen/v1/desktop/components/data?id=desktop.component.TemperatureMonitoring",
        path="data.cpu_status",
        nas_part_category="Status",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="temperature_status",
            name="Temperature Status Code",
            icon="mdi:information",
            unit_of_measurement=None,
        ),
        endpoint="/ugreen/v1/desktop/components/data?id=desktop.component.TemperatureMonitoring",
        path="data.status",
        nas_part_category="Status",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="temperature_message",
            name="Temperature Message",
            icon="mdi:message-alert",
            unit_of_measurement=None,
        ),
        endpoint="/ugreen/v1/desktop/components/data?id=desktop.component.TemperatureMonitoring",
        path="data.message",
        nas_part_category="Status",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="message",
            name="System Message",
            icon="mdi:message",
            unit_of_measurement=None,
        ),
        endpoint="/ugreen/v1/desktop/components/data?id=desktop.component.SystemStatus",
        path="data.message",
        nas_part_category="Status",
    ),
]


# States available in all models - cpu temp, ram usage etc. Updated every 5s.
ALL_NAS_COMMON_STATE_ENTITIES = [ # -- common status entities --

    ### CPU
    UgreenEntity(
        description=EntityDescription(
            key="cpu_usage",
            name="CPU Usage",
            icon="mdi:chip",
            unit_of_measurement=PERCENTAGE,
        ),
        decimal_places=0,
        endpoint="/ugreen/v1/taskmgr/stat/get_all",
        path="data.overview.cpu[0].used_percent",
        nas_part_category="Status",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="cpu_temperature",
            name="CPU Temperature",
            icon="mdi:thermometer",
            unit_of_measurement=UnitOfTemperature.CELSIUS,
        ),
        decimal_places=0,
        endpoint="/ugreen/v1/taskmgr/stat/get_all",
        path="data.overview.cpu[0].temp",
        nas_part_category="Status",
    ),

    ### RAM
    UgreenEntity(
        description=EntityDescription(
            key="mem_usage",
            name="RAM Usage",
            icon="mdi:memory",
            unit_of_measurement=PERCENTAGE,
        ),
        endpoint="/ugreen/v1/taskmgr/stat/get_all",
        path="data.overview.mem[0].used_percent",
        nas_part_category="Status",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="ram_usage_total_usable",
            name="RAM Usage (Usable RAM)",
            icon="mdi:memory",
            unit_of_measurement=UnitOfInformation.BYTES,
        ),
        endpoint="/ugreen/v1/taskmgr/stat/get_all",
        path="data.mem.structure.total",
        nas_part_category="Status",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="ram_usage_free",
            name="RAM Usage (Free RAM)",
            icon="mdi:memory",
            unit_of_measurement=UnitOfInformation.BYTES,
        ),
        endpoint="/ugreen/v1/taskmgr/stat/get_all",
        path="data.mem.structure.free",
        nas_part_category="Status",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="ram_usage_cache",
            name="RAM Usage (Cache)",
            icon="mdi:memory",
            unit_of_measurement=UnitOfInformation.BYTES,
        ),
        endpoint="/ugreen/v1/taskmgr/stat/get_all",
        path="data.mem.structure.cache",
        nas_part_category="Status",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="ram_usage_shared",
            name="RAM Usage (Shared Mem)",
            icon="mdi:memory",
            unit_of_measurement=UnitOfInformation.BYTES,
        ),
        endpoint="/ugreen/v1/taskmgr/stat/get_all",
        path="data.mem.structure.share",
        nas_part_category="Status",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="ram_usage_used_gb",
            name="RAM Usage (Used GB)",
            icon="mdi:memory",
            unit_of_measurement=UnitOfInformation.BYTES,
        ),
        endpoint="/ugreen/v1/taskmgr/stat/get_all",
        path="data.mem.structure.used",
        nas_part_category="Status",
    ),

    ### FAN (overall status)
    UgreenEntity(
        description=EntityDescription(
            key="fan_status_overall",
            name="Fan Status (overall)",
            icon="mdi:fan-alert",
            unit_of_measurement=None,
        ),
        endpoint="/ugreen/v1/desktop/components/data?id=desktop.component.TemperatureMonitoring",
        path="data.fan_status",
        nas_part_category="Status",
    ),

    ### LAN (net.overview = first element, overall)
    UgreenEntity(
        description=EntityDescription(
            key="overall_lan_upload_raw",
            name="Overall LAN Upload (raw)",
            icon="mdi:upload-network",
            unit_of_measurement=UnitOfDataRate.BYTES_PER_SECOND,
        ),
        endpoint="/ugreen/v1/taskmgr/stat/get_all",
        path="data.net.series[0].send_rate",
        nas_part_category="Status",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="overall_lan_upload",
            name="Overall LAN Upload",
            icon="mdi:upload-network",
            unit_of_measurement=None,
        ),
        endpoint="/ugreen/v1/taskmgr/stat/get_all",
        path="calculated:scale_bytes_per_second:data.net.series[0].send_rate",
        nas_part_category="Status",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="overall_lan_download_raw",
            name="Overall LAN Download (raw)",
            icon="mdi:download-network",
            unit_of_measurement=UnitOfDataRate.BYTES_PER_SECOND,
        ),
        endpoint="/ugreen/v1/taskmgr/stat/get_all",
        path="data.net.series[0].recv_rate",
        nas_part_category="Status",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="overall_lan_download",
            name="Overall LAN Download",
            icon="mdi:download-network",
            unit_of_measurement=None,
        ),
        endpoint="/ugreen/v1/taskmgr/stat/get_all",
        path="calculated:scale_bytes_per_second:data.net.series[0].recv_rate",
        nas_part_category="Status",
    ),

    ### Disks (disk.series only = first element, overall)
    UgreenEntity(
        description=EntityDescription(
            key="overall_disk_read_rate_raw",
            name="Overall Disk Read Rate (raw)",
            icon="mdi:harddisk",
            unit_of_measurement=UnitOfDataRate.BYTES_PER_SECOND,
        ),
        endpoint="/ugreen/v1/taskmgr/stat/get_all",
        path="data.disk.series[0].read_rate",
        nas_part_category="Status",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="overall_disk_read_rate",
            name="Overall Disk Read Rate",
            icon="mdi:harddisk",
            unit_of_measurement=None,
        ),
        endpoint="/ugreen/v1/taskmgr/stat/get_all",
        path="calculated:scale_bytes_per_second:data.disk.series[0].read_rate",
        nas_part_category="Status",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="overall_disk_write_rate_raw",
            name="Overall Disk Write Rate (raw)",
            icon="mdi:harddisk",
            unit_of_measurement=UnitOfDataRate.BYTES_PER_SECOND,
        ),
        endpoint="/ugreen/v1/taskmgr/stat/get_all",
        path="data.disk.series[0].write_rate",
        nas_part_category="Status",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="overall_disk_write_rate",
            name="Overall Disk Write Rate",
            icon="mdi:harddisk",
            unit_of_measurement=None,
        ),
        endpoint="/ugreen/v1/taskmgr/stat/get_all",
        path="calculated:scale_bytes_per_second:data.disk.series[0].write_rate",
        nas_part_category="Status",
    ),

    ### Volumes (volume.series only = first element, overall)
    UgreenEntity(
        description=EntityDescription(
            key="overall_volume_read_rate_raw",
            name="Overall Volume Read Rate (raw)",
            icon="mdi:harddisk",
            unit_of_measurement=UnitOfDataRate.BYTES_PER_SECOND,
        ),
        endpoint="/ugreen/v1/taskmgr/stat/get_all",
        path="data.volume.series[0].read_rate",
        nas_part_category="Status",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="overall_volume_read_rate",
            name="Overall Volume Read Rate",
            icon="mdi:harddisk",
            unit_of_measurement=None,
        ),
        endpoint="/ugreen/v1/taskmgr/stat/get_all",
        path="calculated:scale_bytes_per_second:data.volume.series[0].read_rate",
        nas_part_category="Status",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="overall_volume_write_rate_raw",
            name="Overall Volume Write Rate (raw)",
            icon="mdi:harddisk",
            unit_of_measurement=UnitOfDataRate.BYTES_PER_SECOND,
        ),
        endpoint="/ugreen/v1/taskmgr/stat/get_all",
        path="data.volume.series[0].write_rate",
        nas_part_category="Status",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="overall_volume_write_rate",
            name="Overall Volume Write Rate",
            icon="mdi:harddisk",
            unit_of_measurement=None,
        ),
        endpoint="/ugreen/v1/taskmgr/stat/get_all",
        path="calculated:scale_bytes_per_second:data.volume.series[0].write_rate",
        nas_part_category="Status",
    ),
]


# Entities for actions available on any NAS: Shutdown, reboot."""
ALL_NAS_COMMON_BUTTON_ENTITIES: List[UgreenEntity] = [ # -- buttons --

    UgreenEntity(
        description=EntityDescription(
            key="shutdown",
            name="Shutdown",
            icon="mdi:power",
        ),
        endpoint="/ugreen/v1/desktop/shutdown",
        path="",
        request_method="POST",
        nas_part_category="",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="reboot",
            name="Reboot",
            icon="mdi:restart",
        ),
        endpoint="/ugreen/v1/desktop/reboot",
        path="",
        request_method="POST",
        nas_part_category="",
    ),
]


# Blueprint for detected USB devices and its properties (config 60s, status 5s)
NAS_SPECIFIC_CONFIG_TEMPLATES_USB: List[UgreenEntity] = [ # -- USB --

    UgreenEntity(
        description=EntityDescription(
            key="{prefix_key}_model",
            name="{prefix_name} Model",
            icon="mdi:usb-port",
            unit_of_measurement=None,
        ),
        endpoint="{endpoint}",
        path="data.hardware.usb[{i}].model",
        nas_part_category="USB",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="{prefix_key}_vendor",
            name="{prefix_name} Vendor",
            icon="mdi:usb-port",
            unit_of_measurement=None,
        ),
        endpoint="{endpoint}",
        path="data.hardware.usb[{i}].vendor",
        nas_part_category="USB",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="{prefix_key}_type",
            name="{prefix_name} Type",
            icon="mdi:usb-port",
            unit_of_measurement=None,
        ),
        endpoint="{endpoint}",
        path="data.hardware.usb[{i}].device_type",
        nas_part_category="USB",
    ),
]

NAS_SPECIFIC_STATUS_TEMPLATES_USB: list[UgreenEntity] = [
    # Intentionally empty for now.
]


# Blueprint for detected LAN ports and its properties (config 60s, status 5s)
NAS_SPECIFIC_CONFIG_TEMPLATES_LAN: List[UgreenEntity] = [ # -- LAN --

    UgreenEntity(
        description=EntityDescription(
            key="{prefix_key}_model",
            name="{prefix_name} Model",
            icon="mdi:lan",
            unit_of_measurement=None,
        ),
        endpoint="{endpoint}",
        path="data.hardware.net[{i}].model",
        nas_part_category="Network",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="{prefix_key}_ip",
            name="{prefix_name} IP",
            icon="mdi:lan",
            unit_of_measurement=None,
        ),
        endpoint="{endpoint}",
        path="data.hardware.net[{i}].ip",
        nas_part_category="Network",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="{prefix_key}_mac",
            name="{prefix_name} MAC",
            icon="mdi:lan",
            unit_of_measurement=None,
        ),
        endpoint="{endpoint}",
        path="data.hardware.net[{i}].mac",
        nas_part_category="Network",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="{prefix_key}_speed",
            name="{prefix_name} Speed",
            icon="mdi:speedometer",
            unit_of_measurement="Mb/s",
        ),
        endpoint="{endpoint}",
        path="data.hardware.net[{i}].speed",
        nas_part_category="Network",
    ),
    # ToDo: To be checked / verified, always empty
    # UgreenEntity(
    #     description=EntityDescription(
    #         key="{prefix_key}_duplex",
    #         name="{prefix_name} Duplex",
    #         icon="mdi:lan",
    #         unit_of_measurement=None,
    #     ),
    #     endpoint="{endpoint}",
    #     path="data.hardware.net[{i}].duplex",
    #     nas_part_category="Network",
    # ),
    UgreenEntity(
        description=EntityDescription(
            key="{prefix_key}_mtu",
            name="{prefix_name} MTU",
            icon="mdi:lan",
            unit_of_measurement=None,
        ),
        endpoint="{endpoint}",
        path="data.hardware.net[{i}].mtu",
        nas_part_category="Network",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="{prefix_key}_netmask",
            name="{prefix_name} Netmask",
            icon="mdi:lan",
            unit_of_measurement=None,
        ),
        endpoint="{endpoint}",
        path="data.hardware.net[{i}].mask",
        nas_part_category="Network",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="{prefix_key}_gateway",
            name="{prefix_name} Gateway",
            icon="mdi:lan",
            unit_of_measurement=None,
        ),
        endpoint="/ugreen/v1/network/iface/list",
        path="data.ifaces[{i}].ipv4.gateway",
        nas_part_category="Network",
    ),

    UgreenEntity(
        description=EntityDescription(
            key="{prefix_key}_dnsserver",
            name="{prefix_name} DNS Server",
            icon="mdi:lan",
            unit_of_measurement=None,
        ),
        endpoint="/ugreen/v1/network/iface/list",
        path="data.ifaces[{i}].ipv4.dns[0]",
        nas_part_category="Network",
    ),
]

NAS_SPECIFIC_STATUS_TEMPLATES_LAN: List[UgreenEntity] = [

    # raw
    UgreenEntity(
        description=EntityDescription(
            key="{prefix_key}_upload_raw",
            name="{prefix_name} Upload (raw)",
            icon="mdi:upload-network",
            unit_of_measurement="B/s",
        ),
        endpoint="{endpoint}",
        path="data.net.series[{series_index}].send_rate",
        decimal_places=0,
        nas_part_category="Status",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="{prefix_key}_download_raw",
            name="{prefix_name} Download (raw)",
            icon="mdi:download-network",
            unit_of_measurement="B/s",
        ),
        endpoint="{endpoint}",
        path="data.net.series[{series_index}].recv_rate",
        decimal_places=0,
        nas_part_category="Status",
    ),
    # scaled (uses calculated:scale_bytes_per_second handler)
    UgreenEntity(
        description=EntityDescription(
            key="{prefix_key}_upload",
            name="{prefix_name} Upload",
            icon="mdi:upload-network",
            unit_of_measurement=None,
        ),
        endpoint="{endpoint}",
        path="calculated:scale_bytes_per_second:data.net.series[{series_index}].send_rate",
        decimal_places=0,
        nas_part_category="Status",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="{prefix_key}_download",
            name="{prefix_name} Download",
            icon="mdi:download-network",
            unit_of_measurement=None,
        ),
        endpoint="{endpoint}",
        path="calculated:scale_bytes_per_second:data.net.series[{series_index}].recv_rate",
        decimal_places=0,
        nas_part_category="Status",
    ),
]


# Blueprint for detected RAM modules and its properties (config 60s, status 5s)
NAS_SPECIFIC_CONFIG_TEMPLATES_RAM: List[UgreenEntity] = [ # -- RAM --

    UgreenEntity(
        description=EntityDescription(
            key="{prefix_key}_model",
            name="{prefix_name} Model",
            icon="mdi:memory",
            unit_of_measurement=None,
        ),
        endpoint="{endpoint}",
        path="data.hardware.mem[{i}].model",
        nas_part_category="Hardware",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="{prefix_key}_manufacturer",
            name="{prefix_name} Manufacturer",
            icon="mdi:factory",
            unit_of_measurement=None,
        ),
        endpoint="{endpoint}",
        path="data.hardware.mem[{i}].manufacturer",
        nas_part_category="Hardware",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="{prefix_key}_size",
            name="{prefix_name} Size",
            icon="mdi:memory",
            unit_of_measurement=UnitOfInformation.BYTES,
        ),
        endpoint="{endpoint}",
        path="data.hardware.mem[{i}].size",
        decimal_places=0,
        nas_part_category="Hardware",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="{prefix_key}_speed",
            name="{prefix_name} Speed",
            icon="mdi:speedometer",
            unit_of_measurement="MHz",
        ),
        endpoint="{endpoint}",
        path="data.hardware.mem[{i}].mhz",
        decimal_places=0,
        nas_part_category="Hardware",
    ),
]

NAS_SPECIFIC_STATUS_TEMPLATES_RAM: list[UgreenEntity] = [
    # Intentionally empty for now.
]


# Blueprint for a detected UPS device and its properties (config 60s, status 5s)
NAS_SPECIFIC_CONFIG_TEMPLATES_UPS: List[UgreenEntity] = [ # -- UPS --

    UgreenEntity(
        description=EntityDescription(
            key="{prefix_key}_model",
            name="{prefix_name} Model",
            icon="mdi:power-plug-battery",
            unit_of_measurement=None,
        ),
        endpoint="{endpoint}",
        path="data.hardware.ups[0].model",
        nas_part_category="UPS",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="{prefix_key}_vendor",
            name="{prefix_name} Vendor",
            icon="mdi:factory",
            unit_of_measurement=None,
        ),
        endpoint="{endpoint}",
        path="data.hardware.ups[0].vendor",
        nas_part_category="UPS",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="{prefix_key}_power_free",
            name="{prefix_name} Power Remaining",
            icon="mdi:power-plug-battery",
            unit_of_measurement=None,  # incoming string is like '100%'
        ),
        endpoint="{endpoint}",
        path="data.hardware.ups[0].power_free",
        nas_part_category="UPS",
    ),
]

NAS_SPECIFIC_STATUS_TEMPLATES_UPS: list[UgreenEntity] = [
    # Intentionally empty for now.
]


# Blueprint for detected fans and their properties (config 60s, status 5s)
NAS_SPECIFIC_STATUS_TEMPLATES_FANS_CHASSIS: List[UgreenEntity] = [ # -- fans --

    UgreenEntity(
        description=EntityDescription(
            key="{prefix_key}_speed",
            name="{prefix_name}",
            icon="mdi:fan",
            unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        ),
        endpoint="{endpoint}",
        path="data.overview.device_fan[{i}].speed",
        nas_part_category="Status",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="{prefix_key}_status",
            name="{prefix_name} Status",
            icon="mdi:fan-alert",
            unit_of_measurement=None,
        ),
        endpoint="{endpoint}",
        path="data.overview.device_fan[{i}].status",
        nas_part_category="Status",
    ),
]

NAS_SPECIFIC_STATUS_TEMPLATES_FAN_CPU: List[UgreenEntity] = [

    UgreenEntity(
        description=EntityDescription(
            key="cpu_fan_speed",
            name="CPU Fan",
            icon="mdi:fan",
            unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        ),
        endpoint="{endpoint}",
        path="data.overview.cpu_fan[0].speed",
        nas_part_category="Status",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="cpu_fan_status",
            name="CPU Fan Status",
            icon="mdi:fan-alert",
            unit_of_measurement=None,
        ),
        endpoint="{endpoint}",
        path="data.overview.cpu_fan[0].status",
        nas_part_category="Status",
    ),
]

NAS_SPECIFIC_CONFIG_TEMPLATES_FANS: list[UgreenEntity] = [
    # Intentionally empty for now.
]


# Blueprint for detected pools and their properties (config 60s, status 5s)
NAS_SPECIFIC_CONFIG_TEMPLATES_STORAGE_POOL: List[UgreenEntity] = [ # -- pool --

    UgreenEntity(
        description=EntityDescription(
            key="{prefix_key}_name",
            name="({prefix_name}) Name",
            icon="mdi:chip",
            unit_of_measurement=None,
        ),
        endpoint="{endpoint}",
        path="data.result[{i}].name",
        nas_part_category="Pools",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="{prefix_key}_label",
            name="({prefix_name}) Label",
            icon="mdi:label-outline",
            unit_of_measurement=None,
        ),
        endpoint="{endpoint}",
        path="data.result[{i}].label",
        nas_part_category="Pools",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="{prefix_key}_level",
            name="({prefix_name}) Level",
            icon="mdi:database-settings",
            unit_of_measurement=None,
        ),
        endpoint="{endpoint}",
        path="data.result[{i}].level",
        nas_part_category="Pools",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="{prefix_key}_status",
            name="({prefix_name}) Status",
            icon="mdi:check-circle-outline",
            unit_of_measurement=None,
        ),
        endpoint="{endpoint}",
        path="data.result[{i}].status",
        nas_part_category="Pools",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="{prefix_key}_total",
            name="({prefix_name}) Total Size",
            icon="mdi:database",
            unit_of_measurement=UnitOfInformation.BYTES,
        ),
        endpoint="{endpoint}",
        path="data.result[{i}].total",
        nas_part_category="Pools",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="{prefix_key}_used",
            name="({prefix_name}) Used Size",
            icon="mdi:database-check",
            unit_of_measurement=UnitOfInformation.BYTES,
        ),
        endpoint="{endpoint}",
        path="data.result[{i}].used",
        nas_part_category="Pools",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="{prefix_key}_free",
            name="({prefix_name}) Free Size",
            icon="mdi:database-minus",
            unit_of_measurement=UnitOfInformation.BYTES,
        ),
        endpoint="{endpoint}",
        path="data.result[{i}].free",
        nas_part_category="Pools",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="{prefix_key}_available",
            name="({prefix_name}) Available Size",
            icon="mdi:database-plus",
            unit_of_measurement=UnitOfInformation.BYTES,
        ),
        endpoint="{endpoint}",
        path="data.result[{i}].available",
        nas_part_category="Pools",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="{prefix_key}_disk_count",
            name="({prefix_name}) Disk Count",
            icon="mdi:harddisk",
            unit_of_measurement=None,
        ),
        endpoint="{endpoint}",
        path="data.result[{i}].total_disk_num",
        nas_part_category="Pools",
    ),
]

NAS_SPECIFIC_STATUS_TEMPLATES_STORAGE_POOL: list[UgreenEntity] = [
    # Intentionally empty for now.
]


# Blueprint for detected volumes and its properties (config 60s, status 5s)
NAS_SPECIFIC_CONFIG_TEMPLATES_STORAGE_VOLUME: List[UgreenEntity] = [ # -- vol --

    UgreenEntity(
        description=EntityDescription(
            key="{prefix_key}_status",
            name="{prefix_name} Status",
            icon="mdi:check-circle-outline",
            unit_of_measurement=None,
        ),
        endpoint="{endpoint}",
        path="data.result[{pool_index}].volumes[{i}].status",
        nas_part_category="Volumes",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="{prefix_key}_health",
            name="{prefix_name} Health",
            icon="mdi:heart-pulse",
            unit_of_measurement=None,
        ),
        endpoint="{endpoint}",
        path="data.result[{pool_index}].volumes[{i}].health",
        nas_part_category="Volumes",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="{prefix_key}_name",
            name="{prefix_name} Name",
            icon="mdi:label",
            unit_of_measurement=None,
        ),
        endpoint="{endpoint}",
        path="data.result[{pool_index}].volumes[{i}].name",
        nas_part_category="Volumes",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="{prefix_key}_label",
            name="{prefix_name} Label",
            icon="mdi:label-outline",
            unit_of_measurement=None,
        ),
        endpoint="{endpoint}",
        path="data.result[{pool_index}].volumes[{i}].label",
        nas_part_category="Volumes",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="{prefix_key}_poolname",
            name="{prefix_name} Pool Name",
            icon="mdi:database",
            unit_of_measurement=None,
        ),
        endpoint="{endpoint}",
        path="data.result[{pool_index}].volumes[{i}].poolname",
        nas_part_category="Volumes",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="{prefix_key}_total",
            name="{prefix_name} Total Size",
            icon="mdi:database",
            unit_of_measurement=UnitOfInformation.BYTES,
        ),
        endpoint="{endpoint}",
        path="data.result[{pool_index}].volumes[{i}].total",
        nas_part_category="Volumes",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="{prefix_key}_used",
            name="{prefix_name} Used Size",
            icon="mdi:database-check",
            unit_of_measurement=UnitOfInformation.BYTES,
        ),
        endpoint="{endpoint}",
        path="data.result[{pool_index}].volumes[{i}].used",
        nas_part_category="Volumes",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="{prefix_key}_available",
            name="{prefix_name} Available Size",
            icon="mdi:database-plus",
            unit_of_measurement=UnitOfInformation.BYTES,
        ),
        endpoint="{endpoint}",
        path="data.result[{pool_index}].volumes[{i}].available",
        nas_part_category="Volumes",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="{prefix_key}_hascache",
            name="{prefix_name} Has Cache",
            icon="mdi:cached",
            unit_of_measurement=None,
        ),
        endpoint="{endpoint}",
        path="data.result[{pool_index}].volumes[{i}].hascache",
        nas_part_category="Volumes",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="{prefix_key}_filesystem",
            name="{prefix_name} Filesystem",
            icon="mdi:file-cog",
            unit_of_measurement=None,
        ),
        endpoint="{endpoint}",
        path="data.result[{pool_index}].volumes[{i}].filesystem",
        nas_part_category="Volumes",
    ),
]

NAS_SPECIFIC_STATUS_TEMPLATES_STORAGE_VOLUME: list[UgreenEntity] = [
    # Intentionally empty for now.
]


# Blueprint for detected disks and their properties (config 60s, status 5s)
NAS_SPECIFIC_CONFIG_TEMPLATES_STORAGE_DISK: List[UgreenEntity] = [ # -- disks --

    UgreenEntity(
        description=EntityDescription(
            key="{prefix_key}_type",
            name="{prefix_name} Type",
            icon="mdi:harddisk",
            unit_of_measurement=None,
        ),
        endpoint="{endpoint}",
        path="data.result[{series_index}].type",
        nas_part_category="Disks",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="{prefix_key}_model",
            name="{prefix_name} Model",
            icon="mdi:harddisk",
            unit_of_measurement=None,
        ),
        endpoint="{endpoint}",
        path="data.result[{series_index}].model",
        nas_part_category="Disks",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="{prefix_key}_interface_type",
            name="{prefix_name} Interface Type",
            icon="mdi:usb-port",
            unit_of_measurement=None,
        ),
        endpoint="{endpoint}",
        path="data.result[{series_index}].interface_type",
        nas_part_category="Disks",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="{prefix_key}_label",
            name="{prefix_name} Label",
            icon="mdi:label-outline",
            unit_of_measurement=None,
        ),
        endpoint="{endpoint}",
        path="data.result[{series_index}].label",
        nas_part_category="Disks",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="{prefix_key}_serial",
            name="{prefix_name} Serial",
            icon="mdi:barcode",
            unit_of_measurement=None,
        ),
        endpoint="{endpoint}",
        path="data.result[{series_index}].serial",
        nas_part_category="Disks",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="{prefix_key}_size",
            name="{prefix_name} Size",
            icon="mdi:database",
            unit_of_measurement=UnitOfInformation.BYTES,
        ),
        endpoint="{endpoint}",
        path="data.result[{series_index}].size",
        nas_part_category="Disks",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="{prefix_key}_name",
            name="{prefix_name} Name",
            icon="mdi:tag",
            unit_of_measurement=None,
        ),
        endpoint="{endpoint}",
        path="data.result[{series_index}].name",
        nas_part_category="Disks",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="{prefix_key}_dev_name",
            name="{prefix_name} Device",
            icon="mdi:usb-port",
            unit_of_measurement=None,
        ),
        endpoint="{endpoint}",
        path="data.result[{series_index}].dev_name",
        nas_part_category="Disks",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="{prefix_key}_slot",
            name="{prefix_name} Slot",
            icon="mdi:server",
            unit_of_measurement=None,
        ),
        endpoint="{endpoint}",
        path="data.result[{series_index}].slot",
        nas_part_category="Disks",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="{prefix_key}_used_for",
            name="{prefix_name} Used For",
            icon="mdi:database-marker",
            unit_of_measurement=None,
        ),
        endpoint="{endpoint}",
        path="data.result[{series_index}].used_for",
        nas_part_category="Disks",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="{prefix_key}_status",
            name="{prefix_name} Status",
            icon="mdi:check-circle-outline",
            unit_of_measurement=None,
        ),
        endpoint="{endpoint}",
        path="data.result[{series_index}].status",
        nas_part_category="Disks",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="{prefix_key}_temperature",
            name="{prefix_name} Temperature",
            icon="mdi:thermometer",
            unit_of_measurement=UnitOfTemperature.CELSIUS,
        ),
        endpoint="{endpoint}",
        path="data.result[{series_index}].temperature",
        nas_part_category="Disks",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="{prefix_key}_power_on_hours",
            name="{prefix_name} Power-On Hours",
            icon="mdi:clock-outline",
            unit_of_measurement=None,
        ),
        endpoint="{endpoint}",
        path="data.result[{series_index}].power_on_hours",
        nas_part_category="Disks",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="{prefix_key}_brand",
            name="{prefix_name} Brand",
            icon="mdi:tag",
            unit_of_measurement=None,
        ),
        endpoint="{endpoint}",
        path="data.result[{series_index}].brand",
        nas_part_category="Disks",
    )
]

NAS_SPECIFIC_STATUS_TEMPLATES_STORAGE_DISK: List[UgreenEntity] = [
    UgreenEntity(
        description=EntityDescription(
            key="{prefix_key}_temperature",
            name="{prefix_name} Temperature",
            icon="mdi:thermometer",
            unit_of_measurement=UnitOfTemperature.CELSIUS,
        ),
        endpoint="{endpoint}",
        path="data.disk.series[{series_index}].temperature",
        decimal_places=1,
        nas_part_category="Status",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="{prefix_key}_read_rate_raw",
            name="{prefix_name} Read Rate (raw)",
            icon="mdi:download",
            unit_of_measurement=UnitOfDataRate.BYTES_PER_SECOND,
        ),
        endpoint="{endpoint}",
        path="data.disk.series[{series_index}].read_rate",
        decimal_places=0,
        nas_part_category="Status",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="{prefix_key}_read_rate",
            name="{prefix_name} Read Rate",
            icon="mdi:download",
            unit_of_measurement=None,
        ),
        endpoint="{endpoint}",
        path="calculated:scale_bytes_per_second:data.disk.series[{series_index}].read_rate",
        decimal_places=0,
        nas_part_category="Status",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="{prefix_key}_write_rate_raw",
            name="{prefix_name} Write Rate (raw)",
            icon="mdi:upload",
            unit_of_measurement=UnitOfDataRate.BYTES_PER_SECOND,
        ),
        endpoint="{endpoint}",
        path="data.disk.series[{series_index}].write_rate",
        decimal_places=0,
        nas_part_category="Status",
    ),
    UgreenEntity(
        description=EntityDescription(
            key="{prefix_key}_write_rate",
            name="{prefix_name} Write Rate",
            icon="mdi:upload",
            unit_of_measurement=None,
        ),
        endpoint="{endpoint}",
        path="calculated:scale_bytes_per_second:data.disk.series[{series_index}].write_rate",
        decimal_places=0,
        nas_part_category="Status",
    ),
]
