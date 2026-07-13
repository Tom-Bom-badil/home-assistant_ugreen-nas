import logging, re
from typing import Any, Optional, Union, Iterable, List, Awaitable, Callable, Mapping
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from homeassistant.helpers.entity import EntityDescription

from .entities import UgreenEntity


_LOGGER = logging.getLogger(__name__)


def format_dynamic_size(
    raw: Any,
    input_unit: str = 'B',
    decimal_places: int = 2
) -> Optional[Decimal]:
    """Format bytes into a human-readable format with configurable decimal places."""
    try:
        if raw is None or input_unit not in ("B", "kB", "MB", "GB", "TB", "PB"):
            return None
        
        size = Decimal(str(raw).replace(",", "."))
        exponent_map = {'B': 0, 'kB': 1, 'MB': 2, 'GB': 3, 'TB': 4, 'PB': 5}
        exponent = exponent_map[input_unit]

        size_bytes = size * (Decimal(1024) ** exponent)
        
        for _ in ['B', 'kB', 'MB', 'GB', 'TB', 'PB']:
            if size_bytes < 1024:
                quantize_str = f'1.{"0" * decimal_places}'
                return size_bytes.quantize(Decimal(quantize_str), rounding=ROUND_HALF_UP)
            size_bytes /= Decimal(1024)

        quantize_str = f'1.{"0" * decimal_places}'
        return size_bytes.quantize(Decimal(quantize_str), rounding=ROUND_HALF_UP)

    except Exception:
        return None

def determine_unit(
    raw: Any,
    input_unit: str = 'B',
    per_second: bool = False
) -> Optional[str]:
    """Determine the appropriate unit for a given size in bytes."""
        
    units = ['B', 'kB', 'MB', 'GB', 'TB', 'PB']
    
    if per_second:
        input_unit = input_unit.replace("/s", "") if input_unit.endswith("/s") else input_unit

    if input_unit not in units:
        return None

    unit_index = units.index(input_unit)

    try:
        size = Decimal(raw) if isinstance(raw, (int, float, Decimal)) else Decimal(str(raw).replace(",", "."))
    except Exception:
        size = Decimal(0)

    while unit_index < len(units) - 1 and size >= 1024:
        size /= Decimal(1024)
        unit_index += 1

    unit_str = f"{units[unit_index]}/s" if per_second else units[unit_index]
    return unit_str

def format_duration(seconds: float) -> str:
    """Format seconds into a human-readable duration."""
    try:
        seconds = float(seconds)
        if seconds < 60:
            return f"{int(seconds)} s"
        elif seconds < 3600:
            return f"{seconds / 60:.1f} min"
        elif seconds < 86400:
            return f"{seconds / 3600:.1f} h"
        else:
            return f"{seconds / 86400:.1f} d"
    except Exception:
        return str(seconds)

def format_temperature(raw: Any) -> Union[int, Decimal]:
    """Format a raw temperature value to a Decimal representation."""
    if raw is None:
        return Decimal(0)
    try:
        return int(round(float(raw)))
    except Exception:
        return Decimal(0)

def format_percentage(raw: Any) -> Decimal:
    """Format a raw percentage value to a Decimal representation."""
    if raw is None:
        return Decimal(0)
    try:
        return Decimal(str(round(float(raw), 1)))
    except Exception:
        return Decimal(0)
    
def format_timestamp(raw: Any) -> str:
    """Format a raw timestamp value to a human-readable string."""
    if raw is None:
        return "N/A"
    try:
        dt = datetime.fromtimestamp(float(raw))
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return "Invalid timestamp"

def format_unix_timestamp(raw: Any) -> datetime | None:
    """Return a timezone-aware UTC datetime for a positive Unix timestamp."""
    try:
        timestamp = float(raw)
        return datetime.fromtimestamp(timestamp, tz=timezone.utc) if timestamp > 0 else None
    except (TypeError, ValueError, OSError, OverflowError):
        return None

def format_status_code(raw: Any, status_map: dict[int, str]) -> str:
    """Format a raw status code to a human-readable string."""
    try:
        return status_map.get(int(raw), f"Unknown status: {raw}")
    except (ValueError, TypeError):
        return f"Invalid value: {raw}"
    
