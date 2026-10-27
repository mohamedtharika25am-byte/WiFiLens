"""
WiFiLens - Wi-Fi Channel & RF Spectrum Analyzer
Analyzes:
- 2.4 GHz, 5 GHz, and 6 GHz spectrum allocation
- Per-channel AP density & signal distribution
- Co-channel interference (CCI) and adjacent-channel interference (ACI)
- Congestion scoring (0 - 100) per channel
- Optimal channel recommendations for 2.4 GHz (1, 6, 11) and 5 GHz
"""

import sys
import os
from typing import List, Dict, Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from backend.wifi_scanner import channel_to_frequency
except ImportError:
    from wifi_scanner import channel_to_frequency


# Standard non-overlapping channels
RECOMMENDED_24GHZ = [1, 6, 11]
COMMON_5GHZ_CHANNELS = [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144, 149, 153, 157, 161, 165]


def analyze_channels(networks: List[Dict[str, Any]], current_ap: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Computes comprehensive spectrum and channel statistics from scanned APs.
    """
    current_channel = (current_ap or {}).get("channel", 0)
    current_band = (current_ap or {}).get("band", "")

    # Group APs by band
    band_24_aps = []
    band_5_aps = []
    band_6_aps = []

    channel_map: Dict[int, List[Dict[str, Any]]] = {}

    for ap in networks:
        ch = ap.get("channel", 0)
        if ch <= 0:
            continue

        band = ap.get("band", "")
        if ch <= 14:
            band_24_aps.append(ap)
        elif ch <= 177:
            band_5_aps.append(ap)
        else:
            band_6_aps.append(ap)

        if ch not in channel_map:
            channel_map[ch] = []
        channel_map[ch].append(ap)

    # Congestion analysis for 2.4 GHz channels 1 - 14
    channels_24_summary = []
    for ch in range(1, 14):
        aps_on_ch = channel_map.get(ch, [])
        co_channel_count = len(aps_on_ch)

        # 2.4 GHz adjacent channel interference (within +/- 4 channels)
        adjacent_count = 0
        for adj_ch in range(max(1, ch - 4), min(14, ch + 5)):
            if adj_ch != ch:
                adjacent_count += len(channel_map.get(adj_ch, []))

        # Congestion score 0-100: weighted by co-channel (heavy) and adjacent (moderate)
        congestion = min(100, (co_channel_count * 25) + (adjacent_count * 10))

        channels_24_summary.append({
            "channel": ch,
            "frequency": channel_to_frequency(ch, "2.4 GHz"),
            "ap_count": co_channel_count,
            "adjacent_interference_count": adjacent_count,
            "congestion_score": congestion,
            "aps": [{"ssid": a.get("ssid"), "bssid": a.get("bssid"), "rssi": a.get("rssi")} for a in aps_on_ch],
            "is_current": (ch == current_channel and "2.4" in current_band)
        })

    # Congestion analysis for 5 GHz
    channels_5_summary = []
    for ch in COMMON_5GHZ_CHANNELS:
        aps_on_ch = channel_map.get(ch, [])
        co_channel_count = len(aps_on_ch)
        congestion = min(100, co_channel_count * 30)

        channels_5_summary.append({
            "channel": ch,
            "frequency": channel_to_frequency(ch, "5 GHz"),
            "ap_count": co_channel_count,
            "congestion_score": congestion,
            "aps": [{"ssid": a.get("ssid"), "bssid": a.get("bssid"), "rssi": a.get("rssi")} for a in aps_on_ch],
            "is_current": (ch == current_channel and "5" in current_band)
        })

    # Recommendations for 2.4 GHz
    best_24 = min(RECOMMENDED_24GHZ, key=lambda c: next((x["congestion_score"] for x in channels_24_summary if x["channel"] == c), 0))
    
    # Recommendations for 5 GHz
    best_5 = min(COMMON_5GHZ_CHANNELS, key=lambda c: next((x["congestion_score"] for x in channels_5_summary if x["channel"] == c), 0))

    # Evaluate current AP's channel quality
    current_ch_data = next((x for x in (channels_24_summary + channels_5_summary) if x["channel"] == current_channel), None)
    current_congestion = current_ch_data["congestion_score"] if current_ch_data else 0

    return {
        "current_channel": current_channel,
        "current_band": current_band,
        "current_channel_congestion": current_congestion,
        "recommended_24ghz": best_24,
        "recommended_5ghz": best_5,
        "channels_24": channels_24_summary,
        "channels_5": channels_5_summary,
        "total_24ghz_aps": len(band_24_aps),
        "total_5ghz_aps": len(band_5_aps),
        "total_6ghz_aps": len(band_6_aps)
    }


if __name__ == "__main__":
    from backend.wifi_scanner import scan_all_networks_windows, scan_current_interface_windows
    import json
    cur = scan_current_interface_windows()
    nets = scan_all_networks_windows()
    res = analyze_channels(nets, cur)
    print(json.dumps(res, indent=2))
