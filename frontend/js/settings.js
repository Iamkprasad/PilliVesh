var Settings = (function () {
  var el = {};
  var providers = null;
  var currentTab = "assistant";
  var editingId = null;
  var modelTimer = null;
  var memoryTimer = null;
  var logTimer = null;
  var benchTimer = null;
  var modelBusy = false;
  var benchBusy = false;
  var modelData = { catalog: [], download: {}, router_running: false, loaded_ids: [] };
  var telemetryData = null;
  var benchmarkLatest = null;
  var logState = { filter: "all", query: "", offset: 0, limit: 40, total: 0, records: [] };
  var logSeq = 0;

  function init() {
    el = {
      tabs: document.getElementById("settingsTabs"),
      providerList: document.getElementById("providerList"),
      addProvider: document.getElementById("addProvider"),
      formTitle: document.getElementById("providerFormTitle"),
      form: document.getElementById("providerForm"),
      preset: document.getElementById("presetSelect"),
      name: document.getElementById("providerName"),
      type: document.getElementById("providerType"),
      base: document.getElementById("providerBase"),
      model: document.getElementById("providerModel"),
      key: document.getElementById("providerKey"),
      keyHint: document.getElementById("providerKeyHint"),
      saveBtn: document.getElementById("providerSaveBtn"),
      cancelBtn: document.getElementById("providerCancelBtn"),
      formMsg: document.getElementById("providerFormMsg"),
      testMsg: document.getElementById("providerTestMsg"),
      harnessPrompt: document.getElementById("harnessPrompt"),
      harnessTemp: document.getElementById("harnessTemp"),
      tempOut: document.getElementById("tempOut"),
      harnessTokens: document.getElementById("harnessTokens"),
      harnessTools: document.getElementById("harnessTools"),
      harnessMsg: document.getElementById("harnessMsg"),
      clearAll: document.getElementById("clearAllChatsBtn"),
      freeRam: document.getElementById("freeRamBtn"),
      modelList: document.getElementById("modelList"),
      modelsMsg: document.getElementById("modelsMsg"),
      modelsRefresh: document.getElementById("modelsRefreshBtn"),
      sysStats: document.getElementById("sysStats"),
      deviceSummary: document.getElementById("deviceSummary"),
      runtimeStatus: document.getElementById("runtimeStatus"),
      runtimeSummary: document.getElementById("runtimeSummary"),
      sysMsg: document.getElementById("sysMsg"),
      stopServer: document.getElementById("stopServerBtn"),
      benchShortcut: document.getElementById("benchShortcutBtn"),
      taskForm: document.getElementById("taskForm"),
      taskProject: document.getElementById("taskProject"),
      taskTitle: document.getElementById("taskTitle"),
      taskMsg: document.getElementById("taskMsg"),
      taskCounts: document.getElementById("taskCounts"),
      taskList: document.getElementById("taskList"),
      taskSummary: document.getElementById("taskSummary"),
      logFilter: document.getElementById("logFilter"),
      logSearch: document.getElementById("logSearch"),
      logsRefresh: document.getElementById("logsRefreshBtn"),
      logsMore: document.getElementById("logsMoreBtn"),
      logSummary: document.getElementById("logSummary"),
      logList: document.getElementById("logList"),
      memSearch: document.getElementById("memSearch"),
      memRetry: document.getElementById("memRetryBtn"),
      memSummary: document.getElementById("memSummary"),
      memState: document.getElementById("memState"),
      memCounts: document.getElementById("memCounts"),
      memMsg: document.getElementById("memMsg"),
      memList: document.getElementById("memList"),
      benchState: document.getElementById("benchState"),
      benchModel: document.getElementById("benchModel"),
      benchSub: document.getElementById("benchSub"),
      benchRun: document.getElementById("benchRunBtn"),
      benchModels: document.getElementById("benchModelsBtn"),
      benchMsg: document.getElementById("benchMsg"),
      benchProgress: document.getElementById("benchProgress"),
      benchElapsed: document.getElementById("benchElapsed"),
      benchResults: document.getElementById("benchResults"),
      benchHistory: document.getElementById("benchHistory")
    };
    bind();
  }

  function bind() {
    el.tabs.addEventListener("click", function (event) {
      var button = event.target.closest("button[data-tab]");
      if (button) setTab(button.getAttribute("data-tab"));
    });
    el.form.addEventListener("submit", saveProvider);
    el.preset.addEventListener("change", applyPreset);
    el.cancelBtn.addEventListener("click", resetProviderForm);
    el.providerList.addEventListener("click", function (event) {
      var button = event.target.closest("button");
      if (!button) return;
      if (button.hasAttribute("data-edit")) editProvider(button.getAttribute("data-edit"));
      else if (button.hasAttribute("data-test")) testProvider(button.getAttribute("data-test"), button);
      else if (button.hasAttribute("data-delete")) removeProvider(button.getAttribute("data-delete"));
      else if (button.hasAttribute("data-models")) setTab("models");
      else if (button.hasAttribute("data-activate")) setActiveProvider(button.getAttribute("data-activate"));
    });

    el.harnessPrompt.addEventListener("input", saveHarness);
    el.harnessTemp.addEventListener("input", function () {
      el.tempOut.textContent = el.harnessTemp.value;
      saveHarness();
    });
    el.harnessTokens.addEventListener("change", function () {
      var value = parseInt(el.harnessTokens.value, 10);
      if (isNaN(value)) value = 512;
      value = Math.max(1, Math.min(2048, value));
      el.harnessTokens.value = value;
      saveHarness();
    });
    el.harnessTools.addEventListener("change", saveHarness);
    el.clearAll.addEventListener("click", function () {
      if (!confirm("Delete every chat on this device? This cannot be undone.")) return;
      Store.saveChats([]);
      if (window.App) App.reloadChats();
      show(el.harnessMsg, "All chats cleared.", "ok");
    });
    el.freeRam.addEventListener("click", freeRam);

    el.modelsRefresh.addEventListener("click", loadModels);
    el.modelList.addEventListener("click", function (event) {
      var button = event.target.closest("button");
      if (!button || modelBusy) return;
      var id = button.getAttribute("data-id");
      if (button.hasAttribute("data-download")) downloadModel(id);
      else if (button.hasAttribute("data-load")) loadModel(id);
      else if (button.hasAttribute("data-unload")) unloadModel(id);
    });

    el.benchRun.addEventListener("click", function () { runBenchmark(null); });
    el.benchModels.addEventListener("click", function () { setTab("models"); });
    el.benchShortcut.addEventListener("click", function () { setTab("benchmarks"); });
    el.stopServer.addEventListener("click", function () {
      if (!confirm("Stop the PilliVesh server and close the port?")) return;
      API.stopServer().then(function () {
        show(el.sysMsg, "Server stopped. Restart with ./run-dashboard.sh.", "ok");
      });
    });

    el.taskForm.addEventListener("submit", createTask);
    el.taskList.addEventListener("click", function (event) {
      var button = event.target.closest("button");
      if (!button) return;
      var id = button.getAttribute("data-task");
      if (button.hasAttribute("data-run")) runTask(id, button);
      else if (button.hasAttribute("data-done")) setTaskStatus(id, "completed");
      else if (button.hasAttribute("data-cancel")) setTaskStatus(id, "cancelled");
      else if (button.hasAttribute("data-result")) showTaskResult(id, button);
    });

    el.logFilter.addEventListener("change", function () { loadLogs(true); });
    el.logsRefresh.addEventListener("click", function () { loadLogs(true); });
    el.logsMore.addEventListener("click", function () { loadLogs(false); });
    el.logSearch.addEventListener("input", function () {
      clearTimeout(logTimer);
      logTimer = setTimeout(function () { loadLogs(true); }, 300);
    });
    el.memSearch.addEventListener("input", function () {
      clearTimeout(memoryTimer);
      memoryTimer = setTimeout(function () { loadMemory(el.memSearch.value); }, 300);
    });
    el.memRetry.addEventListener("click", function () {
      loadMemory(el.memSearch.value);
    });
  }

  function open(tab) {
    setTab(tab || currentTab);
  }

  function close() {
    clearTimeout(logTimer);
    clearTimeout(memoryTimer);
  }

  function setTab(name) {
    if (name === "harness") name = "assistant";
    if (name === "models" || name === "benchmarks") {
      if (window.App) window.App.go(name);
      return;
    }
    if (["assistant", "providers", "system"].indexOf(name) < 0) name = "assistant";
    currentTab = name;
    var page = document.getElementById("page-settings");
    if (page && !page.hidden) showTab(name);
    else if (window.App) window.App.go("settings");
  }

  function showTab(name) {
    name = name || currentTab;
    if (["assistant", "providers", "system"].indexOf(name) < 0) name = "assistant";
    currentTab = name;
    el.tabs.querySelectorAll("button").forEach(function (button) {
      var on = button.getAttribute("data-tab") === name;
      button.classList.toggle("on", on);
      button.setAttribute("aria-selected", on ? "true" : "false");
    });
    document.querySelectorAll("#page-settings [data-panel]").forEach(function (panel) {
      panel.classList.toggle("active", panel.getAttribute("data-panel") === name);
    });
    if (name === "assistant") loadHarnessForm();
    if (name === "providers") loadProviders();
    if (name === "system") loadSystem();
  }

  function show(target, text, kind) {
    if (!target) return;
    target.textContent = text || "";
    if (!target.classList.contains("form-msg")) target.classList.add("form-msg");
    target.classList.remove("ok", "err");
    if (kind) target.classList.add(kind);
  }

  function countLabel(n, one, many) {
    return n + " " + (n === 1 ? one : many);
  }

  function gb(mb) {
    if (mb == null || isNaN(mb)) return "—";
    return (mb / 1024).toFixed(1) + " GB";
  }

  function fmtTime(ts) {
    if (!ts) return "—";
    var date = new Date(ts);
    if (isNaN(date.getTime())) return String(ts);
    try {
      return date.toLocaleString([], {
        day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", hour12: false
      });
    } catch (e) {
      return String(ts);
    }
  }

  function ago(ts) {
    if (!ts) return "";
    var ms = Date.now() - new Date(ts).getTime();
    if (isNaN(ms) || ms < 0) return "";
    var min = Math.floor(ms / 60000);
    if (min < 1) return "just now";
    if (min < 60) return min + "m ago";
    var hours = Math.floor(min / 60);
    if (hours < 24) return hours + "h ago";
    var days = Math.floor(hours / 24);
    return days + "d ago";
  }

  /* ---------------- providers ---------------- */

  function populatePresets(presets) {
    var current = el.preset.value;
    var html = '<option value="">Custom provider</option>';
    (presets || []).forEach(function (preset) {
      if (preset.preset === "custom") return;
      html += '<option value="' + esc(preset.preset) + '">' + esc(preset.name) + "</option>";
    });
    el.preset.innerHTML = html;
    el.preset.value = current || "";
  }

  function applyPreset() {
    var selected = el.preset.value;
    if (!selected) return;
    var preset = ((providers && providers.presets) || []).filter(function (item) {
      return item.preset === selected;
    })[0];
    if (!preset) return;
    el.name.value = preset.name || "";
    el.type.value = preset.type || "openai";
    el.base.value = preset.base_url || "";
    el.model.value = preset.model || "";
    el.key.focus();
  }

  async function loadProviders() {
    var response = await API.providers();
    if (!response.success) {
      el.providerList.innerHTML = '<div class="empty-note">Providers unavailable: ' + esc(response.error) + "</div>";
      return;
    }
    providers = response.data || {};
    populatePresets(providers.presets);
    renderProviders();
    if (window.App) App.setProviders(providers);
  }

  function providerCard(provider) {
    var active = provider.active;
    var isLocal = provider.type === "local";
    var local = (providers && providers.local) || {};
    var modelLabel = isLocal ? (local.loaded_id || "No model loaded") : (provider.model || "no model");
    var meta;
    var metaClass = "";
    var actions = "";
    if (isLocal) {
      if (local.running) {
        meta = "Running on llama-server" + (local.loaded_id ? " · " + local.loaded_id : "");
        metaClass = "ok";
      } else {
        meta = "Not loaded — open Models to load one";
        metaClass = "bad";
      }
      actions = '<button class="mini" data-models="1">Open models</button>' +
        '<button class="mini" data-test="' + esc(provider.id) + '">Test</button>';
    } else {
      if (provider.has_key) {
        meta = "Key " + (provider.key_hint || "saved") + " · " + (provider.base_url || "");
        metaClass = "ok";
      } else {
        meta = "No API key saved";
        metaClass = "bad";
      }
      actions = '<button class="mini" data-test="' + esc(provider.id) + '">Test</button>' +
        '<button class="mini" data-edit="' + esc(provider.id) + '">Edit</button>' +
        '<button class="mini danger" data-delete="' + esc(provider.id) + '">Delete</button>';
    }
    var activate = active
      ? '<span class="badge">active</span>'
      : '<button class="mini" data-activate="' + esc(provider.id) + '">Activate</button>';
    return '<div class="provider-card' + (active ? " active" : "") + '" data-provider="' + esc(provider.id) + '">' +
      '<div class="provider-top">' +
        '<div class="provider-avatar ' + esc(provider.type) + '">' + esc(initialOf(provider.name)) + "</div>" +
        '<div class="provider-main">' +
          '<div class="provider-name">' + esc(provider.name) + " " + activate + "</div>" +
          '<div class="provider-sub">' + esc(modelLabel) + " · " + esc(provider.type_label || provider.type) + "</div>" +
        "</div>" +
      "</div>" +
      '<div class="provider-meta ' + metaClass + '">' + esc(meta) + "</div>" +
      '<div class="provider-actions">' + actions + "</div>" +
      '<div class="form-msg provider-test"></div>' +
    "</div>";
  }

  function renderProviders() {
    var list = (providers && providers.providers) || [];
    el.providerList.innerHTML = list.map(providerCard).join("") ||
      '<div class="empty-note">No providers configured.</div>';
    if (providers && providers.active) {
      var activeProvider = list.filter(function (p) { return p.id === providers.active; })[0];
      if (activeProvider && activeProvider.type !== "local" && !activeProvider.has_key) {
        show(el.testMsg, "The active provider has no API key. Add one before chatting.", "err");
      } else {
        show(el.testMsg, "", "");
      }
    }
  }

  async function setActiveProvider(id) {
    var response = await API.setActiveProvider(id);
    if (!response.success) {
      show(el.testMsg, response.error || "Could not switch provider", "err");
      return;
    }
    await loadProviders();
    show(el.testMsg, "Active provider updated.", "ok");
  }

  async function testProvider(id, button) {
    var card = el.providerList.querySelector('[data-provider="' + id + '"]');
    var target = card ? card.querySelector(".provider-test") : el.testMsg;
    show(target, "Testing…", "");
    button.disabled = true;
    var response = await API.testProvider(id);
    button.disabled = false;
    if (!response.success) {
      show(target, response.error || "Test failed", "err");
      return;
    }
    show(target, (response.data && response.data.detail) || "Connection OK", "ok");
    if (card) {
      var meta = card.querySelector(".provider-meta");
      if (meta) meta.className = "provider-meta ok";
    }
  }

  function editProvider(id) {
    if (!providers) return;
    var provider = (providers.providers || []).filter(function (p) { return p.id === id; })[0];
    if (!provider) return;
    editingId = id;
    el.preset.value = "";
    el.name.value = provider.name || "";
    el.type.value = provider.type || "openai";
    el.base.value = provider.base_url || "";
    el.model.value = provider.model || "";
    el.key.value = "";
    el.key.placeholder = provider.has_key ? "saved key — leave blank to keep" : "paste key";
    el.keyHint.textContent = provider.has_key
      ? "A key is saved (" + provider.key_hint + "). Leave blank to keep it."
      : "No key saved yet.";
    el.formTitle.textContent = "Edit " + provider.name;
    el.saveBtn.textContent = "Save changes";
    el.cancelBtn.hidden = false;
    el.addProvider.open = true;
    show(el.formMsg, "", "");
    el.addProvider.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function resetProviderForm() {
    editingId = null;
    el.form.reset();
    el.preset.value = "";
    el.type.value = "openai";
    el.key.placeholder = "paste key";
    el.keyHint.textContent = "Leave blank when editing to keep the saved key.";
    el.formTitle.textContent = "+ Add a provider";
    el.saveBtn.textContent = "Save provider";
    el.cancelBtn.hidden = true;
    show(el.formMsg, "", "");
  }

  async function saveProvider(event) {
    event.preventDefault();
    var payload = {
      name: el.name.value.trim(),
      type: el.type.value,
      base_url: el.base.value.trim(),
      model: el.model.value.trim(),
      api_key: el.key.value.trim()
    };
    if (editingId) payload.id = editingId;
    if (!payload.name || !payload.base_url || !payload.model) {
      show(el.formMsg, "Name, base URL and model are required.", "err");
      return;
    }
    el.saveBtn.disabled = true;
    show(el.formMsg, "Saving…", "");
    var response = await API.saveProvider(payload);
    el.saveBtn.disabled = false;
    if (!response.success) {
      show(el.formMsg, response.error || "Could not save provider", "err");
      return;
    }
    resetProviderForm();
    await loadProviders();
    show(el.formMsg, "Provider saved. Key stored on this device only.", "ok");
  }

  async function removeProvider(id) {
    if (!confirm("Delete this provider and its saved API key?")) return;
    var response = await API.deleteProvider(id);
    if (!response.success) {
      show(el.testMsg, response.error || "Could not delete provider", "err");
      return;
    }
    await loadProviders();
    show(el.testMsg, "Provider deleted.", "ok");
  }

  /* ---------------- harness ---------------- */

  function loadHarnessForm() {
    var settings = Store.harness();
    el.harnessPrompt.value = settings.systemPrompt || "";
    el.harnessTemp.value = settings.temperature;
    el.tempOut.textContent = settings.temperature;
    el.harnessTokens.value = settings.maxTokens;
    el.harnessTools.checked = !!settings.useTools;
    show(el.harnessMsg, "", "");
  }

  function saveHarness() {
    var settings = Store.harness();
    settings.systemPrompt = el.harnessPrompt.value;
    settings.temperature = parseFloat(el.harnessTemp.value) || 0;
    settings.maxTokens = parseInt(el.harnessTokens.value, 10) || 512;
    settings.useTools = el.harnessTools.checked;
    Store.saveHarness(settings);
    if (window.App) App.applyHarness();
  }

  async function freeRam() {
    if (!confirm("Run best-effort RAM cleanup? Flushes caches, kills stale inferencers and asks Android to clear background apps.")) return;
    el.freeRam.disabled = true;
    show(el.harnessMsg, "Cleaning…", "");
    var response = await API.freeRam();
    el.freeRam.disabled = false;
    if (!response.success) {
      show(el.harnessMsg, response.error || "Cleanup failed", "err");
      return;
    }
    var data = response.data || {};
    var freed = data.freed_mb;
    var head = freed == null
      ? "Cleanup finished (memory delta unavailable)."
      : (freed >= 0 ? "Freed about " + freed + " MB." : "Available RAM changed by " + freed + " MB.");
    show(el.harnessMsg, head, "ok");
  }

  /* ---------------- models ---------------- */

  function setModelData(data) {
    if (!data) return;
    modelData = {
      catalog: data.catalog || [],
      download: data.download || {},
      router_running: !!data.router_running,
      loaded_ids: data.loaded_ids || []
    };
  }

  function residentModel() {
    return modelData.catalog.filter(function (model) { return model.loaded; })[0] || null;
  }

  async function loadModels() {
    clearTimeout(modelTimer);
    var response = await API.models();
    if (!response.success) {
      show(el.modelsMsg, response.error || "Models unavailable", "err");
      return;
    }
    setModelData(response.data || {});
    renderModels();
    var download = modelData.download || {};
    if (download.status === "error") {
      show(el.modelsMsg, download.error || "Download failed", "err");
    } else if (download.status === "downloading") {
      show(el.modelsMsg, "Downloading " + (download.model_id || "model") + "…", "");
      modelTimer = setTimeout(loadModels, 2000);
    } else {
      show(el.modelsMsg, "", "");
    }
    if (window.App) App.refreshProviders();
  }

  function modelCard(model) {
    var download = modelData.download || {};
    var pct = null;
    if (download.status === "downloading" && download.model_id === model.id && download.bytes_total) {
      pct = Math.min(99, Math.round(download.bytes_done / download.bytes_total * 100));
    }
    var buttons = "";
    if (model.loaded) {
      buttons = '<span class="tag ok">resident</span>' +
        '<button class="mini" data-unload="1" data-id="' + esc(model.id) + '">Unload</button>';
    } else if (model.installed) {
      buttons = '<button class="mini" data-load="1" data-id="' + esc(model.id) + '">Load</button>';
    } else if (download.status === "downloading" && download.model_id === model.id) {
      buttons = '<span class="tag warn">downloading ' + (pct != null ? pct + "%" : "…") + "</span>";
    } else {
      buttons = '<button class="mini" data-download="1" data-id="' + esc(model.id) + '">Download</button>';
    }
    var stats = model.stats && model.stats.runs
      ? '<span class="tag">' + esc(model.stats.avg_generation_tps) + " t/s avg</span>"
      : "";
    return '<div class="model-card">' +
      '<div class="model-top"><span class="model-name">' + esc(model.name) + "</span>" +
        '<span class="tag">' + esc(model.quant) + "</span>" + stats + "</div>" +
      '<div class="model-sub">' + esc(model.size_mb) + " MB · needs ~" + esc(model.min_ram_mb) +
        " MB free · ctx " + esc(model.context) + "</div>" +
      (model.notes ? '<div class="model-note">' + esc(model.notes) + "</div>" : "") +
      (pct != null ? '<div class="bar"><i style="width:' + pct + '%"></i></div>' : "") +
      '<div class="model-actions">' + buttons + "</div>" +
    "</div>";
  }

  function modelGroup(key, title, note, items) {
    if (!items.length) return "";
    return '<div class="model-group">' +
      '<div class="model-group-head"><span>' + esc(title) + "</span>" +
        '<small>' + esc(note) + " · " + items.length + "</small></div>" +
      items.map(modelCard).join("") +
      "</div>";
  }

  function renderModels() {
    var catalog = modelData.catalog || [];
    var resident = catalog.filter(function (m) { return m.loaded; });
    var installed = catalog.filter(function (m) { return m.installed && !m.loaded; });
    var available = catalog.filter(function (m) { return !m.installed; });
    var html = modelGroup("resident", "Resident", "loaded in memory", resident) +
      modelGroup("installed", "Installed", "downloaded, not loaded", installed) +
      modelGroup("available", "Available", "not downloaded", available);
    el.modelList.innerHTML = html || '<div class="empty-note">No models in catalog.</div>';
  }

  async function downloadModel(id) {
    modelBusy = true;
    show(el.modelsMsg, "Starting download…", "");
    var response = await API.downloadModel(id);
    modelBusy = false;
    if (!response.success) show(el.modelsMsg, response.error || "Download failed", "err");
    loadModels();
  }

  async function loadModel(id) {
    modelBusy = true;
    show(el.modelsMsg, "Loading " + id + " (up to 30 s)…", "");
    var response = await API.loadModel(id);
    modelBusy = false;
    if (!response.success) show(el.modelsMsg, response.error || "Load failed", "err");
    else show(el.modelsMsg, "Loaded " + id + ". One model stays resident at a time.", "ok");
    await loadModels();
    if (window.App) {
      App.refreshOverview();
    }
  }

  async function unloadModel(id) {
    modelBusy = true;
    show(el.modelsMsg, "Unloading…", "");
    var response = await API.unloadModel(id);
    modelBusy = false;
    if (!response.success) show(el.modelsMsg, response.error || "Unload failed", "err");
    else show(el.modelsMsg, "Model unloaded.", "ok");
    await loadModels();
    if (window.App) {
      App.refreshOverview();
    }
  }

  /* ---------------- benchmarks ---------------- */

  function benchMetric(label, value, unit, sub) {
    return '<div class="bench-metric"><div class="k">' + esc(label) + "</div>" +
      '<div class="v">' + esc(value) + '<span class="u">' + esc(unit || "") + "</span></div>" +
      (sub ? '<div class="s">' + esc(sub) + "</div>" : "") + "</div>";
  }

  function latestEarlierSuccess(history, latestTimestamp, model) {
    var successes = (history || []).filter(function (item) {
      return item.status === "success" && item.metrics &&
        item.metrics.generation_tokens_per_second != null &&
        item.timestamp !== latestTimestamp &&
        (!model || item.model === model);
    });
    return successes.length ? successes[successes.length - 1] : null;
  }

  function renderBenchResults(data, modelsOk, resident) {
    if (!data) {
      el.benchResults.innerHTML = "";
      el.benchHistory.innerHTML = '<div class="empty-note">No probe history yet.</div>';
      return;
    }
    var metrics = data.metrics || {};
    var history = data.history || [];
    var stale = data.status === "stale" ||
      (data.status === "success" && modelsOk === true && !resident);
    var success = data.status === "success" || stale;
    var previous = latestEarlierSuccess(history, data.timestamp, data.model);
    var compare = "";
    if (previous && metrics.generation_tokens_per_second != null && !stale) {
      var before = previous.metrics.generation_tokens_per_second;
      var after = metrics.generation_tokens_per_second;
      if (before) {
        var delta = Math.round((after - before) / before * 100);
        compare = '<div class="bench-compare">Generation ' +
          (delta >= 0 ? "+" : "") + delta + "% vs previous run (" +
          esc(fmtTime(previous.timestamp)) + ": " + esc(before) + " tok/s)</div>";
      }
    }
    var statusLine;
    if (stale) {
      statusLine = "No model is resident now. Showing the last successful run from " + fmtTime(data.timestamp) + ".";
    } else if (data.status === "success") {
      statusLine = "Successful light probe · " + fmtTime(data.timestamp);
    } else {
      statusLine = data.message || "The probe finished without throughput metrics.";
    }
    var cards = "";
    if (success) {
      cards = '<div class="bench-metrics">' +
        benchMetric("Generation", metrics.generation_tokens_per_second != null ? metrics.generation_tokens_per_second : "—", "tok/s", stale ? "last successful run" : "48-token probe") +
        benchMetric("Prompt", metrics.prompt_tokens_per_second != null ? metrics.prompt_tokens_per_second : "—", "tok/s", "prompt processing") +
        benchMetric("Duration", data.elapsed_seconds != null ? data.elapsed_seconds : "—", "s", "end-to-end") +
        benchMetric("Workload", data.completion_tokens != null ? data.completion_tokens : "—", "tokens", data.prompt_tokens != null ? data.prompt_tokens + " prompt tokens" : "light probe") +
      "</div>";
    }
    var resident = modelsOk === false ? null : residentModel();
    var modelName = (resident && resident.name) || data.model || "—";
    var quant = resident ? resident.quant : "—";
    var runtime = data.runtime || {};
    var backend = runtime.backend || (telemetryData && telemetryData.runtime && telemetryData.runtime.backend) || "—";
    var context = resident ? resident.context : "—";
    var meta = '<div class="bench-meta">' +
      '<div><span>Model</span><b>' + esc(modelName) + " · " + esc(quant) + "</b></div>" +
      '<div><span>Backend</span><b>' + esc(backend) + "</b></div>" +
      '<div><span>Context</span><b>' + esc(context) + "</b></div>" +
      (runtime.ram_available_mb != null
        ? '<div><span>RAM available</span><b>' + esc(gb(runtime.ram_available_mb)) + "</b></div>"
        : "") +
      '<div><span>Status</span><b>' + esc(stale ? "stale" : data.status) + "</b></div>" +
      "</div>";
    el.benchResults.innerHTML = '<div class="bench-status' + (stale ? " warn" : "") + '">' +
      esc(statusLine) + "</div>" + cards + compare + meta;

    var rows = history.slice().reverse().slice(0, 8);
    el.benchHistory.innerHTML = rows.length ? rows.map(function (item) {
      var m = item.metrics || {};
      return '<div class="mini-item bench-history-row">' +
        '<div class="meta"><span>' + esc(fmtTime(item.timestamp)) + "</span>" +
          '<span class="tag' + (item.status === "success" ? " ok" : "") + '">' + esc(item.status) + "</span>" +
          '<span>' + esc(item.model || "—") + "</span></div>" +
        '<div class="bench-history-metrics"><span>' +
          esc(m.generation_tokens_per_second != null ? m.generation_tokens_per_second : "—") + " tok/s gen</span><span>" +
          esc(m.prompt_tokens_per_second != null ? m.prompt_tokens_per_second : "—") + " tok/s prompt</span>" +
          (item.elapsed_seconds != null ? "<span>" + esc(item.elapsed_seconds) + " s</span>" : "") +
        "</div></div>";
    }).join("") : '<div class="empty-note">No probe history yet.</div>';
  }

  async function loadBenchmarks() {
    var results = await Promise.all([API.benchmark(), API.models(), API.telemetry()]);
    if (results[1].success) setModelData(results[1].data || {});
    if (results[2].success) telemetryData = results[2].data || {};
    var resident = results[1].success ? residentModel() : null;
    var runtime = (telemetryData && telemetryData.runtime) || {};
    var backend = runtime.backend || "unknown";
    var ready = !!resident;
    el.benchState.className = "bench-readiness " + (ready ? "ready" : "not-ready");
    if (resident) {
      el.benchModel.textContent = resident.name + " · " + resident.quant;
      el.benchSub.textContent = "Resident on llama-server · backend " + backend +
        " · context " + resident.context + " · " + resident.size_mb + " MB on disk";
    } else {
      el.benchModel.textContent = "No model is resident";
      el.benchSub.textContent = results[1].success
        ? "Load a model in Models first. PilliVesh will not load or switch models automatically."
        : "Model state unavailable: " + (results[1].error || "unknown error") +
          ". Load a model in Models once the runtime is reachable.";
    }
    el.benchRun.disabled = !resident || benchBusy;
    el.benchRun.textContent = benchBusy ? "Running light probe…" : "Run light benchmark";
    if (!benchBusy && el.benchProgress) el.benchProgress.hidden = true;

    if (!results[0].success) {
      benchmarkLatest = null;
      renderBenchResults(null);
      show(el.benchMsg, results[0].error || "No benchmark data yet.", "");
      return;
    }
    var data = results[0].data || {};
    benchmarkLatest = data;
    renderBenchResults(data, results[1].success, resident);
    if (data.status === "success") show(el.benchMsg, "", "");
    else if (data.status === "stale") show(el.benchMsg, data.message || "Showing the last successful run.", "");
    else if (data.message) show(el.benchMsg, data.message, "");
    else show(el.benchMsg, "", "");
  }

  function wait(ms) {
    return new Promise(function (resolve) { setTimeout(resolve, ms); });
  }

  async function waitForProbe(beforeTimestamp) {
    var deadline = Date.now() + 75000;
    while (Date.now() < deadline) {
      await wait(3000);
      var response = await API.benchmark();
      if (response.success && response.data) {
        if (!beforeTimestamp || response.data.timestamp !== beforeTimestamp) {
          return true;
        }
      }
    }
    return false;
  }

  async function runBenchmark(id) {
    if (benchBusy) return false;
    var resident = residentModel();
    if (!resident) {
      // Refresh status before refusing: the overview may know more than this cache.
      var models = await API.models();
      if (models.success) {
        setModelData(models.data || {});
        resident = residentModel();
      }
    }
    if (!resident) {
      setTab("benchmarks");
      show(el.benchMsg, "No model is resident. Load one in Models; benchmark will not switch models for you.", "err");
      return false;
    }
    var beforeTimestamp = benchmarkLatest ? benchmarkLatest.timestamp : null;
    if (!beforeTimestamp) {
      var current = await API.benchmark();
      if (current.success && current.data) {
        benchmarkLatest = current.data;
        beforeTimestamp = current.data.timestamp;
      }
    }
    benchBusy = true;
    var startedAt = Date.now();
    el.benchRun.disabled = true;
    el.benchRun.textContent = "Running light probe…";
    if (el.benchProgress) el.benchProgress.hidden = false;
    if (el.benchElapsed) el.benchElapsed.textContent = "0s";
    clearInterval(benchTimer);
    benchTimer = setInterval(function () {
      if (el.benchElapsed) {
        el.benchElapsed.textContent = Math.round((Date.now() - startedAt) / 1000) + "s";
      }
    }, 1000);
    if (window.App) App.setBenchmarkBusy(true);
    show(el.benchMsg, "Running one 48-token probe against " + resident.name + ". This can take up to a minute.", "");
    var finished = false;
    try {
      var response = await API.runBenchmark(id);
      if (!response.success) {
        show(el.benchMsg, response.error || "Benchmark failed", "err");
        return false;
      }
      var data = response.data || {};
      if (data.status === "in_progress") {
        show(el.benchMsg, "A probe is already running. Waiting for it to finish…", "");
        el.benchRun.textContent = "Waiting for running probe…";
        var changed = await waitForProbe(beforeTimestamp);
        await loadBenchmarks();
        if (changed) {
          show(el.benchMsg, "The running light probe finished. Results below are from that run.", "ok");
          finished = true;
        } else {
          show(el.benchMsg, "The probe is taking longer than expected. Refresh Benchmarks in a moment.", "");
        }
        return finished;
      }
      await loadBenchmarks();
      if (data.status === "success") {
        show(el.benchMsg, "Light probe finished. Results below come from the resident model.", "ok");
        finished = true;
      } else {
        show(el.benchMsg, data.message || "Probe finished without throughput metrics.",
          data.status === "stale" || data.status === "waiting" ? "" : "err");
      }
      return finished;
    } finally {
      benchBusy = false;
      clearInterval(benchTimer);
      if (el.benchProgress) el.benchProgress.hidden = true;
      if (window.App) {
        App.setBenchmarkBusy(false);
        App.refreshHome();
      }
      el.benchRun.disabled = false;
      el.benchRun.textContent = "Run light benchmark";
      el.benchRun.disabled = !residentModel();
    }
  }

  /* ---------------- system ---------------- */

  async function loadSystem() {
    loadLogs(true);
    var results = await Promise.all([API.telemetry(), API.models(), API.providers()]);
    if (results[0].success) telemetryData = results[0].data || {};
    if (results[1].success) setModelData(results[1].data || {});
    if (results[2].success) {
      providers = results[2].data || {};
      if (window.App) App.setProviders(providers);
    }
    renderDevice(results[0], results[1]);
    renderRuntime(results[0], results[1]);
  }

  function statCard(label, value, sub) {
    return '<div class="stat"><div class="k">' + esc(label) + '</div><div class="v">' +
      esc(value) + "</div>" + (sub ? '<div class="s">' + esc(sub) + "</div>" : "") + "</div>";
  }

  function renderDevice(telemetryResponse, modelsResponse) {
    if (!telemetryData) {
      el.sysStats.innerHTML = '<div class="empty-note">Telemetry unavailable: ' +
        esc((telemetryResponse && telemetryResponse.error) || "unknown error") + "</div>";
      el.deviceSummary.textContent = "telemetry unavailable";
      return;
    }
    var system = telemetryData.system || {};
    var memory = system.memory || {};
    var gpu = telemetryData.gpu || {};
    var runtime = telemetryData.runtime || {};
    var ramPct = memory.total_mb
      ? Math.round((memory.used_mb || 0) / memory.total_mb * 100)
      : null;
    var modelsOk = modelsResponse && modelsResponse.success;
    var resident = modelsOk ? residentModel() : null;
    var backend = runtime.backend || "unknown";
    var hardware;
    if (backend.indexOf("vulkan") >= 0) hardware = "Vulkan in use";
    else if (gpu.vulkan_available) hardware = "Vulkan available · CPU in use";
    else hardware = "CPU inference";
    el.sysStats.innerHTML =
      statCard("CPU cores", system.cpu_cores != null ? system.cpu_cores : "—", "detected") +
      statCard("RAM", gb(memory.used_mb) + " / " + gb(memory.total_mb),
        ramPct != null ? ramPct + "% used" : "unknown") +
      statCard("Available", gb(memory.available_mb),
        "swap " + gb(memory.swap_used_mb) + " / " + gb(memory.swap_total_mb)) +
      statCard("Backend", backend, "llama.cpp " + (runtime.llama_version || "—")) +
      statCard("Hardware", gpu.device || "None detected", hardware) +
      statCard("Model",
        modelsOk ? (resident ? resident.name : "none resident") : "unavailable",
        modelsOk
          ? (resident ? resident.quant + " · ctx " + resident.context : "load one in Models")
          : "model state error");
    el.deviceSummary.textContent = [
      system.cpu_cores != null ? system.cpu_cores + " cores" : null,
      gb(memory.used_mb) + " / " + gb(memory.total_mb),
      backend
    ].filter(Boolean).join(" · ");
  }

  function renderRuntime(telemetryResponse, modelsResponse) {
    var runtime = (telemetryData && telemetryData.runtime) || {};
    var modelsOk = !!(modelsResponse && modelsResponse.success);
    var resident = modelsOk ? residentModel() : null;
    var activeProvider = null;
    if (providers && providers.active) {
      activeProvider = (providers.providers || []).filter(function (p) {
        return p.id === providers.active;
      })[0] || null;
    }
    var routerState = !modelsOk ? "model state unavailable" : (modelData.router_running
      ? (resident ? resident.name + " · " + resident.quant : "running · no resident model")
      : "idle");
    var rows = [
      ["Local API", "online · " + (location.host || "127.0.0.1:8080")],
      ["llama-server", !modelsOk ? "unknown" :
        (modelData.router_running ? "running on 127.0.0.1:8081" : "idle")],
      ["Resident model", !modelsOk ? "unavailable" : (resident ? resident.name + " · " + resident.quant : "none")],
      ["Active provider", activeProvider
        ? activeProvider.name + " · " + (activeProvider.model || "no model")
        : "—"],
      ["Inference backend", runtime.backend || "unknown"]
    ];
    el.runtimeStatus.innerHTML = rows.map(function (row) {
      return '<div class="kv"><span>' + esc(row[0]) + "</span><b>" + esc(row[1]) + "</b></div>";
    }).join("");
    el.runtimeSummary.textContent = routerState;
    if (!modelsOk) {
      el.runtimeStatus.insertAdjacentHTML("afterbegin",
        '<div class="empty-note">Model state unavailable: ' +
        esc((modelsResponse && modelsResponse.error) || "unknown error") + "</div>");
    }
  }

  /* ---------------- tasks ---------------- */

  function statusTag(status) {
    var cls = status === "completed" ? "ok" : (status === "failed" ? "err" : (status === "active" ? "warn" : ""));
    return '<span class="tag ' + cls + '">' + esc(status) + "</span>";
  }

  function taskActions(task) {
    if (task.status === "active") {
      return '<div class="mini-actions">' +
        '<button class="mini" data-run="1" data-task="' + esc(task.id) + '">Run</button>' +
        '<button class="mini" data-done="1" data-task="' + esc(task.id) + '">Done</button>' +
        '<button class="mini" data-cancel="1" data-task="' + esc(task.id) + '">Cancel</button>' +
      "</div>";
    }
    if (task.status === "completed") {
      return '<div class="mini-actions">' +
        '<button class="mini" data-result="1" data-task="' + esc(task.id) + '">Result</button>' +
      "</div>";
    }
    return "";
  }

  function taskEntry(task) {
    return '<details class="task-entry">' +
      '<summary><span class="task-name">' + esc(task.title) + "</span>" +
        statusTag(task.status) + "</summary>" +
      '<div class="task-detail">' +
        '<div class="meta"><span>' + esc(task.project || "no project") + "</span>" +
          "<span>priority " + esc(task.priority) + "</span>" +
          (task.step_count ? "<span>" + esc(task.step_count) + " steps</span>" : "") +
          "<span>created " + esc(fmtTime(task.created_at)) + "</span></div>" +
        (task.notes ? '<div class="body">' + esc(task.notes) + "</div>" : "") +
        taskActions(task) +
      "</div></details>";
  }

  async function loadTasks() {
    var response = await API.tasks();
    if (!response.success) {
      el.taskList.innerHTML = '<div class="empty-note">Tasks unavailable: ' + esc(response.error) + "</div>";
      el.taskSummary.textContent = "unavailable";
      el.taskCounts.innerHTML = "";
      return;
    }
    var data = response.data || {};
    var counts = data.counts || {};
    var active = data.active || [];
    var recent = (data.recent || []).filter(function (task) {
      return task.status !== "active";
    });
    var total = counts.total != null ? counts.total : (active.length + recent.length);
    el.taskSummary.textContent = (counts.active || 0) + " active · " + total + " total";
    el.taskCounts.innerHTML = [
      ["active", counts.active],
      ["completed", counts.completed],
      ["failed", counts.failed],
      ["cancelled", counts.cancelled]
    ].map(function (pair) {
      return "<span>" + pair[0] + ": " + esc(pair[1] != null ? pair[1] : 0) + "</span>";
    }).join("");
    if (!active.length && !recent.length) {
      el.taskList.innerHTML = '<div class="empty-note">No tasks yet. Add one above; active tasks can run against the local model.</div>';
      return;
    }
    var html = "";
    if (active.length) {
      html += '<div class="group-label">Active</div>';
      html += active.map(taskEntry).join("");
    }
    if (recent.length) {
      html += '<div class="group-label">Recent</div>';
      html += recent.slice(0, 10).map(taskEntry).join("");
    }
    el.taskList.innerHTML = html;
  }

  async function createTask(event) {
    event.preventDefault();
    var project = el.taskProject.value.trim();
    var title = el.taskTitle.value.trim();
    if (!project || !title) {
      show(el.taskMsg, "Project and title are required.", "err");
      return;
    }
    var response = await API.createTask({ project: project, title: title, priority: 5 });
    if (!response.success) {
      show(el.taskMsg, response.error || "Could not create task", "err");
      return;
    }
    el.taskTitle.value = "";
    show(el.taskMsg, "Task created.", "ok");
    loadTasks();
  }

  async function runTask(id, button) {
    show(el.taskMsg, "Running task " + id + " against the local model…", "");
    if (button) button.disabled = true;
    var response = await API.runTask(id);
    if (button) button.disabled = false;
    if (!response.success) {
      show(el.taskMsg, response.error || "Task failed", "err");
      loadTasks();
      return;
    }
    show(el.taskMsg, "Task " + id + " completed.", "ok");
    loadTasks();
  }

  async function setTaskStatus(id, status) {
    var response = await API.updateTaskStatus({ id: id, status: status });
    if (!response.success) {
      show(el.taskMsg, response.error || "Could not update task", "err");
      return;
    }
    loadTasks();
  }

  async function showTaskResult(id, button) {
    button.disabled = true;
    var response = await API.taskResult({ id: id });
    button.disabled = false;
    if (!response.success) {
      show(el.taskMsg, response.error || "No result", "err");
      return;
    }
    var result = response.data.result || {};
    var content = "";
    try {
      content = result.choices[0].message.content || "";
    } catch (e) {
      content = JSON.stringify(result, null, 2);
    }
    var host = button.closest(".task-entry");
    if (!host) return;
    var existing = host.querySelector(".details-row");
    if (existing) existing.remove();
    var row = document.createElement("details");
    row.className = "details-row";
    row.open = true;
    row.innerHTML = "<summary>result</summary><pre>" + esc(content || "(empty)") + "</pre>";
    host.appendChild(row);
  }

  /* ---------------- logs ---------------- */

  function logRecordSummary(record) {
    var data = record.data || {};
    var event = record.event || "event";
    if (data.message) return String(data.message);
    if (data.summary) return String(data.summary);
    if (event === "task_created") {
      return "project " + (data.project || "—") + " · task #" + (data.id != null ? data.id : "?");
    }
    if (event === "task_updated" || event === "task_started" || event === "task_completed") {
      return "task #" + (data.id != null ? data.id : "?") + (data.status ? " · " + data.status : "");
    }
    if (event.indexOf("task_") === 0 && data.id != null) {
      return "task #" + data.id + (data.status ? " · " + data.status : "");
    }
    if (event === "chat_request") {
      return (data.model || "local") + " · " + (data.messages != null ? data.messages : "?") +
        " messages" + (data.use_tools ? " · tools" : "");
    }
    if (event.indexOf("chat_") === 0) {
      return (data.model || "local") + (data.category ? " · " + data.category : "");
    }
    if (event.indexOf("tool_") === 0) {
      return (data.tool || "tool") + (data.success === false ? " · failed" : "");
    }
    if (event.indexOf("model_") === 0) {
      return (data.model || data.model_id || "model") + (data.status ? " · " + data.status : "");
    }
    if (event.indexOf("benchmark") === 0) {
      return (data.model || "model") + (data.status ? " · " + data.status : "");
    }
    if (event === "provider_saved") return String(data.provider_type || "provider saved");
    if (event === "provider_deleted") return "provider removed";
    return "";
  }

  function logGroups(records) {
    var groups = [];
    records.forEach(function (record) {
      var last = groups[groups.length - 1];
      if (last && last.event === record.event) last.records.push(record);
      else groups.push({ event: record.event || "event", records: [record] });
    });
    return groups;
  }

  function renderLogs() {
    var records = logState.records;
    if (!records.length) {
      el.logList.innerHTML = '<div class="empty-note">' +
        (logState.query ? "No events match this search." :
          (logState.filter === "all" ? "No events stored yet." : "No events for this filter.")) +
        "</div>";
      el.logSummary.textContent = "0 events";
      el.logsMore.hidden = true;
      return;
    }
    var groups = logGroups(records);
    el.logList.innerHTML = groups.map(function (group) {
      var latest = group.records[0];
      var count = group.records.length;
      var countText = "×" + count;
      if (groups.length === 1 && logState.total > count) countText += " of " + logState.total;
      var entries = group.records.map(function (record) {
        return '<div class="log-entry">' +
          '<div class="log-line"><span class="log-time">' + esc(fmtTime(record.timestamp)) + "</span>" +
            "<span>" + esc(logRecordSummary(record)) + "</span></div>" +
          '<details class="details-row"><summary>raw event</summary><pre>' +
            esc(JSON.stringify(record, null, 2).slice(0, 3000)) + "</pre></details>" +
        "</div>";
      }).join("");
      return '<details class="log-group">' +
        '<summary><span class="log-time">' + esc(fmtTime(latest.timestamp)) + "</span>" +
          '<span class="tag">' + esc(group.event) + "</span>" +
          '<span class="log-summary">' + esc(logRecordSummary(latest)) + "</span>" +
          '<span class="log-count">' + countText + "</span></summary>" +
        '<div class="log-entries">' + entries + "</div>" +
      "</details>";
    }).join("");
    var label = countLabel(logState.total, "event", "events");
    if (logState.query) label += ' matching "' + logState.query + '"';
    var shown = records.length < logState.total
      ? " · showing " + records.length
      : "";
    el.logSummary.textContent = label + shown;
    el.logsMore.hidden = records.length >= logState.total;
  }

  async function loadLogs(reset) {
    clearTimeout(logTimer);
    if (reset) {
      logState.offset = 0;
      logState.total = 0;
      logState.records = [];
    }
    var seq = ++logSeq;
    logState.filter = el.logFilter.value;
    logState.query = el.logSearch.value.trim();
    var response = await API.logs(logState.filter, logState.query, logState.offset, logState.limit);
    if (seq !== logSeq) return;
    if (!response.success) {
      el.logList.innerHTML = '<div class="empty-note">Logs unavailable: ' + esc(response.error) + "</div>";
      el.logSummary.textContent = "unavailable";
      el.logsMore.hidden = true;
      return;
    }
    var data = response.data || {};
    logState.records = logState.records.concat(data.records || []);
    logState.total = data.count || 0;
    logState.offset = logState.records.length;
    renderLogs();
  }

  /* ---------------- memory ---------------- */

  async function loadMemory(query) {
    var response = await API.memory(query);
    if (!response.success) {
      el.memSummary.textContent = "Unavailable";
      if (el.memState) el.memState.innerHTML = '<span class="dot bad"></span><span>Database unavailable</span>';
      el.memCounts.innerHTML = "";
      el.memList.innerHTML = "";
      show(el.memMsg, (response.error || "Memory unavailable") +
        ". Use Retry after checking runtime/memory/memory.db permissions.", "err");
      return;
    }
    var data = response.data || {};
    var counts = data.counts || {};
    var items = data.items || [];
    var total = Object.keys(counts).reduce(function (sum, key) {
      return sum + (Number(counts[key]) || 0);
    }, 0);
    el.memSummary.textContent = countLabel(total, "memory", "memories");
    if (el.memState) {
      el.memState.innerHTML = '<span class="dot ok"></span><span>Local SQLite · ' +
        countLabel(total, "record", "records") + "</span>";
    }
    show(el.memMsg, "", "");
    el.memCounts.innerHTML = ["procedural", "semantic", "episodic", "project"].map(function (key) {
      return "<span>" + esc(key) + ": " + esc(counts[key] != null ? counts[key] : 0) + "</span>";
    }).join("");
    el.memList.innerHTML = items.length ? items.map(function (item) {
      return '<div class="mini-item"><div class="meta"><span class="tag">' + esc(item.type) +
        "</span><span>" + esc(fmtTime(item.created_at)) + "</span>" +
        (item.importance != null ? "<span>importance " + esc(item.importance) + "</span>" : "") +
        "</div>" +
        '<div class="body">' + esc(String(item.content || "").slice(0, 500)) + "</div></div>";
    }).join("") : '<div class="empty-note">' +
      (query ? "No memories match this search." :
        "No memories stored yet. Verified tool episodes are recorded here as you use tools.") +
      "</div>";
  }

  return {
    init: init,
    open: open,
    close: close,
    showTab: showTab,
    refreshProviders: loadProviders,
    refreshModels: loadModels,
    refreshMemory: loadMemory,
    refreshTasks: loadTasks,
    getProviders: function () { return providers; },
    runBenchmark: runBenchmark,
    refreshBenchmarks: loadBenchmarks
  };
})();
