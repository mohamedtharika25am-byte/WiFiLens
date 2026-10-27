"""
WiFiLens — Automated Verification Test Suite
Tests all layers: scanner, database, performance, ARP discovery,
channel analysis, diagnostics, scheduler, and FastAPI endpoints.
"""

import os
import sys
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import (
    init_db,
    insert_measurement,
    get_measurements,
    get_floorplan_measurements,
    get_active_floorplan,
    get_all_floorplans,
    insert_ap_marker,
    get_ap_markers,
    get_setting,
    set_setting
)
from backend.wifi_scanner import (
    channel_to_frequency,
    signal_percent_to_dbm,
    radio_type_to_standard,
    scan_current_interface_windows,
    scan_all_networks_windows
)
from backend.network_scanner import get_mac_vendor, get_connected_devices
from backend.channel_analyzer import analyze_channels
from backend.diagnostics import evaluate_signal, evaluate_latency, calculate_health_and_diagnostics
from backend.app import app


client = TestClient(app)


def test_wifi_scanner_helpers():
    """Verify frequency and dBm formulas."""
    assert channel_to_frequency(1, "2.4 GHz") == 2412.0
    assert channel_to_frequency(6, "2.4 GHz") == 2437.0
    assert channel_to_frequency(11, "2.4 GHz") == 2462.0
    assert channel_to_frequency(36, "5 GHz") == 5180.0
    assert channel_to_frequency(149, "5 GHz") == 5745.0

    assert signal_percent_to_dbm(100) == -50.0
    assert signal_percent_to_dbm(50) == -75.0
    assert signal_percent_to_dbm(0) == -100.0

    assert "Wi-Fi 6" in radio_type_to_standard("802.11ax")
    assert "Wi-Fi 5" in radio_type_to_standard("802.11ac")


def test_native_wifi_scan():
    """Verify real Windows interface scanning returns non-empty structure."""
    res = scan_current_interface_windows()
    assert isinstance(res, dict)
    assert "status" in res
    assert "connected" in res
    if res["connected"]:
        assert res["ssid"] != ""
        assert res["channel"] > 0
        assert res["rssi"] <= 0


def test_database_crud():
    """Verify SQLite persistence and schema."""
    init_db()
    
    # Insert measurement
    m_id = insert_measurement({
        "session_id": "test_session",
        "ssid": "Test-Network",
        "rssi": -45.0,
        "channel": 6,
        "floorplan_id": "test_fp",
        "x": 120.0,
        "y": 240.0
    })
    assert m_id > 0

    measurements = get_measurements(limit=5, session_id="test_session")
    assert len(measurements) > 0
    assert measurements[0]["ssid"] == "Test-Network"

    # Settings
    set_setting("test_key", "test_val")
    assert get_setting("test_key") == "test_val"


def test_network_devices_discovery():
    """Verify ARP parsing and MAC vendor lookup."""
    vendor = get_mac_vendor("7c:5a:1c:d2:b7:2a")
    assert "Cisco" in vendor or "Meraki" in vendor

    data = get_connected_devices()
    assert isinstance(data, dict)
    assert "devices" in data
    assert "traffic_note" in data
    assert "Traffic statistics unavailable" in data["traffic_note"]


def test_channel_analyzer():
    """Verify channel spectrum computation and congestion scoring."""
    sample_aps = [
        {"ssid": "NetA", "bssid": "aa:bb:cc:dd:ee:01", "channel": 6, "band": "2.4 GHz", "rssi": -60},
        {"ssid": "NetB", "bssid": "aa:bb:cc:dd:ee:02", "channel": 6, "band": "2.4 GHz", "rssi": -70},
        {"ssid": "NetC", "bssid": "aa:bb:cc:dd:ee:03", "channel": 149, "band": "5 GHz", "rssi": -55}
    ]
    cur_ap = {"channel": 149, "band": "5 GHz"}
    res = analyze_channels(sample_aps, cur_ap)

    assert res["current_channel"] == 149
    assert res["recommended_24ghz"] in [1, 11]  # Channel 6 has congestion from 2 APs
    assert len(res["channels_24"]) == 13


def test_diagnostics_and_health_scoring():
    """Verify composite health scoring and rule-based insights."""
    wifi = {"connected": True, "rssi": -50.0, "ssid": "TestNet", "channel": 36, "band": "5 GHz"}
    perf = {"wifi_hop_latency_ms": 10.0, "internet_latency_ms": 30.0, "packet_loss_pct": 0.0, "download_mbps": 80.0}
    chan = {"current_channel_congestion": 20}

    diag = calculate_health_and_diagnostics(wifi, perf, chan)
    assert diag["health_score"] >= 90
    assert diag["overall_status"] == "Excellent"
    assert "breakdown" in diag
    assert "insights" in diag


def test_fastapi_endpoints():
    """Verify REST API responses."""
    # Desktop HTML
    r_index = client.get("/")
    assert r_index.status_code == 200
    assert "WiFiLens" in r_index.text

    # Mobile HTML
    r_mobile = client.get("/mobile")
    assert r_mobile.status_code == 200
    assert "WiFiLens" in r_mobile.text

    # Status API
    r_status = client.get("/api/wifi/status")
    assert r_status.status_code == 200
    assert "status" in r_status.json()

    # Performance API
    r_perf = client.get("/api/performance")
    assert r_perf.status_code == 200
    assert "wifi_hop_latency_ms" in r_perf.json()

    # Devices API
    r_dev = client.get("/api/devices")
    assert r_dev.status_code == 200
    assert "devices" in r_dev.json()

    # Host Info & QR
    r_host = client.get("/api/network/host-info")
    assert r_host.status_code == 200
    assert "qr_code_b64" in r_host.json()


if __name__ == "__main__":
    pytest.main(["-v", __file__])
