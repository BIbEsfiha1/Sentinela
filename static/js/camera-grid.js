/* Sentinela - Live Camera Grid with WebRTC */

let webrtcConnections = {};

document.addEventListener('DOMContentLoaded', () => {
    loadDashboard();
    setInterval(loadStats, 10000);
});

async function loadDashboard() {
    await loadStats();
    await loadCameraGrid();
}

async function loadStats() {
    try {
        const s = await api('/api/status');
        document.getElementById('statCameras').textContent = s.cameras_total;
        document.getElementById('statRecording').textContent = s.cameras_recording;
        document.getElementById('statDisk').textContent = s.disk_free_gb + ' GB';
        document.getElementById('statRecSize').textContent = s.recordings_size_gb + ' GB';
        document.getElementById('statUptime').textContent = formatUptime(s.uptime_seconds);

        if (s.tunnel_active && s.tunnel_url) {
            document.getElementById('tunnelStat').style.display = '';
            document.getElementById('statTunnel').textContent = 'Ativo';
        }
    } catch (e) { /* ignore */ }
}

// ─── Aspect Ratio & Order Persistence ────────────────────────────────────────

const ASPECT_RATIOS = {
    '16:9': '16/9',
    '4:3': '4/3',
    '1:1': '1/1',
    '9:16': '9/16',
    'auto': 'auto',
};

function getCameraPrefs() {
    try { return JSON.parse(localStorage.getItem('cameraPrefs') || '{}'); }
    catch { return {}; }
}

function saveCameraPref(camId, key, value) {
    const prefs = getCameraPrefs();
    if (!prefs[camId]) prefs[camId] = {};
    prefs[camId][key] = value;
    localStorage.setItem('cameraPrefs', JSON.stringify(prefs));
}

function getCameraOrder() {
    try { return JSON.parse(localStorage.getItem('cameraOrder') || '[]'); }
    catch { return []; }
}

function saveCameraOrder(order) {
    localStorage.setItem('cameraOrder', JSON.stringify(order));
}

function sortCamerasByOrder(cameras) {
    const order = getCameraOrder();
    if (order.length === 0) return cameras;
    return cameras.slice().sort((a, b) => {
        const ia = order.indexOf(a.id);
        const ib = order.indexOf(b.id);
        if (ia === -1 && ib === -1) return 0;
        if (ia === -1) return 1;
        if (ib === -1) return -1;
        return ia - ib;
    });
}