def format_frequency_mhz(raw: Any) -> Any:
    """Convert a string like '4800 MHz' or '4800MHz' to an integer."""
    if isinstance(raw, str) and "MHz" in raw:
        cleaned = raw.replace("MHz", "").strip()
        if cleaned.isdigit():
            return int(cleaned)
    return raw

def convert_string_to_number(value: Union[str, int, float, Decimal], decimal_places: int) -> Union[int, float, Decimal, str]:
    """Convert a string to a number (int, float, or Decimal) if possible."""
    if isinstance(value, str):
        value = value.strip().replace(",", ".")
        if not value:
            return value 
        try:
            if '.' in value:
                return round(float(value), decimal_places)
            else:
                return int(value)
        except ValueError:
            try:
                return round(Decimal(value), decimal_places)
            except Exception:
                return str(value) 
    return value

def format_sensor_value(raw: Any, endpoint: UgreenEntity) -> Any:
    """Format a raw value based on the endpoint definition."""
    try:

        if endpoint.description.key.endswith(("_smart_last_test", "_smart_next_test")):
            return format_unix_timestamp(raw)

        if isinstance(endpoint.description.name, str) and "Timestamp" in endpoint.description.name:
            return format_timestamp(raw)

        if endpoint.description.unit_of_measurement is not None and endpoint.description.unit_of_measurement in ("B", "kB", "MB", "GB", "TB"):
            if endpoint.description.key.endswith("_raw"):
                return raw
            else:
                return format_dynamic_size(raw, endpoint.description.unit_of_measurement, endpoint.decimal_places)

        if endpoint.description.key == "power_mode":
            return format_status_code(raw, {
                0: "High Performance",
                1: "Balanced",
                2: "Energy Saving",
            })

        if "server_status" in endpoint.description.key:
            return format_status_code(raw, {
                2: "Normal",
            })

        if "USB_device_type" in endpoint.description.key:
            return format_status_code(raw, {
                0: "Generic USB Device",   # 0 = External HDD?
            })

        if endpoint.description.key in {"fan_mode", "fans_system_mode"}:
            return format_status_code(raw, {
                1: "quiet",
                2: "default",
                3: "full power",
            })

        if "fan" in endpoint.description.key and "overall" in endpoint.description.key:
            return format_status_code(raw, {
                0: "Normal",
            })

        if "fan" in endpoint.description.key and "status" in endpoint.description.key:
            return format_status_code(raw, {
                0: "Off",
                1: "On",
            })

        if endpoint.description.key.endswith("_smart_last_result"):
            return format_status_code(raw, {
                0: "Unsupported",
                1: "Normal",
                2: "Warning",
                3: "Critical",
                4: "Not tested",
                5: "Test failed",
                6: "Test interrupted",
                7: "Corrupted",
            })

        if "disk" in endpoint.description.key and "status" in endpoint.description.key:
            return format_status_code(raw, {
                0: "Undetectable",
                1: "Normal",
                2: "Warning",
                3: "Critical",
                4: "Failure",
                5: "Locked",
            })

        if "disk" in endpoint.description.key and not "interface" in endpoint.description.key and "type" in endpoint.description.key:
        # Web GUI .js states: "0":"Intern HDD","1":"Intern SSD","2":"M2-Festplatte","3":"Extern HDD","4":"Extern SSD","5":"Extern USB","6":"Unbekannt"
            return format_status_code(raw, {
                0: "HDD",
                1: "SSD",
                2: "M.2",
                3: "HDD (ext)",
                4: "SSD (ext)",
                5: "USB",
                6: "???",
            })

        if "volume" in endpoint.description.key and "health" in endpoint.description.key:
            return format_status_code(raw, {
                0: "Normal",
            })

        if "volume" in endpoint.description.key and "status" in endpoint.description.key:
        # Web GUI .js states: "0":"Normal","1":"Warnung","2":"Gefährlich","3":"Schwerwiegend"
            return format_status_code(raw, {
                0: "Normal",
                1: "Warning",
                2: "Danger",
                3: "Faulty",
            })

        if "pool" in endpoint.description.key and "status" in endpoint.description.key:
        # Web GUI .js states: "0":"Normal","1":"Warnung","2":"Gefährlich","3":"Schwerwiegend"
            return format_status_code(raw, {
                0: "Normal",
                1: "Rebuilding",
                2: "Degraded",
                3: "Faulty",
            })

        if endpoint.description.unit_of_measurement is not None and endpoint.description.unit_of_measurement == "%":
            return format_percentage(raw)

        if endpoint.description.unit_of_measurement is not None and endpoint.description.unit_of_measurement == "°C":
            return format_temperature(raw)

        if endpoint.description.unit_of_measurement is not None and endpoint.description.unit_of_measurement in ("kB/s", "MB/s", "GB/s"):
            return format_dynamic_size(raw, endpoint.description.unit_of_measurement, endpoint.decimal_places)

        if endpoint.description.unit_of_measurement is not None and endpoint.description.unit_of_measurement == "MHz":
            return format_frequency_mhz(raw)
        
        return convert_string_to_number(raw, endpoint.decimal_places)

    except Exception:
        return Decimal(0)


