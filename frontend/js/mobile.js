/**
 * WiFiLens — Mobile Scanner & Camera HUD Controller
 * Manages phone survey mode, camera HUD overlay, GPS sensors, and laptop synchronization.
 */

class MobileAppController {
  constructor() {
    this.ws = null;
    this.connected = false;
    this.wifi = {};
    this.floorplan = null;
    this.bgImage = null;
    this.surveyPoint = null;
    this.gps = null;

    this.videoStream = null;
    this.cameraActive = false;

    this.init();
  }

  async init() {
    this.initNavigation();
    this.initWebSocket();
    this.initGeolocation();
    await this.loadActiveFloorplan();
    this.initSurveyCanvas();
    this.bindEvents();

    // Regular polling fallback if ws drops
    setInterval(() => this.fetchTelemetry(), 3500);
  }

  initNavigation() {
    const navBtns = document.querySelectorAll('.mobile-nav-btn');
    navBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        navBtns.forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.mobile-pane').forEach(p => p.classList.remove('active'));

        btn.classList.add('active');
        const targetId = btn.getAttribute('data-pane');
        const targetPane = document.getElementById(targetId);
        if (targetPane) targetPane.classList.add('active');

        // Manage camera stream lifecycle
        if (targetId === 'pane-camera') {
          this.startCamera();
        } else {
          this.stopCamera();
        }

        if (targetId === 'pane-survey') {
          this.drawSurveyCanvas();
        }
      });
    });
  }

  // ==========================================
  // WebSocket Communication with Laptop
  // ==========================================
  initWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;

    this.updateStatus('reconnecting', 'Connecting...');
    this.ws = new WebSocket(wsUrl);

    this.ws.onopen = () => {
      this.connected = true;
      this.updateStatus('connected', 'CONNECTED');
      // Announce mobile presence
      this.ws.send(JSON.stringify({ type: 'mobile_telemetry', data: { status: 'online' } }));
    };

    this.ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === 'init' && msg.wifi) {
          this.updateTelemetryUI(msg.wifi);
        } else if (msg.type === 'new_measurement') {
          this.updateTelemetryUI(msg.data);
        }
      } catch (e) {
        console.error('WS Parse Error:', e);
      }
    };

    this.ws.onclose = () => {
      this.connected = false;
      this.updateStatus('disconnected', 'DISCONNECTED');
      setTimeout(() => this.initWebSocket(), 3000);
    };

    this.ws.onerror = () => {
      this.connected = false;
      this.updateStatus('disconnected', 'ERROR');
    };
  }

  updateStatus(state, label) {
    const pill = document.getElementById('mobile-conn-status');
    if (!pill) return;
    pill.className = `mobile-status-pill ${state}`;
    pill.textContent = label;
  }

  async fetchTelemetry() {
    try {
      const res = await fetch('/api/wifi/status');
      const data = await res.json();
      this.updateTelemetryUI(data);
    } catch (e) {
      console.warn('Telemetry fetch error:', e);
    }
  }

  updateTelemetryUI(wifi) {
    if (!wifi) return;
    this.wifi = wifi;

    // SSID & BSSID
    const ssidEl = document.getElementById('mob-ssid');
    if (ssidEl) ssidEl.textContent = wifi.ssid || 'Disconnected';

    const bssidEl = document.getElementById('mob-bssid');
    if (bssidEl) bssidEl.textContent = wifi.bssid ? `BSSID: ${wifi.bssid}` : '';

    // RSSI
    const rssiEl = document.getElementById('mob-rssi');
    if (rssiEl) rssiEl.textContent = wifi.rssi ? `${wifi.rssi}` : '--';

    // Submetrics
    const chanEl = document.getElementById('mob-channel');
    if (chanEl) chanEl.textContent = `${wifi.band || '5 GHz'} (Ch ${wifi.channel || 0})`;

    const stdEl = document.getElementById('mob-standard');
    if (stdEl) stdEl.textContent = wifi.wifi_standard || wifi.radio_type || '802.11';

    const rateEl = document.getElementById('mob-link-rate');
    if (rateEl) rateEl.textContent = wifi.rx_rate_mbps ? `${wifi.rx_rate_mbps} Mbps` : 'Connected';

    const qualEl = document.getElementById('mob-quality');
    if (qualEl) qualEl.textContent = `${wifi.signal_quality || 85}%`;

    // Update Camera HUD overlay
    this.updateCameraHud(wifi);
  }

  // ==========================================
  // Geolocation Sensor
  // ==========================================
  initGeolocation() {
    if ('geolocation' in navigator) {
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          this.gps = {
            latitude: pos.coords.latitude,
            longitude: pos.coords.longitude,
            accuracy: pos.coords.accuracy
          };
          const gpsEl = document.getElementById('mob-gps-status');
          if (gpsEl) gpsEl.textContent = `GPS: ±${Math.round(pos.coords.accuracy)}m`;
        },
        (err) => {
          console.warn('Geolocation denied or unavailable:', err.message);
          const gpsEl = document.getElementById('mob-gps-status');
          if (gpsEl) gpsEl.textContent = 'GPS: Unavailable';
        },
        { enableHighAccuracy: true, timeout: 5000 }
      );
    }
  }

  // ==========================================
  // Floor Plan Survey Mode
  // ==========================================
  async loadActiveFloorplan() {
    try {
      const res = await fetch('/api/floorplans/active');
      const data = await res.json();
      if (data && data.id) {
        this.floorplan = data;
        await this.loadFloorplanImage(data.file_path);
      }
    } catch (e) {
      console.error('Failed to load active floor plan:', e);
    }
  }

  loadFloorplanImage(url) {
    return new Promise((resolve) => {
      const img = new Image();
      img.crossOrigin = 'anonymous';
      img.onload = () => {
        this.bgImage = img;
        this.drawSurveyCanvas();
        resolve(true);
      };
      img.onerror = () => {
        this.bgImage = null;
        resolve(false);
      };
      img.src = url;
    });
  }

  initSurveyCanvas() {
    this.surveyCanvas = document.getElementById('mobile-survey-canvas');
    if (!this.surveyCanvas) return;
    this.sCtx = this.surveyCanvas.getContext('2d');

    const handleTap = (e) => {
      const rect = this.surveyCanvas.getBoundingClientRect();
      const clientX = e.touches ? e.touches[0].clientX : e.clientX;
      const clientY = e.touches ? e.touches[0].clientY : e.clientY;

      const sx = clientX - rect.left;
      const sy = clientY - rect.top;

      // Scale to image world coordinates
      const scaleX = (this.bgImage ? this.bgImage.width : 1000) / this.surveyCanvas.width;
      const scaleY = (this.bgImage ? this.bgImage.height : 650) / this.surveyCanvas.height;

      this.surveyPoint = {
        x: Math.round(sx * scaleX),
        y: Math.round(sy * scaleY)
      };

      this.drawSurveyCanvas();
    };

    this.surveyCanvas.addEventListener('touchstart', handleTap, { passive: true });
    this.surveyCanvas.addEventListener('click', handleTap);
  }

  drawSurveyCanvas() {
    if (!this.surveyCanvas || !this.sCtx) return;
    const cw = this.surveyCanvas.width = this.surveyCanvas.parentElement.clientWidth;
    const ch = this.surveyCanvas.height = 360;
    const ctx = this.sCtx;

    ctx.clearRect(0, 0, cw, ch);

    if (this.bgImage) {
      ctx.drawImage(this.bgImage, 0, 0, cw, ch);
    } else {
      ctx.fillStyle = '#0f172a';
      ctx.fillRect(0, 0, cw, ch);
    }

    // Draw active pinpoint target
    if (this.surveyPoint) {
      const scaleX = cw / (this.bgImage ? this.bgImage.width : 1000);
      const scaleY = ch / (this.bgImage ? this.bgImage.height : 650);
      const px = this.surveyPoint.x * scaleX;
      const py = this.surveyPoint.y * scaleY;

      // Animated target ring
      ctx.beginPath();
      ctx.arc(px, py, 18, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(0, 242, 254, 0.25)';
      ctx.fill();
      ctx.strokeStyle = '#00f2fe';
      ctx.lineWidth = 2.5;
      ctx.stroke();

      ctx.beginPath();
      ctx.arc(px, py, 5, 0, Math.PI * 2);
      ctx.fillStyle = '#fff';
      ctx.fill();
    }
  }

  // ==========================================
  // Camera HUD Mode
  // ==========================================
  async startCamera() {
    const video = document.getElementById('camera-video');
    if (!video) return;

    try {
      this.videoStream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'environment', width: { ideal: 1280 }, height: { ideal: 720 } },
        audio: false
      });
      video.srcObject = this.videoStream;
      video.play();
      this.cameraActive = true;
    } catch (err) {
      console.warn('Camera access denied or unavailable:', err.message);
      alert('Camera access permission required to display HUD overlay over your environment.');
    }
  }

  stopCamera() {
    if (this.videoStream) {
      this.videoStream.getTracks().forEach(track => track.stop());
      this.videoStream = null;
    }
    this.cameraActive = false;
  }

  updateCameraHud(wifi) {
    const hudSsid = document.getElementById('hud-ssid');
    const hudRssi = document.getElementById('hud-rssi');
    const hudBadge = document.getElementById('hud-status-badge');
    const hudDetails = document.getElementById('hud-details');

    if (hudSsid) hudSsid.textContent = wifi.ssid || 'Scanning...';
    if (hudRssi) hudRssi.textContent = wifi.rssi ? `${wifi.rssi} dBm` : '--';

    if (hudBadge) {
      let rating = 'GOOD';
      if (wifi.rssi >= -55) rating = 'EXCELLENT';
      else if (wifi.rssi < -75) rating = 'POOR';
      hudBadge.textContent = rating;
    }

    if (hudDetails) {
      hudDetails.textContent = `${wifi.wifi_standard || 'Wi-Fi'} | ${wifi.band || '5 GHz'} Ch ${wifi.channel || 0} | Ping: ~9ms`;
    }
  }

  takeSnapshot() {
    const video = document.getElementById('camera-video');
    if (!video) return;

    const snapCanvas = document.createElement('canvas');
    snapCanvas.width = video.videoWidth || 1280;
    snapCanvas.height = video.videoHeight || 720;
    const ctx = snapCanvas.getContext('2d');

    // Draw camera frame
    ctx.drawImage(video, 0, 0, snapCanvas.width, snapCanvas.height);

    // Draw HUD Watermark
    ctx.fillStyle = 'rgba(9, 14, 23, 0.85)';
    ctx.fillRect(20, 20, 420, 160);
    ctx.strokeStyle = '#00f2fe';
    ctx.lineWidth = 2;
    ctx.strokeRect(20, 20, 420, 160);

    ctx.fillStyle = '#00f2fe';
    ctx.font = 'bold 16px sans-serif';
    ctx.fillText('WiFiLens — Live Telemetry Lens', 40, 50);

    ctx.fillStyle = '#fff';
    ctx.font = 'bold 22px sans-serif';
    ctx.fillText(`SSID: ${this.wifi.ssid || 'N/A'}`, 40, 85);

    ctx.fillStyle = '#00f2fe';
    ctx.font = 'bold 26px sans-serif';
    ctx.fillText(`Signal: ${this.wifi.rssi || -75} dBm`, 40, 125);

    ctx.fillStyle = '#94a3b8';
    ctx.font = '13px sans-serif';
    ctx.fillText(`${this.wifi.wifi_standard || 'Wi-Fi 6'} | ${this.wifi.band || '5 GHz'} Ch ${this.wifi.channel || 0}`, 40, 155);

    // Download snapshot
    const dataUrl = snapCanvas.toDataURL('image/jpeg', 0.9);
    const a = document.createElement('a');
    a.href = dataUrl;
    a.download = `WiFiLens-Survey-Snapshot-${Date.now()}.jpg`;
    a.click();
  }

  bindEvents() {
    // Record Survey Button
    const recBtn = document.getElementById('btn-record-survey-point');
    if (recBtn) {
      recBtn.addEventListener('click', async () => {
        if (!this.surveyPoint) {
          alert('Please tap on your current position on the floor plan first!');
          return;
        }

        recBtn.disabled = true;
        recBtn.textContent = 'Recording Telemetry...';

        try {
          const payload = {
            source: 'phone',
            floorplan_id: this.floorplan ? this.floorplan.id : 'default-floorplan-01',
            x: this.surveyPoint.x,
            y: this.surveyPoint.y,
            latitude: this.gps ? this.gps.latitude : null,
            longitude: this.gps ? this.gps.longitude : null,
            notes: 'Mobile Survey Point'
          };

          const res = await fetch('/api/measurements', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
          });
          const data = await res.json();
          if (data.status === 'SUCCESS') {
            alert(`Point recorded at (${this.surveyPoint.x}, ${this.surveyPoint.y}): ${data.data.rssi} dBm`);
            this.surveyPoint = null;
            this.drawSurveyCanvas();
          }
        } catch (e) {
          alert('Failed to send measurement to laptop backend.');
        } finally {
          recBtn.disabled = false;
          recBtn.textContent = 'Record Sample Here';
        }
      });
    }

    // Camera Snapshot Button
    const snapBtn = document.getElementById('btn-camera-snap');
    if (snapBtn) {
      snapBtn.addEventListener('click', () => this.takeSnapshot());
    }
  }
}

window.addEventListener('DOMContentLoaded', () => {
  window.mobileApp = new MobileAppController();
});