async function loadCameraGrid() {
    try {
        const rawCameras = await api('/api/cameras');
        const cameras = sortCamerasByOrder(rawCameras);
        const grid = document.getElementById('cameraGrid');
        const empty = document.getElementById('noCameras');

        if (cameras.length === 0) {
            grid.classList.add('hidden');
            empty.classList.remove('hidden');
            return;
        }

        empty.classList.add('hidden');
        grid.classList.remove('hidden');

        const prefs = getCameraPrefs();

        grid.innerHTML = cameras.map(cam => {
            const aspect = (prefs[cam.id] && prefs[cam.id].aspect) || '16:9';
            const cssAspect = ASPECT_RATIOS[aspect] || '16/9';
            return `
            <div class="camera-card" id="cam-${cam.id}" draggable="true"
                 ondragstart="onCamDragStart(event, '${cam.id}')"
                 ondragover="onCamDragOver(event)"
                 ondrop="onCamDrop(event, '${cam.id}')"
                 ondragend="onCamDragEnd(event)">
                <div class="camera-video" id="video-${cam.id}"
                     style="aspect-ratio:${cssAspect}"
                     ondblclick="expandCamera('${cam.id}', '${escH(cam.name)}')">
                    <div class="no-signal">
                        <img src="/static/img/no-signal.svg" alt="" style="width:80px;opacity:0.5"><br>
                        <small>Conectando...</small>
                    </div>
                    <!-- Action Toolbar -->
                    <div class="camera-toolbar">
                        <button class="toolbar-btn" onclick="event.stopPropagation(); takeScreenshot('${cam.id}', '${escH(cam.name)}')" title="Screenshot (S)">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="12" cy="13" r="4"/><path d="M12 3v2"/></svg>
                            📸
                        </button>
                        <button class="toolbar-btn" onclick="event.stopPropagation(); toggleZoomMode('${cam.id}')" title="Zoom (Z)" id="zoomBtn-${cam.id}">
                            🔍
                        </button>
                        <button class="toolbar-btn" onclick="event.stopPropagation(); expandCamera('${cam.id}', '${escH(cam.name)}')" title="Expandir (F)">
                            ⛶
                        </button>
                    </div>
                    <!-- Zoom indicator -->
                    <div class="zoom-indicator" id="zoomLevel-${cam.id}" style="display:none">1.0x</div>
                </div>
                <div class="camera-info">
                    <div class="camera-info-left">
                        <span class="camera-drag-handle" title="Arraste para reorganizar">⠿</span>
                        <span class="camera-name">${escH(cam.name)}</span>
                    </div>
                    <div class="camera-info-right">
                        <div class="aspect-selector" onclick="event.stopPropagation()">
                            ${Object.keys(ASPECT_RATIOS).map(r =>
                `<button class="aspect-btn ${r === aspect ? 'active' : ''}"
                                         onclick="setAspect('${cam.id}', '${r}')"
                                         title="${r}">${r}</button>`
            ).join('')}
                        </div>
                        <span class="camera-status">
                            ${cam.enabled ? statusBadgeHtml(cam.status) : '<span class="badge badge-offline">Desabilitada</span>'}
                        </span>
                    </div>
                </div>
            </div>
        `}).join('');

        // Start WebRTC for each camera
        for (const cam of cameras) {
            if (cam.enabled) {
                startWebRTC(cam.id);
            }
        }
    } catch (e) {
        document.getElementById('cameraGrid').innerHTML =
            `<div class="alert alert-danger">Erro: ${escH(e.message)}</div>`;
    }
}

// ─── Aspect Ratio Control ────────────────────────────────────────────────────

function setAspect(camId, ratio) {
    saveCameraPref(camId, 'aspect', ratio);
    const videoEl = document.getElementById(`video-${camId}`);
    if (videoEl) {
        videoEl.style.aspectRatio = ASPECT_RATIOS[ratio] || '16/9';
    }
    // Update button states
    const card = document.getElementById(`cam-${camId}`);
    if (card) {
        card.querySelectorAll('.aspect-btn').forEach(btn => {
            btn.classList.toggle('active', btn.textContent.trim() === ratio);
        });
    }
}

// ─── Drag & Drop Reorder ─────────────────────────────────────────────────────

let draggedCamId = null;

function onCamDragStart(e, camId) {
    draggedCamId = camId;
    e.dataTransfer.effectAllowed = 'move';
    e.target.closest('.camera-card').classList.add('dragging');
}

function onCamDragOver(e) {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    const card = e.target.closest('.camera-card');
    if (card) card.classList.add('drag-over');
}

function onCamDrop(e, targetCamId) {
    e.preventDefault();
    const card = e.target.closest('.camera-card');
    if (card) card.classList.remove('drag-over');

    if (!draggedCamId || draggedCamId === targetCamId) return;

    // Reorder in DOM
    const grid = document.getElementById('cameraGrid');
    const cards = [...grid.querySelectorAll('.camera-card')];
    const ids = cards.map(c => c.id.replace('cam-', ''));
    const fromIdx = ids.indexOf(draggedCamId);
    const toIdx = ids.indexOf(targetCamId);

    if (fromIdx === -1 || toIdx === -1) return;

    // Move element
    ids.splice(fromIdx, 1);
    ids.splice(toIdx, 0, draggedCamId);
    saveCameraOrder(ids);

    // Rearrange DOM without re-rendering (preserves video streams)
    const orderedCards = ids.map(id => document.getElementById(`cam-${id}`)).filter(Boolean);
    orderedCards.forEach(c => grid.appendChild(c));
}

function onCamDragEnd(e) {
    draggedCamId = null;
    document.querySelectorAll('.camera-card').forEach(c => {
        c.classList.remove('dragging', 'drag-over');
    });
}

