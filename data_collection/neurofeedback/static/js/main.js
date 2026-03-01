/**
 * Neurofeedback app - main UI logic
 */

function showFileBox(data) {
    var box = document.getElementById('file-box');
    var errEl = document.getElementById('file-box-error');
    if (!box || !errEl) return;
    box.classList.remove('hidden');
    if (data.parse_error) {
        errEl.textContent = data.parse_error;
        errEl.classList.remove('hidden');
        document.getElementById('file-box-streams').textContent = '—';
        document.getElementById('file-box-channels').textContent = '—';
        document.getElementById('file-box-markers').textContent = '—';
        document.getElementById('file-box-notes').textContent = '—';
        return;
    }
    errEl.classList.add('hidden');
    var streams = data.streams || [];
    var channels = data.channels || [];
    var markers = data.markers || [];
    var notes = data.notes || [];
    document.getElementById('file-box-streams').textContent = streams.length
        ? streams.map(function (s) {
            return s.name + ' | ' + (s.type || '') + ' | ' + (s.channel_count || 0) + ' ch | ' + (s.nominal_srate || 0) + ' Hz';
        }).join('\n')
        : 'No streams';
    document.getElementById('file-box-channels').textContent = channels.length
        ? channels.join(', ')
        : 'No channels';
    document.getElementById('file-box-markers').textContent = markers.length
        ? JSON.stringify(markers.slice(0, 30), null, 2) + (markers.length > 30 ? '\n...' : '')
        : 'No markers';
    document.getElementById('file-box-notes').textContent = notes.length
        ? notes.slice(0, 50).map(function (n) { return 'Trial ' + n.trial_number + ' → ' + n.rating; }).join('\n') + (notes.length > 50 ? '\n...' : '')
        : 'No ratings';
}

function hideFileBox() {
    var box = document.getElementById('file-box');
    if (box) box.classList.add('hidden');
}

document.addEventListener('DOMContentLoaded', function () {
    var fileInput = document.getElementById('xdf-file-input');
    var importBtn = document.getElementById('xdf-import-btn');
    var filenameEl = document.getElementById('xdf-filename');

    if (!importBtn || !fileInput || !filenameEl) return;

    importBtn.addEventListener('click', function () {
        fileInput.click();
    });

    fileInput.addEventListener('change', function () {
        var file = fileInput.files[0];
        if (!file) {
            filenameEl.textContent = 'No file loaded';
            filenameEl.classList.remove('loaded');
            hideFileBox();
            return;
        }
        var formData = new FormData();
        formData.append('file', file);
        importBtn.disabled = true;
        importBtn.textContent = 'Loading…';
        fetch('/api/upload_xdf', {
            method: 'POST',
            body: formData
        })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.ok) {
                    filenameEl.textContent = data.filename;
                    filenameEl.classList.add('loaded');
                    showFileBox(data);
                } else {
                    filenameEl.textContent = 'Error: ' + (data.error || 'upload failed');
                    filenameEl.classList.remove('loaded');
                    hideFileBox();
                }
            })
            .catch(function () {
                filenameEl.textContent = 'Connection error';
                filenameEl.classList.remove('loaded');
                hideFileBox();
            })
            .finally(function () {
                importBtn.disabled = false;
                importBtn.textContent = 'Load XDF file';
            });
    });
});
