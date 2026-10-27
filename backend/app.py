"""
WiFiLens - Main Application Server (FastAPI + WebSockets + Uvicorn)
Coordinates Wi-Fi telemetry, real-time WebSocket broadcast,
REST APIs, floor plan management, and phone pairing.
"""

import os
import io
import json
import socket
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import qrcode

from backend.database import (
    init_db,
    insert_measurement,
    get_measurements,
    get_floorplan_measurements,
    get_history_series,
    save_floorplan,
    get_active_floorplan,
    get_all_floorplans,
    set_active_floorplan,
    update_floorplan_scale,
    insert_ap_marker,
    get_ap_markers,
    delete_ap_marker,
    get_all_settings,
    set_setting,
    get_setting
)
from backend.wifi_scanner import scan_current_interface_windows, scan_all_networks_windows, get_wifi_state
from backend.speed_test import run_full_performance_check, measure_gateway_ping, measure_internet_latency
from backend.network_scanner import get_connected_devices
from backend.channel_analyzer import analyze_channels
from backend.diagnostics import calculate_health_and_diagnostics
from backend.scheduler import MonitoringScheduler

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads", "floorplans")
ASSETS_DIR = os.path.join(FRONTEND_DIR, "assets")

os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(ASSETS_DIR, exist_ok=True)

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("wifilens.app")


# ==========================================
# WebSocket Connection Manager
# ==========================================
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket client connected. Total clients: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket client disconnected. Total clients: {len(self.active_connections)}")

    async def broadcast(self, message: Dict[str, Any]):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                self.disconnect(connection)

manager = ConnectionManager()
scheduler = MonitoringScheduler(broadcast_fn=manager.broadcast)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_db()
    ensure_default_floorplan()
    scheduler.start()
    logger.info("WiFiLens backend started successfully.")
    yield
    # Shutdown
    scheduler.stop()
    logger.info("WiFiLens backend stopped.")


app = FastAPI(title="WiFiLens", version="1.0.0", lifespan=lifespan)

