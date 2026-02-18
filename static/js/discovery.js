/* Sentinela - Camera Discovery & Management */

document.addEventListener('DOMContentLoaded', loadCameras);

async function loadCameras() {
    const el = document.getElementById('cameraList');
    try {
        const cameras = await api('/api/cameras');
        if (cameras.length === 0) {
            el.innerHTML = `
                <div class="empty-state">
                    <h3>Nenhuma camera cadastrada</h3>
                    <p class="mb-2">Adicione cameras manualmente ou use a descoberta automatica.</p>
                </div>`;
            return;
        }

        el.innerHTML = `
            <div class="table-wrap">
                <table>
                    <thead>
                        <tr>
                            <th>Nome</th>
                            <th>IP / Rota</th>
                            <th>Marca</th>
                            <th>Status Manager</th>
                            <th>Acoes</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${cameras.map(c => `
                        <tr>
                            <td>
                                <strong>${esc(c.name)}</strong>
                                ${!c.enabled ? '<span class="badge badge-offline" style="font-size:0.7em">DESATIVADA</span>' : ''}
                            </td>
                            <td>
                                <div class="text-xs text-muted">${esc(c.ip)}:${c.port}</div>
                                <div class="text-xs text-muted" title="${esc(c.id)}">ID: ${c.id}</div>
                            </td>
                            <td>
                                <span class="badge ${c.brand === 'auto' ? 'badge-secondary' : 'badge-primary'}" style="font-size:0.7em">
                                    ${esc(c.brand || 'auto')}
                                </span>
                            </td>
                            <td>${statusBadge(c.status)}</td>
                            <td>
                                <div class="flex gap-1">
                                    <button class="btn btn-sm ${c.enabled ? 'btn-warning' : 'btn-success'}" 
                                            onclick="toggleCamera('${c.id}')" title="${c.enabled ? 'Desativar' : 'Ativar'}">
                                        ${c.enabled ? 'Pause' : 'Play'}
                                    </button>
                                    <button class="btn btn-sm btn-secondary" onclick="editCamera('${c.id}')">Editar</button>
                                </div>
                            </td>
                        </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>`;
    } catch (e) {
        el.innerHTML = `<div class="alert alert-danger">Erro ao carregar cameras: ${esc(e.message)}</div>`;
    }
}

function statusBadge(status) {
    const m = {
        recording: '<span class="badge badge-recording">Gravando</span>',
        online: '<span class="badge badge-online">Online</span>',
        offline: '<span class="badge badge-offline">Offline</span>',
        error: '<span class="badge badge-error">Erro</span>',
    };
    return m[status] || m.offline;
}

// ─── Discovery ───────────────────────────────────────────────────────────────

async function startDiscovery() {
    const el = document.getElementById('discoverResults');
    el.innerHTML = '<div class="loading-text"><div class="spinner"></div> Buscando cameras... (pode levar ate 30s)</div>';

    try {
        const cameras = await api('/api/discover', 'POST');
        if (cameras.length === 0) {
            el.innerHTML = '<div class="alert alert-warning">Nenhuma camera encontrada na rede. Verifique se estao ligadas.</div>';
            return;
        }

        el.innerHTML = cameras.map(c => `
            <div class="card mb-1" style="padding:0.75rem; border:1px solid #333">
                <div class="flex justify-between items-center">
                    <div>
                        <strong>${esc(c.ip)}</strong>
                        <span class="text-muted text-sm">Portas: ${c.port} | ${c.source}</span>
                    </div>
                    <div>
                        ${c.already_added
                ? '<span class="badge badge-secondary">Ja adicionada</span>'
                : `<button class="btn btn-sm btn-primary" onclick="quickAdd('${esc(c.ip)}', ${c.port}, '${esc(c.name || '')}')">Adicionar</button>`
            }
                    </div>
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
            username: 'admin', password: '',
            channel: 1, stream: 0,
            brand: 'auto',
            codec: 'auto',
        });
        showToast('Camera adicionada! Configure a senha.', 'success');
        closeModal('discoverModal');
        loadCameras();
    } catch (e) {
        showToast('Erro: ' + e.message, 'danger');
    }
}

