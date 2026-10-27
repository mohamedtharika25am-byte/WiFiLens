"""
WiFiLens - Network Health Scoring & Rule-Based Diagnostics Engine
Calculates an explainable 0-100 Wi-Fi Health Score and generates
objective, evidence-backed network diagnostic insights.
"""

from typing import Dict, Any, List


def evaluate_signal(rssi: float) -> Dict[str, Any]:
    if rssi >= -50:
        return {"score": 100, "rating": "Excellent", "label": f"{rssi} dBm (Outstanding)"}
    elif rssi >= -60:
        return {"score": 90, "rating": "Very Good", "label": f"{rssi} dBm (Strong)"}
    elif rssi >= -67:
        return {"score": 80, "rating": "Good", "label": f"{rssi} dBm (Good for HD Streaming/VoIP)"}
    elif rssi >= -75:
        return {"score": 55, "rating": "Fair", "label": f"{rssi} dBm (Usable, nearing weak boundary)"}
    elif rssi >= -82:
        return {"score": 35, "rating": "Poor", "label": f"{rssi} dBm (Weak signal, high attenuation)"}
    else:
        return {"score": 10, "rating": "Critical", "label": f"{rssi} dBm (Severe degradation)"}


def evaluate_latency(latency_ms: float) -> Dict[str, Any]:
    if latency_ms <= 0:
        return {"score": 70, "rating": "Unknown", "label": "No latency probe"}
    if latency_ms <= 15:
        return {"score": 100, "rating": "Excellent", "label": f"{latency_ms} ms (Ultra-responsive)"}
    elif latency_ms <= 35:
        return {"score": 90, "rating": "Very Good", "label": f"{latency_ms} ms (Responsive)"}
    elif latency_ms <= 70:
        return {"score": 75, "rating": "Good", "label": f"{latency_ms} ms (Normal browsing/streaming)"}
    elif latency_ms <= 120:
        return {"score": 50, "rating": "Fair", "label": f"{latency_ms} ms (Noticeable lag for real-time apps)"}
    else:
        return {"score": 20, "rating": "Poor", "label": f"{latency_ms} ms (High latency / lag)"}


def evaluate_packet_loss(loss_pct: float) -> Dict[str, Any]:
    if loss_pct <= 0.0:
        return {"score": 100, "rating": "Excellent", "label": "0% (Zero loss)"}
    elif loss_pct <= 1.0:
        return {"score": 85, "rating": "Good", "label": f"{loss_pct}% (Minor packet jitter)"}
    elif loss_pct <= 4.0:
        return {"score": 55, "rating": "Fair", "label": f"{loss_pct}% (Occasional packet drop)"}
    else:
        return {"score": 20, "rating": "Critical", "label": f"{loss_pct}% (Severe packet loss / unstable link)"}


def evaluate_speed(dl_mbps: float) -> Dict[str, Any]:
    if dl_mbps <= 0:
        return {"score": 75, "rating": "Unmeasured", "label": "Speed test not run"}
    if dl_mbps >= 50:
        return {"score": 100, "rating": "Excellent", "label": f"{dl_mbps} Mbps (High-speed broadband)"}
    elif dl_mbps >= 25:
        return {"score": 85, "rating": "Good", "label": f"{dl_mbps} Mbps (4K streaming ready)"}
    elif dl_mbps >= 10:
        return {"score": 70, "rating": "Fair", "label": f"{dl_mbps} Mbps (Standard web speed)"}
    elif dl_mbps >= 3:
        return {"score": 45, "rating": "Slow", "label": f"{dl_mbps} Mbps (Basic web browsing)"}
    else:
        return {"score": 20, "rating": "Very Slow", "label": f"{dl_mbps} Mbps (Bandwidth constrained)"}


def evaluate_congestion(congestion_score: float) -> Dict[str, Any]:
    if congestion_score <= 15:
        return {"score": 100, "rating": "Low", "label": "Clean channel with minimal interference"}
    elif congestion_score <= 35:
        return {"score": 80, "rating": "Moderate", "label": "Acceptable airtime competition"}
    elif congestion_score <= 65:
        return {"score": 50, "rating": "Crowded", "label": "Multiple overlapping access points"}
    else:
        return {"score": 25, "rating": "Severe", "label": "Heavy co-channel contention"}


