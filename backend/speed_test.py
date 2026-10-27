"""
WiFiLens - Internet Performance & Latency Engine
Measures REAL:
1. Wi-Fi Hop Latency (ms) to local gateway (reflects RF & router responsiveness)
2. Internet / WAN Latency (ms) via fast HTTP/TCP round-trip
3. Packet Loss (%)
4. Download Throughput (Mbps) via chunked streaming
5. Upload Throughput (Mbps) via chunked POST

CRITICAL PRINCIPLE: Clearly distinguish Wi-Fi Signal from Internet Speed.
Wi-Fi Signal is the local wireless physical link (dBm).
Internet Speed is the WAN throughput delivered by the ISP (Mbps).
"""

import time
import socket
import subprocess
import urllib.request
import urllib.error
import re
from typing import Dict, Any, Optional


def find_default_gateway_windows() -> Optional[str]:
    """Finds default IPv4 gateway on Windows using netstat / route print."""
    try:
        res = subprocess.run(["route", "print", "0.0.0.0"], capture_output=True, text=True, timeout=4)
        for line in res.stdout.splitlines():
            parts = line.strip().split()
            if len(parts) >= 5 and parts[0] == "0.0.0.0" and parts[1] == "0.0.0.0":
                gateway_ip = parts[2]
                if re.match(r"^\d+\.\d+\.\d+\.\d+$", gateway_ip):
                    return gateway_ip
    except Exception:
        pass
    return "172.16.192.1"  # Fallback to detected local institutional gateway


def measure_gateway_ping(gateway_ip: Optional[str] = None, count: int = 4) -> Dict[str, Any]:
    """
    Pings the local Wi-Fi router / default gateway.
    Measures physical Wi-Fi hop latency and local wireless packet loss.
    """
    if not gateway_ip:
        gateway_ip = find_default_gateway_windows() or "172.16.192.1"

    result = {
        "gateway_ip": gateway_ip,
        "latency_ms": 0.0,
        "packet_loss_pct": 0.0,
        "packets_sent": count,
        "packets_received": 0,
        "status": "UNAVAILABLE"
    }

    try:
        cmd = ["ping", "-n", str(count), "-w", "1000", gateway_ip]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=6)
        out = proc.stdout

        # Extract loss %
        loss_match = re.search(r"\((\d+)%\s*loss\)", out, re.IGNORECASE)
        if loss_match:
            result["packet_loss_pct"] = float(loss_match.group(1))

        # Extract received
        recv_match = re.search(r"Received\s*=\s*(\d+)", out, re.IGNORECASE)
        if recv_match:
            result["packets_received"] = int(recv_match.group(1))

        # Extract average latency
        avg_match = re.search(r"Average\s*=\s*(\d+)ms", out, re.IGNORECASE)
        if avg_match:
            result["latency_ms"] = float(avg_match.group(1))
            result["status"] = "OK"
        elif result["packets_received"] > 0:
            # Fallback to min/max
            time_matches = re.findall(r"time[=<](\d+)ms", out, re.IGNORECASE)
            if time_matches:
                times = [float(t) for t in time_matches]
                result["latency_ms"] = round(sum(times) / len(times), 1)
                result["status"] = "OK"
        else:
            result["status"] = "TIMEOUT"

    except Exception as e:
        result["status"] = "ERROR"
        result["error"] = str(e)

    return result


def measure_internet_latency() -> Dict[str, Any]:
    """
    Measures Internet WAN latency using lightweight TCP handshake to high-availability endpoints.
    Provides reliable WAN latency even when ICMP is blocked by institutional firewalls.
    """
    endpoints = [
        ("1.1.1.1", 80),        # Cloudflare
        ("8.8.8.8", 53),        # Google DNS
        ("www.google.com", 80)  # Google Web
    ]

    latencies = []
    for host, port in endpoints:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2.5)
            t0 = time.perf_counter()
            s.connect((host, port))
            t1 = time.perf_counter()
            s.close()
            ms = (t1 - t0) * 1000.0
            latencies.append(ms)
        except Exception:
            continue

    if latencies:
        avg_lat = round(sum(latencies) / len(latencies), 1)
        return {
            "internet_latency_ms": avg_lat,
            "status": "ONLINE"
        }

    return {
        "internet_latency_ms": 0.0,
        "status": "OFFLINE"
    }


