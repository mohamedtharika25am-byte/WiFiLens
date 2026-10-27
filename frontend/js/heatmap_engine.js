/**
 * WiFiLens — Heatmap Rendering Engine
 * Implements Inverse Distance Weighting (IDW) spatial interpolation
 * for Signal (dBm), Speed (Mbps), Latency (ms), Stability (loss %), and Health Score.
 * 
 * Inspired by JWH2985/wifi-heatmap and professional GIS/RF survey methods.
 */

class HeatmapEngine {
  constructor() {
    this.power = 2.5; // IDW power parameter
    this.maxRadius = 220; // Pixel radius of RF propagation
    this.alpha = 0.65; // Heatmap overlay opacity
    this.metric = 'rssi'; // Default metric: 'rssi', 'download', 'latency', 'packet_loss', 'health'
    this.showWeakZones = true;
    this.weakThresholdDbm = -75.0;
  }

  setMetric(metric) {
    this.metric = metric;
  }

  setWeakZoneDetection(enabled) {
    this.showWeakZones = enabled;
  }

  /**
   * Color ramp generator for given value and metric
   * Returns [r, g, b, a] (0-255)
   */
  getColorForValue(val) {
    let t = 0; // Normalized 0.0 (worst) to 1.0 (best)

    if (this.metric === 'rssi') {
      // Range: -90 dBm (dead) to -45 dBm (maximum)
      t = (val - (-90)) / (-45 - (-90));
    } else if (this.metric === 'download') {
      // Range: 0 Mbps (poor) to 100 Mbps (blazing)
      t = Math.min(1.0, Math.max(0.0, val / 80.0));
    } else if (this.metric === 'latency') {
      // Inverted: 10 ms (best) to 150 ms (worst)
      t = 1.0 - Math.min(1.0, Math.max(0.0, (val - 10) / 130.0));
    } else if (this.metric === 'packet_loss') {
      // Inverted: 0% loss (best) to 10% loss (worst)
      t = 1.0 - Math.min(1.0, Math.max(0.0, val / 8.0));
    } else if (this.metric === 'health') {
      // Range: 0 to 100
      t = Math.min(1.0, Math.max(0.0, val / 100.0));
    }

    t = Math.max(0.0, Math.min(1.0, t));

    // Smooth Turbo / Thermal color palette
    // 0.0 -> Crimson Red [220, 38, 38]
    // 0.25 -> Orange [245, 158, 11]
    // 0.50 -> Gold/Yellow [234, 179, 8]
    // 0.75 -> Lime/Emerald Green [16, 185, 129]
    // 1.0 -> Cyan/Teal [0, 242, 254]
    let r, g, b;
    if (t < 0.25) {
      const seg = t / 0.25;
      r = Math.round(220 + (245 - 220) * seg);
      g = Math.round(38 + (158 - 38) * seg);
      b = Math.round(38 + (11 - 38) * seg);
    } else if (t < 0.50) {
      const seg = (t - 0.25) / 0.25;
      r = Math.round(245 + (234 - 245) * seg);
      g = Math.round(158 + (179 - 158) * seg);
      b = Math.round(11 + (8 - 11) * seg);
    } else if (t < 0.75) {
      const seg = (t - 0.50) / 0.25;
      r = Math.round(234 + (16 - 234) * seg);
      g = Math.round(179 + (185 - 179) * seg);
      b = Math.round(8 + (129 - 8) * seg);
    } else {
      const seg = (t - 0.75) / 0.25;
      r = Math.round(16 + (0 - 16) * seg);
      g = Math.round(185 + (242 - 185) * seg);
      b = Math.round(129 + (254 - 129) * seg);
    }

    return [r, g, b];
  }

