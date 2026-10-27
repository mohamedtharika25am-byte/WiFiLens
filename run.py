"""
WiFiLens - One-Click Launcher
Starts the FastAPI server, exposes on local Wi-Fi subnet for mobile pairing,
and launches the interactive desktop dashboard.
"""

import os
import sys
import socket
import webbrowser
import uvicorn


def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def print_banner(host_ip: str, port: int):
    banner = f"""
======================================================================
  __          ___ ______ _ _                    
  \\ \\        / (_)  ____(_) |                   
   \\ \\  /\\  / / _| |__   _| |     ___ _ __  ___ 
    \\ \\/  \\/ / | |  __| | | |    / _ \\ '_ \\/ __|
     \\  /\\  /  | | |    | | |___|  __/ | | \\__ \\
      \\/  \\/   |_|_|    |_|______\\___|_| |_|___/
                                                
  WiFiLens — See. Measure. Map. Optimize.
======================================================================
  [x] Backend Server     : http://127.0.0.1:{port}
  [x] Laptop Dashboard   : http://localhost:{port}
  [x] Mobile Scanner App : http://{host_ip}:{port}/mobile
  [x] Native Wi-Fi Engine: Windows netsh wlan + ARP + Gateway Ping
  [x] Background Monitor : 10-Minute Periodic Scheduler (Active)
======================================================================
  Scan the QR code on the desktop dashboard with your phone camera
  to pair the mobile scanner & AR overlay mode instantly!
======================================================================
"""
    print(banner)


def is_port_in_use(port: int) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            return s.connect_ex(('127.0.0.1', port)) == 0
    except Exception:
        return False


def find_free_port(preferred_port: int = 8000) -> int:
    """Checks if preferred port is free; if occupied, finds next open port."""
    for p in [preferred_port, 8500, 8080, 8888, 9000]:
        if not is_port_in_use(p):
            return p
    return 8500


def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(base_dir)
    sys.path.insert(0, base_dir)

    host_ip = get_local_ip()
    port = find_free_port(8000)
    print_banner(host_ip, port)

    # Automatically open desktop dashboard
    try:
        webbrowser.open(f"http://localhost:{port}")
    except Exception:
        pass

    uvicorn.run("backend.app:app", host="0.0.0.0", port=port, log_level="info", reload=False)


if __name__ == "__main__":
    main()