def get_ssl_context():
    """Returns an SSL context that tolerates institutional proxy certificates."""
    import ssl
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def measure_download_speed(duration_target: float = 3.5) -> Dict[str, Any]:
    """
    Measures real download speed (Mbps) by streaming chunked data from high-speed CDN.
    Uses Cloudflare speed test endpoints with fallback to Wikimedia CDN.
    """
    urls = [
        "https://speed.cloudflare.com/__down?bytes=10000000",
        "https://upload.wikimedia.org/wikipedia/commons/3/3f/Fronalpstock_big.jpg"
    ]

    total_bytes = 0
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) WiFiLens/1.0"}
    ctx = get_ssl_context()

    for test_url in urls:
        try:
            req = urllib.request.Request(test_url, headers=headers)
            with urllib.request.urlopen(req, timeout=6.0, context=ctx) as response:
                t0 = time.perf_counter()
                while True:
                    chunk = response.read(65536)  # 64 KB chunks
                    if not chunk:
                        break
                    total_bytes += len(chunk)
                    elapsed = time.perf_counter() - t0
                    if elapsed >= duration_target:
                        break
                
                total_duration = time.perf_counter() - t0
                if total_duration > 0 and total_bytes > 0:
                    mbps = round((total_bytes * 8.0) / (total_duration * 1_000_000.0), 2)
                    return {
                        "download_mbps": mbps,
                        "bytes_transferred": total_bytes,
                        "duration_sec": round(total_duration, 2),
                        "status": "OK"
                    }
        except Exception:
            continue

    return {
        "download_mbps": 0.0,
        "bytes_transferred": 0,
        "duration_sec": 0.0,
        "status": "UNAVAILABLE"
    }


def measure_upload_speed(payload_bytes: int = 4_000_000) -> Dict[str, Any]:
    """
    Measures real upload speed (Mbps) by POSTing dummy payload chunks to HTTP test endpoints.
    """
    urls = [
        "https://speed.cloudflare.com/__up",
        "https://httpbin.org/post"
    ]

    data_payload = b"0" * payload_bytes
    headers = {
        "Content-Type": "application/octet-stream",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) WiFiLens/1.0"
    }
    ctx = get_ssl_context()

    for test_url in urls:
        try:
            req = urllib.request.Request(test_url, data=data_payload, headers=headers, method="POST")
            t0 = time.perf_counter()
            with urllib.request.urlopen(req, timeout=7.0, context=ctx) as response:
                if response.status in [200, 204]:
                    duration = time.perf_counter() - t0
                    if duration > 0:
                        mbps = round((len(data_payload) * 8.0) / (duration * 1_000_000.0), 2)
                        return {
                            "upload_mbps": mbps,
                            "bytes_transferred": len(data_payload),
                            "duration_sec": round(duration, 2),
                            "status": "OK"
                        }
        except Exception:
            continue

    return {
        "upload_mbps": 0.0,
        "bytes_transferred": 0,
        "duration_sec": 0.0,
        "status": "UNAVAILABLE"
    }


def run_full_performance_check(run_speedtest: bool = True) -> Dict[str, Any]:
    """
    Runs full performance suite:
    - Gateway hop latency (Wi-Fi physical link)
    - Internet WAN latency
    - Packet loss
    - Download & upload throughput (if run_speedtest is True)
    """
    gw = measure_gateway_ping()
    inet = measure_internet_latency()

    perf = {
        "wifi_hop_latency_ms": gw.get("latency_ms", 0.0),
        "gateway_ip": gw.get("gateway_ip", ""),
        "packet_loss_pct": gw.get("packet_loss_pct", 0.0),
        "internet_latency_ms": inet.get("internet_latency_ms", 0.0),
        "internet_status": inet.get("status", "OFFLINE"),
        "download_mbps": 0.0,
        "upload_mbps": 0.0,
        "speedtest_run": run_speedtest
    }

    if run_speedtest and inet.get("status") == "ONLINE":
        dl = measure_download_speed()
        ul = measure_upload_speed()
        perf["download_mbps"] = dl.get("download_mbps", 0.0)
        perf["upload_mbps"] = ul.get("upload_mbps", 0.0)

    return perf


if __name__ == "__main__":
    import json
    print("Testing Internet & Gateway Performance...")
    res = run_full_performance_check(run_speedtest=True)
    print(json.dumps(res, indent=2))
