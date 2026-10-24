var API = (function () {
  async function request(path, options) {
    try {
      var resp = await fetch(path, Object.assign({ cache: "no-store" }, options || {}));
      var text = await resp.text();
      var data = null;
      try { data = text ? JSON.parse(text) : null; } catch (e) { data = null; }
      if (!data) {
        return { success: false, error: "HTTP " + resp.status + " — unexpected response" };
      }
      return data;
    } catch (e) {
      return { success: false, error: String(e && e.message ? e.message : e) };
    }
  }

  function post(path, body) {
    return request(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {})
    });
  }

  return {
    get: function (path) { return request(path); },
    post: post,

    providers: function () { return request("/api/providers"); },
    providerAction: function (body) { return post("/api/providers", body); },
    saveProvider: function (data) {
      return post("/api/providers", Object.assign({ action: "save" }, data));
    },
    deleteProvider: function (id) {
      return post("/api/providers", { action: "delete", id: id });
    },
    setActiveProvider: function (id) {
      return post("/api/providers", { action: "active", id: id });
    },
    testProvider: function (id) {
      return post("/api/providers", { action: "test", id: id });
    },

    telemetry: function () { return request("/api/telemetry"); },
    benchmark: function () { return request("/api/benchmark"); },
    runBenchmark: function (id) { return post("/api/benchmark/run", id ? { id: id } : {}); },
    logs: function (filter, query, offset, limit) {
      var params = [
        "limit=" + encodeURIComponent(limit || 40),
        "type=" + encodeURIComponent(filter || "all"),
        "offset=" + encodeURIComponent(offset || 0)
      ];
      if (query) params.push("q=" + encodeURIComponent(query));
      return request("/api/logs?" + params.join("&"));
    },
    memory: function (query) {
      return request("/api/memory?limit=20" + (query ? "&q=" + encodeURIComponent(query) : ""));
    },
    skills: function (name) {
      return request("/api/skills" + (name ? "?name=" + encodeURIComponent(name) : ""));
    },
    tools: function () { return request("/api/tools"); },
    tasks: function () { return request("/api/tasks"); },
    createTask: function (data) { return post("/api/tasks/create", data); },
    updateTaskStatus: function (data) { return post("/api/tasks/status", data); },
    runTask: function (id) { return post("/api/tasks/run", { id: id }); },
    taskResult: function (data) { return post("/api/tasks/result", data); },

    models: function () { return request("/api/models"); },
    downloadModel: function (id) { return post("/api/models/download", { id: id }); },
    loadModel: function (id) { return post("/api/models/load", { id: id }); },
    unloadModel: function (id) { return post("/api/models/unload", { id: id }); },
    freeRam: function () { return post("/api/memory/free", {}); },
    stopServer: function () { return post("/api/server/stop", {}); },

    chat: function (messages, options) {
      var opts = options || {};
      var body = Object.assign({ messages: messages }, opts);
      delete body.signal;
      return request("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal: opts.signal
      });
    },
    chatStream: function (messages, options) {
      var opts = options || {};
      var body = Object.assign({ messages: messages, stream: true }, opts);
      delete body.signal;
      return fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal: opts.signal
      });
    }
  };
})();
