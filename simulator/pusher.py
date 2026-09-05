"""
Prometheus Remote Write Pusher.

Sends synthetic telemetry metrics to Grafana Cloud via Prometheus Remote Write.
Uses the prometheus_client library for metric serialization and requests for HTTP.

Each metric is pushed with labels that allow Grafana to filter and visualize:
  - production="nightfall"
  - environment="stage-7"
  - device=<specific device>
  - scene="42" (for scene-specific metrics)
"""
import base64
import struct
import time
from typing import Any

import requests
import snappy
import structlog

from config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()


# Infrastructure devices and their categories
DEVICE_ASSIGNMENTS: dict[str, dict[str, list[str]]] = {
    "storage": ["INGEST-01", "INGEST-02", "NAS-01", "MEDIA-STORE-01"],
    "network": ["NET-CORE-01", "NET-EDGE-07"],
    "cameras": ["CAM-01", "CAM-02", "CAM-03", "CAM-04"],
    "editing": ["EDIT-01", "EDIT-02"],
}

# Which metrics belong to which device category
METRIC_DEVICE_MAP: dict[str, str] = {
    "storage_utilization": "storage",
    "disk_read_latency_ms": "storage",
    "disk_write_latency_ms": "storage",
    "disk_iops": "storage",
    "disk_errors": "storage",
    "ingest_throughput_gbps": "storage",
    "ingest_latency_ms": "storage",
    "upload_queue_depth": "storage",
    "failed_uploads_per_min": "storage",
    "frames_dropped_per_min": "cameras",
    "upload_retry_rate_pct": "storage",
    "network_latency_ms": "network",
    "packet_loss_pct": "network",
    "bandwidth_gbps": "network",
    "connections": "network",
    "camera_temperature_c": "cameras",
    "camera_errors_per_min": "cameras",
    "camera_bitrate_mbps": "cameras",
    "gpu_usage_pct": "editing",
    "cpu_usage_pct": "editing",
    "render_queue_depth": "editing",
    "render_latency_min": "editing",
    "checksum_errors_per_min": "storage",
    "media_validation_failures": "storage",
}

# Primary device for each metric category (for single-device metrics)
PRIMARY_DEVICE_MAP: dict[str, str] = {
    "storage": "INGEST-01",
    "network": "NET-EDGE-07",
    "cameras": "CAM-03",
    "editing": "EDIT-01",
}


def _build_write_request(time_series_list: list[dict]) -> bytes:
    """
    Build a Prometheus Remote Write request using protobuf + snappy.

    This is a simplified implementation that builds the protobuf manually
    to avoid heavy protobuf dependencies.
    """
    # We'll use the prometheus_client remote_write format
    # For simplicity, build a raw protobuf WriteRequest
    # Format: repeated TimeSeries timeseries = 1
    # TimeSeries: repeated Label labels = 1, repeated Sample samples = 2
    # Label: string name = 1, string value = 2
    # Sample: double value = 1, int64 timestamp = 2

    def encode_varint(value: int) -> bytes:
        bits = value & 0x7F
        result = b""
        value >>= 7
        while value:
            result += bytes([0x80 | bits])
            bits = value & 0x7F
            value >>= 7
        result += bytes([bits])
        return result

    def encode_string(s: str) -> bytes:
        encoded = s.encode("utf-8")
        return encode_varint(len(encoded)) + encoded

    def encode_field(field_num: int, wire_type: int, data: bytes) -> bytes:
        tag = (field_num << 3) | wire_type
        return encode_varint(tag) + data

    def encode_label(name: str, value: str) -> bytes:
        label_data = (
            encode_field(1, 2, encode_string(name)) +
            encode_field(2, 2, encode_string(value))
        )
        return encode_field(1, 2, encode_varint(len(label_data)) + label_data)

    # Wait — this is getting complex. Use a simpler approach:
    # Use prometheus_client to write to a local gauge, then serialize.
    # Actually the cleanest approach for Python is to use the remote_write
    # module from prometheus_client or build minimal protobuf.

    # Let's use a simple HTTP approach instead with the Prometheus text format
    # pushed via the Grafana Cloud /api/prom/push endpoint
    raise NotImplementedError("Use _push_influx_line_protocol instead")


