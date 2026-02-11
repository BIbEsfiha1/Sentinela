/* Sentinela - Recordings Browser & Player */

let currentCameras = [];

document.addEventListener('DOMContentLoaded', loadDates);

async function loadDates() {
    try {
        const dates = await api('/api/recordings/dates');
        const sel = document.getElementById('dateSelect');
        sel.innerHTML = '<option value="">Selecione a data</option>';
        for (const d of dates) {
            const opt = document.createElement('option');
            opt.value = d;
            opt.textContent = formatDate(d);
            sel.appendChild(opt);
        }
        // Auto-select today if available
        const today = new Date().toISOString().split('T')[0];
        if (dates.includes(today)) {
            sel.value = today;
            loadDate();
        }
    } catch (e) { /* ignore */ }
}

async function loadDate() {
    const date = document.getElementById('dateSelect').value;
    if (!date) return;

    try {
        currentCameras = await api(`/api/recordings/${date}`);
        const camSel = document.getElementById('cameraSelect');
        camSel.style.display = '';
        camSel.innerHTML = '<option value="">Todas as cameras</option>';
        for (const cam of currentCameras) {
            const opt = document.createElement('option');
            opt.value = cam.id;
            opt.textContent = cam.name;
            camSel.appendChild(opt);
        }
        renderFiles();
    } catch (e) {
        document.getElementById('fileList').innerHTML =
            `<div class="alert alert-danger">Erro: ${escR(e.message)}</div>`;
    }
}

function loadFiles() {
    renderFiles();
}

function renderFiles() {
    const filter = document.getElementById('cameraSelect').value;
    const date = document.getElementById('dateSelect').value;
    const el = document.getElementById('fileList');

    const cameras = filter
        ? currentCameras.filter(c => c.id === filter)
        : currentCameras;

    if (cameras.length === 0 || cameras.every(c => c.files.length === 0)) {
        el.innerHTML = '<div class="empty-state"><h3>Nenhuma gravacao encontrada</h3></div>';
        return;
    }

    el.innerHTML = cameras.map(cam => `
        <div class="card mb-2">
            <div class="card-header">
                <h3 class="card-title">${escR(cam.name)}</h3>
                <span class="text-muted">${cam.files.length} arquivo(s)</span>
            </div>
            <div class="table-wrap">
                <table>
                    <thead>
                        <tr>
                            <th>Horario</th>
                            <th>Tamanho</th>
                            <th>Acoes</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${cam.files.map(f => `
                            <tr>
                                <td>${formatTime(f.name)}</td>
                                <td>${f.size_mb} MB</td>
                                <td>
                                    <button class="btn btn-sm btn-primary"
                                            onclick="playFile('${date}', '${cam.id}', '${escR(f.name)}', '${escR(cam.name)}')">
                                        Assistir
                                    </button>
                                    <a class="btn btn-sm btn-secondary"
                                       href="/api/recordings/play/${date}/${cam.id}/${f.name}" download>
                                        Baixar
                                    </a>
                                </td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        </div>
    `).join('');
}

function playFile(date, cameraId, filename, cameraName) {
    const container = document.getElementById('playerContainer');
    const player = document.getElementById('videoPlayer');
    const title = document.getElementById('playerTitle');
    const download = document.getElementById('downloadLink');

    const url = `/api/recordings/play/${date}/${cameraId}/${filename}`;
    player.src = url;
    title.textContent = `${cameraName} - ${formatTime(filename)}`;
    download.href = url;
    container.classList.remove('hidden');
    player.play();

    // Scroll to player
    container.scrollIntoView({ behavior: 'smooth' });
}

function formatDate(d) {
    const [y, m, day] = d.split('-');
    return `${day}/${m}/${y}`;
}

function formatTime(filename) {
    // rec_14-30-00.mp4 -> 14:30:00
    const match = filename.match(/rec_(\d{2})-(\d{2})-(\d{2})/);
    if (match) return `${match[1]}:${match[2]}:${match[3]}`;
    return filename;
}

function escR(s) {
    const d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
}
