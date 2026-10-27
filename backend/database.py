"""
WiFiLens - Database Layer (SQLite)
Handles persistent storage for real Wi-Fi measurements, floor plans, AP markers,
monitoring history, sessions, and configuration settings.
"""

import os
import sqlite3
import json
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DB_PATH = os.path.join(DB_DIR, "wifilens.db")

os.makedirs(DB_DIR, exist_ok=True)


def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Measurements table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS measurements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        session_id TEXT,
        source TEXT DEFAULT 'laptop',
        ssid TEXT,
        bssid TEXT,
        rssi REAL,
        signal_quality INTEGER,
        channel INTEGER,
        frequency REAL,
        band TEXT,
        radio_type TEXT,
        download_speed REAL,
        upload_speed REAL,
        ping_latency REAL,
        packet_loss REAL,
        health_score INTEGER,
        latitude REAL,
        longitude REAL,
        floorplan_id TEXT,
        x REAL,
        y REAL,
        notes TEXT
    )
    """)

    # Floor plans table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS floorplans (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        file_path TEXT NOT NULL,
        width INTEGER,
        height INTEGER,
        scale_pixels REAL DEFAULT 0,
        scale_meters REAL DEFAULT 0,
        created_at TEXT NOT NULL,
        active INTEGER DEFAULT 0
    )
    """)

    # AP markers table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ap_markers (
        id TEXT PRIMARY KEY,
        floorplan_id TEXT NOT NULL,
        bssid TEXT,
        ssid TEXT,
        x REAL NOT NULL,
        y REAL NOT NULL,
        channel INTEGER,
        band TEXT,
        label TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (floorplan_id) REFERENCES floorplans(id) ON DELETE CASCADE
    )
    """)

    # Room zones table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS rooms (
        id TEXT PRIMARY KEY,
        floorplan_id TEXT NOT NULL,
        name TEXT NOT NULL,
        polygon_json TEXT NOT NULL,
        color TEXT DEFAULT '#00f2fe',
        FOREIGN KEY (floorplan_id) REFERENCES floorplans(id) ON DELETE CASCADE
    )
    """)

    # Settings table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """)

    # Default settings
    defaults = {
        "monitor_interval_seconds": "600",  # 10 minutes default
        "monitor_enabled": "1",
        "speedtest_on_interval": "0",       # speedtests optional during interval to save bandwidth
        "ping_target": "172.16.192.1",      # default gateway or 1.1.1.1
        "health_threshold_rssi": "-75",
        "health_threshold_ping": "100"
    }

    for k, v in defaults.items():
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))

    conn.commit()
    conn.close()


# ==========================================
# Measurements Operations
# ==========================================

