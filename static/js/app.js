/* Sentinela - Main JS */

// ─── Nav toggle (mobile) ─────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    const toggle = document.getElementById('navToggle');
    const links = document.getElementById('navLinks');
    if (toggle && links) {
        toggle.addEventListener('click', () => links.classList.toggle('open'));
    }
    updateStatusBar();
    setInterval(updateStatusBar, 10000);
});

// ─── API helper ──────────────────────────────────────────────────────
async function api(url, method = 'GET', body = null) {
    const opts = { method, headers: { 'Content-Type': 'application/json' } };
    if (body) opts.body = JSON.stringify(body);
    const res = await fetch(url, opts);
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || 'Erro na requisicao');
    }
    return res.json();
}

// ─── Status bar ──────────────────────────────────────────────────────
async function updateStatusBar() {
    try {
        const s = await api('/api/status');
        const bar = document.getElementById('statusBar');
        if (bar) {
            const parts = [];
            parts.push(`${s.cameras_recording}/${s.cameras_total} gravando`);
            parts.push(`Disco: ${s.disk_free_gb} GB livre`);
            if (s.tunnel_active) parts.push(`Remoto: ativo`);
            bar.textContent = parts.join(' | ');
        }
    } catch (e) {
        const bar = document.getElementById('statusBar');
        if (bar) bar.textContent = 'Sem conexao';
    }
}

// ─── Modal helper ────────────────────────────────────────────────────
function openModal(id) {
    const el = document.getElementById(id);
    if (el) el.classList.add('active');
}

function closeModal(id) {
    const el = document.getElementById(id);
    if (el) el.classList.remove('active');
}

// Close modal on overlay click
document.addEventListener('click', (e) => {
    if (e.target.classList.contains('modal-overlay')) {
        e.target.classList.remove('active');
    }
});

// ─── Toast notifications ─────────────────────────────────────────────
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `alert alert-${type}`;
    toast.style.cssText = 'position:fixed;top:70px;right:1rem;z-index:300;min-width:250px;animation:slideIn 0.3s ease';
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transition = 'opacity 0.3s';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// ─── Format helpers ──────────────────────────────────────────────────
function formatUptime(seconds) {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    return h > 0 ? `${h}h ${m}m` : `${m}m`;
}

function formatSize(mb) {
    if (mb >= 1024) return `${(mb / 1024).toFixed(1)} GB`;
    return `${mb.toFixed(1)} MB`;
}