def calculate_health_and_diagnostics(
    wifi_info: Dict[str, Any],
    perf_info: Dict[str, Any],
    channel_info: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Computes explainable composite health score (0-100) and triggers rule-based diagnostics.
    """
    rssi = wifi_info.get("rssi", -100.0)
    connected = wifi_info.get("connected", False)

    if not connected:
        return {
            "health_score": 0,
            "overall_status": "Disconnected",
            "breakdown": {
                "signal": {"score": 0, "rating": "Disconnected", "label": "No active Wi-Fi connection"},
                "latency": {"score": 0, "rating": "Disconnected", "label": "No gateway connection"},
                "packet_loss": {"score": 0, "rating": "Disconnected", "label": "N/A"},
                "speed": {"score": 0, "rating": "Disconnected", "label": "N/A"},
                "congestion": {"score": 0, "rating": "Disconnected", "label": "N/A"}
            },
            "insights": [
                {
                    "severity": "CRITICAL",
                    "title": "Wi-Fi Interface Disconnected",
                    "description": "Your device is not currently connected to any wireless access point. Connect to a network to begin telemetry.",
                    "recommendation": "Turn on Wi-Fi and join an SSID."
                }
            ]
        }

    # Extract metrics
    gw_latency = perf_info.get("wifi_hop_latency_ms", 0.0)
    inet_latency = perf_info.get("internet_latency_ms", 0.0)
    effective_latency = gw_latency if gw_latency > 0 else inet_latency

    loss = perf_info.get("packet_loss_pct", 0.0)
    dl_speed = perf_info.get("download_mbps", 0.0)
    congestion = channel_info.get("current_channel_congestion", 0)

    # Sub-scores
    sig_eval = evaluate_signal(rssi)
    lat_eval = evaluate_latency(effective_latency)
    loss_eval = evaluate_packet_loss(loss)
    spd_eval = evaluate_speed(dl_speed)
    cng_eval = evaluate_congestion(congestion)

    # Weighted calculation: Signal 30%, Latency 25%, Packet Loss 20%, Speed 15%, Congestion 10%
    composite = (
        sig_eval["score"] * 0.30 +
        lat_eval["score"] * 0.25 +
        loss_eval["score"] * 0.20 +
        spd_eval["score"] * 0.15 +
        cng_eval["score"] * 0.10
    )
    final_score = int(round(composite))
    final_score = max(0, min(100, final_score))

    # Overall rating
    if final_score >= 85:
        overall_status = "Excellent"
    elif final_score >= 70:
        overall_status = "Good"
    elif final_score >= 50:
        overall_status = "Fair"
    else:
        overall_status = "Poor"

    # ==========================================
    # Rule-Based Diagnostics Engine
    # ==========================================
    insights: List[Dict[str, Any]] = []

    # Rule 1: Weak RSSI
    if rssi < -75:
        insights.append({
            "severity": "WARNING",
            "title": "Weak Wi-Fi Signal Detected",
            "description": f"Measured signal strength is {rssi} dBm. High physical attenuation or distance from the AP degrades link throughput and causes packet retransmissions.",
            "recommendation": "Move closer to the router, clear physical line of sight, or deploy a Wi-Fi mesh repeater node."
        })

    # Rule 2: High Latency
    if effective_latency > 100:
        insights.append({
            "severity": "WARNING",
            "title": "High Latency Detected",
            "description": f"Round-trip hop latency is {effective_latency} ms. This will cause lag in video conferencing, cloud gaming, and interactive sessions.",
            "recommendation": "Check for bandwidth-heavy background downloads or router queue bufferbloat."
        })

    # Rule 3: Strong RSSI + Poor Speed (WAN Backhaul Bottleneck)
    if rssi >= -65 and dl_speed > 0 and dl_speed < 10:
        insights.append({
            "severity": "INFO",
            "title": "Possible Internet / WAN Backhaul Bottleneck",
            "description": f"Your local Wi-Fi RF signal is strong ({rssi} dBm), but internet download throughput is only {dl_speed} Mbps. The bottleneck is the ISP connection or WAN gateway, not your Wi-Fi interface.",
            "recommendation": "Restart your modem/gateway or check your ISP service plan subscription."
        })

    # Rule 4: Packet Loss
    if loss > 2.0:
        insights.append({
            "severity": "WARNING",
            "title": "Connection Stability Issue (Packet Loss)",
            "description": f"Observed {loss}% packet loss on the local wireless link. Packets are being dropped before reaching the router.",
            "recommendation": "Check for 2.4 GHz RF interference from microwaves, Bluetooth devices, or faulty router antennas."
        })

    # Rule 5: Channel Congestion
    if congestion >= 60:
        recommended_ch = channel_info.get("recommended_5ghz" if "5" in wifi_info.get("band", "") else "recommended_24ghz")
        insights.append({
            "severity": "WARNING",
            "title": "High Channel Congestion Detected",
            "description": f"Current channel {wifi_info.get('channel')} has high co-channel airtime interference from nearby access points.",
            "recommendation": f"Change your router's wireless channel to recommended channel {recommended_ch} to avoid co-channel collisions."
        })

    # Rule 6: Band Optimization
    if "2.4" in wifi_info.get("band", ""):
        insights.append({
            "severity": "INFO",
            "title": "Connected on 2.4 GHz Band",
            "description": "2.4 GHz provides long range but has limited bandwidth and high interference from household appliances.",
            "recommendation": "If your router supports 5 GHz, connect to the 5 GHz SSID for dramatically higher speeds and lower latency."
        })

    # Rule 7: Positive confirmation if healthy
    if not insights and final_score >= 80:
        insights.append({
            "severity": "SUCCESS",
            "title": "Network Performing Optimally",
            "description": f"Your connection to {wifi_info.get('ssid')} ({wifi_info.get('band')}, Ch {wifi_info.get('channel')}) is operating with low latency ({effective_latency} ms) and healthy signal ({rssi} dBm).",
            "recommendation": "No optimizations required at this time."
        })

    return {
        "health_score": final_score,
        "overall_status": overall_status,
        "breakdown": {
            "signal": sig_eval,
            "latency": lat_eval,
            "packet_loss": loss_eval,
            "speed": spd_eval,
            "congestion": cng_eval
        },
        "insights": insights
    }


if __name__ == "__main__":
    import json
    dummy_wifi = {"connected": True, "rssi": -42, "channel": 149, "band": "5 GHz", "ssid": "KITE-1F-202"}
    dummy_perf = {"wifi_hop_latency_ms": 9.0, "internet_latency_ms": 35.0, "packet_loss_pct": 0.0, "download_mbps": 95.0}
    dummy_chan = {"current_channel_congestion": 25, "recommended_5ghz": 36}
    res = calculate_health_and_diagnostics(dummy_wifi, dummy_perf, dummy_chan)
    print(json.dumps(res, indent=2))
