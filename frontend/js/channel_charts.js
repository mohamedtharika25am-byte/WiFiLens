/**
 * WiFiLens — Channel Spectrum & RF Distribution Renderer
 * Renders 2.4 GHz overlapping channel bell curves and 5 GHz channel spectrum.
 * Inspired by WiFiAnalyzer reference architecture.
 */

class ChannelSpectrumVisualizer {
  constructor(canvas24Id, canvas5Id) {
    this.canvas24 = document.getElementById(canvas24Id);
    this.canvas5 = document.getElementById(canvas5Id);
    this.ctx24 = this.canvas24 ? this.canvas24.getContext('2d') : null;
    this.ctx5 = this.canvas5 ? this.canvas5.getContext('2d') : null;

    this.palette = [
      '#00f2fe', '#818cf8', '#10b981', '#f59e0b', '#ec4899', '#38bdf8', '#a855f7'
    ];
  }

  render(channelData, networks) {
    if (this.ctx24) this.render24Spectrum(channelData, networks);
    if (this.ctx5) this.render5Spectrum(channelData, networks);
  }

  render24Spectrum(channelData, networks) {
    const ctx = this.ctx24;
    const canvas = this.canvas24;
    const w = canvas.width = canvas.parentElement.clientWidth;
    const h = canvas.height = 240;

    ctx.clearRect(0, 0, w, h);

    const padLeft = 40;
    const padRight = 30;
    const padBottom = 35;
    const padTop = 20;

    const plotW = w - padLeft - padRight;
    const plotH = h - padTop - padBottom;

    // Y Axis: RSSI from -100 dBm (bottom) to -30 dBm (top)
    const minDbm = -100;
    const maxDbm = -30;

    const dbmToY = (dbm) => {
      const clamped = Math.max(minDbm, Math.min(maxDbm, dbm));
      const norm = (clamped - minDbm) / (maxDbm - minDbm);
      return padTop + plotH * (1.0 - norm);
    };

    // X Axis: Frequency from 2400 MHz to 2490 MHz
    const minFreq = 2400;
    const maxFreq = 2490;
    const freqToX = (freq) => {
      return padLeft + ((freq - minFreq) / (maxFreq - minFreq)) * plotW;
    };

    // Draw Grid Lines & Channel Numbers
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.08)';
    ctx.lineWidth = 1;
    ctx.fillStyle = '#64748b';
    ctx.font = '10px sans-serif';
    ctx.textAlign = 'center';

    for (let ch = 1; ch <= 13; ch++) {
      const freq = 2407 + ch * 5;
      const x = freqToX(freq);

      ctx.beginPath();
      ctx.moveTo(x, padTop);
      ctx.lineTo(x, padTop + plotH);
      ctx.stroke();

      // Channel label
      ctx.fillStyle = (ch === 1 || ch === 6 || ch === 11) ? '#00f2fe' : '#94a3b8';
      ctx.font = (ch === 1 || ch === 6 || ch === 11) ? 'bold 11px sans-serif' : '10px sans-serif';
      ctx.fillText(`Ch ${ch}`, x, h - 14);
      ctx.fillText(`${freq}`, x, h - 2);
    }

    // Y Axis dBm labels
    ctx.textAlign = 'right';
    ctx.fillStyle = '#64748b';
    for (let dbm = -90; dbm <= -30; dbm += 20) {
      const y = dbmToY(dbm);
      ctx.fillText(`${dbm}`, padLeft - 6, y + 4);
      ctx.beginPath();
      ctx.moveTo(padLeft, y);
      ctx.lineTo(padLeft + plotW, y);
      ctx.stroke();
    }

    // Filter 2.4 GHz APs
    const aps24 = (networks || []).filter(ap => (ap.channel <= 14 && ap.channel >= 1));

    // Render AP Parabolic Spectrum Curves
    let colorIdx = 0;
    for (const ap of aps24) {
      const ch = ap.channel;
      const centerFreq = 2407 + ch * 5;
      const peakDbm = ap.rssi || -75;
      const color = this.palette[colorIdx % this.palette.length];
      colorIdx++;

      // Curve spans 22 MHz (center +/- 11 MHz)
      const leftFreq = centerFreq - 11;
      const rightFreq = centerFreq + 11;

      ctx.save();
      ctx.beginPath();
      ctx.moveTo(freqToX(leftFreq), dbmToY(-100));

      const points = 30;
      for (let i = 0; i <= points; i++) {
        const curFreq = leftFreq + (i / points) * (rightFreq - leftFreq);
        // Parabolic / Gaussian bell curve
        const normDist = (curFreq - centerFreq) / 11.0;
        const curveFactor = Math.cos(normDist * (Math.PI / 2.0));
        const effectiveDbm = -100 + (peakDbm - (-100)) * Math.max(0, curveFactor);
        ctx.lineTo(freqToX(curFreq), dbmToY(effectiveDbm));
      }

      ctx.lineTo(freqToX(rightFreq), dbmToY(-100));
      ctx.closePath();

      // Semi-transparent gradient fill
      const grad = ctx.createLinearGradient(0, dbmToY(peakDbm), 0, dbmToY(-100));
      grad.addColorStop(0, color + '55');
      grad.addColorStop(1, color + '05');
      ctx.fillStyle = grad;
      ctx.fill();

      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.stroke();

      // SSID badge at peak
      ctx.fillStyle = '#fff';
      ctx.font = 'bold 10px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(`${ap.ssid} (${peakDbm} dBm)`, freqToX(centerFreq), dbmToY(peakDbm) - 8);

      ctx.restore();
    }

