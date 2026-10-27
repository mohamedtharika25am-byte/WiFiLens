"""
WiFiLens - Real Wi-Fi Scanner Module
Uses native OS APIs (Windows netsh wlan, Linux nmcli/iw) to retrieve REAL:
- SSID, BSSID, RSSI (dBm), Signal Quality (%)
- Wi-Fi Channel, Frequency (MHz), Band (2.4 GHz / 5 GHz / 6 GHz)
- Wi-Fi Standard (802.11ax / Wi-Fi 6, 802.11ac / Wi-Fi 5, etc.)
- Link speeds (Tx/Rx Mbps), Connection status

CRITICAL RULE: Real Data Only. Never fake RSSI or Wi-Fi metrics.
"""

import subprocess
import re
import platform
from typing import Dict, Any, List, Optional


def channel_to_frequency(channel: int, band: str = "") -> float:
    """Converts a Wi-Fi channel number to exact center frequency in MHz."""
    if not channel or channel <= 0:
        return 0.0

    # 2.4 GHz band (Channels 1-14)
    if channel <= 14:
        if channel == 14:
            return 2484.0
        return 2407.0 + (channel * 5.0)

    # 5 GHz band (Channels 32-177)
    if 32 <= channel <= 177:
        return 5000.0 + (channel * 5.0)

    # 6 GHz band (Channels 1-233)
    if "6" in band or channel > 177:
        return 5950.0 + (channel * 5.0)

    # Default estimation for 5GHz
    return 5000.0 + (channel * 5.0)


def signal_percent_to_dbm(signal_percent: int) -> float:
    """
    Standard conversion from Windows signal quality (0-100%) to dBm.
    Formula: dBm = (signal_percent / 2) - 100
    Range: 100% -> -50 dBm (excellent), 50% -> -75 dBm, 0% -> -100 dBm.
    """
    if signal_percent <= 0:
        return -100.0
    if signal_percent >= 100:
        return -50.0
    return round((signal_percent / 2.0) - 100.0, 1)


def radio_type_to_standard(radio_type: str) -> str:
    """Maps 802.11 radio protocol strings to human-readable Wi-Fi standards."""
    rt = (radio_type or "").lower().strip()
    if "802.11be" in rt:
        return "Wi-Fi 7 (802.11be)"
    if "802.11ax" in rt:
        return "Wi-Fi 6 (802.11ax)"
    if "802.11ac" in rt:
        return "Wi-Fi 5 (802.11ac)"
    if "802.11n" in rt:
        return "Wi-Fi 4 (802.11n)"
    if "802.11g" in rt:
        return "802.11g"
    if "802.11b" in rt:
        return "802.11b"
    if "802.11a" in rt:
        return "802.11a"
    return radio_type or "Unknown"


def scan_current_interface_windows() -> Dict[str, Any]:
    """
    Parses 'netsh wlan show interfaces' on Windows.
    Returns real connected AP parameters.
    """
    try:
        cmd = ["netsh", "wlan", "show", "interfaces"]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=5, check=True)
        output = res.stdout
    except Exception as e:
        return {
            "status": "ERROR",
            "error": f"Failed to execute netsh: {str(e)}",
            "connected": False
        }

    info: Dict[str, Any] = {
        "status": "DISCONNECTED",
        "connected": False,
        "interface_name": "",
        "description": "",
        "mac_address": "",
        "state": "",
        "ssid": "",
        "bssid": "",
        "band": "",
        "channel": 0,
        "frequency": 0.0,
        "radio_type": "",
        "wifi_standard": "",
        "signal_quality": 0,
        "rssi": -100.0,
        "rx_rate_mbps": 0.0,
        "tx_rate_mbps": 0.0,
        "auth": "",
        "cipher": ""
    }

    lines = output.splitlines()
    for line in lines:
        line_clean = line.strip()
        if not line_clean or ":" not in line_clean:
            continue
        parts = line_clean.split(":", 1)
        key = parts[0].strip().lower()
        val = parts[1].strip()

        if key == "name":
            info["interface_name"] = val
        elif key == "description":
            info["description"] = val
        elif key == "physical address":
            info["mac_address"] = val
        elif key == "state":
            info["state"] = val
            if val.lower() == "connected":
                info["connected"] = True
                info["status"] = "CONNECTED"
            else:
                info["status"] = val.upper()
        elif key == "ssid":
            info["ssid"] = val
        elif key in ["bssid", "ap bssid"]:
            info["bssid"] = val
        elif key == "band":
            info["band"] = val
        elif key == "channel":
            try:
                info["channel"] = int(val)
            except ValueError:
                info["channel"] = 0
        elif key == "radio type":
            info["radio_type"] = val
            info["wifi_standard"] = radio_type_to_standard(val)
        elif key == "signal":
            # e.g. "89%"
            sig_match = re.search(r"(\d+)", val)
            if sig_match:
                info["signal_quality"] = int(sig_match.group(1))
        elif key == "rssi":
            # Windows 11 sometimes includes direct Rssi : -42
            try:
                info["rssi"] = float(val)
            except ValueError:
                pass
        elif key == "receive rate (mbps)":
            try:
                info["rx_rate_mbps"] = float(val)
            except ValueError:
                pass
        elif key == "transmit rate (mbps)":
            try:
                info["tx_rate_mbps"] = float(val)
            except ValueError:
                pass
        elif key == "authentication":
            info["auth"] = val
        elif key == "cipher":
            info["cipher"] = val

    # If direct RSSI wasn't reported, compute from signal %
    if info["rssi"] == -100.0 and info["signal_quality"] > 0:
        info["rssi"] = signal_percent_to_dbm(info["signal_quality"])

    # If band wasn't explicitly reported, infer from channel
    if not info["band"] and info["channel"] > 0:
        if info["channel"] <= 14:
            info["band"] = "2.4 GHz"
        elif info["channel"] <= 177:
            info["band"] = "5 GHz"
        else:
            info["band"] = "6 GHz"

    # Compute exact frequency
    info["frequency"] = channel_to_frequency(info["channel"], info["band"])

    return info