function statusBadgeHtml(status) {
    const m = {
        recording: '<span class="badge badge-recording">Gravando</span>',
        online: '<span class="badge badge-online">Online</span>',
        offline: '<span class="badge badge-offline">Offline</span>',
        error: '<span class="badge badge-error">Erro</span>',
    };
    return m[status] || m.offline;
}

let retryCount = {};
const MAX_RETRIES = 10;

async function startWebRTC(cameraId) {
    const container = document.getElementById(`video-${cameraId}`);
    if (!container) return;

    // Track retries
    if (!retryCount[cameraId]) retryCount[cameraId] = 0;

    // Stop if exceeded max retries
    if (retryCount[cameraId] > MAX_RETRIES) {
        container.innerHTML = `
            <div class="no-signal">
                <img src="/static/img/no-signal.svg" alt="" style="width:64px;opacity:0.4"><br>
                <small style="color:#ff6b6b">Camera indisponivel</small><br>
                <small style="color:#aaa">Verifique rede e credenciais</small><br>
                <button onclick="retryCount['${cameraId}']=0; startWebRTC('${cameraId}')" class="btn btn-sm btn-secondary" style="margin-top:8px;font-size:0.7rem">Tentar novamente</button>
            </div>`;
        return;
    }

    const whepUrl = `${window.location.origin}/api/whep/${cameraId}`;
    console.log(`[${cameraId}] Starting WebRTC (attempt ${retryCount[cameraId]}), WHEP: ${whepUrl}`);

    try {
        // Close previous connection if any
        if (webrtcConnections[cameraId]) {
            webrtcConnections[cameraId].close();
            delete webrtcConnections[cameraId];
        }

        const pc = new RTCPeerConnection({
            iceServers: [{ urls: 'stun:stun.l.google.com:19302' }],
        });

        webrtcConnections[cameraId] = pc;

        pc.ontrack = (evt) => {
            console.log(`[${cameraId}] ontrack: kind=${evt.track.kind}, readyState=${evt.track.readyState}`);

            // Only create video element once (on first track, usually video)
            if (container.querySelector('video')) {
                // Video already created, just add this track's stream
                const existing = container.querySelector('video');
                if (!existing.srcObject) {
                    existing.srcObject = evt.streams[0];
                }
                return;
            }

            const video = document.createElement('video');
            video.srcObject = evt.streams[0];
            video.autoplay = true;
            video.muted = true;
            video.playsInline = true;
            video.style.width = '100%';
            video.style.height = '100%';
            video.style.objectFit = 'contain';
            video.style.background = '#000';

            // Debug: monitor video state
            video.onloadedmetadata = () => {
                console.log(`[${cameraId}] Video metadata: ${video.videoWidth}x${video.videoHeight}`);
            };
            video.onplaying = () => {
                console.log(`[${cameraId}] Video PLAYING`);
                retryCount[cameraId] = 0; // Reset on success
            };
            video.onerror = (e) => {
                console.error(`[${cameraId}] Video error:`, e);
            };

            container.innerHTML = '';
            container.appendChild(video);

            // Force play
            video.play().then(() => {
                console.log(`[${cameraId}] play() OK`);
                retryCount[cameraId] = 0;
            }).catch(err => {
                console.warn(`[${cameraId}] play() blocked:`, err);
            });
        };

        pc.oniceconnectionstatechange = () => {
            console.log(`[${cameraId}] ICE state: ${pc.iceConnectionState}`);
            if (pc.iceConnectionState === 'failed' || pc.iceConnectionState === 'disconnected') {
                retryCount[cameraId]++;
                if (retryCount[cameraId] <= MAX_RETRIES) {
                    setTimeout(() => startWebRTC(cameraId), 5000);
                }
            }
        };

        pc.onconnectionstatechange = () => {
            console.log(`[${cameraId}] Connection state: ${pc.connectionState}`);
        };

        pc.addTransceiver('video', { direction: 'recvonly' });
        pc.addTransceiver('audio', { direction: 'recvonly' });

        const offer = await pc.createOffer();
        await pc.setLocalDescription(offer);

        await new Promise((resolve) => {
            if (pc.iceGatheringState === 'complete') {
                resolve();
            } else {
                const checkState = () => {
                    if (pc.iceGatheringState === 'complete') {
                        pc.removeEventListener('icegatheringstatechange', checkState);
                        resolve();
                    }
                };
                pc.addEventListener('icegatheringstatechange', checkState);
                setTimeout(resolve, 2000);
            }
        });

        console.log(`[${cameraId}] Sending WHEP offer...`);
        const res = await fetch(whepUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/sdp' },
            body: pc.localDescription.sdp,
        });

        console.log(`[${cameraId}] WHEP response: ${res.status}`);

        if (res.ok) {
            const answer = await res.text();
            await pc.setRemoteDescription({ type: 'answer', sdp: answer });
            console.log(`[${cameraId}] Remote description set`);
        } else if (res.status === 400) {
            pc.close();
            retryCount[cameraId]++;
            console.warn(`[${cameraId}] WHEP 400, retry ${retryCount[cameraId]}/${MAX_RETRIES}`);
            container.innerHTML = `
                <div class="no-signal">
                    <div class="spinner" style="margin:0 auto 8px"></div>
                    <small style="color:#ffa500">Aguardando stream...</small><br>
                    <small style="color:#666">Tentativa ${retryCount[cameraId]}/${MAX_RETRIES}</small>
                </div>`;
            setTimeout(() => startWebRTC(cameraId), 10000);
            return;
        } else if (res.status === 404) {
            pc.close();
            retryCount[cameraId]++;
            console.log(`[${cameraId}] Stream not ready, retry ${retryCount[cameraId]}/${MAX_RETRIES}`);
            container.innerHTML = `
                <div class="no-signal">
                    <div class="spinner" style="margin:0 auto 8px"></div>
                    <small style="color:#ffa500">Iniciando stream...</small><br>
                    <small style="color:#666">Tentativa ${retryCount[cameraId]}/${MAX_RETRIES}</small>
                </div>`;
            setTimeout(() => startWebRTC(cameraId), 5000);
            return;
        } else {
            throw new Error(`WHEP ${res.status}`);
        }
    } catch (e) {
        console.error(`[${cameraId}] WebRTC error:`, e);
        retryCount[cameraId]++;
        container.innerHTML = `
            <div class="no-signal">
                <img src="/static/img/no-signal.svg" alt="" style="width:64px;opacity:0.4"><br>
                <small style="color:#ffa500">Conectando...</small><br>
                <small style="color:#666">Tentativa ${retryCount[cameraId]}/${MAX_RETRIES}</small>
            </div>`;
        if (retryCount[cameraId] <= MAX_RETRIES) {
            setTimeout(() => startWebRTC(cameraId), 10000);
        } else {
            container.innerHTML = `
                <div class="no-signal">
                    <img src="/static/img/no-signal.svg" alt="" style="width:64px;opacity:0.4"><br>
                    <small style="color:#ff6b6b">Camera indisponivel</small><br>
                    <small style="color:#aaa">Verifique rede e credenciais</small><br>
                    <a href="/cameras" class="btn btn-sm btn-secondary" style="margin-top:8px;font-size:0.7rem">Configurar</a>
                </div>`;
        }
    }
}

