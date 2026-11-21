/* PilliVesh image API wrapper. Classic IIFE, no modules, no build step. */
var ImageAPI = (function () {
  function parse(res) {
    return res.json().then(function (body) {
      if (!body || body.success === false) {
        throw new Error((body && body.error) || ('HTTP ' + res.status));
      }
      return body.data;
    });
  }

  function request(path, options) {
    return fetch(path, options).then(function (res) {
      if (res.headers.get('Content-Type') &&
          res.headers.get('Content-Type').indexOf('application/json') !== -1) {
        return parse(res);
      }
      return res;
    });
  }

  function get(path) {
    return request(path, { method: 'GET', credentials: 'same-origin' });
  }

  function post(path, body) {
    return request(path, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body || {})
    });
  }

  function streamGenerate(payload, handlers) {
    return fetch('/api/image/generate', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }).then(function (res) {
      if (!res.ok || !res.body) {
        throw new Error('Generation request failed (HTTP ' + res.status + ')');
      }
      var reader = res.body.getReader();
      var decoder = new TextDecoder();
      var buffer = '';
      function pump() {
        return reader.read().then(function (out) {
          if (out.done) { return; }
          buffer += decoder.decode(out.value, { stream: true });
          var lines = buffer.split('\n');
          buffer = lines.pop();
          for (var i = 0; i < lines.length; i++) {
            var line = lines[i].trim();
            if (!line) { continue; }
            var event;
            try { event = JSON.parse(line); } catch (e) { continue; }
            if (event.t === 'progress' && handlers.onProgress) {
              handlers.onProgress(event);
            } else if (event.t === 'done' && handlers.onDone) {
              handlers.onDone(event);
            } else if (event.t === 'error' && handlers.onError) {
              handlers.onError(event);
            }
          }
          return pump();
        });
      }
      return pump();
    });
  }

  return {
    get: get,
    post: post,
    models: function () { return get('/api/image/models'); },
    status: function () { return get('/api/image/status'); },
    downloadStatus: function () { return get('/api/image/download/status'); },
    search: function (q) {
      return get('/api/image/search?q=' + encodeURIComponent(q));
    },
    load: function (id) { return post('/api/image/load', { id: id }); },
    unload: function (id) { return post('/api/image/unload', { id: id }); },
    download: function (id) { return post('/api/image/download', { id: id }); },
    cancel: function () { return post('/api/image/cancel', {}); },
    generate: streamGenerate
  };
})();