// ─── Add/Edit/Test ───────────────────────────────────────────────────────────

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
        brand: form.brand.value,
        codec: form.codec ? form.codec.value : 'auto',
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
    const resultEl = document.getElementById('testResult');

    btn.textContent = 'Testando...';
    btn.disabled = true;
    resultEl.innerHTML = '<div class="text-muted text-sm">Testando conexao... (auto-detect)</div>';

    try {
        const result = await api('/api/test-camera', 'POST', {
            name: 'test',
            ip: form.ip.value,
            port: parseInt(form.port.value),
            username: form.username.value,
            password: form.password.value,
            channel: parseInt(form.channel.value),
            stream: parseInt(form.stream.value),
            brand: form.brand.value,
        });

        if (result.ok) {
            if (result.brand && form.brand.value === 'auto') {
                form.brand.value = result.brand;
            }
            resultEl.innerHTML = `<div class="alert badge-online" style="margin-bottom:5px">Conexao OK! Marca detectada: <strong>${result.brand || 'auto'}</strong></div>`;
            showToast('Conexao OK!', 'success');
        } else {
            const errMsg = result.error || 'Falha na conexao. Verifique IP, usuario e senha.';
            resultEl.innerHTML = `<div class="alert badge-error" style="margin-bottom:5px">${esc(errMsg)}</div>`;
            showToast(errMsg, 'danger');
        }
    } catch (e) {
        resultEl.innerHTML = `<div class="alert badge-error">Erro: ${esc(e.message)}</div>`;
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
    const form = document.getElementById('editForm');
    document.getElementById('editId').value = id;
    document.getElementById('editName').value = cam.name;
    document.getElementById('editIp').value = cam.ip;
    document.getElementById('editPort').value = cam.port;
    document.getElementById('editUser').value = cam.username;
    // Password is not filled for security, or we could fill a placeholder
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

// ─── Wi-Fi Setup ─────────────────────────────────────────────────────────────

function openWifiModal() {
    openModal('wifiModal');
    resetWifiModal();
}

async function generateWifiQr(e) {
    if (e && e.preventDefault) e.preventDefault();
    const ssid = document.getElementById('wifiSSID').value;
    const pass = document.getElementById('wifiPass').value;

    if (!ssid || !pass) return;

    let qrData = '';
    const useAlt = document.getElementById('wifiAltFormat') && document.getElementById('wifiAltFormat').checked;

    if (useAlt) {
        // iCSee / XM format: JSON style
        // They use {s:"SSID", p:"PASSWORD", k:"TOKEN"}
        // Token is usually random
        const token = Math.floor(Math.random() * 100000000).toString();
        qrData = JSON.stringify({ s: ssid, p: pass, k: token });
    } else {
        // Standard Wi-Fi QR format: WIFI:S:SSID;T:WPA;P:PASSWORD;;
        const escape = (s) => s.replace(/;/g, '\\;').replace(/:/g, '\\:').replace(/\\/g, '\\\\');
        qrData = `WIFI:S:${escape(ssid)};T:WPA;P:${escape(pass)};;`;
    }

    const img = document.getElementById('qrImage');
    img.src = `/api/tools/qr?text=${encodeURIComponent(qrData)}`;

    document.getElementById('wifiStep1').style.display = 'none';
    document.getElementById('wifiStep2').style.display = 'block';
}

function resetWifiModal() {
    document.getElementById('wifiStep1').style.display = 'block';
    document.getElementById('wifiStep2').style.display = 'none';
    const s3 = document.getElementById('wifiStep3');
    if (s3) s3.style.display = 'none';

    document.getElementById('qrImage').src = '';

    // Clear ble list
    const bleList = document.getElementById('bleList');
    if (bleList) bleList.innerHTML = '<div class="text-center text-muted p-2">Clique em Buscar...</div>';
}

function esc(s) {
    if (typeof s !== 'string') return s;
    const div = document.createElement('div');
    div.textContent = s;
    return div.innerHTML;
}

// ─── BLE Tools ───────────────────────────────────────────────────────────────

async function startBleScan() {
    // Show step 3
    document.getElementById('wifiStep1').style.display = 'none';
    document.getElementById('wifiStep2').style.display = 'none';
    const step3 = document.getElementById('wifiStep3');
    if (step3) step3.style.display = 'block';

    const list = document.getElementById('bleList');
    list.innerHTML = '<div class="text-center p-2"><div class="spinner"></div> Buscando (4s)...</div>';

    try {
        const devices = await api('/api/tools/ble/scan');
        if (devices.error) throw new Error(devices.error);

        if (devices.length === 0) {
            list.innerHTML = '<div class="text-center text-muted p-2">Nenhum dispositivo encontrado.<br>Aproxime a camera.</div>';
            return;
        }

        list.innerHTML = devices.map(d => `
            <div class="card mb-1" style="padding:8px; border:1px solid ${d.is_likely_camera ? '#4caf50' : '#444'}; cursor:pointer" 
                 onclick="configureBle('${d.address}')">
                <div class="flex justify-between">
                    <strong>${esc(d.name)}</strong>
                    <span class="text-muted text-xs">${d.rssi} dBm</span>
                </div>
                <div class="text-xs text-muted">${d.address}</div>
                ${d.is_likely_camera ? '<div class="text-xs text-success">Provavel Camera</div>' : ''}
            </div>
        `).join('');

    } catch (e) {
        list.innerHTML = `<div class="text-danger p-2">Erro: ${esc(e.message)}</div>`;
    }
}

async function configureBle(address) {
    const ssid = document.getElementById('wifiSSID').value;
    const pass = document.getElementById('wifiPass').value;

    if (!ssid || !pass) {
        alert('Preencha SSID e Senha na tela anterior primeiro!');
        resetWifiModal();
        return;
    }

    if (!confirm(`Enviar Wi-Fi "${ssid}" para o dispositivo ${address}?`)) return;

    const list = document.getElementById('bleList');
    list.innerHTML = '<div class="text-center p-2"><div class="spinner"></div> Conectando e configurando...<br>Isso pode levar 15s.</div>';

    try {
        const res = await api('/api/tools/ble/configure', 'POST', {
            address, ssid, password: pass
        });

        if (res.ok) {
            list.innerHTML = `<div class="alert alert-success p-2">Successo!<br>${res.message}</div>`;
            showToast('Configuracao enviada via Bluetooth!', 'success');
        } else {
            throw new Error(res.error || 'Falha desconhecida');
        }
    } catch (e) {
        list.innerHTML = `<div class="alert alert-danger p-2">Erro: ${esc(e.message)}</div>`;
        // Restore list button
        setTimeout(() => startBleScan(), 3000);
    }
}
