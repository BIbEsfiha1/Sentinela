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

async function loadCameraGrid() {
    try {
        const cameras = await api('/api/cameras');
        const grid = document.getElementById('cameraGrid');
        const empty = document.getElementById('noCameras');

        if (cameras.length === 0) {
            grid.classList.add('hidden');
            empty.classList.remove('hidden');
            return;
        }

        empty.classList.add('hidden');
        grid.classList.remove('hidden');

        grid.innerHTML = cameras.map(cam => `
            <div class="camera-card" id="cam-${cam.id}">
                <div class="camera-video" id="video-${cam.id}">
                    <div class="no-signal">
                        <img src="/static/img/no-signal.svg" alt="" style="width:80px;opacity:0.5"><br>
                        <small>Conectando...</small>
                    </div>
                </div>
                <div class="camera-info">
                    <span class="camera-name">${escH(cam.name)}</span>
                    <span class="camera-status">
                        ${cam.enabled ? statusBadgeHtml(cam.status) : '<span class="badge badge-offline">Desabilitada</span>'}
                    </span>
                </div>
            </div>
        `).join('');

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

function statusBadgeHtml(status) {
    const m = {
        recording: '<span class="badge badge-recording">Gravando</span>',
        online: '<span class="badge badge-online">Online</span>',
        offline: '<span class="badge badge-offline">Offline</span>',
        error: '<span class="badge badge-error">Erro</span>',
    };
    return m[status] || m.offline;
}

async function startWebRTC(cameraId) {
    const container = document.getElementById(`video-${cameraId}`);
    if (!container) return;

    // Determine the WebRTC WHEP endpoint
    const host = window.location.hostname;
    const whepUrl = `http://${host}:8889/${cameraId}/whep`;

    try {
        const pc = new RTCPeerConnection({
            iceServers: [{ urls: 'stun:stun.l.google.com:19302' }],
        });

        webrtcConnections[cameraId] = pc;

        pc.ontrack = (evt) => {
            const video = document.createElement('video');
            video.srcObject = evt.streams[0];
            video.autoplay = true;
            video.muted = true;
            video.playsInline = true;
            container.innerHTML = '';
            container.appendChild(video);
        };

        pc.oniceconnectionstatechange = () => {
            if (pc.iceConnectionState === 'failed' || pc.iceConnectionState === 'disconnected') {
                // Retry after delay
                setTimeout(() => startWebRTC(cameraId), 5000);
            }
        };

        // Add receive-only transceivers
        pc.addTransceiver('video', { direction: 'recvonly' });
        pc.addTransceiver('audio', { direction: 'recvonly' });

        const offer = await pc.createOffer();
        await pc.setLocalDescription(offer);

        // Wait for ICE gathering to complete (or timeout)
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

        const res = await fetch(whepUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/sdp' },
            body: pc.localDescription.sdp,
        });

        if (res.ok) {
            const answer = await res.text();
            await pc.setRemoteDescription({ type: 'answer', sdp: answer });
        } else {
            throw new Error(`WHEP failed: ${res.status}`);
        }
    } catch (e) {
        // Show fallback - try HLS or show offline
        container.innerHTML = `
            <div class="no-signal">
                <img src="/static/img/no-signal.svg" alt="" style="width:80px;opacity:0.5"><br>
                <small>Sem sinal</small>
            </div>`;
        // Retry after 10s
        setTimeout(() => startWebRTC(cameraId), 10000);
    }
}

function escH(s) {
    const d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
}

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    for (const pc of Object.values(webrtcConnections)) {
        pc.close();
    }
});