    if (aps24.length === 0) {
      ctx.fillStyle = '#94a3b8';
      ctx.font = '12px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('No active 2.4 GHz APs in current RF range', w / 2, h / 2);
    }
  }

  render5Spectrum(channelData, networks) {
    const ctx = this.ctx5;
    const canvas = this.canvas5;
    const w = canvas.width = canvas.parentElement.clientWidth;
    const h = canvas.height = 240;

    ctx.clearRect(0, 0, w, h);

    const padLeft = 40;
    const padRight = 30;
    const padBottom = 35;
    const padTop = 20;

    const plotW = w - padLeft - padRight;
    const plotH = h - padTop - padBottom;

    const minDbm = -100;
    const maxDbm = -30;
    const dbmToY = (dbm) => {
      const clamped = Math.max(minDbm, Math.min(maxDbm, dbm));
      const norm = (clamped - minDbm) / (maxDbm - minDbm);
      return padTop + plotH * (1.0 - norm);
    };

    // 5 GHz common channels
    const channels = [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144, 149, 153, 157, 161, 165];
    const chToX = (ch) => {
      const idx = channels.indexOf(ch);
      if (idx === -1) return padLeft + plotW / 2;
      return padLeft + (idx / (channels.length - 1)) * plotW;
    };

    // Draw Grid
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.08)';
    ctx.lineWidth = 1;
    ctx.fillStyle = '#64748b';
    ctx.font = '9px sans-serif';
    ctx.textAlign = 'center';

    for (const ch of channels) {
      const x = chToX(ch);
      if (ch === 36 || ch === 48 || ch === 100 || ch === 149 || ch === 165) {
        ctx.beginPath();
        ctx.moveTo(x, padTop);
        ctx.lineTo(x, padTop + plotH);
        ctx.stroke();
        ctx.fillText(`Ch ${ch}`, x, h - 14);
      }
    }

    // Y Axis dBm labels
    ctx.textAlign = 'right';
    for (let dbm = -90; dbm <= -30; dbm += 20) {
      const y = dbmToY(dbm);
      ctx.fillText(`${dbm}`, padLeft - 6, y + 4);
      ctx.beginPath();
      ctx.moveTo(padLeft, y);
      ctx.lineTo(padLeft + plotW, y);
      ctx.stroke();
    }

    // Filter 5 GHz APs
    const aps5 = (networks || []).filter(ap => (ap.channel > 14));

    let colorIdx = 0;
    for (const ap of aps5) {
      const ch = ap.channel;
      const x = chToX(ch);
      const peakDbm = ap.rssi || -75;
      const color = this.palette[colorIdx % this.palette.length];
      colorIdx++;

      // Non-overlapping block curve
      const blockWidth = 28;

      ctx.save();
      ctx.beginPath();
      ctx.moveTo(x - blockWidth, dbmToY(-100));
      ctx.lineTo(x - blockWidth + 6, dbmToY(peakDbm));
      ctx.lineTo(x + blockWidth - 6, dbmToY(peakDbm));
      ctx.lineTo(x + blockWidth, dbmToY(-100));
      ctx.closePath();

      const grad = ctx.createLinearGradient(0, dbmToY(peakDbm), 0, dbmToY(-100));
      grad.addColorStop(0, color + '66');
      grad.addColorStop(1, color + '08');
      ctx.fillStyle = grad;
      ctx.fill();

      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.stroke();

      // Label
      ctx.fillStyle = '#fff';
      ctx.font = 'bold 10px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(`${ap.ssid} (Ch ${ch})`, x, dbmToY(peakDbm) - 8);
      ctx.fillText(`${peakDbm} dBm`, x, dbmToY(peakDbm) - 20);

      ctx.restore();
    }
  }
}

window.ChannelSpectrumVisualizer = ChannelSpectrumVisualizer;