function escH(s) {
    const d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
}

// ─── Screenshot ─────────────────────────────────────────────────────────────

function takeScreenshot(cameraId, cameraName) {
    const container = document.getElementById(`video-${cameraId}`);
    // Check fullscreen video too
    const fullscreenOverlay = document.getElementById('cameraFullscreen');
    let video = null;
    if (fullscreenOverlay) {
        video = fullscreenOverlay.querySelector('video');
    }
    if (!video) {
        video = container ? container.querySelector('video') : null;
    }

    if (!video || !video.videoWidth) {
        showToast('Sem video para capturar', 'warning');
        return;
    }

    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(video, 0, 0);

    const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
    const filename = `${cameraName || cameraId}_${timestamp}.png`;

    canvas.toBlob((blob) => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.click();
        URL.revokeObjectURL(url);
        showToast(`📸 Screenshot salvo: ${filename}`, 'success');
    }, 'image/png');
}

// ─── Toast Notifications ────────────────────────────────────────────────────

function showToast(message, type = 'info') {
    let container = document.getElementById('toastContainer');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toastContainer';
        container.style.cssText = `
            position:fixed; bottom:20px; right:20px; z-index:99999;
            display:flex; flex-direction:column-reverse; gap:8px;
        `;
        document.body.appendChild(container);
    }

    const colors = {
        success: '#22c55e',
        warning: '#f59e0b',
        error: '#ef4444',
        info: '#3b82f6',
    };

    const toast = document.createElement('div');
    toast.style.cssText = `
        background:rgba(20,20,30,0.95); backdrop-filter:blur(12px);
        border:1px solid ${colors[type] || colors.info};
        border-left:4px solid ${colors[type] || colors.info};
        color:#e4e6f0; padding:12px 16px; border-radius:8px;
        font-size:0.85rem; max-width:350px; box-shadow:0 8px 24px rgba(0,0,0,0.5);
        animation: toastIn 0.3s ease;
    `;
    toast.textContent = message;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.animation = 'toastOut 0.3s ease forwards';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// ─── Digital Zoom (Pan & Zoom) ──────────────────────────────────────────────