def insert_measurement(data: Dict[str, Any]) -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    now_iso = datetime.now(timezone.utc).isoformat()

    cursor.execute("""
    INSERT INTO measurements (
        timestamp, session_id, source, ssid, bssid, rssi, signal_quality,
        channel, frequency, band, radio_type, download_speed, upload_speed,
        ping_latency, packet_loss, health_score, latitude, longitude,
        floorplan_id, x, y, notes
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.get("timestamp") or now_iso,
        data.get("session_id", "default"),
        data.get("source", "laptop"),
        data.get("ssid"),
        data.get("bssid"),
        data.get("rssi"),
        data.get("signal_quality"),
        data.get("channel"),
        data.get("frequency"),
        data.get("band"),
        data.get("radio_type"),
        data.get("download_speed"),
        data.get("upload_speed"),
        data.get("ping_latency"),
        data.get("packet_loss"),
        data.get("health_score"),
        data.get("latitude"),
        data.get("longitude"),
        data.get("floorplan_id"),
        data.get("x"),
        data.get("y"),
        data.get("notes")
    ))
    last_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return last_id


def get_measurements(
    limit: int = 100,
    session_id: Optional[str] = None,
    floorplan_id: Optional[str] = None,
    time_filter: Optional[str] = None
) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()

    query = "SELECT * FROM measurements WHERE 1=1"
    params = []

    if session_id:
        query += " AND session_id = ?"
        params.append(session_id)

    if floorplan_id:
        query += " AND floorplan_id = ?"
        params.append(floorplan_id)

    if time_filter == "today":
        today_prefix = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        query += " AND timestamp LIKE ?"
        params.append(f"{today_prefix}%")
    elif time_filter == "24h":
        from datetime import timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        query += " AND timestamp >= ?"
        params.append(cutoff)

    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_floorplan_measurements(floorplan_id: str) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT * FROM measurements 
    WHERE floorplan_id = ? AND x IS NOT NULL AND y IS NOT NULL
    ORDER BY id ASC
    """, (floorplan_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_history_series(hours: int = 24) -> Dict[str, List[Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()

    cursor.execute("""
    SELECT timestamp, rssi, download_speed, upload_speed, ping_latency, packet_loss, health_score
    FROM measurements
    WHERE timestamp >= ?
    ORDER BY id ASC
    """, (cutoff,))
    rows = cursor.fetchall()
    conn.close()

    result = {
        "timestamps": [],
        "rssi": [],
        "download": [],
        "upload": [],
        "latency": [],
        "packet_loss": [],
        "health": []
    }
    for row in rows:
        result["timestamps"].append(row["timestamp"])
        result["rssi"].append(row["rssi"])
        result["download"].append(row["download_speed"])
        result["upload"].append(row["upload_speed"])
        result["latency"].append(row["ping_latency"])
        result["packet_loss"].append(row["packet_loss"])
        result["health"].append(row["health_score"])

    return result


# ==========================================
# Floor Plans Operations
# ==========================================

def save_floorplan(floorplan: Dict[str, Any]):
    conn = get_db_connection()
    cursor = conn.cursor()
    now_iso = datetime.now(timezone.utc).isoformat()

    # If this is marked active, deactivate others
    if floorplan.get("active", 0) == 1:
        cursor.execute("UPDATE floorplans SET active = 0")

    cursor.execute("""
    INSERT OR REPLACE INTO floorplans (
        id, name, file_path, width, height, scale_pixels, scale_meters, created_at, active
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        floorplan["id"],
        floorplan["name"],
        floorplan["file_path"],
        floorplan.get("width", 0),
        floorplan.get("height", 0),
        floorplan.get("scale_pixels", 0.0),
        floorplan.get("scale_meters", 0.0),
        floorplan.get("created_at", now_iso),
        floorplan.get("active", 1)
    ))
    conn.commit()
    conn.close()


def get_active_floorplan() -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM floorplans WHERE active = 1 ORDER BY created_at DESC LIMIT 1")
    row = cursor.fetchone()
    if not row:
        cursor.execute("SELECT * FROM floorplans ORDER BY created_at DESC LIMIT 1")
        row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_floorplans() -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM floorplans ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def set_active_floorplan(floorplan_id: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE floorplans SET active = 0")
    cursor.execute("UPDATE floorplans SET active = 1 WHERE id = ?", (floorplan_id,))
    conn.commit()
    conn.close()


def update_floorplan_scale(floorplan_id: str, scale_pixels: float, scale_meters: float):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE floorplans SET scale_pixels = ?, scale_meters = ? WHERE id = ?
    """, (scale_pixels, scale_meters, floorplan_id))
    conn.commit()
    conn.close()


# ==========================================
# AP Markers Operations
# ==========================================

def insert_ap_marker(marker: Dict[str, Any]):
    conn = get_db_connection()
    cursor = conn.cursor()
    now_iso = datetime.now(timezone.utc).isoformat()

    cursor.execute("""
    INSERT OR REPLACE INTO ap_markers (
        id, floorplan_id, bssid, ssid, x, y, channel, band, label, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        marker["id"],
        marker["floorplan_id"],
        marker.get("bssid"),
        marker.get("ssid"),
        marker["x"],
        marker["y"],
        marker.get("channel"),
        marker.get("band"),
        marker.get("label", "Access Point"),
        marker.get("created_at", now_iso)
    ))
    conn.commit()
    conn.close()


def get_ap_markers(floorplan_id: str) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ap_markers WHERE floorplan_id = ?", (floorplan_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def delete_ap_marker(marker_id: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM ap_markers WHERE id = ?", (marker_id,))
    conn.commit()
    conn.close()


# ==========================================
# Settings Operations
# ==========================================

def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row["value"] if row else default


def set_setting(key: str, value: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()


def get_all_settings() -> Dict[str, str]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM settings")
    rows = cursor.fetchall()
    conn.close()
    return {row["key"]: row["value"] for row in rows}


# Auto-initialize on import
init_db()
