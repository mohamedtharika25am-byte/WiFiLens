"""
WiFiLens - Background Periodic Monitoring Scheduler
Implements automatic Wi-Fi telemetry sampling (default: 10-minute interval).
Records measurements to the database without saturating network bandwidth.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional, Callable

from backend.database import (
    insert_measurement,
    get_setting,
    set_setting,
    get_active_floorplan
)
from backend.wifi_scanner import scan_current_interface_windows
from backend.speed_test import measure_gateway_ping, measure_internet_latency, measure_download_speed, measure_upload_speed
from backend.channel_analyzer import analyze_channels
from backend.diagnostics import calculate_health_and_diagnostics

logger = logging.getLogger("wifilens.scheduler")


class MonitoringScheduler:
    def __init__(self, broadcast_fn: Optional[Callable] = None):
        self.broadcast_fn = broadcast_fn
        self.is_running = False
        self._task: Optional[asyncio.Task] = None

    def get_interval(self) -> int:
        """Reads interval in seconds from persistent settings (default: 600s = 10m)."""
        val = get_setting("monitor_interval_seconds", "600")
        try:
            return max(30, int(val))
        except ValueError:
            return 600

    def is_enabled(self) -> bool:
        return get_setting("monitor_enabled", "1") == "1"

    def speedtest_on_interval(self) -> bool:
        return get_setting("speedtest_on_interval", "0") == "1"

    async def execute_sample(self, trigger: str = "scheduled") -> dict:
        """Collects live measurement and writes to database."""
        # 1. Scan Wi-Fi Interface
        wifi_info = scan_current_interface_windows()
        
        # 2. Measure Hop Latency & Internet Latency
        gw_res = measure_gateway_ping()
        inet_res = measure_internet_latency()
        
        dl_speed = 0.0
        ul_speed = 0.0

        # Run speedtest only if enabled for interval or triggered manually
        if self.speedtest_on_interval() or trigger == "manual":
            dl_res = measure_download_speed(duration_target=2.0)
            ul_res = measure_upload_speed(payload_bytes=2_000_000)
            dl_speed = dl_res.get("download_mbps", 0.0)
            ul_speed = ul_res.get("upload_mbps", 0.0)

        # 3. Channel Analysis
        chan_data = analyze_channels([], wifi_info)

        # 4. Diagnostics & Health Score
        perf_data = {
            "wifi_hop_latency_ms": gw_res.get("latency_ms", 0.0),
            "internet_latency_ms": inet_res.get("internet_latency_ms", 0.0),
            "packet_loss_pct": gw_res.get("packet_loss_pct", 0.0),
            "download_mbps": dl_speed,
            "upload_mbps": ul_speed
        }
        health_data = calculate_health_and_diagnostics(wifi_info, perf_data, chan_data)

        # 5. Active Floor Plan
        active_fp = get_active_floorplan()
        floorplan_id = active_fp["id"] if active_fp else None

        # 6. Store in Database
        sample_record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": "auto_monitor",
            "source": f"scheduler ({trigger})",
            "ssid": wifi_info.get("ssid"),
            "bssid": wifi_info.get("bssid"),
            "rssi": wifi_info.get("rssi"),
            "signal_quality": wifi_info.get("signal_quality"),
            "channel": wifi_info.get("channel"),
            "frequency": wifi_info.get("frequency"),
            "band": wifi_info.get("band"),
            "radio_type": wifi_info.get("wifi_standard") or wifi_info.get("radio_type"),
            "download_speed": dl_speed,
            "upload_speed": ul_speed,
            "ping_latency": gw_res.get("latency_ms") or inet_res.get("internet_latency_ms"),
            "packet_loss": gw_res.get("packet_loss_pct"),
            "health_score": health_data.get("health_score"),
            "floorplan_id": floorplan_id,
            "notes": f"Auto sample ({trigger})"
        }

        row_id = insert_measurement(sample_record)
        sample_record["id"] = row_id

        # 7. Broadcast over WebSocket if active
        if self.broadcast_fn:
            try:
                await self.broadcast_fn({
                    "type": "new_measurement",
                    "data": sample_record
                })
            except Exception as e:
                logger.error(f"Broadcast error: {e}")

        return sample_record

    async def _loop(self):
        logger.info("WiFiLens 10-Minute Monitoring Scheduler started.")
        while self.is_running:
            try:
                interval = self.get_interval()
                if self.is_enabled():
                    await self.execute_sample(trigger="scheduled")
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Scheduler loop error: {e}")
                await asyncio.sleep(60)

    def start(self):
        if not self.is_running:
            self.is_running = True
            self._task = asyncio.create_task(self._loop())

    def stop(self):
        self.is_running = False
        if self._task and not self._task.done():
            self._task.cancel()
