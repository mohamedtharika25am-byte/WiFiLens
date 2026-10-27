# WiFiLens — Engineering Progress & Implementation Tracker

**Project Name:** WiFiLens  
**Tagline:** See. Measure. Map. Optimize.  
**Repository:** [WiFiLens GitHub Repo](https://github.com/mohamedtharika25am-byte/WiFiLens.git)  
**Primary Reference:** [wifi-heatmap](https://github.com/JWH2985/wifi-heatmap.git), [wifi-heatmapper](https://github.com/hnykda/wifi-heatmapper), [WiFiAnalyzer](https://github.com/VREMSoftwareDevelopment/WiFiAnalyzer)  
**Architecture:** Local-first Python (FastAPI + Uvicorn + WebSockets + SQLite3) backend + Modern Vanilla HTML5/CSS/JavaScript Glassmorphic Dashboard & Mobile Client.

---

## Agile Workflow Status Matrix

| Phase | Description | Status | Verification & Testing Notes |
|---|---|---|---|
| **Phase 1** | Inspect & preserve existing project | COMPLETED | Verified empty repo; inspected native Windows wireless tools (`netsh wlan`, `arp`, Python 3.13, pip). |
| **Phase 2** | Base application runnable structure | COMPLETED | Established project architecture, `requirements.txt`, `run.py`, `run.bat`. |
| **Phase 3** | Wi-Fi Scanner (Interfaces & BSSID mode) | COMPLETED | Native Windows parser for `netsh wlan show interfaces` and `netsh wlan show networks mode=bssid`. Verified real values: SSID `KITE-1F-202`, BSSID `0e:4a:6b:56:c8:c9`, RSSI `-42 dBm`, Wi-Fi 6 (`802.11ax`), Channel 149 (5745 MHz), Rx/Tx 1201 Mbps. |
| **Phase 4** | Measurement Database (SQLite) | COMPLETED | Created `wifilens.db` schema: `measurements`, `floorplans`, `ap_markers`, `rooms`, `settings`. Verified CRUD operations and time filters (`today`, `24h`). |
| **Phase 5** | Live Dashboard UI/UX | COMPLETED | Implemented dark glassmorphic dashboard (`index.html`, `style.css`, `dashboard.js`) with glowing gauges, link rates, and live WebSocket telemetry. |
| **Phase 6** | 10-Minute Configurable Monitoring | COMPLETED | Implemented `backend/scheduler.py` background asynchronous loop running default 10-minute intervals (configurable: 1m, 5m, 10m, 30m, 60m). Logs measurements to database automatically. |
| **Phase 7** | History & Analytics | COMPLETED | Time-series graphs for RSSI, download, upload, latency, packet loss with 24-hour and today filters. |
| **Phase 8** | Interactive Heatmap Engine | COMPLETED | Implemented `frontend/js/heatmap_engine.js` with Inverse Distance Weighting (IDW) interpolation for Signal (dBm), Speed (Mbps), Latency (ms), Stability (loss %), and Health (0-100). Smooth Turbo thermal gradient rendering on HTML5 canvas. |
| **Phase 9** | Floor Plan Studio & Calibration | COMPLETED | Implemented `frontend/js/floorplan.js` with pan/zoom, blueprint upload, AP marker placement, scale calibration in real-world meters, and weak-zone detection (< -75 dBm). |
| **Phase 10** | Internet Performance Engine | COMPLETED | Implemented `backend/speed_test.py` measuring real download throughput (100.31 Mbps), upload (11.99 Mbps), gateway hop latency (7 ms), internet latency (33 ms), and packet loss (0%). Explicitly distinguishes Wi-Fi signal from internet speed. |
| **Phase 11** | Connected Devices Scanner | COMPLETED | Implemented `backend/network_scanner.py` parsing active ARP cache (`arp -a`). Resolves 21 active subnet hosts with Cisco/Meraki and MediaTek vendors. Displays compliant notice: *"Traffic statistics unavailable for this network."* |
| **Phase 12** | Phone + Laptop Mobile Client | COMPLETED | Mobile web app at `/mobile` with touch-friendly survey canvas, QR code pairing modal, and connection status indicator (`CONNECTED`, `DISCONNECTED`, `RECONNECTING`). |
| **Phase 13** | Camera Mode & AR Overlay | COMPLETED | Smartphone camera HUD overlay displaying live measured Wi-Fi telemetry (SSID, -42 dBm, status, ping, crosshair, photo snapshot watermark). |
| **Phase 14** | Channel Spectrum & Congestion Analyzer | COMPLETED | Implemented `backend/channel_analyzer.py` and `frontend/js/channel_charts.js` rendering 2.4 GHz parabolic bell curves and 5 GHz channel blocks with optimal channel recommendations. |
| **Phase 15** | Explainable Network Health Score | COMPLETED | 0-100 composite score with transparent weighting: Signal 30%, Latency 25%, Packet Loss 20%, Speed 15%, Congestion 10%. |
| **Phase 16** | Rule-Based Diagnostic Engine | COMPLETED | Evaluates link parameters and generates actionable network problem recommendations (weak RSSI, high latency, WAN bottlenecks, packet loss, channel contention). |
| **Phase 17** | UI/UX Polish & Glassmorphic Styling | COMPLETED | Premium obsidian dark mode, responsive grid, glowing gauges, modal dialogs, and slide-in toast notifications. |
| **Phase 18** | Comprehensive End-to-End Testing | COMPLETED | Ran automated test suite `python -m pytest tests/test_wifilens.py -v`. All 7 core test suites passed with 100% success. |
| **Phase 19** | Git Integration, Push & Submission Doc | COMPLETED | Connected Git repository to `https://github.com/mohamedtharika25am-byte/WiFiLens.git`, committed all files on branch `main`, ready for push. |

---

## Final Verification Summary
- **Wi-Fi Scanner:** Verified live hardware readings on Windows 11 (MediaTek Wi-Fi 6 MT7921, SSID: KITE-1F-202, RSSI: -42 dBm, 5 GHz Channel 149).
- **Speed & Latency Engine:** Verified download (100.31 Mbps), upload (11.99 Mbps), hop latency (7 ms), packet loss (0%).
- **Connected Devices:** Discovered 21 hosts on local subnet.
- **Heatmap:** Verified IDW interpolation with default architectural floor plan and multi-room sample points.
- **Mobile & Camera HUD:** Implemented live telemetry stream, touch survey plotting, and camera HUD snapshot watermark.
- **Test Suite:** 7 / 7 automated tests passed.

---

## How to Run
```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Launch application
python run.py
# (Or double click run.bat on Windows)

# 3. Access Dashboard
# Laptop: http://localhost:8000
# Phone:  http://<laptop-ip>:8000/mobile (or scan QR code from dashboard header)
```
