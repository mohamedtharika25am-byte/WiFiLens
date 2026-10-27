/**
 * WiFiLens — Master Dashboard Controller
 * Orchestrates live telemetry, WebSockets, health scoring,
 * history graphs, connected device discovery, and UI state.
 */

class DashboardController {
  constructor() {
    this.ws = null;
    this.wsConnected = false;
    this.wifiState = null;
    this.performanceState = null;
    this.diagnosticsState = null;
    this.devicesState = null;
    this.channelState = null;

    this.floorplanStudio = null;
    this.spectrumViz = null;

    this.init();
  }

  async init() {
    this.initNavigation();
    this.initFloorPlanStudio();
    this.initSpectrumVisualizer();
    this.initWebSocket();
    this.bindEvents();

    // Initial Data Fetch
    await this.refreshAll();

    // Periodic poll every 4 seconds for interface state
    setInterval(() => this.pollLiveTelemetry(), 4000);
  }

  initNavigation() {
    const tabs = document.querySelectorAll('.nav-tab');
    tabs.forEach(tab => {
      tab.addEventListener('click', () => {
        tabs.forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));

        tab.classList.add('active');
        const targetId = tab.getAttribute('data-tab');
        const targetPane = document.getElementById(targetId);
        if (targetPane) targetPane.classList.add('active');

        // Trigger canvas resize if switching to floor plan or spectrum
        if (targetId === 'tab-heatmap' && this.floorplanStudio) {
          setTimeout(() => this.floorplanStudio.resizeCanvas(), 50);
        } else if (targetId === 'tab-channels' && this.spectrumViz && this.channelState) {
          setTimeout(() => this.spectrumViz.render(this.channelState, this.wifiState?.networks || []), 50);
        } else if (targetId === 'tab-history') {
          this.loadHistoryCharts();
        }
      });
    });
  }

  initFloorPlanStudio() {
    if (document.getElementById('floorplan-canvas')) {
      this.floorplanStudio = new FloorPlanStudio('floorplan-canvas');
      this.floorplanStudio.loadActiveFloorplan();
    }
  }

  initSpectrumVisualizer() {
    this.spectrumViz = new ChannelSpectrumVisualizer('spectrum-24-canvas', 'spectrum-5-canvas');
  }

  // ==========================================
  // WebSocket Connectivity
  // ==========================================
  initWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;

    this.updateStatusPill('reconnecting', 'Connecting...');
    this.ws = new WebSocket(wsUrl);

    this.ws.onopen = () => {
      this.wsConnected = true;
      this.updateStatusPill('connected', 'Live Telemetry');
      console.log('WiFiLens WebSocket connected.');
    };

    this.ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        this.handleWebSocketMessage(msg);
      } catch (e) {
        console.error('WS Parse Error:', e);
      }
    };

    this.ws.onclose = () => {
      this.wsConnected = false;
      this.updateStatusPill('disconnected', 'Disconnected');
      // Retry connection after 3 seconds
      setTimeout(() => this.initWebSocket(), 3000);
    };

    this.ws.onerror = (err) => {
      console.error('WebSocket Error:', err);
    };
  }

  updateStatusPill(state, text) {
    const pill = document.getElementById('header-status-pill');
    const textSpan = document.getElementById('header-status-text');
    if (!pill || !textSpan) return;

    pill.className = `status-pill ${state}`;
    textSpan.textContent = text;
  }

  handleWebSocketMessage(msg) {
    if (msg.type === 'init') {
      if (msg.wifi) this.updateWifiUI(msg.wifi);
    } else if (msg.type === 'new_measurement') {
      this.showToast(`New Measurement Recorded: ${msg.data.rssi} dBm`, 'success');
      if (this.floorplanStudio) {
        this.floorplanStudio.points.push(msg.data);
        this.floorplanStudio.draw();
      }
      this.pollLiveTelemetry();
    } else if (msg.type === 'mobile_update') {
      this.showToast(`Mobile Scanner Sync Active`, 'info');
    }
  }

  // ==========================================
  // Data Polling & Updates
  // ==========================================
  async refreshAll() {
    await Promise.all([
      this.pollLiveTelemetry(),
      this.pollPerformance(false),
      this.pollDiagnostics(),
      this.pollChannels(),
      this.pollDevices()
    ]);
  }

  async pollLiveTelemetry() {
    try {
      const res = await fetch('/api/wifi/status');
      const data = await res.json();
      this.wifiState = { current: data };
      this.updateWifiUI(data);
    } catch (e) {
      console.error('Failed to poll Wi-Fi:', e);
    }
  }

  async pollPerformance(speedtest = false) {
    try {
      const res = await fetch(`/api/performance?speedtest=${speedtest}`);
      const data = await res.json();
      this.performanceState = data;
      this.updatePerformanceUI(data);
    } catch (e) {
      console.error('Failed to poll performance:', e);
    }
  }

  async pollDiagnostics() {
    try {
      const res = await fetch('/api/diagnostics');
      const data = await res.json();
      this.diagnosticsState = data;
      this.updateDiagnosticsUI(data);
    } catch (e) {
      console.error('Failed to poll diagnostics:', e);
    }
  }

  async pollChannels() {
    try {
      const res = await fetch('/api/channels');
      const data = await res.json();
      this.channelState = data;
      this.updateChannelsUI(data);
    } catch (e) {
      console.error('Failed to poll channels:', e);
    }
  }

  async pollDevices() {
    try {
      const res = await fetch('/api/devices');
      const data = await res.json();
      this.devicesState = data;
      this.updateDevicesUI(data);
    } catch (e) {
      console.error('Failed to poll devices:', e);
    }
  }

  // ==========================================
  // UI Renderers
  // ==========================================
  updateWifiUI(wifi) {
    if (!wifi) return;

    // SSID & Connection Status
    const ssidEl = document.getElementById('val-ssid');
    if (ssidEl) ssidEl.textContent = wifi.ssid || 'Disconnected';

    const bssidEl = document.getElementById('val-bssid');
    if (bssidEl) bssidEl.textContent = wifi.bssid ? `BSSID: ${wifi.bssid}` : 'No Access Point';

    // RSSI & Signal Quality
    const rssiValEl = document.getElementById('val-rssi');
    if (rssiValEl) rssiValEl.textContent = wifi.rssi ? `${wifi.rssi}` : '--';

    const sigPctEl = document.getElementById('val-signal-pct');
    if (sigPctEl) sigPctEl.textContent = `${wifi.signal_quality || 0}%`;

    // Circular Gauge
    const gaugeBar = document.getElementById('signal-gauge-bar');
    const gaugeNum = document.getElementById('signal-gauge-num');
    if (gaugeBar && gaugeNum) {
      const pct = Math.max(0, Math.min(100, wifi.signal_quality || 0));
      const circumference = 2 * Math.PI * 45; // r = 45
      const offset = circumference - (pct / 100) * circumference;
      gaugeBar.style.strokeDashoffset = offset;

      if (wifi.rssi >= -60) gaugeBar.style.stroke = 'var(--accent-emerald)';
      else if (wifi.rssi >= -75) gaugeBar.style.stroke = 'var(--accent-amber)';
      else gaugeBar.style.stroke = 'var(--accent-rose)';

      gaugeNum.textContent = wifi.rssi ? `${wifi.rssi}` : '--';
    }

    // Hardware & Protocol Details
    const stdEl = document.getElementById('val-standard');
    if (stdEl) stdEl.textContent = wifi.wifi_standard || wifi.radio_type || 'Unknown';

    const bandEl = document.getElementById('val-band');
    if (bandEl) bandEl.textContent = `${wifi.band || '5 GHz'} (Ch ${wifi.channel || 0})`;

    const rxTxEl = document.getElementById('val-link-rate');
    if (rxTxEl) {
      rxTxEl.textContent = (wifi.rx_rate_mbps > 0) ? `${wifi.rx_rate_mbps} / ${wifi.tx_rate_mbps} Mbps` : 'Negotiating';
    }
  }

  updatePerformanceUI(perf) {
    if (!perf) return;

    const hopEl = document.getElementById('val-wifi-hop');
    if (hopEl) hopEl.textContent = `${perf.wifi_hop_latency_ms} ms`;

    const inetEl = document.getElementById('val-inet-latency');
    if (inetEl) inetEl.textContent = `${perf.internet_latency_ms} ms`;

    const lossEl = document.getElementById('val-packet-loss');
    if (lossEl) lossEl.textContent = `${perf.packet_loss_pct}%`;

    const dlEl = document.getElementById('val-dl-speed');
    if (dlEl) {
      dlEl.textContent = perf.download_mbps > 0 ? `${perf.download_mbps}` : '--';
    }

    const ulEl = document.getElementById('val-ul-speed');
    if (ulEl) {
      ulEl.textContent = perf.upload_mbps > 0 ? `${perf.upload_mbps}` : '--';
    }
  }

  updateDiagnosticsUI(diag) {
    if (!diag) return;

    const scoreNum = document.getElementById('health-score-num');
    const scoreRating = document.getElementById('health-score-rating');
    const healthBar = document.getElementById('health-gauge-bar');

    if (scoreNum) scoreNum.textContent = diag.health_score;
    if (scoreRating) scoreRating.textContent = diag.overall_status;

    if (healthBar) {
      const circumference = 2 * Math.PI * 45;
      const offset = circumference - (diag.health_score / 100) * circumference;
      healthBar.style.strokeDashoffset = offset;
      if (diag.health_score >= 80) healthBar.style.stroke = 'var(--accent-emerald)';
      else if (diag.health_score >= 60) healthBar.style.stroke = 'var(--accent-amber)';
      else healthBar.style.stroke = 'var(--accent-rose)';
    }

    // Breakdown Bars
    if (diag.breakdown) {
      this.setBreakdownBar('breakdown-signal', diag.breakdown.signal);
      this.setBreakdownBar('breakdown-latency', diag.breakdown.latency);
      this.setBreakdownBar('breakdown-loss', diag.breakdown.packet_loss);
      this.setBreakdownBar('breakdown-speed', diag.breakdown.speed);
      this.setBreakdownBar('breakdown-congestion', diag.breakdown.congestion);
    }

    // Diagnostic Insights List
    const insightsList = document.getElementById('diagnostics-insights-list');
    if (insightsList && diag.insights) {
      insightsList.innerHTML = diag.insights.map(item => `
        <div class="insight-item ${item.severity.toLowerCase()}">
          <div class="insight-header">
            <span class="insight-badge ${item.severity.toLowerCase()}">${item.severity}</span>
            <span class="insight-title">${item.title}</span>
          </div>
          <p class="insight-desc">${item.description}</p>
          <div class="insight-recom"><strong>Recommendation:</strong> ${item.recommendation}</div>
        </div>
      `).join('');
    }
  }

  setBreakdownBar(id, item) {
    const el = document.getElementById(id);
    if (!el || !item) return;
    const bar = el.querySelector('.bar-fill');
    const label = el.querySelector('.bar-label');
    if (bar) bar.style.width = `${item.score}%`;
    if (label) label.textContent = `${item.rating} (${item.label})`;
  }

  updateChannelsUI(data) {
    if (!data) return;

    const rec24El = document.getElementById('rec-channel-24');
    if (rec24El) rec24El.textContent = `Channel ${data.recommended_24ghz}`;

    const rec5El = document.getElementById('rec-channel-5');
    if (rec5El) rec5El.textContent = `Channel ${data.recommended_5ghz}`;

    // Render Canvas Curves
    if (this.spectrumViz) {
      this.spectrumViz.render(data, this.wifiState?.networks || []);
    }
  }

  updateDevicesUI(data) {
    if (!data) return;

    const countEl = document.getElementById('devices-count-badge');
    if (countEl) countEl.textContent = `${data.total_count} Active Hosts`;

    const tableBody = document.getElementById('devices-table-body');
    if (tableBody) {
      tableBody.innerHTML = (data.devices || []).map(dev => `
        <tr>
          <td><strong style="color:#00f2fe">${dev.hostname}</strong></td>
          <td><code>${dev.ip}</code></td>
          <td><code>${dev.mac}</code></td>
          <td>${dev.vendor}</td>
          <td><span class="status-pill connected" style="padding:2px 8px;font-size:11px">Online</span></td>
          <td style="color:#94a3b8;font-style:italic">Traffic statistics unavailable for this network</td>
        </tr>
      `).join('');
    }
  }

  // ==========================================
  // Event Bindings
  // ==========================================
  bindEvents() {
    // Speed Test Button
    const speedBtn = document.getElementById('btn-run-speedtest');
    if (speedBtn) {
      speedBtn.addEventListener('click', async () => {
        speedBtn.disabled = true;
        speedBtn.innerHTML = '<span class="status-dot"></span> Testing Throughput...';
        this.showToast('Measuring live download and upload throughput...', 'info');

        try {
          const res = await fetch('/api/performance/test', { method: 'POST' });
          const data = await res.json();
          this.updatePerformanceUI(data);
          this.showToast(`Speed Test Complete: ${data.download_mbps} Mbps DL / ${data.upload_mbps} Mbps UL`, 'success');
        } catch (e) {
          this.showToast('Speed test error', 'error');
        } finally {
          speedBtn.disabled = false;
          speedBtn.innerHTML = 'Test Speed Now';
        }
      });
    }

    // Force Sample Button
    const sampleNowBtn = document.getElementById('btn-sample-now');
    if (sampleNowBtn) {
      sampleNowBtn.addEventListener('click', async () => {
        sampleNowBtn.disabled = true;
        try {
          const res = await fetch('/api/scheduler/sample-now', { method: 'POST' });
          const data = await res.json();
          if (data.status === 'SUCCESS') {
            this.showToast('Manual telemetry sample captured to database', 'success');
            await this.refreshAll();
          }
        } catch (e) {
          this.showToast('Sample error', 'error');
        } finally {
          sampleNowBtn.disabled = false;
        }
      });
    }

    // Heatmap Metric Buttons
    const metricBtns = document.querySelectorAll('.btn-metric');
    metricBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        metricBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        const metric = btn.getAttribute('data-metric');
        if (this.floorplanStudio) {
          this.floorplanStudio.heatmap.setMetric(metric);
          this.floorplanStudio.draw();
          this.updateHeatmapLegend(metric);
        }
      });
    });

    // Floor Plan Toolbar Buttons
    const toolBtns = document.querySelectorAll('.tool-mode-btn');
    toolBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        toolBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        const mode = btn.getAttribute('data-mode');
        if (this.floorplanStudio) this.floorplanStudio.setMode(mode);
      });
    });

    // Weak Zone Toggle
    const weakToggle = document.getElementById('toggle-weak-zones');
    if (weakToggle) {
      weakToggle.addEventListener('change', (e) => {
        if (this.floorplanStudio) {
          this.floorplanStudio.heatmap.setWeakZoneDetection(e.target.checked);
          this.floorplanStudio.draw();
        }
      });
    }

    // Export Heatmap Button
    const exportBtn = document.getElementById('btn-export-heatmap');
    if (exportBtn) {
      exportBtn.addEventListener('click', () => {
        if (this.floorplanStudio) this.floorplanStudio.exportImage();
      });
    }

    // Phone Pairing Modal
    const pairBtn = document.getElementById('btn-phone-pairing');
    const pairModal = document.getElementById('modal-phone-pairing');
    const closePairBtn = document.getElementById('btn-close-pair-modal');
    if (pairBtn && pairModal) {
      pairBtn.addEventListener('click', async () => {
        pairModal.classList.add('active');
        try {
          const res = await fetch('/api/network/host-info');
          const data = await res.json();
          const qrImg = document.getElementById('pair-qr-img');
          const urlLink = document.getElementById('pair-mobile-url');
          if (qrImg) qrImg.src = data.qr_code_b64;
          if (urlLink) {
            urlLink.href = data.mobile_url;
            urlLink.textContent = data.mobile_url;
          }
        } catch (e) {
          console.error('Pairing error:', e);
        }
      });
    }
    if (closePairBtn && pairModal) {
      closePairBtn.addEventListener('click', () => pairModal.classList.remove('active'));
    }

    // Floorplan Upload Form
    const fpForm = document.getElementById('form-upload-floorplan');
    if (fpForm) {
      fpForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(fpForm);
        try {
          const res = await fetch('/api/floorplans/upload', { method: 'POST', body: formData });
          const data = await res.json();
          if (data && data.id) {
            this.showToast('Floor plan uploaded successfully!', 'success');
            await this.floorplanStudio.loadActiveFloorplan();
            const uploadModal = document.getElementById('modal-upload-floorplan');
            if (uploadModal) uploadModal.classList.remove('active');
          }
        } catch (e) {
          this.showToast('Upload failed', 'error');
        }
      });
    }

    // Settings Form
    const settingsForm = document.getElementById('settings-form');
    if (settingsForm) {
      settingsForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const interval = document.getElementById('setting-interval').value;
        const enabled = document.getElementById('setting-enabled').checked ? '1' : '0';
        const speedOnInterval = document.getElementById('setting-speed-interval').checked ? '1' : '0';

        try {
          await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              monitor_interval_seconds: interval,
              monitor_enabled: enabled,
              speedtest_on_interval: speedOnInterval
            })
          });
          this.showToast('Monitoring settings saved successfully!', 'success');
        } catch (e) {
          this.showToast('Settings save failed', 'error');
        }
      });
    }
  }

  updateHeatmapLegend(metric) {
    const titleEl = document.getElementById('legend-metric-title');
    const barEl = document.getElementById('legend-gradient-bar');
    const minEl = document.getElementById('legend-min-label');
    const maxEl = document.getElementById('legend-max-label');
    if (!titleEl || !barEl) return;

    if (metric === 'rssi') {
      titleEl.textContent = 'Signal Strength (dBm)';
      barEl.style.background = 'linear-gradient(to right, #dc2626, #f59e0b, #eab308, #10b981, #00f2fe)';
      if (minEl) minEl.textContent = '-90 dBm (Weak)';
      if (maxEl) maxEl.textContent = '-45 dBm (Strong)';
    } else if (metric === 'download') {
      titleEl.textContent = 'Download Throughput (Mbps)';
      barEl.style.background = 'linear-gradient(to right, #dc2626, #f59e0b, #10b981, #00f2fe)';
      if (minEl) minEl.textContent = '0 Mbps';
      if (maxEl) maxEl.textContent = '100+ Mbps';
    } else if (metric === 'latency') {
      titleEl.textContent = 'Latency (ms)';
      barEl.style.background = 'linear-gradient(to right, #00f2fe, #10b981, #f59e0b, #dc2626)';
      if (minEl) minEl.textContent = '< 15 ms (Fast)';
      if (maxEl) maxEl.textContent = '> 120 ms (Lag)';
    } else if (metric === 'health') {
      titleEl.textContent = 'Wi-Fi Health Score';
      barEl.style.background = 'linear-gradient(to right, #dc2626, #f59e0b, #10b981, #00f2fe)';
      if (minEl) minEl.textContent = '0 (Critical)';
      if (maxEl) maxEl.textContent = '100 (Optimal)';
    }
  }

  async loadHistoryCharts() {
    try {
      const res = await fetch('/api/history/series?hours=24');
      const data = await res.json();
      this.renderHistoryCanvas('history-rssi-canvas', data.timestamps, data.rssi, 'Signal (dBm)', '#00f2fe', -100, -30);
      this.renderHistoryCanvas('history-speed-canvas', data.timestamps, data.download, 'Download (Mbps)', '#10b981', 0, 120);
      this.renderHistoryCanvas('history-latency-canvas', data.timestamps, data.latency, 'Latency (ms)', '#f59e0b', 0, 150);
    } catch (e) {
      console.error('History chart error:', e);
    }
  }

  renderHistoryCanvas(canvasId, labels, values, title, color, minY, maxY) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const w = canvas.width = canvas.parentElement.clientWidth;
    const h = canvas.height = 180;

    ctx.clearRect(0, 0, w, h);

    if (!values || values.length === 0) {
      ctx.fillStyle = '#64748b';
      ctx.font = '12px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(`No historical telemetry records logged yet for ${title}`, w / 2, h / 2);
      return;
    }

    const padLeft = 40;
    const padRight = 20;
    const padTop = 20;
    const padBottom = 25;
    const plotW = w - padLeft - padRight;
    const plotH = h - padTop - padBottom;

    // Grid lines
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)';
    ctx.lineWidth = 1;
    ctx.strokeRect(padLeft, padTop, plotW, plotH);

    // Plot line
    ctx.beginPath();
    ctx.strokeStyle = color;
    ctx.lineWidth = 2.5;

    for (let i = 0; i < values.length; i++) {
      const x = padLeft + (i / Math.max(1, values.length - 1)) * plotW;
      const v = values[i] !== null ? values[i] : minY;
      const normY = (v - minY) / (maxY - minY);
      const y = padTop + plotH * (1.0 - Math.max(0, Math.min(1, normY)));

      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();

    // Axis Labels
    ctx.fillStyle = '#94a3b8';
    ctx.font = '10px sans-serif';
    ctx.textAlign = 'right';
    ctx.fillText(`${maxY}`, padLeft - 6, padTop + 8);
    ctx.fillText(`${minY}`, padLeft - 6, padTop + plotH);
  }

  showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `<span>${message}</span>`;
    container.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transition = 'opacity 0.3s';
      setTimeout(() => toast.remove(), 300);
    }, 3500);
  }
}

window.showToast = (msg, type) => {
  if (window.dashboard) window.dashboard.showToast(msg, type);
};

window.addEventListener('DOMContentLoaded', () => {
  window.dashboard = new DashboardController();
});