const zoomState = {}; // { camId: { scale, panX, panY, active, dragging, lastX, lastY } }

function getZoom(camId) {
    if (!zoomState[camId]) {
        zoomState[camId] = { scale: 1, panX: 0, panY: 0, active: false, dragging: false, lastX: 0, lastY: 0 };
    }
    return zoomState[camId];
}

function toggleZoomMode(camId) {
    const z = getZoom(camId);
    z.active = !z.active;
    const btn = document.getElementById(`zoomBtn-${camId}`);
    if (btn) btn.classList.toggle('active', z.active);

    if (!z.active) {
        resetZoom(camId);
    } else {
        showToast('🔍 Zoom ativado: scroll para zoom, arraste para mover', 'info');
        setupZoomListeners(camId);
    }
}

function resetZoom(camId) {
    const z = getZoom(camId);
    z.scale = 1;
    z.panX = 0;
    z.panY = 0;
    applyZoomTransform(camId);
    const indicator = document.getElementById(`zoomLevel-${camId}`);
    if (indicator) indicator.style.display = 'none';
}

function applyZoomTransform(camId) {
    const z = getZoom(camId);
    const container = document.getElementById(`video-${camId}`);
    if (!container) return;
    const video = container.querySelector('video');
    if (!video) return;
    video.style.transform = `scale(${z.scale}) translate(${z.panX}px, ${z.panY}px)`;
    video.style.transformOrigin = 'center center';

    const indicator = document.getElementById(`zoomLevel-${camId}`);
    if (indicator) {
        if (z.scale > 1.05) {
            indicator.style.display = 'block';
            indicator.textContent = `${z.scale.toFixed(1)}x`;
        } else {
            indicator.style.display = 'none';
        }
    }
}