# Allow CORS for local network and phone connections
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_local_ip() -> str:
    """Detects current machine's local Wi-Fi IP address."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def ensure_default_floorplan():
    """Generates a default sample architectural floor plan if none exist."""
    active = get_active_floorplan()
    if not active:
        sample_svg_path = os.path.join(ASSETS_DIR, "default_floorplan.svg")
        if not os.path.exists(sample_svg_path):
            svg_content = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 650" width="1000" height="650">
  <defs>
    <pattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse">
      <path d="M 20 0 L 0 0 0 20" fill="none" stroke="rgba(255,255,255,0.05)" stroke-width="1"/>
    </pattern>
  </defs>
  <rect width="1000" height="650" fill="#0d1117"/>
  <rect width="1000" height="650" fill="url(#grid)"/>
  
  <!-- Outer Perimeter Walls -->
  <rect x="50" y="50" width="900" height="550" fill="none" stroke="#00f2fe" stroke-width="4" rx="8"/>
  
  <!-- Living / Reception Area -->
  <rect x="50" y="50" width="450" height="350" fill="rgba(0, 242, 254, 0.04)" stroke="#38bdf8" stroke-width="2"/>
  <text x="70" y="90" fill="#38bdf8" font-family="sans-serif" font-size="18" font-weight="bold">Living &amp; Common Area</text>
  
  <!-- Office / Lab Room -->
  <rect x="500" y="50" width="450" height="250" fill="rgba(168, 85, 247, 0.04)" stroke="#a855f7" stroke-width="2"/>
  <text x="520" y="90" fill="#a855f7" font-family="sans-serif" font-size="18" font-weight="bold">Main Lab / Workspace</text>
  
  <!-- Server / Router Hub -->
  <rect x="750" y="300" width="200" height="300" fill="rgba(16, 185, 129, 0.04)" stroke="#10b981" stroke-width="2"/>
  <text x="770" y="340" fill="#10b981" font-family="sans-serif" font-size="16" font-weight="bold">Server Room</text>
  
  <!-- Conference Room -->
  <rect x="50" y="400" width="450" height="200" fill="rgba(245, 158, 11, 0.04)" stroke="#f59e0b" stroke-width="2"/>
  <text x="70" y="440" fill="#f59e0b" font-family="sans-serif" font-size="18" font-weight="bold">Conference Room</text>
  
  <!-- Breakout Space -->
  <rect x="500" y="300" width="250" height="300" fill="rgba(244, 63, 94, 0.04)" stroke="#f43f5e" stroke-width="2"/>
  <text x="520" y="340" fill="#f43f5e" font-family="sans-serif" font-size="16" font-weight="bold">Breakout Space</text>
  
  <!-- Scale Reference -->
  <line x1="80" y1="580" x2="280" y2="580" stroke="#94a3b8" stroke-width="3"/>
  <line x1="80" y1="575" x2="80" y2="585" stroke="#94a3b8" stroke-width="3"/>
  <line x1="280" y1="575" x2="280" y2="585" stroke="#94a3b8" stroke-width="3"/>
  <text x="145" y="572" fill="#94a3b8" font-family="sans-serif" font-size="12">10.0 Meters</text>
</svg>"""
            with open(sample_svg_path, "w", encoding="utf-8") as f:
                f.write(svg_content)

        default_fp = {
            "id": "default-floorplan-01",
            "name": "Headquarters / Lab Floor 1",
            "file_path": "/assets/default_floorplan.svg",
            "width": 1000,
            "height": 650,
            "scale_pixels": 200.0,
            "scale_meters": 10.0,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "active": 1
        }
        save_floorplan(default_fp)

        # Place initial detected Access Point marker
        insert_ap_marker({
            "id": "ap-main-01",
            "floorplan_id": "default-floorplan-01",
            "bssid": "0e:4a:6b:56:c8:c9",
            "ssid": "KITE-1F-202",
            "x": 850.0,
            "y": 450.0,
            "channel": 149,
            "band": "5 GHz",
            "label": "Main AP (Server Room)"
        })

        # Seed initial survey measurement points across rooms
        initial_points = [
            {"x": 850.0, "y": 450.0, "rssi": -42.0, "signal_quality": 92, "download_speed": 100.3, "upload_speed": 12.0, "ping_latency": 7.0, "health_score": 98, "notes": "Server Room AP Proximity"},
            {"x": 650.0, "y": 150.0, "rssi": -52.0, "signal_quality": 84, "download_speed": 88.5, "upload_speed": 11.2, "ping_latency": 9.0, "health_score": 92, "notes": "Main Lab Workspace Desk 4"},
            {"x": 600.0, "y": 450.0, "rssi": -58.0, "signal_quality": 78, "download_speed": 75.0, "upload_speed": 10.5, "ping_latency": 11.0, "health_score": 86, "notes": "Breakout Space Pod 1"},
            {"x": 250.0, "y": 150.0, "rssi": -65.0, "signal_quality": 70, "download_speed": 55.4, "upload_speed": 8.0, "ping_latency": 14.0, "health_score": 78, "notes": "Living / Common Area Reception"},
            {"x": 200.0, "y": 500.0, "rssi": -72.0, "signal_quality": 56, "download_speed": 32.1, "upload_speed": 5.2, "ping_latency": 24.0, "health_score": 65, "notes": "Conference Room Center Table"},
            {"x": 90.0, "y": 560.0, "rssi": -81.0, "signal_quality": 38, "download_speed": 9.8, "upload_speed": 2.1, "ping_latency": 45.0, "health_score": 42, "notes": "Far Hallway Corner (Weak Zone)"}
        ]

        wifi = scan_current_interface_windows()
        for pt in initial_points:
            pt.update({
                "floorplan_id": "default-floorplan-01",
                "ssid": wifi.get("ssid") or "KITE-1F-202",
                "bssid": wifi.get("bssid") or "0e:4a:6b:56:c8:c9",
                "channel": wifi.get("channel") or 149,
                "band": wifi.get("band") or "5 GHz",
                "radio_type": wifi.get("wifi_standard") or "Wi-Fi 6 (802.11ax)",
                "packet_loss": 0.0,
                "session_id": "initial_survey",
                "source": "calibration_survey"
            })
            insert_measurement(pt)