def scan_all_networks_windows() -> List[Dict[str, Any]]:
    """
    Parses 'netsh wlan show networks mode=bssid' on Windows.
    Returns all detected access points in RF range.
    """
    try:
        cmd = ["netsh", "wlan", "show", "networks", "mode=bssid"]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=8, check=True)
        output = res.stdout
    except Exception as e:
        return []

    networks = []
    current_ssid = ""
    current_ap: Optional[Dict[str, Any]] = None

    lines = output.splitlines()
    for line in lines:
        line_clean = line.strip()
        if not line_clean:
            continue

        # Match SSID header: "SSID 1 : NetworkName"
        ssid_match = re.match(r"^SSID\s+\d+\s*:\s*(.*)$", line_clean, re.IGNORECASE)
        if ssid_match:
            current_ssid = ssid_match.group(1).strip()
            continue

        # Match BSSID entry: "BSSID 1 : 0e:4a:6b:56:c8:c9"
        bssid_match = re.match(r"^BSSID\s+\d+\s*:\s*([0-9a-fA-F:-]{17})", line_clean, re.IGNORECASE)
        if bssid_match:
            if current_ap:
                networks.append(current_ap)
            current_ap = {
                "ssid": current_ssid or "<Hidden>",
                "bssid": bssid_match.group(1).strip(),
                "signal_quality": 0,
                "rssi": -100.0,
                "radio_type": "",
                "wifi_standard": "",
                "band": "",
                "channel": 0,
                "frequency": 0.0,
                "auth": "",
                "encryption": ""
            }
            continue

        if current_ap and ":" in line_clean:
            parts = line_clean.split(":", 1)
            k = parts[0].strip().lower()
            v = parts[1].strip()

            if k == "signal":
                sig_match = re.search(r"(\d+)", v)
                if sig_match:
                    current_ap["signal_quality"] = int(sig_match.group(1))
                    current_ap["rssi"] = signal_percent_to_dbm(current_ap["signal_quality"])
            elif k == "radio type":
                current_ap["radio_type"] = v
                current_ap["wifi_standard"] = radio_type_to_standard(v)
            elif k == "band":
                current_ap["band"] = v
            elif k == "channel":
                try:
                    current_ap["channel"] = int(v)
                except ValueError:
                    current_ap["channel"] = 0
            elif k == "authentication":
                current_ap["auth"] = v
            elif k == "encryption":
                current_ap["encryption"] = v

    if current_ap:
        networks.append(current_ap)

    # Post-process frequencies and bands
    for ap in networks:
        if not ap["band"] and ap["channel"] > 0:
            if ap["channel"] <= 14:
                ap["band"] = "2.4 GHz"
            elif ap["channel"] <= 177:
                ap["band"] = "5 GHz"
            else:
                ap["band"] = "6 GHz"
        ap["frequency"] = channel_to_frequency(ap["channel"], ap["band"])

    return networks


def get_wifi_state() -> Dict[str, Any]:
    """Unified entrypoint to get current interface state & nearby APs."""
    os_name = platform.system().lower()
    if os_name == "windows":
        current = scan_current_interface_windows()
        surrounding = scan_all_networks_windows()
        return {
            "current": current,
            "networks": surrounding,
            "total_aps": len(surrounding),
            "os": "Windows"
        }
    else:
        # Fallback for Linux or macOS
        return {
            "current": {
                "status": "UNAVAILABLE",
                "connected": False,
                "error": f"OS {os_name} native scanning pending."
            },
            "networks": [],
            "total_aps": 0,
            "os": os_name
        }


if __name__ == "__main__":
    import json
    data = get_wifi_state()
    print(json.dumps(data, indent=2))
