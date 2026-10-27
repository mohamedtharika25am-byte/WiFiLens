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


def find_free_port(preferred_port: int = 8000) -> int:
    """Checks if preferred port is free; if not, finds an open port."""
    for p in [preferred_port, 8500, 8080, 8888, 9000]:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("0.0.0.0", p))
            s.close()
            return p
        except OSError:
            continue
    return preferred_port


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
