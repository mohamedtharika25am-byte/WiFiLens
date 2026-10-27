# WiFiLens — See. Measure. Map. Optimize.

[![Python Version](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-7%20passed-brightgreen.svg)](tests/)

**WiFiLens** is a local-first Wi-Fi monitoring, heatmap visualization, and network diagnostics system. It turns your laptop into a primary diagnostic mission-control dashboard and pairs with your smartphone as a mobile surveying and AR camera HUD device.

---

## Key Capabilities & Core Features

### 1. Real Wi-Fi Monitoring & Hardware Telemetry
- **Native OS APIs:** Direct hardware integration with Windows `netsh wlan show interfaces` and `netsh wlan show networks mode=bssid`.
- **Metrics Tracked:** Real SSID, BSSID (AP MAC), exact RSSI (dBm), signal quality (%), operational channel, center frequency (MHz), band (2.4 GHz, 5 GHz, 6 GHz), negotiated link rates (Tx/Rx Mbps), and Wi-Fi standard (Wi-Fi 6 / 802.11ax, Wi-Fi 5 / 802.11ac, etc.).
- **Strict Real Data Rule:** Never fabricates fake RF measurements or mock signals.

### 2. Internet Performance Engine (Signal vs. Speed Distinction)
- **Wi-Fi Hop Latency:** Measures direct ICMP round-trip time (e.g. ~7-10 ms) and packet loss (0%) to the local default gateway router. Reflects physical wireless RF link health.
- **Internet WAN Latency:** Measures round-trip time across global CDNs.
- **Throughput Engine:** Real HTTP chunk streaming for true download (e.g. 100+ Mbps) and upload (e.g. 12+ Mbps) performance.
- **Clear Distinction:** Physically decouples local RF attenuation (dBm) from ISP backhaul bandwidth (Mbps).

### 3. Interactive Floor Plan Heatmap Studio
- **Inverse Distance Weighting (IDW):** Mathematical spatial RF propagation engine with smooth color gradients (Turbo thermal palette).
- **Multi-Metric Layers:** Heatmap modes for **Signal (dBm)**, **Download Speed (Mbps)**, **Hop Latency (ms)**, **Packet Loss (%)**, and **Health Score (0-100)**.
- **Real-World Scale Calibration:** Click two points on the blueprint and set real-world meters to calibrate pixel-to-meter ratio.
- **Access Point Markers:** Place and manage router/AP markers with visual antenna radiation waves.
- **Weak-Zone Detection:** Automatically detects and highlights rooms/zones where RSSI drops below -75 dBm with glowing warning outlines.
- **Export:** Instant high-resolution PNG export of surveyed heatmaps.

### 4. Phone + Laptop Mobile Integration & Camera HUD
- **Instant QR Pairing:** Desktop dashboard renders dynamic QR codes for zero-friction phone pairing on the local Wi-Fi subnet (`/mobile`).
- **Walking Survey Mode:** Touch the blueprint on your phone screen while walking through the facility to log survey coordinates synchronized with live Wi-Fi telemetry.
- **AR Camera Lens Mode:** Fullscreen smartphone camera feed with live HUD telemetry overlay (SSID, -42 dBm Signal, Link Status, Frequency, Targeting Crosshair).
- **Survey Snapshot:** Captures camera photos stamped with real-time Wi-Fi measurement watermarks.
- **Compliance:** Transparently states that overlays represent actual connection measurements, never claiming the camera optical sensor detects radio waves.

### 5. 10-Minute Periodic Background Monitoring
- **Configurable Scheduler:** Automated background telemetry sampling (default: 10 minutes; configurable to 1m, 5m, 10m, 30m, 60m).
- **Bandwidth-Conservative:** Samples RF link and gateway latency continuously while reserving heavy speed tests for manual triggers or scheduled intervals.
- **Persistent SQLite Database:** Stores timestamps, coordinates, SSID, BSSID, RSSI, channel, frequency, band, throughput, and hop latency.

### 6. Channel Spectrum & RF Congestion Analyzer
- **2.4 GHz Spectrum Curves:** Parabolic bell curves spanning 20/22 MHz per AP across channels 1 to 13.
- **5 GHz Spectrum Blocks:** Non-overlapping UNII-1, UNII-2, UNII-3 channel allocation.
- **Optimal Channel Recommendations:** Automated algorithmic recommendations (e.g., Channels 1, 6, 11 on 2.4 GHz; Channel 36/149 on 5 GHz) based on co-channel interference (CCI) and adjacent-channel interference (ACI).

### 7. Connected Subnet Device Discovery
- **ARP Table Parser:** Discovers active devices on the local Wi-Fi subnet.
- **MAC OUI Vendor Resolution:** Identifies hardware manufacturers (Cisco/Meraki, Apple, Intel, MediaTek, Samsung, etc.).
- **Compliant Traffic Note:** Displays `"Traffic statistics unavailable for this network"` when router SNMP/NetFlow is inaccessible, strictly avoiding fabricated device usage.

