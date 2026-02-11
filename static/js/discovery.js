/* Sentinela - Camera Discovery & Management */

document.addEventListener('DOMContentLoaded', loadCameras);

async function loadCameras() {
    try {
        const cameras = await api('/api/cameras');
        const el = document.getElementById('cameraList');
        if (cameras.length === 0) {
            el.innerHTML = `
                <div class="empty-state">
                    <h3>Nenhuma camera cadastrada</h3>
                    <p>Use "Descobrir na Rede" para encontrar cameras automaticamente.</p>
                </div>`;
            return;
        }
        el.innerHTML = `
            <div class="table-wrap">
                <table>
                    <thead>
                        <tr>
                            <th>Nome</th>
                            <th>IP</th>
                            <th>Status</th>
                            <th>Habilitada</th>
                            <th>Acoes</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${cameras.map(c => `
                            <tr>
                                <td><strong>${esc(c.name)}</strong></td>
                                <td>${esc(c.ip)}:${c.port}</td>
                                <td>${statusBadge(c.status)}</td>
                                <td>
                                    <button class="btn btn-sm ${c.enabled ? 'btn-success' : 'btn-secondary'}"
                                            onclick="toggleCamera('${c.id}')">
                                        ${c.enabled ? 'Sim' : 'Nao'}
                                    </button>
                                </td>
                                <td>
                                    <button class="btn btn-sm btn-secondary" onclick="editCamera('${c.id}')">Editar</button>
                                </td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>`;
    } catch (e) {
        document.getElementById('cameraList').innerHTML =
            `<div class="alert alert-danger">Erro ao carregar cameras: ${esc(e.message)}</div>`;
    }
}

function statusBadge(status) {
    const map = {
        recording: '<span class="badge badge-recording">Gravando</span>',
        online: '<span class="badge badge-online">Online</span>',
        offline: '<span class="badge badge-offline">Offline</span>',
        error: '<span class="badge badge-error">Erro</span>',
    };
    return map[status] || map.offline;
}

async function startDiscovery() {
    const el = document.getElementById('discoverResults');
    el.innerHTML = '<div class="loading-text"><div class="spinner"></div> Buscando cameras... (pode levar ate 30s)</div>';
    try {
        const cameras = await api('/api/discover', 'POST');
        if (cameras.length === 0) {
            el.innerHTML = `
                <div class="alert alert-warning">Nenhuma camera encontrada na rede.</div>
                <p class="text-muted">Verifique se as cameras estao ligadas e conectadas ao Wi-Fi.</p>`;
            return;
        }
        el.innerHTML = cameras.map(c => `
            <div class="card mb-1" style="padding:0.75rem">
                <div class="flex justify-between items-center">
                    <div>
                        <strong>${esc(c.name || c.ip)}</strong>
                        <span class="text-muted">${esc(c.ip)}:${c.port}</span>
                        <span class="badge badge-${c.source === 'onvif' ? 'online' : 'offline'}">${c.source}</span>
                    </div>
                    ${c.already_added
                        ? '<span class="text-muted">Ja adicionada</span>'
                        : `<button class="btn btn-sm btn-primary" onclick="quickAdd('${esc(c.ip)}', ${c.port}, '${esc(c.name || '')}')">Adicionar</button>`
                    }
                </div>
            </div>
        `).join('');
    } catch (e) {
        el.innerHTML = `<div class="alert alert-danger">Erro: ${esc(e.message)}</div>`;
    }
}

async function quickAdd(ip, port, name) {
    try {
        await api('/api/cameras', 'POST', {
            name: name || `Camera ${ip.split('.').pop()}`,
            ip, port,
            username: 'admin', password: '12345678',
            channel: 1, stream: 0,
        });
        showToast('Camera adicionada!', 'success');
        closeModal('discoverModal');
        loadCameras();
    } catch (e) {
        showToast('Erro: ' + e.message, 'danger');
    }
}

async function addCamera(e) {
    e.preventDefault();
    const form = e.target;
    const data = {
        name: form.name.value,
        ip: form.ip.value,
        port: parseInt(form.port.value),
        username: form.username.value,
        password: form.password.value,
        channel: parseInt(form.channel.value),
        stream: parseInt(form.stream.value),
    };
    try {
        await api('/api/cameras', 'POST', data);
        showToast('Camera adicionada!', 'success');
        closeModal('addModal');
        form.reset();
        loadCameras();
    } catch (e) {
        showToast('Erro: ' + e.message, 'danger');
    }
}

async function testCamera() {
    const form = document.getElementById('addForm');
    const btn = document.getElementById('testBtn');
    btn.textContent = 'Testando...';
    btn.disabled = true;
    try {
        const result = await api('/api/test-camera', 'POST', {
            name: 'test',
            ip: form.ip.value,
            port: parseInt(form.port.value),
            username: form.username.value,
            password: form.password.value,
            channel: parseInt(form.channel.value),
            stream: parseInt(form.stream.value),
        });
        showToast(result.ok ? 'Conexao OK!' : 'Falha na conexao', result.ok ? 'success' : 'danger');
    } catch (e) {
        showToast('Erro: ' + e.message, 'danger');
    }
    btn.textContent = 'Testar Conexao';
    btn.disabled = false;
}

let editingId = null;

async function editCamera(id) {
    const cameras = await api('/api/cameras');
    const cam = cameras.find(c => c.id === id);
    if (!cam) return;
    editingId = id;
    document.getElementById('editId').value = id;
    document.getElementById('editName').value = cam.name;
    document.getElementById('editIp').value = cam.ip;
    document.getElementById('editPort').value = cam.port;
    document.getElementById('editUser').value = cam.username;
    document.getElementById('editPass').value = cam.password;
    openModal('editModal');
}

async function saveCamera(e) {
    e.preventDefault();
    const form = e.target;
    try {
        await api(`/api/cameras/${editingId}`, 'PUT', {
            name: form.name.value,
            ip: form.querySelector('[name=ip]').value,
            port: parseInt(form.querySelector('[name=port]').value),
            username: form.querySelector('[name=username]').value,
            password: form.querySelector('[name=password]').value,
        });
        showToast('Camera atualizada!', 'success');
        closeModal('editModal');
        loadCameras();
    } catch (e) {
        showToast('Erro: ' + e.message, 'danger');
    }
}

async function deleteCamera() {
    if (!confirm('Tem certeza que deseja remover esta camera?')) return;
    try {
        await api(`/api/cameras/${editingId}`, 'DELETE');
        showToast('Camera removida', 'success');
        closeModal('editModal');
        loadCameras();
    } catch (e) {
        showToast('Erro: ' + e.message, 'danger');
    }
}

async function toggleCamera(id) {
    try {
        await api(`/api/cameras/${id}/toggle`, 'POST');
        loadCameras();
    } catch (e) {
        showToast('Erro: ' + e.message, 'danger');
    }
}

function esc(s) {
    const div = document.createElement('div');
    div.textContent = s;
    return div.innerHTML;
}