function setupZoomListeners(camId) {
    const container = document.getElementById(`video-${camId}`);
    if (!container || container.dataset.zoomSetup) return;
    container.dataset.zoomSetup = 'true';

    // Mouse wheel zoom
    container.addEventListener('wheel', (e) => {
        const z = getZoom(camId);
        if (!z.active) return;
        e.preventDefault();
        e.stopPropagation();

        const delta = e.deltaY > 0 ? -0.2 : 0.2;
        z.scale = Math.max(1, Math.min(5, z.scale + delta));

        if (z.scale <= 1) {
            z.panX = 0;
            z.panY = 0;
        }
        applyZoomTransform(camId);
    }, { passive: false });

    // Mouse drag pan
    container.addEventListener('mousedown', (e) => {
        const z = getZoom(camId);
        if (!z.active || z.scale <= 1) return;
        e.preventDefault();
        z.dragging = true;
        z.lastX = e.clientX;
        z.lastY = e.clientY;
        container.style.cursor = 'grabbing';
    });

    document.addEventListener('mousemove', (e) => {
        const z = getZoom(camId);
        if (!z.dragging) return;
        const dx = (e.clientX - z.lastX) / z.scale;
        const dy = (e.clientY - z.lastY) / z.scale;
        z.panX += dx;
        z.panY += dy;
        z.lastX = e.clientX;
        z.lastY = e.clientY;
        applyZoomTransform(camId);
    });

    document.addEventListener('mouseup', () => {
        const z = getZoom(camId);
        if (z.dragging) {
            z.dragging = false;
            container.style.cursor = z.active && z.scale > 1 ? 'grab' : '';
        }
    });

    // Touch pinch-to-zoom
    let lastTouchDist = 0;
    container.addEventListener('touchstart', (e) => {
        const z = getZoom(camId);
        if (!z.active) return;
        if (e.touches.length === 2) {
            e.preventDefault();
            lastTouchDist = Math.hypot(
                e.touches[0].clientX - e.touches[1].clientX,
                e.touches[0].clientY - e.touches[1].clientY
            );
        } else if (e.touches.length === 1 && z.scale > 1) {
            z.dragging = true;
            z.lastX = e.touches[0].clientX;
            z.lastY = e.touches[0].clientY;
        }
    }, { passive: false });

    container.addEventListener('touchmove', (e) => {
        const z = getZoom(camId);
        if (!z.active) return;
        if (e.touches.length === 2) {
            e.preventDefault();
            const dist = Math.hypot(
                e.touches[0].clientX - e.touches[1].clientX,
                e.touches[0].clientY - e.touches[1].clientY
            );
            const delta = (dist - lastTouchDist) * 0.01;
            z.scale = Math.max(1, Math.min(5, z.scale + delta));
            lastTouchDist = dist;
            if (z.scale <= 1) { z.panX = 0; z.panY = 0; }
            applyZoomTransform(camId);
        } else if (e.touches.length === 1 && z.dragging) {
            e.preventDefault();
            const dx = (e.touches[0].clientX - z.lastX) / z.scale;
            const dy = (e.touches[0].clientY - z.lastY) / z.scale;
            z.panX += dx;
            z.panY += dy;
            z.lastX = e.touches[0].clientX;
            z.lastY = e.touches[0].clientY;
            applyZoomTransform(camId);
        }
    }, { passive: false });

    container.addEventListener('touchend', () => {
        const z = getZoom(camId);
        z.dragging = false;
    });

    // Double-click to reset zoom
    container.addEventListener('dblclick', (e) => {
        const z = getZoom(camId);
        if (z.active && z.scale > 1) {
            e.stopPropagation();
            resetZoom(camId);
        }
    });
}

// ─── Fullscreen Expand (Improved) ───────────────────────────────────────────

let fullscreenCameras = [];
let fullscreenIndex = 0;

function expandCamera(cameraId, cameraName) {
    // Build camera list for navigation
    const cards = document.querySelectorAll('.camera-card');
    fullscreenCameras = [];
    cards.forEach(c => {
        const id = c.id.replace('cam-', '');
        const name = c.querySelector('.camera-name')?.textContent || id;
        fullscreenCameras.push({ id, name });
    });
    fullscreenIndex = fullscreenCameras.findIndex(c => c.id === cameraId);
    if (fullscreenIndex < 0) fullscreenIndex = 0;

    renderFullscreen(cameraId, cameraName);
}