# ==========================================
# REST API Endpoints
# ==========================================

@app.get("/api/wifi/status")
async def get_wifi_interface_status():
    """Live Wi-Fi interface details (SSID, BSSID, RSSI, channel, standard, link rate)."""
    return scan_current_interface_windows()


@app.get("/api/wifi/networks")
async def get_surrounding_networks():
    """Surrounding AP scan with BSSID, Signal %, Band, and Channels."""
    return scan_all_networks_windows()


@app.get("/api/performance")
async def get_network_performance(speedtest: bool = False):
    """
    Measures Gateway Hop Latency (Wi-Fi hop) & Internet WAN Latency.
    Optionally runs throughput speedtest if requested.
    """
    gw = measure_gateway_ping()
    inet = measure_internet_latency()
    
    res = {
        "wifi_hop_latency_ms": gw.get("latency_ms", 0.0),
        "gateway_ip": gw.get("gateway_ip", ""),
        "packet_loss_pct": gw.get("packet_loss_pct", 0.0),
        "internet_latency_ms": inet.get("internet_latency_ms", 0.0),
        "internet_status": inet.get("status", "OFFLINE"),
        "download_mbps": 0.0,
        "upload_mbps": 0.0
    }

    if speedtest:
        from backend.speed_test import measure_download_speed, measure_upload_speed
        dl = measure_download_speed(duration_target=2.5)
        ul = measure_upload_speed(payload_bytes=2_000_000)
        res["download_mbps"] = dl.get("download_mbps", 0.0)
        res["upload_mbps"] = ul.get("upload_mbps", 0.0)

    return res


@app.post("/api/performance/test")
async def trigger_full_speedtest():
    """Triggers complete on-demand throughput & latency test."""
    return run_full_performance_check(run_speedtest=True)


@app.get("/api/devices")
async def get_subnet_devices():
    """Discovers real connected devices on Wi-Fi subnet via ARP."""
    return get_connected_devices()


@app.get("/api/channels")
async def get_channel_analysis():
    """2.4 GHz & 5 GHz channel spectrum, congestion, and recommendations."""
    cur = scan_current_interface_windows()
    nets = scan_all_networks_windows()
    return analyze_channels(nets, cur)


@app.get("/api/diagnostics")
async def get_network_diagnostics():
    """Composite explainable Wi-Fi Health Score (0-100) and rule-based insights."""
    wifi_info = scan_current_interface_windows()
    gw_res = measure_gateway_ping()
    inet_res = measure_internet_latency()
    chan_data = analyze_channels([], wifi_info)

    perf_info = {
        "wifi_hop_latency_ms": gw_res.get("latency_ms", 0.0),
        "internet_latency_ms": inet_res.get("internet_latency_ms", 0.0),
        "packet_loss_pct": gw_res.get("packet_loss_pct", 0.0),
        "download_mbps": 0.0,
        "upload_mbps": 0.0
    }
    return calculate_health_and_diagnostics(wifi_info, perf_info, chan_data)


@app.get("/api/measurements")
async def list_measurements(
    limit: int = 100,
    session_id: Optional[str] = None,
    floorplan_id: Optional[str] = None,
    filter: Optional[str] = None
):
    """Retrieves stored measurements from database."""
    return get_measurements(limit=limit, session_id=session_id, floorplan_id=floorplan_id, time_filter=filter)