def scale_bytes_per_second(raw: Any) -> Optional[str]:
    """Convert raw Bps value to a human-readable string like 316.45 MB/s."""
    # Normally, transfer speeds are specified in bps (bits per second), e.g. 10Gbps.
    # The UGOS API and Web interface are actually reporting in *Bytes* per second (GBps).
    try:
        if raw is None:
            return None
        bytes_per_second = Decimal(str(raw).replace(",", "."))
        units = ["B/s", "kB/s", "MB/s", "GB/s", "TB/s"]
        unit_index = 0
        while bytes_per_second >= 1024 and unit_index < len(units) - 1:
            bytes_per_second /= 1024
            unit_index += 1
        value = int(bytes_per_second.to_integral_value(rounding=ROUND_HALF_UP))
        return f"{value} {units[unit_index]}"
    except Exception:
        return None


def megabits_to_gigabits(raw: Any) -> Decimal | str | None:
    """Convert link speed from Mbit/s to Gbit/s; hide disconnected ports."""
    try:
        speed = Decimal(str(raw).replace(",", "."))
        return "" if speed == 0 else speed / Decimal(1000)
    except (ArithmeticError, TypeError, ValueError):
        return None


def extract_value_from_path(data: dict[str, Any], path: str) -> Any:
    """Extract a value from nested dictionary/list structure using dot and index notation."""
    try:
        parts = path.split(".")
        value: Any = data
        for part in parts:
            if "[" in part and "]" in part:
                part_name, index = part[:-1].split("[")
                value = value.get(part_name, []) if isinstance(value, dict) else []
                value = value[int(index)] if isinstance(value, list) else None
            else:
                value = value.get(part) if isinstance(value, dict) else None
        return value
    except Exception:
        return None


def _last_smart_detection(data: dict[str, Any]) -> dict[str, Any]:
    """Return the latest SMART detection entry selected by the UGOS UI."""
    results = ((data or {}).get("data", {}) or {}).get("result", []) or []
    return next(
        (item for item in results if isinstance(item, dict) and str(item.get("type")) == "0"),
        {},
    )


async def get_entity_data_from_api(
    api: Any,
    session: Any,
    endpoint_to_entities: Mapping[str, Iterable[UgreenEntity]],
) -> dict[str, Any]:
    """Fetch data per endpoint and extract values for the given entities."""
    data: dict[str, Any] = {}

    for endpoint_str, entities in endpoint_to_entities.items():
        try:
            response = await api.get(session, endpoint_str)
        except Exception as err:
            _LOGGER.warning(
                "[UGREEN NAS] Failed to fetch '%s': %s",
                endpoint_str,
                err,
            )
            for entity in entities:
                data[entity.description.key] = None
            continue

        for entity in entities:
            try:
                path = entity.path

                if not path.startswith("calculated:"):
                    value = extract_value_from_path(response, path)
                elif path.startswith("calculated:ram_total_size"):
                    value = sum(
                        value
                        for key, value in data.items()
                        if key.startswith("RAM") and key.endswith("_size")
                    )
                elif path.startswith("calculated:scale_bytes_per_second:"):
                    value = scale_bytes_per_second(
                        extract_value_from_path(response, path.split(":", 2)[2])
                    )
                elif path.startswith("calculated:megabits_to_gigabits:"):
                    value = megabits_to_gigabits(
                        extract_value_from_path(response, path.split(":", 2)[2])
                    )
                elif path.startswith("calculated:empty_if_missing:"):
                    value = extract_value_from_path(
                        response,
                        path.split(":", 2)[2],
                    )
                    value = "" if value is None else value
                elif path.startswith("calculated:last_smart_detection:"):
                    value = _last_smart_detection(response).get(path.rsplit(":", 1)[1])
                else:
                    value = None # fallback for unknown 'calculated' identifiers

                data[entity.description.key] = value
            except Exception as err:
                _LOGGER.warning(
                    "[UGREEN NAS] Failed to extract '%s': %s",
                    entity.description.key,
                    err,
                )
                data[entity.description.key] = None

    return data

