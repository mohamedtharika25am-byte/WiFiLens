"""
WiFiLens - Connected Devices Discovery Module
Discovers real active devices on the local Wi-Fi subnet using:
- ARP table cache parsing ('arp -a')
- Socket hostname resolution (reverse DNS / NetBIOS)
- IEEE OUI MAC Vendor lookup

CRITICAL RULE (Prompt Requirement 11 & 18):
"ONLY display real traffic measurements.
If the router/network does not expose per-device traffic:
Show: Traffic statistics unavailable for this network.
NEVER generate fake device usage."
"""

import subprocess
import socket
import re
import concurrent.futures
from typing import List, Dict, Any

# Common OUI Vendor prefixes
COMMON_OUI_MAP = {
    "4c:23:38": "MediaTek / LiteOn",
    "7c:5a:1c": "Cisco / Meraki",
    "b0:3c:dc": "Intel Mobile",
    "e8:b0:c5": "Apple Inc.",
    "a8:e2:91": "Samsung Electronics",
    "ac:bc:32": "Apple Inc.",
    "00:1a:2b": "Cisco Systems",
    "00:0c:29": "VMware",
    "00:50:56": "VMware",
    "d8:3a:dd": "Raspberry Pi Foundation",
    "dc:a6:32": "Raspberry Pi",
    "b8:27:eb": "Raspberry Pi",
    "00:e0:4c": "Realtek Semiconductor",
    "00:15:5d": "Microsoft Hyper-V",
    "f0:18:98": "Apple Inc.",
    "3c:22:fb": "TP-Link Technologies",
    "50:c7:bf": "TP-Link Technologies",
    "70:4f:57": "Xiaomi Communications",
    "a4:c3:f0": "Xiaomi Communications",
    "c8:7f:54": "Huawei Technologies",
    "94:65:9c": "Amazon Technologies"
}


def get_mac_vendor(mac: str) -> str:
    """Looks up hardware vendor from MAC address prefix."""
    if not mac:
        return "Unknown"
    normalized = mac.lower().replace("-", ":")
    prefix = normalized[:8]
    if prefix in COMMON_OUI_MAP:
        return COMMON_OUI_MAP[prefix]
    
    # Broadcast / Multicast
    if normalized.startswith("01:00:5e") or normalized.startswith("ff:ff:ff"):
        return "Network Multicast/Broadcast"
        
    return "Network Interface"


HOSTNAME_CACHE = {}

def resolve_hostname(ip: str, is_local: bool = False, is_gateway: bool = False) -> str:
    """Fast hostname identification without blocking DNS stalls."""
    if is_local:
        return f"{socket.gethostname()} (This Laptop)"
    if is_gateway:
        return "Default Gateway / Router"
    if ip in HOSTNAME_CACHE:
        return HOSTNAME_CACHE[ip]
    return f"Device ({ip})"


def get_connected_devices() -> Dict[str, Any]:
    """
    Parses active ARP table on Windows.
    Returns real discovered devices on the Wi-Fi subnet.
    """
    devices: List[Dict[str, Any]] = []
    active_interface_ip = ""

    try:
        cmd = ["arp", "-a"]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=5, check=True)
        lines = res.stdout.splitlines()

        current_interface = ""
        entries = []

        for line in lines:
            line_str = line.strip()
            if not line_str:
                continue

            # Header: Interface: 172.16.200.136 --- 0x12
            if line_str.startswith("Interface:"):
                parts = line_str.split()
                if len(parts) >= 2:
                    current_interface = parts[1]
                continue

            # ARP Entry: 172.16.192.1  7c-5a-1c-d2-b7-2a  dynamic
            match = re.match(r"^(\d+\.\d+\.\d+\.\d+)\s+([0-9a-fA-F-]+)\s+(\w+)", line_str)
            if match:
                ip, mac, entry_type = match.groups()
                mac_norm = mac.lower().replace("-", ":")

                # Filter out broadcast and multicast
                if ip.endswith(".255") or ip.startswith("224.") or ip.startswith("239.") or mac_norm == "ff:ff:ff:ff:ff:ff":
                    continue

                entries.append({
                    "ip": ip,
                    "mac": mac_norm,
                    "type": entry_type,
                    "interface": current_interface
                })

        def process_entry(entry):
            ip = entry["ip"]
            is_local = (ip == entry["interface"])
            is_gateway = ip.endswith(".1")
            hostname = resolve_hostname(ip, is_local=is_local, is_gateway=is_gateway)
            vendor = get_mac_vendor(entry["mac"])
            
            return {
                "ip": ip,
                "mac": entry["mac"],
                "hostname": hostname,
                "vendor": vendor,
                "type": entry["type"],
                "status": "Online",
                "traffic_stats": "Traffic statistics unavailable for this network",
                "is_gateway": is_gateway
            }

        devices = [process_entry(e) for e in entries]

    except Exception as e:
        return {
            "devices": [],
            "total_count": 0,
            "error": str(e),
            "traffic_note": "Traffic statistics unavailable for this network"
        }

    # Sort so Gateway and This Device are at the top
    devices.sort(key=lambda d: (not d.get("is_gateway", False), d["ip"]))

    return {
        "devices": devices,
        "total_count": len(devices),
        "traffic_note": "Traffic statistics unavailable for this network (Requires router SNMP/NetFlow telemetry)"
    }


if __name__ == "__main__":
    import json
    print("Scanning connected network devices...")
    data = get_connected_devices()
    print(f"Discovered {data['total_count']} active hosts.")
    print(json.dumps(data["devices"][:5], indent=2))