  /**
   * Renders interpolated heatmap onto target canvas
   */
  render(targetCtx, width, height, points) {
    if (!points || points.length === 0) {
      return;
    }

    // Step size for downsampled fast calculation
    const step = 4;
    const cols = Math.ceil(width / step);
    const rows = Math.ceil(height / step);

    const offscreen = document.createElement('canvas');
    offscreen.width = cols;
    offscreen.height = rows;
    const offCtx = offscreen.getContext('2d');
    const imgData = offCtx.createImageData(cols, rows);
    const data = imgData.data;

    // Filter points that have coordinates
    const validPoints = points.filter(p => p.x !== null && p.y !== null && !isNaN(p.x) && !isNaN(p.y));
    if (validPoints.length === 0) return;

    // Extract metric values
    const prepared = validPoints.map(p => {
      let v = 0;
      if (this.metric === 'rssi') v = p.rssi || -75;
      else if (this.metric === 'download') v = p.download_speed || 0;
      else if (this.metric === 'latency') v = p.ping_latency || 25;
      else if (this.metric === 'packet_loss') v = p.packet_loss || 0;
      else if (this.metric === 'health') v = p.health_score || 80;
      return { x: p.x, y: p.y, val: v, rawRssi: p.rssi || -75 };
    });

    const maxR2 = this.maxRadius * this.maxRadius;

    // IDW Interpolation Loop
    for (let r = 0; r < rows; r++) {
      const py = r * step;
      for (let c = 0; c < cols; c++) {
        const px = c * step;

        let numerator = 0;
        let denominator = 0;
        let minDist2 = Infinity;
        let exactMatch = null;

        for (let i = 0; i < prepared.length; i++) {
          const pt = prepared[i];
          const dx = px - pt.x;
          const dy = py - pt.y;
          const d2 = dx * dx + dy * dy;

          if (d2 < minDist2) {
            minDist2 = d2;
          }

          if (d2 < 4) { // Exactly on point
            exactMatch = pt.val;
            break;
          }

          if (d2 <= maxR2) {
            const w = 1.0 / Math.pow(Math.sqrt(d2), this.power);
            numerator += w * pt.val;
            denominator += w;
          }
        }

        const idx = (r * cols + c) * 4;

        if (exactMatch !== null) {
          const rgb = this.getColorForValue(exactMatch);
          data[idx] = rgb[0];
          data[idx + 1] = rgb[1];
          data[idx + 2] = rgb[2];
          data[idx + 3] = Math.round(255 * this.alpha);
        } else if (denominator > 0 && minDist2 <= maxR2) {
          const interpolatedVal = numerator / denominator;
          const dist = Math.sqrt(minDist2);
          // Smooth edge falloff
          const edgeAlpha = Math.max(0.0, 1.0 - (dist / this.maxRadius));
          const finalAlpha = Math.round(255 * this.alpha * edgeAlpha);

          const rgb = this.getColorForValue(interpolatedVal);
          data[idx] = rgb[0];
          data[idx + 1] = rgb[1];
          data[idx + 2] = rgb[2];
          data[idx + 3] = finalAlpha;
        } else {
          // Out of RF radius: transparent
          data[idx + 3] = 0;
        }
      }
    }

    offCtx.putImageData(imgData, 0, 0);

    // Draw smoothed interpolated image onto target canvas
    targetCtx.save();
    targetCtx.imageSmoothingEnabled = true;
    targetCtx.drawImage(offscreen, 0, 0, width, height);

    // Highlight weak zones if enabled and metric is rssi
    if (this.showWeakZones && this.metric === 'rssi') {
      this.drawWeakZoneIndicators(targetCtx, prepared);
    }

    targetCtx.restore();
  }

  /**
   * Highlights sample points where RSSI is below threshold (< -75 dBm)
   */
  drawWeakZoneIndicators(ctx, points) {
    const weakPoints = points.filter(p => p.rawRssi < this.weakThresholdDbm);
    if (weakPoints.length === 0) return;

    ctx.save();
    for (const wp of weakPoints) {
      ctx.beginPath();
      ctx.arc(wp.x, wp.y, 45, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(244, 63, 94, 0.15)';
      ctx.fill();
      ctx.lineWidth = 2;
      ctx.setLineDash([4, 4]);
      ctx.strokeStyle = '#f43f5e';
      ctx.stroke();

      // Warning icon label
      ctx.fillStyle = '#f43f5e';
      ctx.font = 'bold 11px sans-serif';
      ctx.fillText(`Weak Zone (${wp.rawRssi} dBm)`, wp.x - 40, wp.y - 50);
    }
    ctx.restore();
  }
}

window.HeatmapEngine = HeatmapEngine;