def apply_templates(templates: Iterable[UgreenEntity], **fmt: Any) -> List[UgreenEntity]:
    """Create UgreenEntity objects by filling placeholders in templates.
    Supported placeholders: {prefix_key}, {prefix_name}, {i}, {endpoint}, {category}, {series_index}
    Also supported: Simple arithmetics with +/-: {series_index}-1, {series_index}+1"""
    entities: List[UgreenEntity] = []
    for t in templates:
        desc = EntityDescription(
            key=t.description.key.format(**fmt),
            name=t.description.name.format(**fmt) if isinstance(t.description.name, str) else t.description.name,
            icon=t.description.icon,
            unit_of_measurement=t.description.unit_of_measurement,
        )
        filled_endpoint = t.endpoint.format(**fmt)
        filled_path = t.path.format(**fmt)
        filled_path = _simplify_index_expr(filled_path)
        entities.append(UgreenEntity(
            description=desc,
            endpoint=filled_endpoint,
            path=filled_path,
            request_method=t.request_method,
            payload=t.payload,
            decimal_places=t.decimal_places,
            nas_part_category=(t.nas_part_category or "").format(**fmt),
        ))
    return entities


async def make_entities(
    fetch: Optional[Callable[[str], Awaitable[dict[str, Any]]]],
    *,
    templates: Iterable[UgreenEntity],
    endpoint: str,
    prefix_key_base: str,
    prefix_name_base: str,
    category: str,
    list_path: Optional[str] = None,
    count: Optional[int] = None,
    index_start: int = 1,
    single_compact: bool = True,
) -> List[UgreenEntity]:
    """Build dynamic entities either from an API list or a given count."""
    if list_path:
        if fetch is None:
            return []
        data = await fetch(endpoint)
        items = extract_value_from_path(data or {}, list_path) or []
        n = len(items)
    else:
        n = max(0, int(count or 0))

    if n == 0:
        return []

    single = (n == 1) and single_compact
    entities: List[UgreenEntity] = []

    for i in range(n):
        idx_num = i + index_start
        idx_txt = "" if single else f"{idx_num}"
        prefix_key  = f"{prefix_key_base}{idx_txt}"
        prefix_name = f"{prefix_name_base}{'' if single else f' {idx_num}'}"

        entities.extend(apply_templates(
            templates,
            i=i,
            series_index=idx_num,
            prefix_key=prefix_key,
            prefix_name=prefix_name,
            endpoint=endpoint,
            category=category,
        ))
    return entities


_INDEX_EXPR_RE = re.compile(r"\[(\d+)\s*([+-])\s*(\d+)\]")
def _simplify_index_expr(s: str) -> str:
    """Resolve simple integer +/- expressions *inside brackets* of a JSONPath-like string.
    Example: 'disk[{series_index}-1]' -> starts with 'disk[0]' if '{series_index}' starts with 1.
    This is needed for a very few endpoints only. +/- with integers are supported."""
    if not s:
        return s
    def repl(m: re.Match) -> str:
        a = int(m.group(1))
        op = m.group(2)
        b = int(m.group(3))
        val = a + b if op == "+" else a - b
        val = max(val, 0) # prevent '-1' (Python would interpret this as 'last element')
        return f"[{val}]"
    return _INDEX_EXPR_RE.sub(repl, s)


# Compile only once for strip_parent_prefix
_PREFIX_VENDOR_RX = re.compile(r"^UGREEN\s+NAS\s*", re.IGNORECASE)
_PREFIX_PARENT_RX = re.compile(r"^.*?\([^)]*\)\s*")
def strip_parent_prefix(s: str | None) -> str:
    """Remove 'UGREEN NAS ' and a leading '(...) ' group from labels."""
    txt = (s or "")
    txt = _PREFIX_VENDOR_RX.sub("", txt)
    txt = _PREFIX_PARENT_RX.sub("", txt)
    return txt.strip()
