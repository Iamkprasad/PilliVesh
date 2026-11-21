/* PilliVesh Image Studio UI. Classic IIFE; matches the chat frontend style. */
(function () {
  var GALLERY_KEY = 'pv-image-gallery';
  var state = { models: [], status: {}, busy: false };

  function byId(id) { return document.getElementById(id); }
  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) { node.className = cls; }
    if (text !== undefined && text !== null) { node.textContent = String(text); }
    return node;
  }
  function message(text, isError) {
    var node = byId('message');
    node.textContent = text || '';
    node.style.color = isError ? 'var(--red)' : 'var(--gray)';
  }

  function renderModels(data) {
    state.models = data.models || [];
    var list = byId('model-list');
    list.textContent = '';
    if (!state.models.length) {
      list.appendChild(el('p', 'muted', 'No curated models.'));
      return;
    }
    state.models.forEach(function (entry) {
      var card = el('div', 'model');
      var head = el('div', 'model-head');
      head.appendChild(el('span', 'model-name', entry.name));
      var chipText = entry.status === 'loaded' ? 'LOADED' :
        (entry.installed ? 'INSTALLED' : 'NOT INSTALLED');
      head.appendChild(el('span', 'status-chip ' + (
        entry.status === 'loaded' ? 'loaded' :
        (entry.installed ? 'installed' : '')), chipText));
      card.appendChild(head);
      card.appendChild(el('p', 'model-meta',
        '~' + entry.size_mb + ' MB · ' + entry.license + ' · ' + entry.notes));

      var actions = el('div', 'model-actions');
      if (!entry.installed) {
        var dl = el('button', '', 'Download');
        dl.type = 'button';
        dl.addEventListener('click', function () {
          ImageAPI.download(entry.id).then(function (result) {
            message(result.status === 'started' ?
              'Downloading ' + entry.name + '…' : result.status);
            refreshDownload();
          }).catch(function (e) { message(e.message, true); });
        });
        actions.appendChild(dl);
      } else if (entry.status === 'loaded') {
        var unload = el('button', '', 'Unload');
        unload.type = 'button';
        unload.addEventListener('click', function () {
          ImageAPI.unload(entry.id).then(function () {
            message('Model unloaded.');
            refreshAll();
          }).catch(function (e) { message(e.message, true); });
        });
        actions.appendChild(unload);
      } else {
        var load = el('button', 'primary', 'Load');
        load.type = 'button';
        load.addEventListener('click', function () {
          message('Loading model…');
          ImageAPI.load(entry.id).then(function () {
            message(entry.name + ' ready.');
            byId('size').value = String(entry.width || 256);
            byId('steps').value = String(entry.steps || 10);
            refreshAll();
          }).catch(function (e) { message(e.message, true); });
        });
        actions.appendChild(load);
      }
      var link = el('a', '', 'Model page ↗');
      link.href = entry.source_url;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      link.style.cssText = 'min-height:40px;display:flex;align-items:center;font-size:13px;';
      actions.appendChild(link);
      card.appendChild(actions);
      list.appendChild(card);
    });
  }

  function refreshStatus() {
    ImageAPI.status().then(function (data) {
      state.status = data;
      var pill = byId('engine-pill');
      pill.textContent = data.engine_running ? 'Engine online' : 'Engine offline';
      pill.className = 'pill' + (data.engine_running ? ' online' : '');
      byId('generate-btn').disabled = !data.engine_running || state.busy;
      byId('cancel-btn').disabled = !state.busy;
    }).catch(function () {});
  }

  function refreshDownload() {
    ImageAPI.downloadStatus().then(function (data) {
      var node = byId('download-status');
      node.textContent = '';
      if (!data || data.status === 'idle') { return; }
      if (data.status === 'downloading') {
        node.appendChild(el('div', 'hint', 'Downloading: ' +
          (data.downloaded_mb || 0) + ' / ' + (data.total_mb || '?') +
          ' MB (' + (data.percent || 0) + '%)'));
      } else if (data.status === 'completed') {
        node.appendChild(el('div', 'hint', 'Download complete.'));
        refreshModelsOnly();
      } else if (data.status === 'error') {
        node.appendChild(el('div', 'message', 'Download failed: ' + data.error));
      }
    }).catch(function () {});
  }

  function refreshModelsOnly() {
    ImageAPI.models().then(renderModels).catch(function () {});
  }

  function refreshAll() {
    refreshModelsOnly();
    refreshStatus();
  }

  function renderSearch(results) {
    var node = byId('search-results');
    node.textContent = '';
    if (!results || !results.length) {
      node.appendChild(el('p', 'muted', 'No GGUF models found.'));
      return;
    }
    results.forEach(function (item) {
      var row = el('div', 'result-row');
      var info = el('span', '', item.id + ' · ' + item.file);
      row.appendChild(info);
      var copy = el('button', '', 'Copy link');
      copy.type = 'button';
      copy.addEventListener('click', function () {
        var url = item.source_url + '/resolve/main/' + item.file;
        if (navigator.clipboard) {
          navigator.clipboard.writeText(url).then(function () {
            message('Link copied. Add it to image_catalog.py to enable in-app download.');
          });
        } else {
          message(url);
        }
      });
      row.appendChild(copy);
      node.appendChild(row);
    });
  }

  function setProgress(event) {
    byId('progress-wrap').hidden = false;
    byId('stage').textContent = event.stage || event.detail || 'working';
    var completed = event.completed;
    var total = event.total;
    if (typeof completed === 'number' && typeof total === 'number' && total > 0) {
      var pct = Math.min(100, Math.round(completed * 100 / total));
      byId('progress-bar').style.width = pct + '%';
      byId('step-label').textContent = completed + ' / ' + total + ' ' + (event.unit || '');
    } else {
      byId('step-label').textContent = '';
    }
  }

  function loadGallery() {
    var items = [];
    try { items = JSON.parse(localStorage.getItem(GALLERY_KEY) || '[]'); } catch (e) { items = []; }
    return Array.isArray(items) ? items : [];
  }
  function renderGallery() {
    var node = byId('gallery');
    node.textContent = '';
    var items = loadGallery();
    if (!items.length) {
      node.appendChild(el('p', 'muted', 'No images yet.'));
      return;
    }
    items.forEach(function (item) {
      var img = el('img', '', '');
      img.src = item.path;
      img.alt = item.prompt || 'generated image';
      img.title = item.prompt || '';
      img.addEventListener('click', function () {
        byId('result-img').src = item.path;
        byId('result-link').href = item.path;
        byId('result').hidden = false;
      });
      node.appendChild(img);
    });
  }
  function addToGallery(event) {
    var items = loadGallery();
    items.unshift({ id: event.id, path: event.path, prompt: byId('prompt').value });
    try { localStorage.setItem(GALLERY_KEY, JSON.stringify(items.slice(0, 12))); } catch (e) {}
    renderGallery();
  }

  function generate() {
    var payload = {
      prompt: byId('prompt').value,
      negative_prompt: byId('negative').value,
      width: parseInt(byId('size').value, 10),
      height: parseInt(byId('size').value, 10),
      steps: parseInt(byId('steps').value, 10),
      seed: parseInt(byId('seed').value, 10)
    };
    if (!payload.prompt.trim()) { message('Enter a prompt first.', true); return; }
    state.busy = true;
    byId('generate-btn').disabled = true;
    byId('cancel-btn').disabled = false;
    byId('progress-wrap').hidden = false;
    byId('progress-bar').style.width = '0%';
    byId('step-label').textContent = '';
    message('Generating…');
    ImageAPI.generate(payload, {
      onProgress: setProgress,
      onDone: function (event) {
        byId('progress-bar').style.width = '100%';
        byId('result-img').src = event.path;
        byId('result-link').href = event.path;
        byId('result-link').download = event.id + '.png';
        byId('result').hidden = false;
        addToGallery(event);
        message('Done in ' + Math.round((event.ms || 0) / 1000) + 's.');
      },
      onError: function (event) { message(event.e || 'Generation failed.', true); }
    }).catch(function (e) {
      message(e.message, true);
    }).then(function () {
      state.busy = false;
      byId('generate-btn').disabled = !state.status.engine_running;
      byId('cancel-btn').disabled = true;
      refreshStatus();
    });
  }

  function bind() {
    byId('search-btn').addEventListener('click', function () {
      var q = byId('search-input').value.trim();
      if (!q) { message('Enter a search term.', true); return; }
      ImageAPI.search(q).then(renderSearch).catch(function (e) {
        message(e.message, true);
      });
    });
    byId('generate-btn').addEventListener('click', generate);
    byId('cancel-btn').addEventListener('click', function () {
      ImageAPI.cancel().then(function () { message('Cancel requested.'); })
        .catch(function (e) { message(e.message, true); });
    });
  }

  bind();
  refreshAll();
  refreshDownload();
  renderGallery();
  setInterval(refreshStatus, 5000);
  setInterval(refreshDownload, 3000);
})();