function renderFullscreen(cameraId, cameraName) {
    // Remove existing overlay
    const existing = document.getElementById('cameraFullscreen');
    if (existing) existing.remove();

    const overlay = document.createElement('div');
    overlay.id = 'cameraFullscreen';
    overlay.style.cssText = `
        position:fixed; inset:0; z-index:9999;
        background:rgba(0,0,0,0.95);
        display:flex; flex-direction:column;
        align-items:center; justify-content:center;
        cursor:default;
    `;

    // Header bar (auto-hide)
    const header = document.createElement('div');
    header.className = 'fs-header';
    header.style.cssText = `
        position:absolute; top:0; left:0; right:0;
        padding:12px 20px; display:flex;
        justify-content:space-between; align-items:center;
        background:linear-gradient(rgba(0,0,0,0.8), transparent);
        z-index:10; transition: opacity 0.3s;
    `;
    header.innerHTML = `
        <span style="color:#fff;font-size:1.1rem;font-weight:600">${cameraName}</span>
        <div style="display:flex;gap:8px">
            <button onclick="takeScreenshot('${cameraId}', '${escH(cameraName)}')"
                class="fs-btn" title="Screenshot (S)">📸</button>
            <button onclick="fsToggleZoom()" class="fs-btn" id="fsZoomBtn" title="Zoom (Z)">🔍</button>
            ${fullscreenCameras.length > 1 ? `
                <button onclick="fsNavigate(-1)" class="fs-btn" title="Anterior (←)">◀</button>
                <button onclick="fsNavigate(1)" class="fs-btn" title="Proxima (→)">▶</button>
            ` : ''}
            <button onclick="toggleNativeFullscreen()" class="fs-btn" title="Tela cheia (F)">⛶</button>
            <button onclick="closeFullscreen()" class="fs-btn" title="Fechar (ESC)">✕</button>
        </div>
    `;
    overlay.appendChild(header);

    // Video container
    const videoWrap = document.createElement('div');
    videoWrap.id = 'fsVideoWrap';
    videoWrap.style.cssText = `
        width:95vw; height:85vh;
        display:flex; align-items:center; justify-content:center;
        overflow:hidden; position:relative;
    `;

    // Clone the video stream
    const srcContainer = document.getElementById(`video-${cameraId}`);
    const srcVideo = srcContainer ? srcContainer.querySelector('video') : null;

    if (srcVideo && srcVideo.srcObject) {
        const video = document.createElement('video');
        video.srcObject = srcVideo.srcObject;
        video.autoplay = true;
        video.muted = true;
        video.playsInline = true;
        video.style.cssText = `
            max-width:100%; max-height:100%;
            width:auto; height:auto;
            object-fit:contain;
            border-radius:8px;
            transition: transform 0.1s ease;
        `;
        video.play().catch(() => { });
        videoWrap.appendChild(video);
    } else {
        videoWrap.innerHTML = `<div style="color:#888;text-align:center"><p style="font-size:1.2rem">Sem sinal</p><p style="font-size:0.85rem">Aguarde a camera conectar</p></div>`;
    }

    // Zoom indicator for fullscreen
    const fsZoomIndicator = document.createElement('div');
    fsZoomIndicator.id = 'fsZoomLevel';
    fsZoomIndicator.className = 'zoom-indicator';
    fsZoomIndicator.style.display = 'none';
    videoWrap.appendChild(fsZoomIndicator);

    overlay.appendChild(videoWrap);

    // Close on click background
    overlay.addEventListener('click', (e) => {
        if (e.target === overlay) closeFullscreen();
    });

    document.body.appendChild(overlay);

    // Setup fullscreen zoom
    setupFullscreenZoom();

    // Auto-hide header
    let hideTimeout;
    const showHeader = () => {
        header.style.opacity = '1';
        clearTimeout(hideTimeout);
        hideTimeout = setTimeout(() => { header.style.opacity = '0'; }, 4000);
    };
    overlay.addEventListener('mousemove', showHeader);
    overlay.addEventListener('touchstart', showHeader);
    showHeader();
}

// Fullscreen zoom state
const fsZoom = { scale: 1, panX: 0, panY: 0, active: false, dragging: false, lastX: 0, lastY: 0 };

function fsToggleZoom() {
    fsZoom.active = !fsZoom.active;
    const btn = document.getElementById('fsZoomBtn');
    if (btn) btn.style.background = fsZoom.active ? 'rgba(59,130,246,0.7)' : 'rgba(255,255,255,0.1)';
    if (!fsZoom.active) {
        fsZoom.scale = 1; fsZoom.panX = 0; fsZoom.panY = 0;
        applyFsZoom();
    }
}