def push_metrics_to_grafana(metrics: dict[str, float]) -> bool:
    """
    Push metrics to Grafana Cloud via Prometheus Remote Write.

    Returns True on success, False on failure.
    """
    remote_write_url = settings.grafana_prometheus_remote_write_url
    user_id = settings.grafana_prometheus_user_id
    api_key = settings.grafana_prometheus_api_key

    if not all([remote_write_url, user_id, api_key]):
        logger.debug(
            "grafana_pusher.skipped",
            reason="Prometheus remote write not configured",
        )
        return False

    try:
        timestamp_ms = int(time.time() * 1000)
        samples = _build_prometheus_samples(metrics, timestamp_ms)

        response = requests.post(
            url=remote_write_url,
            content_type="application/x-protobuf",
            headers={
                "Content-Encoding": "snappy",
                "X-Prometheus-Remote-Write-Version": "0.1.0",
            },
            data=samples,
            auth=(user_id, api_key),
            timeout=10,
        )

        if response.status_code in (200, 204):
            logger.debug("grafana_pusher.success", metric_count=len(metrics))
            return True
        else:
            logger.warning(
                "grafana_pusher.http_error",
                status_code=response.status_code,
                response=response.text[:200],
            )
            return False

    except Exception as e:
        logger.error("grafana_pusher.error", error=str(e))
        return False


def _build_prometheus_samples(
    metrics: dict[str, float], timestamp_ms: int
) -> bytes:
    """Build protobuf-encoded Prometheus Remote Write samples."""
    # Build using prometheus_remote_write_format
    # We'll use the prometheus_pb2 from the prometheus_client package
    try:
        from prometheus_client.exposition import _build_remote_write_proto  # type: ignore
    except ImportError:
        pass

    # Manual protobuf construction for Prometheus RemoteWrite
    # This is the minimal implementation
    write_request = _build_write_request_proto(metrics, timestamp_ms)
    return snappy.compress(write_request)


def _build_write_request_proto(
    metrics: dict[str, float], timestamp_ms: int
) -> bytes:
    """Build a minimal Prometheus Remote Write protobuf message."""
    # We'll build this without dependencies using pure struct/bytes
    # Protobuf wire format:
    #   field 1, wire type 2 (length-delimited) = TimeSeries
    #     field 1, wire type 2 = Label
    #       field 1, wire type 2 = name string
    #       field 2, wire type 2 = value string
    #     field 2, wire type 2 = Sample
    #       field 1, wire type 1 (64-bit) = value (double)
    #       field 2, wire type 0 (varint) = timestamp_ms

    def write_varint(value: int) -> bytes:
        result = b""
        while True:
            bits = value & 0x7F
            value >>= 7
            if value:
                result += bytes([bits | 0x80])
            else:
                result += bytes([bits])
                break
        return result

    def write_length_delimited(field_num: int, data: bytes) -> bytes:
        tag = write_varint((field_num << 3) | 2)
        return tag + write_varint(len(data)) + data

    def write_string_field(field_num: int, value: str) -> bytes:
        encoded = value.encode("utf-8")
        return write_length_delimited(field_num, encoded)

    def write_label(name: str, value: str) -> bytes:
        label = write_string_field(1, name) + write_string_field(2, value)
        return write_length_delimited(1, label)

    def write_sample(value: float, timestamp_ms: int) -> bytes:
        value_bytes = struct.pack("<d", value)
        timestamp_bytes = write_varint(timestamp_ms)
        sample = (
            write_varint((1 << 3) | 1) + value_bytes +
            write_varint((2 << 3) | 0) + timestamp_bytes
        )
        return write_length_delimited(2, sample)

    def write_timeseries(labels: list[tuple[str, str]], value: float) -> bytes:
        ts_data = b""
        for name, val in sorted(labels, key=lambda x: x[0]):
            ts_data += write_label(name, val)
        ts_data += write_sample(value, timestamp_ms)
        return write_length_delimited(1, ts_data)

    write_request = b""
    production = settings.production_name
    environment = settings.production_environment

    for metric_name, value in metrics.items():
        device_category = METRIC_DEVICE_MAP.get(metric_name, "storage")
        device = PRIMARY_DEVICE_MAP.get(device_category, "INGEST-01")

        labels = [
            ("__name__", f"production_guardian_{metric_name}"),
            ("production", production),
            ("environment", environment),
            ("device", device),
            ("scene", "42"),
            ("service", "media-ingest"),
            ("system", device_category),
        ]

        write_request += write_timeseries(labels, float(value))

    return write_request


class TelemetryPusher:
    """
    Manages periodic telemetry push to Grafana Cloud.

    Can be run as a background task or called directly.
    """

    def __init__(self) -> None:
        self._push_count = 0
        self._error_count = 0

    def push(self, metrics: dict[str, float]) -> bool:
        """Push metrics and update counters."""
        success = push_metrics_to_grafana(metrics)
        if success:
            self._push_count += 1
        else:
            self._error_count += 1
        return success

    @property
    def push_count(self) -> int:
        return self._push_count

    @property
    def error_count(self) -> int:
        return self._error_count