@app.post("/api/measurements")
async def record_measurement(payload: Dict[str, Any]):
    """
    Records a new measurement point (from laptop survey click or mobile phone scanner).
    """
    # If wireless fields are not provided by mobile, sample from host interface
    if not payload.get("rssi") or payload.get("rssi") == -100:
        wifi = scan_current_interface_windows()
        payload["ssid"] = wifi.get("ssid")
        payload["bssid"] = wifi.get("bssid")
        payload["rssi"] = wifi.get("rssi")
        payload["signal_quality"] = wifi.get("signal_quality")
        payload["channel"] = wifi.get("channel")
        payload["frequency"] = wifi.get("frequency")
        payload["band"] = wifi.get("band")
        payload["radio_type"] = wifi.get("wifi_standard")

    # If latency wasn't provided, quick ping
    if not payload.get("ping_latency"):
        gw = measure_gateway_ping(count=2)
        payload["ping_latency"] = gw.get("latency_ms", 0.0)
        payload["packet_loss"] = gw.get("packet_loss_pct", 0.0)

    # Calculate health score for this point
    chan = analyze_channels([], payload)
    diag = calculate_health_and_diagnostics(payload, payload, chan)
    payload["health_score"] = diag.get("health_score", 85)

    row_id = insert_measurement(payload)
    payload["id"] = row_id

    # Broadcast point update to all connected dashboard websockets
    await manager.broadcast({
        "type": "new_measurement",
        "data": payload
    })

    return {"status": "SUCCESS", "id": row_id, "data": payload}


@app.get("/api/history/series")
async def get_history_chart_data(hours: int = 24):
    """Returns time-series arrays for Chart.js / canvas graphs."""
    return get_history_series(hours=hours)


# ==========================================
# Floor Plans & Markers API
# ==========================================

@app.get("/api/floorplans")
async def list_floorplans():
    return get_all_floorplans()


@app.get("/api/floorplans/active")
async def get_current_active_floorplan():
    return get_active_floorplan()


@app.post("/api/floorplans/active")
async def activate_floorplan(payload: Dict[str, str]):
    fp_id = payload.get("id")
    if not fp_id:
        raise HTTPException(status_code=400, detail="Missing floorplan id")
    set_active_floorplan(fp_id)
    return {"status": "SUCCESS", "active_id": fp_id}


@app.post("/api/floorplans/upload")
async def upload_floorplan_image(file: UploadFile = File(...), name: str = Form(...)):
    """Uploads a floor plan image file (PNG, JPG, SVG)."""
    import uuid
    fp_id = f"fp-{uuid.uuid4().hex[:8]}"
    ext = os.path.splitext(file.filename)[1].lower() or ".png"
    filename = f"{fp_id}{ext}"
    dest_path = os.path.join(UPLOADS_DIR, filename)

    contents = await file.read()
    with open(dest_path, "wb") as f:
        f.write(contents)

    # Determine dimensions if image
    width, height = 1000, 650
    try:
        from PIL import Image
        with Image.open(dest_path) as img:
            width, height = img.size
    except Exception:
        pass

    rel_url = f"/uploads/floorplans/{filename}"
    fp_data = {
        "id": fp_id,
        "name": name or file.filename,
        "file_path": rel_url,
        "width": width,
        "height": height,
        "scale_pixels": 0.0,
        "scale_meters": 0.0,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "active": 1
    }
    save_floorplan(fp_data)
    return fp_data


@app.post("/api/floorplans/scale")
async def calibrate_scale(payload: Dict[str, Any]):
    fp_id = payload.get("floorplan_id")
    px = float(payload.get("scale_pixels", 0))
    meters = float(payload.get("scale_meters", 0))
    if not fp_id or px <= 0 or meters <= 0:
        raise HTTPException(status_code=400, detail="Invalid scale parameters")
    update_floorplan_scale(fp_id, px, meters)
    return {"status": "SUCCESS", "ratio_px_per_meter": round(px / meters, 2)}