function applyFsZoom() {
    const wrap = document.getElementById('fsVideoWrap');
    if (!wrap) return;
    const video = wrap.querySelector('video');
    if (!video) return;
    video.style.transform = `scale(${fsZoom.scale}) translate(${fsZoom.panX}px, ${fsZoom.panY}px)`;

    const indicator = document.getElementById('fsZoomLevel');
    if (indicator) {
        if (fsZoom.scale > 1.05) {
            indicator.style.display = 'block';
            indicator.textContent = `${fsZoom.scale.toFixed(1)}x`;
        } else {
            indicator.style.display = 'none';
        }
    }
}

function setupFullscreenZoom() {
    const wrap = document.getElementById('fsVideoWrap');
    if (!wrap) return;

    // Reset
    fsZoom.scale = 1; fsZoom.panX = 0; fsZoom.panY = 0; fsZoom.active = false;

    wrap.addEventListener('wheel', (e) => {
        if (!fsZoom.active) return;
        e.preventDefault();
        const delta = e.deltaY > 0 ? -0.25 : 0.25;
        fsZoom.scale = Math.max(1, Math.min(8, fsZoom.scale + delta));
        if (fsZoom.scale <= 1) { fsZoom.panX = 0; fsZoom.panY = 0; }
        applyFsZoom();
    }, { passive: false });

    wrap.addEventListener('mousedown', (e) => {
        if (!fsZoom.active || fsZoom.scale <= 1) return;
        fsZoom.dragging = true;
        fsZoom.lastX = e.clientX;
        fsZoom.lastY = e.clientY;
        wrap.style.cursor = 'grabbing';
        e.preventDefault();
    });

    document.addEventListener('mousemove', (e) => {
        if (!fsZoom.dragging) return;
        fsZoom.panX += (e.clientX - fsZoom.lastX) / fsZoom.scale;
        fsZoom.panY += (e.clientY - fsZoom.lastY) / fsZoom.scale;
        fsZoom.lastX = e.clientX;
        fsZoom.lastY = e.clientY;
        applyFsZoom();
    });

    document.addEventListener('mouseup', () => {
        if (fsZoom.dragging) {
            fsZoom.dragging = false;
            const wrap = document.getElementById('fsVideoWrap');
            if (wrap) wrap.style.cursor = '';
        }
    });

    // Double-click to reset
    wrap.addEventListener('dblclick', () => {
        if (fsZoom.active) {
            fsZoom.scale = 1; fsZoom.panX = 0; fsZoom.panY = 0;
            applyFsZoom();
        }
    });
}

function fsNavigate(direction) {
    if (fullscreenCameras.length <= 1) return;
    fullscreenIndex = (fullscreenIndex + direction + fullscreenCameras.length) % fullscreenCameras.length;
    const cam = fullscreenCameras[fullscreenIndex];
    renderFullscreen(cam.id, cam.name);
}

function closeFullscreen() {
    const overlay = document.getElementById('cameraFullscreen');
    if (overlay) {
        if (document.fullscreenElement) {
            document.exitFullscreen().catch(() => { });
        }
        overlay.remove();
    }
}

function toggleNativeFullscreen() {
    const overlay = document.getElementById('cameraFullscreen');
    if (!overlay) return;
    if (document.fullscreenElement) {
        document.exitFullscreen().catch(() => { });
    } else {
        overlay.requestFullscreen().catch(() => { });
    }
}

// ─── Keyboard Shortcuts ─────────────────────────────────────────────────────

document.addEventListener('keydown', (e) => {
    const overlay = document.getElementById('cameraFullscreen');

    if (overlay) {
        // Fullscreen shortcuts
        switch (e.key) {
            case 'Escape': closeFullscreen(); break;
            case 'ArrowLeft': fsNavigate(-1); break;
            case 'ArrowRight': fsNavigate(1); break;
            case 's': case 'S': {
                const cam = fullscreenCameras[fullscreenIndex];
                if (cam) takeScreenshot(cam.id, cam.name);
                break;
            }
            case 'z': case 'Z': fsToggleZoom(); break;
            case 'f': case 'F': toggleNativeFullscreen(); break;
        }
    }
});

// ─── Cleanup ────────────────────────────────────────────────────────────────

window.addEventListener('beforeunload', () => {
    for (const pc of Object.values(webrtcConnections)) {
        pc.close();
    }
});
