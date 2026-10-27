/**
 * WiFiLens — Floor Plan Studio & Calibration Controller
 * Manages floor plan rendering, pan/zoom, measurement point plotting,
 * AP marker positioning, and scale calibration.
 */

class FloorPlanStudio {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    this.ctx = this.canvas.getContext('2d');
    this.heatmap = new HeatmapEngine();

    this.floorplan = null;
    this.bgImage = null;
    this.points = [];
    this.apMarkers = [];

    // Viewport transform (Pan & Zoom)
    this.scale = 1.0;
    this.offsetX = 0;
    this.offsetY = 0;
    this.isDragging = false;
    this.dragStartX = 0;
    this.dragStartY = 0;

    // Interaction modes: 'survey', 'ap_marker', 'calibrate', 'pan'
    this.mode = 'survey';

    // Calibration state
    this.calibStep = 0;
    this.calibPointA = null;
    this.calibPointB = null;

    this.initEvents();
  }

  initEvents() {
    this.canvas.addEventListener('mousedown', (e) => this.onMouseDown(e));
    this.canvas.addEventListener('mousemove', (e) => this.onMouseMove(e));
    this.canvas.addEventListener('mouseup', () => this.onMouseUp());
    this.canvas.addEventListener('wheel', (e) => this.onWheel(e), { passive: false });

    window.addEventListener('resize', () => this.resizeCanvas());
    this.resizeCanvas();
  }

  resizeCanvas() {
    const parent = this.canvas.parentElement;
    if (parent) {
      this.canvas.width = parent.clientWidth;
      this.canvas.height = parent.clientHeight;
      this.draw();
    }
  }

  setMode(mode) {
    this.mode = mode;
    this.calibStep = 0;
    this.calibPointA = null;
    this.calibPointB = null;
    this.draw();
  }

  async loadActiveFloorplan() {
    try {
      const res = await fetch('/api/floorplans/active');
      const data = await res.json();
      if (data && data.id) {
        this.floorplan = data;
        await this.loadFloorplanImage(data.file_path);
        await this.loadData(data.id);
      }
    } catch (e) {
      console.error('Failed to load floorplan:', e);
    }
  }

  loadFloorplanImage(url) {
    return new Promise((resolve) => {
      const img = new Image();
      img.crossOrigin = 'anonymous';
      img.onload = () => {
        this.bgImage = img;
        this.fitToScreen();
        this.draw();
        resolve(true);
      };
      img.onerror = () => {
        console.warn('Image failed to load, using default canvas');
        this.bgImage = null;
        resolve(false);
      };
      img.src = url;
    });
  }

  async loadData(floorplanId) {
    try {
      const [ptsRes, mkrRes] = await Promise.all([
        fetch(`/api/floorplans/${floorplanId}/measurements`),
        fetch(`/api/floorplans/${floorplanId}/markers`)
      ]);
      this.points = await ptsRes.json();
      this.apMarkers = await mkrRes.json();
      this.draw();
    } catch (e) {
      console.error('Failed to load floorplan data:', e);
    }
  }

  fitToScreen() {
    if (!this.bgImage) return;
    const cw = this.canvas.width;
    const ch = this.canvas.height;
    const iw = this.bgImage.width || 1000;
    const ih = this.bgImage.height || 650;

    const scaleX = (cw * 0.95) / iw;
    const scaleY = (ch * 0.95) / ih;
    this.scale = Math.min(scaleX, scaleY, 1.2);

    this.offsetX = (cw - iw * this.scale) / 2;
    this.offsetY = (ch - ih * this.scale) / 2;
  }

  // Coordinate transformations
  screenToWorld(sx, sy) {
    return {
      x: (sx - this.offsetX) / this.scale,
      y: (sy - this.offsetY) / this.scale
    };
  }

  worldToScreen(wx, wy) {
    return {
      x: wx * this.scale + this.offsetX,
      y: wy * this.scale + this.offsetY
    };
  }

  onMouseDown(e) {
    const rect = this.canvas.getBoundingClientRect();
    const sx = e.clientX - rect.left;
    const sy = e.clientY - rect.top;

    if (e.button === 1 || this.mode === 'pan' || e.shiftKey) {
      // Middle click, Pan mode, or Shift+Click for drag
      this.isDragging = true;
      this.dragStartX = sx - this.offsetX;
      this.dragStartY = sy - this.offsetY;
      return;
    }

    const world = this.screenToWorld(sx, sy);

    if (this.mode === 'survey') {
      this.handleSurveyClick(world.x, world.y);
    } else if (this.mode === 'ap_marker') {
      this.handleAPMarkerClick(world.x, world.y);
    } else if (this.mode === 'calibrate') {
      this.handleCalibrateClick(world.x, world.y);
    }
  }

  onMouseMove(e) {
    const rect = this.canvas.getBoundingClientRect();
    const sx = e.clientX - rect.left;
    const sy = e.clientY - rect.top;

    if (this.isDragging) {
      this.offsetX = sx - this.dragStartX;
      this.offsetY = sy - this.dragStartY;
      this.draw();
      return;
    }

    // Hover tooltip detection
    const world = this.screenToWorld(sx, sy);
    this.checkHoverTooltip(world.x, world.y, sx, sy);
  }

  onMouseUp() {
    this.isDragging = false;
  }

  onWheel(e) {
    e.preventDefault();
    const rect = this.canvas.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    const zoomFactor = e.deltaY < 0 ? 1.12 : 0.88;
    const newScale = Math.max(0.2, Math.min(5.0, this.scale * zoomFactor));

    // Zoom toward mouse pointer
    this.offsetX = mouseX - (mouseX - this.offsetX) * (newScale / this.scale);
    this.offsetY = mouseY - (mouseY - this.offsetY) * (newScale / this.scale);
    this.scale = newScale;

    this.draw();
  }

  async handleSurveyClick(wx, wy) {
    // Record sample point at (wx, wy)
    if (!this.floorplan) return;
    try {
      const payload = {
        floorplan_id: this.floorplan.id,
        x: Math.round(wx),
        y: Math.round(wy),
        notes: `Survey point (${Math.round(wx)}, ${Math.round(wy)})`
      };

      const res = await fetch('/api/measurements', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (data.status === 'SUCCESS') {
        this.points.push(data.data);
        this.draw();
        if (window.showToast) {
          window.showToast(`Sample recorded: ${data.data.rssi} dBm on ${data.data.ssid}`, 'success');
        }
      }
    } catch (e) {
      console.error('Failed to record survey sample:', e);
    }
  }

  async handleAPMarkerClick(wx, wy) {
    if (!this.floorplan) return;
    const label = prompt('Enter Access Point Label:', 'Router / Access Point');
    if (!label) return;

    try {
      const payload = {
        floorplan_id: this.floorplan.id,
        x: Math.round(wx),
        y: Math.round(wy),
        label: label,
        ssid: 'Primary AP',
        band: '5 GHz',
        channel: 149
      };

      const res = await fetch('/api/floorplans/markers', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (data.status === 'SUCCESS') {
        this.apMarkers.push(data.marker);
        this.draw();
      }
    } catch (e) {
      console.error('Failed to add AP marker:', e);
    }
  }

  handleCalibrateClick(wx, wy) {
    if (this.calibStep === 0) {
      this.calibPointA = { x: wx, y: wy };
      this.calibStep = 1;
      this.draw();
      if (window.showToast) window.showToast('Point A set. Now click Point B on the floor plan.', 'info');
    } else if (this.calibStep === 1) {
      this.calibPointB = { x: wx, y: wy };
      this.draw();
      
      const dx = this.calibPointB.x - this.calibPointA.x;
      const dy = this.calibPointB.y - this.calibPointA.y;
      const pxDist = Math.sqrt(dx * dx + dy * dy);

      const metersStr = prompt(`Pixel distance is ${Math.round(pxDist)}px.\nEnter real-world distance in meters:`, '10.0');
      if (metersStr && !isNaN(parseFloat(metersStr))) {
        const meters = parseFloat(metersStr);
        this.saveCalibration(pxDist, meters);
      }
      this.calibStep = 0;
      this.calibPointA = null;
      this.calibPointB = null;
    }
  }

  async saveCalibration(px, meters) {
    if (!this.floorplan) return;
    try {
      const res = await fetch('/api/floorplans/scale', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          floorplan_id: this.floorplan.id,
          scale_pixels: px,
          scale_meters: meters
        })
      });
      const data = await res.json();
      if (data.status === 'SUCCESS') {
        this.floorplan.scale_pixels = px;
        this.floorplan.scale_meters = meters;
        if (window.showToast) {
          window.showToast(`Calibrated: ${data.ratio_px_per_meter} px/meter`, 'success');
        }
      }
    } catch (e) {
      console.error('Scale calibration failed:', e);
    }
  }

  draw() {
    const ctx = this.ctx;
    const w = this.canvas.width;
    const h = this.canvas.height;

    ctx.clearRect(0, 0, w, h);

    // Save initial state for zoom/pan transform
    ctx.save();
    ctx.translate(this.offsetX, this.offsetY);
    ctx.scale(this.scale, this.scale);

    // 1. Draw Floor Plan Image
    if (this.bgImage) {
      ctx.drawImage(this.bgImage, 0, 0);
    } else {
      // Empty blueprint background grid
      ctx.fillStyle = '#0f172a';
      ctx.fillRect(0, 0, 1000, 650);
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)';
      ctx.lineWidth = 1;
      for (let x = 0; x <= 1000; x += 40) {
        ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, 650); ctx.stroke();
      }
      for (let y = 0; y <= 650; y += 40) {
        ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(1000, y); ctx.stroke();
      }
    }

    // 2. Render Heatmap Layer
    if (this.points && this.points.length > 0) {
      const fpW = (this.bgImage && this.bgImage.width) || 1000;
      const fpH = (this.bgImage && this.bgImage.height) || 650;
      this.heatmap.render(ctx, fpW, fpH, this.points);
    }

    // 3. Draw AP Markers
    this.drawAPMarkers(ctx);

    // 4. Draw Survey Sample Points
    this.drawSamplePoints(ctx);

    // 5. Draw Calibration Line if active
    if (this.calibPointA) {
      ctx.strokeStyle = '#00f2fe';
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.arc(this.calibPointA.x, this.calibPointA.y, 6, 0, Math.PI * 2);
      ctx.fillStyle = '#00f2fe';
      ctx.fill();

      if (this.calibPointB) {
        ctx.arc(this.calibPointB.x, this.calibPointB.y, 6, 0, Math.PI * 2);
        ctx.fill();
        ctx.beginPath();
        ctx.moveTo(this.calibPointA.x, this.calibPointA.y);
        ctx.lineTo(this.calibPointB.x, this.calibPointB.y);
        ctx.stroke();
      }
    }

    ctx.restore();
  }

  drawAPMarkers(ctx) {
    for (const ap of this.apMarkers) {
      ctx.save();
      ctx.translate(ap.x, ap.y);

      // Glowing concentric waves
      ctx.beginPath();
      ctx.arc(0, 0, 24, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(0, 242, 254, 0.15)';
      ctx.fill();
      ctx.strokeStyle = '#00f2fe';
      ctx.lineWidth = 2;
      ctx.stroke();

      // Router Core Icon
      ctx.beginPath();
      ctx.arc(0, 0, 10, 0, Math.PI * 2);
      ctx.fillStyle = '#0284c7';
      ctx.fill();
      ctx.strokeStyle = '#fff';
      ctx.lineWidth = 2;
      ctx.stroke();

      // Label
      ctx.fillStyle = '#fff';
      ctx.font = 'bold 12px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(ap.label || 'AP', 0, -32);

      ctx.restore();
    }
  }

  drawSamplePoints(ctx) {
    let idx = 1;
    for (const pt of this.points) {
      if (pt.x === null || pt.y === null) continue;

      ctx.save();
      ctx.translate(pt.x, pt.y);

      // Point circle
      ctx.beginPath();
      ctx.arc(0, 0, 7, 0, Math.PI * 2);
      ctx.fillStyle = '#0f172a';
      ctx.fill();
      ctx.lineWidth = 2;
      ctx.strokeStyle = pt.rssi < -75 ? '#f43f5e' : '#10b981';
      ctx.stroke();

      // Inner dot
      ctx.beginPath();
      ctx.arc(0, 0, 3, 0, Math.PI * 2);
      ctx.fillStyle = '#fff';
      ctx.fill();

      // Point index label
      ctx.fillStyle = '#94a3b8';
      ctx.font = '9px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(idx.toString(), 0, 18);

      ctx.restore();
      idx++;
    }
  }

  checkHoverTooltip(wx, wy, sx, sy) {
    const tooltip = document.getElementById('canvas-tooltip');
    if (!tooltip) return;

    // Check if hovering over any point
    const hitPt = this.points.find(p => {
      const d = Math.hypot(p.x - wx, p.y - wy);
      return d < 15;
    });

    if (hitPt) {
      tooltip.style.display = 'block';
      tooltip.style.left = `${sx + 15}px`;
      tooltip.style.top = `${sy + 15}px`;
      tooltip.innerHTML = `
        <strong>${hitPt.ssid || 'Wi-Fi Point'}</strong><br/>
        Signal: <span style="color:#00f2fe;font-weight:bold">${hitPt.rssi} dBm</span> (${hitPt.signal_quality || 85}%)<br/>
        Speed: ${hitPt.download_speed ? hitPt.download_speed + ' Mbps' : 'N/A'}<br/>
        Latency: ${hitPt.ping_latency ? hitPt.ping_latency + ' ms' : 'N/A'}<br/>
        Health: ${hitPt.health_score ? hitPt.health_score + '/100' : 'N/A'}
      `;
      return;
    }

    tooltip.style.display = 'none';
  }

  exportImage() {
    const tempCanvas = document.createElement('canvas');
    const fpW = (this.bgImage && this.bgImage.width) || 1000;
    const fpH = (this.bgImage && this.bgImage.height) || 650;
    tempCanvas.width = fpW;
    tempCanvas.height = fpH;
    const tCtx = tempCanvas.getContext('2d');

    if (this.bgImage) tCtx.drawImage(this.bgImage, 0, 0);
    this.heatmap.render(tCtx, fpW, fpH, this.points);
    this.drawAPMarkers(tCtx);

    const dataUrl = tempCanvas.toDataURL('image/png');
    const a = document.createElement('a');
    a.href = dataUrl;
    a.download = `WiFiLens-Heatmap-${this.heatmap.metric}.png`;
    a.click();
  }
}

window.FloorPlanStudio = FloorPlanStudio;