### 8. Explainable Wi-Fi Health Score & Rule-Based Diagnostics
- **Composite 0-100 Score:** Transparent parameter weights (Signal: 30%, Latency: 25%, Packet Loss: 20%, Speed: 15%, Congestion: 10%).
- **Rule-Based Diagnostic Engine:**
  - Weak RSSI (< -75 dBm) → Distance/attenuation alert with repeater recommendation.
  - High Latency (> 100 ms) → Bufferbloat / queueing delay detection.
  - Strong RSSI + Low Speed → Identifies ISP / WAN backhaul bottleneck.
  - Packet Loss (> 1%) → RF interference alert (Bluetooth, microwave, physical contention).
  - Channel Congestion → Specific channel migration guidance.

---

## System Architecture

```
                          ┌─────────────────────────────┐
                          │   Mobile Phone Scanner      │
                          │   - Floor Plan Touch Survey │
                          │   - Real Camera HUD Overlay │
                          │   - HTML5 GPS Sensors       │
                          └──────────────┬──────────────┘
                                         │ Local Wi-Fi (HTTP / WebSocket)
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          FastAPI Backend Server                             │
│                                                                             │
│  ┌───────────────────────┐  ┌───────────────────────┐  ┌─────────────────┐  │
│  │ Native Wi-Fi Scanner  │  │   Performance Engine  │  │ Network Scanner │  │
│  │ (netsh wlan / BSSID)  │  │ (Ping / Speed Test)   │  │ (ARP Discovery) │  │
│  └───────────┬───────────┘  └───────────┬───────────┘  └────────┬────────┘  │
│              │                          │                       │           │
│              ▼                          ▼                       ▼           │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │             SQLite Persistent Database (wifilens.db)                  │  │
│  │       Measurements • Floorplans • AP Markers • 10-Min History         │  │
│  └──────────────────────────────────┬────────────────────────────────────┘  │
│                                     │                                       │
│                                     ▼                                       │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │             10-Minute Configurable Monitoring Scheduler               │  │
│  └──────────────────────────────────┬────────────────────────────────────┘  │
└─────────────────────────────────────┼───────────────────────────────────────┘
                                      │ WebSocket / REST API
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       Laptop Desktop Dashboard                              │
│                                                                             │
│  ┌───────────────────────┐  ┌───────────────────────┐  ┌─────────────────┐  │
│  │ Overview & Live Gauges│  │ IDW Heatmap Studio    │  │ Channel Spectrum│  │
│  └───────────────────────┘  └───────────────────────┘  └─────────────────┘  │
│  ┌───────────────────────┐  ┌───────────────────────┐  ┌─────────────────┐  │
│  │ Connected Devices     │  │ Diagnostics & Health  │  │ 24h Time Series │  │
│  └───────────────────────┘  └───────────────────────┘  └─────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Quick Start & How to Run

### Prerequisites
- Python 3.10+ (Tested and verified on Python 3.13)
- Windows 10/11 (or Linux/macOS with wireless tools)

### 1. Installation
Clone the repository and install dependencies:
```bash
git clone https://github.com/mohamedtharika25am-byte/WiFiLens.git
cd WiFiLens
pip install -r requirements.txt
```

### 2. Launch the Application
Start WiFiLens with one command:
```bash
python run.py
```
*Or double-click `run.bat` on Windows.*

The console will display:
```
======================================================================
  WiFiLens — See. Measure. Map. Optimize.
======================================================================
  [x] Backend Server     : http://127.0.0.1:8000
  [x] Laptop Dashboard   : http://localhost:8000
  [x] Mobile Scanner App : http://172.16.200.136:8000/mobile
  [x] Native Wi-Fi Engine: Windows netsh wlan + ARP + Gateway Ping
  [x] Background Monitor : 10-Minute Periodic Scheduler (Active)
======================================================================
```

Your browser will automatically open to `http://localhost:8000`.

### 3. Pairing Phone Scanner & Camera HUD
1. Click **"Phone Scanner (QR)"** in the top navigation header of the laptop dashboard.
2. Scan the displayed QR code with your mobile phone camera (ensure the phone is connected to the same Wi-Fi network).
3. The phone will instantly load the touch survey map and AR Camera HUD mode!

---

## Automated Test Verification

Run the comprehensive pytest suite:
```bash
python -m pytest tests/test_wifilens.py -v
```

All 7 core subsystem tests pass with 100% success:
- `test_wifi_scanner_helpers PASSED`
- `test_native_wifi_scan PASSED`
- `test_database_crud PASSED`
- `test_network_devices_discovery PASSED`
- `test_channel_analyzer PASSED`
- `test_diagnostics_and_health_scoring PASSED`
- `test_fastapi_endpoints PASSED`

---

## Primary References & Acknowledgments
- [wifi-heatmap](https://github.com/JWH2985/wifi-heatmap.git) — IDW interpolation and floor plan surveying concepts.
- [wifi-heatmapper](https://github.com/hnykda/wifi-heatmapper) — Spatial signal mapping.
- [WiFiAnalyzer](https://github.com/VREMSoftwareDevelopment/WiFiAnalyzer) — Parabolic channel spectrum modeling.

---

## License
MIT License. Free for academic, personal, and commercial network optimization.