@app.get("/api/floorplans/{floorplan_id}/measurements")
async def get_points_for_floorplan(floorplan_id: str):
    """Returns all coordinate-mapped sample points for heatmap rendering."""
    return get_floorplan_measurements(floorplan_id)


@app.get("/api/floorplans/{floorplan_id}/markers")
async def get_markers_for_floorplan(floorplan_id: str):
    return get_ap_markers(floorplan_id)


@app.post("/api/floorplans/markers")
async def create_ap_marker(payload: Dict[str, Any]):
    import uuid
    if not payload.get("id"):
        payload["id"] = f"ap-{uuid.uuid4().hex[:8]}"
    insert_ap_marker(payload)
    return {"status": "SUCCESS", "marker": payload}


@app.delete("/api/floorplans/markers/{marker_id}")
async def remove_ap_marker(marker_id: str):
    delete_ap_marker(marker_id)
    return {"status": "SUCCESS", "deleted_id": marker_id}


# ==========================================
# Settings & Background Scheduler
# ==========================================

@app.get("/api/settings")
async def get_settings():
    return get_all_settings()


@app.post("/api/settings")
async def update_settings(payload: Dict[str, str]):
    for k, v in payload.items():
        set_setting(k, str(v))
    return {"status": "SUCCESS", "settings": get_all_settings()}


@app.post("/api/scheduler/sample-now")
async def trigger_immediate_sample():
    """Forces an instantaneous telemetry sample into the database."""
    sample = await scheduler.execute_sample(trigger="manual")
    return {"status": "SUCCESS", "sample": sample}


# ==========================================
# Phone Pairing & QR Code
# ==========================================

from fastapi import Request

@app.get("/api/network/host-info")
async def get_host_info(request: Request):
    """Provides local laptop IP and pairing URLs for phone scanner."""
    local_ip = get_local_ip()
    port = request.url.port or 8000
    mobile_url = f"http://{local_ip}:{port}/mobile"

    # Generate QR Code in memory
    qr = qrcode.QRCode(box_size=8, border=2)
    qr.add_data(mobile_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#00f2fe", back_color="#0d1117")
    
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    import base64
    qr_b64 = "data:image/png;base64," + base64.b64encode(buffered.getvalue()).decode()

    return {
        "local_ip": local_ip,
        "port": port,
        "mobile_url": mobile_url,
        "qr_code_b64": qr_b64
    }


# ==========================================
# WebSocket Endpoint for Live Telemetry
# ==========================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # Send initial state
        wifi = scan_current_interface_windows()
        await websocket.send_json({
            "type": "init",
            "wifi": wifi,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        })

        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                # Handle messages from mobile or desktop
                msg_type = msg.get("type")
                if msg_type == "ping":
                    await websocket.send_json({"type": "pong"})
                elif msg_type == "mobile_telemetry":
                    # Phone reporting live status/location
                    await manager.broadcast({
                        "type": "mobile_update",
                        "data": msg.get("data")
                    })
                elif msg_type == "record_sample":
                    # Record sample point
                    sample_data = msg.get("data", {})
                    row_id = insert_measurement(sample_data)
                    sample_data["id"] = row_id
                    await manager.broadcast({
                        "type": "new_measurement",
                        "data": sample_data
                    })
            except Exception as e:
                logger.error(f"WS message error: {e}")

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WS error: {e}")
        manager.disconnect(websocket)


# ==========================================
# Static Files & Frontend Routing
# ==========================================

app.mount("/css", StaticFiles(directory=os.path.join(FRONTEND_DIR, "css")), name="css")
app.mount("/js", StaticFiles(directory=os.path.join(FRONTEND_DIR, "js")), name="js")
app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")
app.mount("/uploads", StaticFiles(directory=os.path.join(BASE_DIR, "uploads")), name="uploads")


@app.get("/")
async def serve_dashboard():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


@app.get("/mobile")
async def serve_mobile_scanner():
    return FileResponse(os.path.join(FRONTEND_DIR, "mobile.html"))
