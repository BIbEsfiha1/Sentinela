/* Sentinela - Settings Page */

document.addEventListener('DOMContentLoaded', () => {
    loadSettings();
    loadTunnelStatus();
    loadSystemInfo();
    setInterval(loadTunnelStatus, 10000);
});

async function loadSettings() {
    try {
        const s = await api('/api/settings');

        // Recording
        document.getElementById('segDuration').value = s.recording.segment_duration;
        document.getElementById('retDays').value = s.recording.retention_days;

        // System
        document.getElementById('webPort').value = s.system.web_port;
        document.getElementById('defUser').value = s.system.default_username;
        document.getElementById('defPass').value = s.system.default_password;

        // Tunnel
        document.getElementById('tunnelMode').value = s.tunnel.mode;
        if (s.tunnel.hostname) {
            document.getElementById('tunnelHostname').value = s.tunnel.hostname;
        }
        toggleTunnelFields();
    } catch (e) { /* ignore */ }
}

async function saveRecording(e) {
    e.preventDefault();
    try {
        await api('/api/settings/recording', 'PUT', {
            segment_duration: parseInt(document.getElementById('segDuration').value),
            retention_days: parseInt(document.getElementById('retDays').value),
            recordings_path: 'recordings',
        });
        showToast('Configuracoes de gravacao salvas!', 'success');
    } catch (e) {
        showToast('Erro: ' + e.message, 'danger');
    }
}

async function saveSystem(e) {
    e.preventDefault();
    try {
        await api('/api/settings/system', 'PUT', {
            web_port: parseInt(document.getElementById('webPort').value),
            default_username: document.getElementById('defUser').value,
            default_password: document.getElementById('defPass').value,
            auto_start: false,
            language: 'pt-BR',
            first_run: false,
            mediamtx_api_port: 9997,
            mediamtx_webrtc_port: 8889,
        });
        showToast('Configuracoes do sistema salvas!', 'success');
    } catch (e) {
        showToast('Erro: ' + e.message, 'danger');
    }
}

function toggleTunnelFields() {
    const mode = document.getElementById('tunnelMode').value;
    const fields = document.getElementById('tunnelFields');
    const hostname = document.getElementById('hostnameGroup');
    fields.classList.toggle('hidden', mode === 'disabled');
    hostname.style.display = mode === 'named' ? '' : 'none';
}

async function saveTunnel() {
    const mode = document.getElementById('tunnelMode').value;
    const hostname = document.getElementById('tunnelHostname').value;
    try {
        await api('/api/settings/tunnel', 'PUT', {
            mode: mode,
            hostname: hostname || null,
            tunnel_name: null,
            public_url: null,
        });
        showToast('Configuracoes de tunnel salvas!', 'success');
        loadTunnelStatus();
    } catch (e) {
        showToast('Erro: ' + e.message, 'danger');
    }
}

async function toggleTunnel() {
    try {
        const status = await api('/api/tunnel/status');
        if (status.active) {
            await api('/api/tunnel/stop', 'POST');
            showToast('Tunnel parado', 'info');
        } else {
            await api('/api/tunnel/start', 'POST');
            showToast('Tunnel iniciando...', 'info');
        }
        setTimeout(loadTunnelStatus, 3000);
    } catch (e) {
        showToast('Erro: ' + e.message, 'danger');
    }
}

async function loadTunnelStatus() {
    try {
        const s = await api('/api/tunnel/status');
        const statusEl = document.getElementById('tunnelStatus');
        const btn = document.getElementById('tunnelToggle');
        const urlEl = document.getElementById('tunnelUrl');
        const link = document.getElementById('tunnelLink');

        if (s.active) {
            statusEl.innerHTML = '<span class="text-success">Tunnel ativo</span>';
            btn.textContent = 'Parar';
            btn.className = 'btn btn-danger';
            if (s.url) {
                urlEl.classList.remove('hidden');
                link.href = s.url;
                link.textContent = s.url;
            }
        } else {
            statusEl.innerHTML = '<span class="text-muted">Tunnel inativo</span>';
            btn.textContent = 'Iniciar';
            btn.className = 'btn btn-secondary';
            urlEl.classList.add('hidden');
        }
    } catch (e) { /* ignore */ }
}

async function loadSystemInfo() {
    try {
        const s = await api('/api/status');
        document.getElementById('sysInfo').innerHTML = `
            <p class="text-muted">CPU: ${s.cpu_percent}% | RAM: ${s.ram_percent}%</p>
            <p class="text-muted">Disco: ${s.disk_used_gb} / ${s.disk_total_gb} GB</p>
            <p class="text-muted">Gravacoes: ${s.recordings_size_gb} GB</p>
            <p class="text-muted">Uptime: ${formatUptime(s.uptime_seconds)}</p>
        `;
    } catch (e) { /* ignore */ }
}
