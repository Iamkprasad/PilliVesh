var App = (function () {
  var el = {};
  var state = {
    providers: null,
    providerSig: "",
    activeId: null,
    live: null,
    busy: false,
    controller: null,
    search: "",
    harness: Store.harness(),
    benchBusy: false,
    page: "home",
    skills: null
  };
  var SEND_ICON = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 20 21 12 4 4l3 8-3 8Z"/></svg>';
  var STOP_ICON = '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="7" y="7" width="10" height="10" rx="1.5"/></svg>';

  function init() {
    el = {
      app: document.getElementById("app"),
      nav: document.getElementById("nav"),
      navToggle: document.getElementById("navToggle"),
      navScrim: document.getElementById("navScrim"),
      pages: document.getElementById("pages"),
      pageTitle: document.getElementById("pageTitle"),
      topStatus: document.getElementById("topStatus"),
      theme: document.getElementById("themeBtn"),
      topChat: document.getElementById("topChatBtn"),
      homeGreeting: document.getElementById("homeGreeting"),
      homeStatus: document.getElementById("homeStatus"),
      homePromptForm: document.getElementById("homePromptForm"),
      homePrompt: document.getElementById("homePrompt"),
      homeChips: document.getElementById("homeChips"),
      homeCpu: document.getElementById("homeCpu"),
      homeCpuSub: document.getElementById("homeCpuSub"),
      homeRam: document.getElementById("homeRam"),
      homeRamSub: document.getElementById("homeRamSub"),
      homeRamBar: document.getElementById("homeRamBar"),
      homeGpu: document.getElementById("homeGpu"),
      homeGpuSub: document.getElementById("homeGpuSub"),
      homeAvail: document.getElementById("homeAvail"),
      homeAvailSub: document.getElementById("homeAvailSub"),
      homeModel: document.getElementById("homeModel"),
      homeModelList: document.getElementById("homeModelList"),
      homeMemory: document.getElementById("homeMemory"),
      homeMemoryList: document.getElementById("homeMemoryList"),
      homeSkills: document.getElementById("homeSkills"),
      homeSkillsList: document.getElementById("homeSkillsList"),
      homeTools: document.getElementById("homeTools"),
      homeToolsList: document.getElementById("homeToolsList"),
      homeBench: document.getElementById("homeBench"),
      homeBenchBtn: document.getElementById("homeBenchBtn"),
      homeMsg: document.getElementById("homeMsg"),
      homeChats: document.getElementById("homeChats"),
      chatList: document.getElementById("chatList"),
      search: document.getElementById("chatSearch"),
      messages: document.getElementById("messages"),
      chatTitle: document.getElementById("chatTitle"),
      chatSub: document.getElementById("chatSub"),
      chatAvatar: document.getElementById("chatAvatar"),
      providerPick: document.getElementById("providerPick"),
      input: document.getElementById("chatInput"),
      send: document.getElementById("sendBtn"),
      tools: document.getElementById("toolsBtn"),
      notice: document.getElementById("composerNotice"),
      composerMeta: document.getElementById("composerMeta"),
      charCount: document.getElementById("charCount"),
      sideStatus: document.getElementById("sideStatus"),
      chatSideStatus: document.getElementById("chatSideStatus"),
      menuBtn: document.getElementById("menuBtn"),
      menu: document.getElementById("chatMenu"),
      back: document.getElementById("backBtn"),
      newChat: document.getElementById("newChatBtn"),
      harnessBtn: document.getElementById("harnessBtn"),
      skillsList: document.getElementById("skillsList"),
      skillsSummary: document.getElementById("skillsSummary"),
      skillsMsg: document.getElementById("skillsMsg"),
      skillSearch: document.getElementById("skillSearch"),
      skillsRefresh: document.getElementById("skillsRefreshBtn"),
      toolsList: document.getElementById("toolsList"),
      toolsSummary: document.getElementById("toolsSummary"),
      toolsMsg: document.getElementById("toolsMsg"),
      toolsRefresh: document.getElementById("toolsRefreshBtn")
    };
    applyTheme(Store.theme());
    Settings.init();
    bind();
    renderSidebar();
    renderChat();
    refreshProviders();
    refreshHealth();
    refreshHome();
    setInterval(refreshHealth, 15000);
    setInterval(refreshHome, 30000);
    document.addEventListener("visibilitychange", function () {
      if (!document.hidden && state.page === "home") refreshHome();
    });
    showPage("home", true);
  }

  function bind() {
    el.navToggle.onclick = function () {
      setNav(!el.app.classList.contains("nav-open"));
    };
    el.navScrim.onclick = function () { setNav(false); };
    el.theme.onclick = function () {
      applyTheme(document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark");
    };
    el.newChat.onclick = newChat;
    el.topChat.onclick = newChat;
    el.harnessBtn.onclick = function () { Settings.open("assistant"); };
    el.search.addEventListener("input", function () {
      state.search = el.search.value.trim().toLowerCase();
      renderSidebar();
    });
    el.chatList.addEventListener("click", function (event) {
      if (event.target.closest("[data-new-chat]")) {
        newChat();
        return;
      }
      var item = event.target.closest(".chat-item");
      if (item) openChat(item.getAttribute("data-id"));
    });
    el.back.onclick = function () {
      el.app.classList.remove("chat-open");
      renderSidebar();
    };
    el.send.onclick = function () {
      if (state.busy) stopStreaming();
      else send();
    };
    el.input.addEventListener("keydown", function (event) {
      if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
        event.preventDefault();
        if (!state.busy) send();
      }
    });
    el.input.addEventListener("input", function () {
      autosize();
      updateCharCount();
    });
    el.tools.onclick = function () {
      var settings = Store.harness();
      settings.useTools = !settings.useTools;
      Store.saveHarness(settings);
      state.harness = settings;
      updateToolsButton();
      updateComposerMeta();
    };
    el.providerPick.addEventListener("change", function () {
      var value = el.providerPick.value;
      if (value === "__add") {
        el.providerPick.value = currentProviderId();
        Settings.open("providers");
        return;
      }
      var chat = activeChat();
      if (chat) {
        chat.providerId = value;
        chat.updatedAt = Date.now();
        Store.putChat(chat);
      }
      state.harness.providerId = value;
      Store.saveHarness(state.harness);
      updateHeader();
      renderComposerNotice();
      updateSideStatus();
      renderSidebar();
      el.input.focus();
    });
    el.notice.addEventListener("click", function () {
      var action = el.notice.getAttribute("data-action");
      if (action) Settings.open(action);
    });
    el.menuBtn.addEventListener("click", function (event) {
      event.stopPropagation();
      toggleMenu();
    });
    el.menu.addEventListener("click", function (event) {
      var button = event.target.closest("button[data-menu]");
      if (!button) return;
      handleMenu(button.getAttribute("data-menu"));
      closeMenu();
    });
    document.addEventListener("click", function (event) {
      if (!event.target.closest(".menu-wrap")) closeMenu();

      var pageBtn = event.target.closest(".nav-item[data-page]");
      if (pageBtn) {
        event.preventDefault();
        showPage(pageBtn.getAttribute("data-page"));
        return;
      }
      var actionBtn = event.target.closest("[data-action]");
      if (actionBtn) {
        event.preventDefault();
        homeAction(actionBtn.getAttribute("data-action"), actionBtn);
        return;
      }
      var homeChat = event.target.closest("[data-open-chat]");
      if (homeChat) openChat(homeChat.getAttribute("data-open-chat"));
    });
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") {
        closeMenu();
        setNav(false);
      }
    });
    el.messages.addEventListener("click", function (event) {
      var suggestion = event.target.closest("[data-prompt]");
      if (suggestion) {
        el.input.value = suggestion.getAttribute("data-prompt");
        autosize();
        updateCharCount();
        el.input.focus();
        return;
      }
      var copy = event.target.closest("[data-copy]");
      if (copy) {
        var chat = activeChat();
        var index = parseInt(copy.getAttribute("data-copy"), 10);
        var message = chat && chat.messages[index];
        if (!message) return;
        copyText(message.content || "").then(function (ok) {
          if (ok) {
            copy.innerHTML = "✓";
            setTimeout(function () { copy.innerHTML = "⧉"; }, 1200);
          }
        });
      }
    });

    el.homePromptForm.addEventListener("submit", function (event) {
      event.preventDefault();
      var text = el.homePrompt.value.trim();
      if (!text) { el.homePrompt.focus(); return; }
      newChat();
      el.input.value = text;
      autosize();
      updateCharCount();
      send();
    });
    el.homeChips.addEventListener("click", function (event) {
      var button = event.target.closest("[data-prompt]");
      if (!button) return;
      el.homePrompt.value = button.getAttribute("data-prompt");
      el.homePromptForm.requestSubmit();
    });
    el.skillsRefresh.onclick = loadSkills;
    el.toolsRefresh.onclick = loadTools;
    el.skillSearch.addEventListener("input", renderSkills);
    el.skillsList.addEventListener("toggle", function (event) {
      var card = event.target.closest(".skill-card");
      if (card && card.open) loadSkillBody(card);
    }, true);
  }

  var PAGE_TITLES = {
    home: "Home", models: "Models", skills: "Skills", tools: "Tools",
    memory: "Memory", benchmarks: "Benchmarks", settings: "Settings", chat: "Chat"
  };

  function setNav(open) {
    el.app.classList.toggle("nav-open", open);
    el.navScrim.hidden = !open;
    el.navToggle.setAttribute("aria-expanded", open ? "true" : "false");
  }

  function showPage(name, initial) {
    if (!PAGE_TITLES[name]) name = "home";
    state.page = name;
    if (window.matchMedia("(max-width: 900px)").matches) setNav(false);
    el.nav.querySelectorAll(".nav-item").forEach(function (item) {
      item.classList.toggle("on", item.getAttribute("data-page") === name);
    });
    document.querySelectorAll(".page").forEach(function (page) {
      var active = page.getAttribute("data-page") === name;
      page.classList.toggle("active", active);
      page.hidden = !active;
    });
    el.pages.classList.toggle("chat-mode", name === "chat");
    el.pageTitle.textContent = PAGE_TITLES[name];
    if (!initial) el.pages.scrollTop = 0;
    if (name === "chat") el.app.classList.remove("chat-open");
    if (name === "skills") loadSkills();
    if (name === "tools") {
      loadTools();
      Settings.refreshTasks();
    }
    if (name === "memory") Settings.refreshMemory();
    if (name === "models") Settings.refreshModels();
    if (name === "benchmarks") Settings.refreshBenchmarks();
    if (name === "settings") Settings.showTab();
  }

  function homeAction(action, button) {
    if (action === "download") {
      showPage("models");
      return;
    }
    if (action === "memory") {
      showPage("memory");
      return;
    }
    if (action === "benchmark") {
      runOverviewBenchmark();
      return;
    }
    if (action === "terminal") {
      Settings.open("system");
      openSystemCard("terminalCard");
      return;
    }
    if (action === "logs") {
      Settings.open("system");
      openSystemCard("sysLogs");
      return;
    }
    if (button) button.blur();
  }

  function openSystemCard(id) {
    var card = document.getElementById(id);
    if (!card) return;
    card.open = true;
    requestAnimationFrame(function () {
      card.scrollIntoView({ block: "start", behavior: "smooth" });
    });
  }

  /* ---------------- providers ---------------- */

  async function refreshProviders() {
    return Settings.refreshProviders();
  }

  function setProviders(data) {
    state.providers = data || null;
    var signature = JSON.stringify({
      providers: ((data && data.providers) || []).map(function (provider) {
        return [provider.id, provider.name, provider.model, provider.has_key, provider.active, provider.type];
      }),
      active: data && data.active,
      local: data && data.local
    });
    if (signature === state.providerSig) return;
    state.providerSig = signature;
    var valid = providerById(state.harness.providerId);
    if (!valid) {
      state.harness.providerId = (data && data.active) || "local";
      Store.saveHarness(state.harness);
    }
    renderProviderPick();
    updateHeader();
    renderComposerNotice();
    updateSideStatus();
  }

  function providerById(id) {
    var list = (state.providers && state.providers.providers) || [];
    for (var i = 0; i < list.length; i++) {
      if (list[i].id === id) return list[i];
    }
    return null;
  }

  function currentProviderId() {
    var chat = activeChat();
    var id = (chat && chat.providerId) || state.harness.providerId ||
      (state.providers && state.providers.active) || "local";
    if (!providerById(id)) id = "local";
    return id;
  }

  function currentProvider() {
    return providerById(currentProviderId()) || {
      id: "local", name: "Local llama.cpp", type: "local", model: "local",
      has_key: false, key_hint: "", base_url: ""
    };
  }

  function renderProviderPick() {
    var list = (state.providers && state.providers.providers) || [];
    var current = currentProviderId();
    var html = list.map(function (provider) {
      return '<option value="' + esc(provider.id) + '">' + esc(provider.name) + "</option>";
    }).join("");
    html += '<option value="__add">+ Add provider…</option>';
    el.providerPick.innerHTML = html;
    el.providerPick.value = current;
  }

  function localStatus() {
    return (state.providers && state.providers.local) || { running: false, loaded_id: null };
  }

  function updateSideStatus() {
    var ready = false;
    var text = "server unreachable";
    var kind = "bad";
    if (state.providers) {
      var provider = currentProvider();
      var local = localStatus();
      if (provider.type === "local") {
        ready = !!local.running;
        text = provider.name + (local.running
          ? " · " + (local.loaded_id || "loaded")
          : " · no model loaded");
      } else {
        ready = !!provider.has_key;
        text = provider.name + " · " + (provider.has_key ? "key saved" : "add API key");
      }
      kind = ready ? "ok" : "warn";
    }
    var html = '<i class="dot ' + kind + '"></i><span>' + esc(text) + "</span>";
    if (el.sideStatus) el.sideStatus.innerHTML = html;
    if (el.chatSideStatus) {
      el.chatSideStatus.innerHTML = '<i class="dot ' + kind + '"></i><span>' +
        esc(state.providers ? text : "server unreachable") + "</span>";
    }
    if (el.topStatus) {
      var short = "Server unreachable";
      if (state.providers) {
        var active = currentProvider();
        var status = localStatus();
        short = active.type === "local"
          ? "llama-server · " + (status.running ? "ready" : "idle")
          : active.name + (active.has_key ? " · ready" : " · no key");
      }
      el.topStatus.innerHTML = '<i class="dot ' + kind + '"></i><span>' + esc(short) + "</span>";
    }
  }

  async function refreshHealth() {
    var response = await API.providers();
    if (!response.success) {
      state.providers = null;
      updateSideStatus();
      return;
    }
    setProviders(response.data);
  }

  /* ---------------- home dashboard ---------------- */

  var homeSeq = 0;

  function gb(mb) {
    if (mb == null || isNaN(mb)) return "—";
    return (mb / 1024).toFixed(1) + " GB";
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
    return Math.floor(hours / 24) + "d ago";
  }

  function shortGpu(name) {
    var text = String(name || "").replace(/\s+/g, " ").trim();
    if (!text) return "";
    var adr = text.match(/Adreno[^,(]*/i);
    if (adr) return adr[0].trim();
    return text.length > 22 ? text.slice(0, 22) + "…" : text;
  }

  function peakCpuTemp(temperatures) {
    var peak = null;
    Object.keys(temperatures || {}).forEach(function (key) {
      if (!/^(cpu|cpuss)/i.test(key)) return;
      var value = Number(temperatures[key]);
      if (!isNaN(value) && (peak == null || value > peak)) peak = value;
    });
    return peak;
  }

  function setHomeStatus(text, kind) {
    el.homeStatus.innerHTML = '<i class="dot ' + (kind || "warn") + '"></i><span>' + esc(text) + "</span>";
  }

  function refreshOverview() {
    return refreshHome();
  }

  async function refreshHome() {
    var seq = ++homeSeq;
    var results = await Promise.all([
      API.telemetry(), API.models(), API.benchmark(),
      API.memory(), API.skills(), API.tools()
    ]);
    if (seq !== homeSeq) return;
    renderHome(
      results[0].success ? results[0].data : null,
      results[1].success ? results[1].data : null,
      results[2].success ? results[2].data : null,
      results[3].success ? results[3].data : null,
      results[4].success ? results[4].data : null,
      results[5].success ? results[5].data : null
    );
    updateSideStatus();
  }

  function renderHome(telemetry, models, benchmark, memory, skills, tools) {
    var hour = new Date().getHours();
    el.homeGreeting.textContent = hour < 12 ? "Good morning." : (hour < 18 ? "Good afternoon." : "Good evening.");

    var system = (telemetry && telemetry.system) || {};
    var mem = system.memory || {};
    var runtime = (telemetry && telemetry.runtime) || {};
    var gpu = (telemetry && telemetry.gpu) || {};
    var temperatures = system.temperatures_c || {};

    if (telemetry && system.cpu_cores != null) {
      el.homeCpu.textContent = system.cpu_cores + " cores";
      var peak = peakCpuTemp(temperatures);
      el.homeCpuSub.textContent = peak != null
        ? "peak " + peak.toFixed(1) + " °C"
        : "read from /proc";
    } else {
      el.homeCpu.textContent = "—";
      el.homeCpuSub.textContent = "telemetry unavailable";
    }

    if (mem.total_mb != null) {
      var pct = Math.round((mem.used_mb || 0) / mem.total_mb * 100);
      el.homeRam.textContent = gb(mem.used_mb) + " / " + gb(mem.total_mb);
      el.homeRamSub.textContent = pct + "% used · " + gb(mem.available_mb) + " available";
      el.homeRamBar.style.width = Math.max(0, Math.min(100, pct)) + "%";
    } else {
      el.homeRam.textContent = "—";
      el.homeRamSub.textContent = "telemetry unavailable";
      el.homeRamBar.style.width = "0%";
    }

    var gpuName = shortGpu(gpu.device);
    el.homeGpu.textContent = gpuName || (gpu.vulkan_available ? "Vulkan" : "None");
    el.homeGpuSub.textContent = (runtime.backend || "unknown") + " inference" +
      (runtime.llama_version ? " · llama.cpp " + runtime.llama_version : "");

    if (mem.available_mb != null) {
      el.homeAvail.textContent = gb(mem.available_mb);
      el.homeAvailSub.textContent = "swap " + gb(mem.swap_used_mb) + " / " + gb(mem.swap_total_mb);
    } else {
      el.homeAvail.textContent = "—";
      el.homeAvailSub.textContent = "telemetry unavailable";
    }

    var catalog = (models && models.catalog) || [];
    var resident = catalog.filter(function (model) { return model.loaded; })[0] || null;
    var installed = catalog.filter(function (model) { return model.installed; });
    var localLoaded = localStatus().loaded_id;

    if (models) {
      if (resident) {
        setHomeStatus(resident.name + " is ready · " + resident.quant + " · " + runtime.backend, "ok");
        el.homeModel.innerHTML = '<span class="dot ok"></span><span><b>' + esc(resident.name) +
          "</b> · " + esc(resident.quant) + " · resident</span>";
      } else if (installed.length) {
        setHomeStatus("No model is loaded. Open Models to bring one online.", "warn");
        el.homeModel.innerHTML = '<span class="dot warn"></span><span>' +
          esc(installed.length + " model" + (installed.length === 1 ? " is" : "s are") +
          " downloaded, but none is resident.") + "</span>";
      } else if (!models.catalog || !models.catalog.length) {
        setHomeStatus("No local models yet. Download one to start chatting.", "bad");
        el.homeModel.innerHTML = '<span class="dot bad"></span><span>No models in the catalog.</span>';
      } else {
        setHomeStatus("No local models yet. Download one to start chatting.", "bad");
        el.homeModel.innerHTML = '<span class="dot bad"></span><span>No models downloaded.</span>';
      }
    } else {
      setHomeStatus("Model state is unavailable. Check the local server.", "bad");
      el.homeModel.innerHTML = '<span class="dot bad"></span><span>Model state unavailable.</span>';
    }

    var chips = [];
    if (installed.length) {
      installed.slice(0, 6).forEach(function (model) {
        chips.push('<span class="chip' + (model.loaded ? " on" : "") + '">' +
          esc(model.name) + (model.loaded ? " · resident" : "") + "</span>");
      });
    } else {
      chips.push('<span class="chip">No downloaded models</span>');
    }
    el.homeModelList.innerHTML = chips.join("");

    var latest = benchmark;
    var metrics = (latest && latest.metrics) || {};
    var generation = metrics.generation_tokens_per_second;
    if (latest && latest.status === "success" && generation != null) {
      var suffix = latest.model ? " · " + latest.model : "";
      el.homeBench.textContent = "Last light probe: " + generation + " tok/s generation" +
        (latest.timestamp ? " · " + ago(latest.timestamp) : "") +
        (resident ? "" : " · no model resident now") + suffix;
    } else if (latest && latest.status === "stale") {
      el.homeBench.textContent = "Last probe has no current model · " + (latest.timestamp ? ago(latest.timestamp) : "unknown time");
    } else if (!latest) {
      el.homeBench.textContent = "No benchmark yet. Run a light probe when a model is resident.";
    } else {
      el.homeBench.textContent = latest.message || "The last probe did not produce throughput metrics.";
    }

    if (memory) {
      var counts = memory.counts || {};
      var total = Object.keys(counts).reduce(function (sum, key) {
        return sum + (Number(counts[key]) || 0);
      }, 0);
      el.homeMemory.textContent = total + (total === 1 ? " note" : " notes");
      var items = (memory.items || []).slice(0, 3);
      el.homeMemoryList.innerHTML = items.length ? items.map(function (item) {
        return '<div class="mini-item"><div class="meta"><span class="tag">' +
          esc(item.type) + "</span><span>" + esc(ago(item.created_at)) + "</span></div>" +
          '<div class="body">' + esc(String(item.content || "").slice(0, 130)) + "</div></div>";
      }).join("") : '<div class="empty-note">No memories yet. Tool episodes appear here once verified.</div>';
    } else {
      el.homeMemory.textContent = "—";
      el.homeMemoryList.innerHTML = '<div class="empty-note">Memory unavailable. Open Memory to retry.</div>';
    }

    var skillItems = (skills && skills.skills) || [];
    if (skills) {
      el.homeSkills.textContent = skillItems.length + (skillItems.length === 1 ? " skill" : " skills");
      el.homeSkillsList.innerHTML = skillItems.slice(0, 5).map(function (skill) {
        return '<span class="chip">' + esc(skill.title || skill.name) + "</span>";
      }).join("") || '<span class="chip">No skills found</span>';
    } else {
      el.homeSkills.textContent = "—";
      el.homeSkillsList.innerHTML = '<span class="chip">Skills unavailable</span>';
    }

    var toolItems = (tools && tools.tools) || [];
    if (tools) {
      el.homeTools.textContent = toolItems.length + (toolItems.length === 1 ? " tool" : " tools");
      el.homeToolsList.innerHTML = toolItems.slice(0, 2).map(function (tool) {
        return '<div class="mini-item"><div class="body"><b>' + esc(tool.name) + "</b> · " +
          esc(tool.description || "") + "</div></div>";
      }).join("") || '<div class="empty-note">No tools registered.</div>';
    } else {
      el.homeTools.textContent = "—";
      el.homeToolsList.innerHTML = '<div class="empty-note">Tools unavailable.</div>';
    }

    renderHomeChats();
  }

  function renderHomeChats() {
    var list = sortedChats().slice(0, 4);
    if (!list.length) {
      el.homeChats.innerHTML = '<div class="empty-note">No conversations yet. Everything stays on this device.</div>';
      return;
    }
    el.homeChats.innerHTML = list.map(function (chat) {
      var messages = chat.messages || [];
      var last = messages[messages.length - 1];
      var preview = last ? String(last.content || "").replace(/\s+/g, " ").trim() : "No messages yet";
      return '<button class="home-chat" data-open-chat="' + esc(chat.id) + '">' +
        '<span class="home-chat-avatar">' + esc(initialOf(chat.title)) + "</span>" +
        '<span class="home-chat-main"><span class="home-chat-name">' + esc(chat.title || "New chat") + "</span>" +
        '<span class="home-chat-sub">' + esc(preview.slice(0, 70) || "No messages yet") + "</span></span>" +
        '<span class="home-chat-time">' + esc(listTime(chat.updatedAt)) + "</span></button>";
    }).join("");
  }

  /* ---------------- skills & tools pages ---------------- */

  async function loadSkills() {
    el.skillsSummary.textContent = "Loading…";
    var response = await API.skills();
    if (!response.success) {
      state.skills = null;
      el.skillsSummary.textContent = "Unavailable";
      el.skillsMsg.textContent = "Skills unavailable: " + (response.error || "unknown error");
      el.skillsMsg.className = "form-msg err";
      el.skillsList.innerHTML = "";
      return;
    }
    state.skills = (response.data && response.data.skills) || [];
    el.skillsMsg.textContent = "";
    el.skillsMsg.className = "form-msg";
    renderSkills();
  }

  function renderSkills() {
    if (!state.skills) return;
    var query = el.skillSearch.value.trim().toLowerCase();
    var list = state.skills.filter(function (skill) {
      return !query || (skill.name + " " + (skill.title || "")).toLowerCase().indexOf(query) >= 0;
    });
    el.skillsSummary.textContent = list.length + (list.length === 1 ? " skill" : " skills");
    el.skillsList.innerHTML = list.length ? list.map(function (skill) {
      return '<details class="skill-card" data-skill="' + esc(skill.name) + '">' +
        '<summary><span class="skill-icon"><svg><use href="#i-skills"/></svg></span>' +
        '<span class="skill-main"><span class="skill-title">' + esc(skill.title || skill.name) + "</span>" +
        '<span class="skill-slug">' + esc(skill.name) + "</span></span>" +
        '<span class="skill-chevron" aria-hidden="true">›</span></summary>' +
        '<div class="skill-body"><div class="empty-note">Loading instructions…</div></div>' +
      "</details>";
    }).join("") : '<div class="empty-note">' +
      (query ? "No skills match this search." : "No skill packs found in runtime/skills.") + "</div>";
  }

  async function loadSkillBody(card) {
    var body = card.querySelector(".skill-body");
    if (!body || body.getAttribute("data-loaded") === "1") return;
    body.setAttribute("data-loaded", "1");
    body.innerHTML = '<div class="empty-note">Loading instructions…</div>';
    var response = await API.skills(card.getAttribute("data-skill"));
    if (!response.success) {
      body.innerHTML = '<div class="empty-note">Could not load this skill: ' +
        esc(response.error || "unknown error") + "</div>";
      return;
    }
    var content = (response.data && response.data.content) || "";
    body.innerHTML = '<pre>' + esc(content) + "</pre>" +
      '<p class="note">Instruction file from runtime/skills/' +
      esc(card.getAttribute("data-skill")) + "/SKILL.md.</p>";
  }

  async function loadTools() {
    el.toolsSummary.textContent = "Loading…";
    var response = await API.tools();
    if (!response.success) {
      el.toolsSummary.textContent = "Unavailable";
      el.toolsMsg.textContent = "Tools unavailable: " + (response.error || "unknown error");
      el.toolsMsg.className = "form-msg err";
      el.toolsList.innerHTML = "";
      return;
    }
    var tools = (response.data && response.data.tools) || [];
    el.toolsSummary.textContent = tools.length + (tools.length === 1 ? " tool" : " tools");
    el.toolsMsg.textContent = "";
    el.toolsMsg.className = "form-msg";
    el.toolsList.innerHTML = tools.length ? tools.map(function (tool) {
      return '<article class="tool-card">' +
        '<span class="tool-icon"><svg><use href="#i-tools"/></svg></span>' +
        '<div class="tool-main"><span class="tool-name"><code>' + esc(tool.name) + "</code></span>" +
        '<span class="tool-slug">read-only · bounded</span>' +
        '<p class="note">' + esc(tool.description || "No description.") + "</p></div></article>";
    }).join("") : '<div class="empty-note">No tools are registered.</div>';
  }

  function showHomeMsg(text, kind) {
    el.homeMsg.textContent = text || "";
    el.homeMsg.className = "form-msg" + (kind ? " " + kind : "");
  }

  async function runOverviewBenchmark() {
    if (state.benchBusy) return;
    if (!localStatus().running) {
      showHomeMsg("No local model is resident. Load one in Models; the probe will not switch models for you.", "err");
      showPage("benchmarks");
      return;
    }
    showHomeMsg("Running one 48-token probe against the resident model…", "");
    var ok = await Settings.runBenchmark(null);
    if (ok) {
      var response = await API.benchmark();
      var metrics = response.success && response.data ? (response.data.metrics || {}) : {};
      var gen = metrics.generation_tokens_per_second;
      showHomeMsg(gen != null
        ? "Light probe complete: " + gen + " tok/s generation. Details are in Benchmarks."
        : "Light probe complete. Details are in Benchmarks.", "ok");
    } else {
      showHomeMsg("Probe did not complete. Benchmarks shows the reason; no results were invented.", "err");
      showPage("benchmarks");
    }
    refreshHome();
  }

  function setBenchmarkBusy(busy) {
    state.benchBusy = !!busy;
    if (!el.homeBenchBtn) return;
    el.homeBenchBtn.disabled = !!busy;
    var label = el.homeBenchBtn.querySelector("span:last-child");
    if (label) label.textContent = busy ? "Running probe…" : "Run benchmark";
  }

  /* ---------------- header / notice ---------------- */

  function updateHeader() {
    var chat = activeChat();
    var provider = currentProvider();
    var local = localStatus();
    el.chatTitle.textContent = chat ? chat.title : "New chat";
    var pieces = [provider.name, provider.model];
    if (provider.type === "local") {
      pieces.push(local.running ? "model loaded" : "no model loaded");
    } else {
      pieces.push(provider.has_key ? "key saved" : "add API key");
    }
    el.chatSub.textContent = pieces.filter(Boolean).join(" · ");
    el.chatAvatar.textContent = initialOf(provider.name);
    if (el.providerPick.value !== currentProviderId()) {
      el.providerPick.value = currentProviderId();
    }
    updateSideStatus();
  }

  function renderComposerNotice() {
    var provider = currentProvider();
    var local = localStatus();
    var action = "";
    var text = "";
    if (provider.type === "local" && !local.running) {
      action = "models";
      text = "Local model not loaded. Open Models to load one, or switch provider.";
    } else if (provider.type !== "local" && !provider.has_key) {
      action = "providers";
      text = provider.name + " has no API key. Add one in Providers.";
    }
    if (text) {
      el.notice.innerHTML = esc(text) + " <b>Open</b>";
      el.notice.setAttribute("data-action", action);
      el.notice.hidden = false;
    } else {
      el.notice.hidden = true;
      el.notice.removeAttribute("data-action");
    }
    updateComposerMeta();
  }

  function updateToolsButton() {
    var on = !!Store.harness().useTools;
    el.tools.classList.toggle("on", on);
    el.tools.setAttribute("aria-pressed", on ? "true" : "false");
    el.tools.title = on ? "Tools enabled — click to disable" : "Tools disabled — click to enable";
  }

  function updateComposerMeta() {
    if (state.busy) {
      el.composerMeta.textContent = "Streaming… press the red button to stop.";
    } else {
      el.composerMeta.textContent = "Enter to send · Shift+Enter for a new line";
    }
  }

  /* ---------------- sidebar ---------------- */

  function sortedChats() {
    return Store.chats().slice().sort(function (a, b) {
      return (b.updatedAt || 0) - (a.updatedAt || 0);
    });
  }

  function listTime(ts) {
    var date = new Date(ts || Date.now());
    if (dayKey(date) === dayKey(Date.now())) return clock(date);
    if (dayKey(date) === dayKey(Date.now() - 86400000)) return "Yesterday";
    try {
      return date.toLocaleDateString([], { day: "2-digit", month: "2-digit" });
    } catch (e) { return ""; }
  }

  function renderSidebar() {
    var list = sortedChats();
    if (state.search) {
      list = list.filter(function (chat) {
        if ((chat.title || "").toLowerCase().indexOf(state.search) >= 0) return true;
        return (chat.messages || []).some(function (message) {
          return String(message.content || "").toLowerCase().indexOf(state.search) >= 0;
        });
      });
    }
    if (!list.length) {
      el.chatList.innerHTML = state.search
        ? '<div class="chat-list-empty">No chats match your search.</div>'
        : '<div class="chat-list-empty"><p>No conversations yet. Your chats stay on this device.</p>' +
          '<button class="btn small" data-new-chat="1">Start your first chat</button></div>';
      return;
    }
    el.chatList.innerHTML = list.map(function (chat) {
      var messages = chat.messages || [];
      var last = messages[messages.length - 1];
      var preview = last
        ? String(last.content || "").replace(/\s+/g, " ").trim().slice(0, 70)
        : "Start a conversation";
      if (!preview && last && last.status === "streaming") preview = "typing…";
      if (!preview) preview = "No messages yet";
      var tick = last && last.role === "user" ? '<span class="tick">✓✓</span>' : "";
      return '<button class="chat-item' + (chat.id === state.activeId ? " on" : "") +
        '" data-id="' + esc(chat.id) + '" role="listitem">' +
        '<div class="avatar">' +
          esc(initialOf(chat.title)) + "</div>" +
        '<div class="chat-item-main">' +
          '<div class="chat-item-top"><span class="chat-item-name">' + esc(chat.title || "New chat") +
            '</span><span class="chat-item-time">' + esc(listTime(chat.updatedAt)) + "</span></div>" +
          '<div class="chat-item-preview">' + tick + "<span>" + esc(preview) + "</span></div>" +
        "</div></button>";
    }).join("");
  }

  function activeChat() {
    return Store.getChat(state.activeId);
  }

  function newChat() {
    state.activeId = null;
    state.live = null;
    el.search.value = "";
    state.search = "";
    showPage("chat");
    el.app.classList.add("chat-open");
    renderSidebar();
    renderChat();
    updateHeader();
    el.input.focus();
  }

  function openChat(id, initial) {
    if (!Store.getChat(id)) return;
    state.activeId = id;
    state.live = null;
    showPage("chat");
    el.app.classList.add("chat-open");
    renderSidebar();
    renderChat();
    updateHeader();
    if (!initial) el.input.focus();
  }

  function reloadChats() {
    state.activeId = null;
    state.live = null;
    el.app.classList.remove("chat-open");
    if (state.page === "chat") showPage("chat");
    renderSidebar();
    renderChat();
    updateHeader();
  }

  /* ---------------- messages ---------------- */

  function scrollBottom(force) {
    var near = el.messages.scrollHeight - el.messages.scrollTop - el.messages.clientHeight < 160;
    if (force || near) {
      requestAnimationFrame(function () {
        el.messages.scrollTop = el.messages.scrollHeight;
      });
    }
  }

  function typingHtml() {
    return '<span class="typing"><i></i><i></i><i></i></span>';
  }

  function messageHtml(message, index, chat) {
    var out = message.role === "user";
    var classes = "msg-row " + (out ? "out" : "in");
    if (message.error) classes += " error";
    var body;
    if (message.status === "streaming" && !message.content) {
      body = typingHtml();
    } else {
      body = markdown(message.content || "");
      if (message.status === "streaming") body += '<span class="caret"></span>';
    }
    var meta = "";
    if (!out) {
      if (message.tool) meta += '<span class="tag">tool: ' + esc(message.tool) + "</span>";
      if (message.status === "stopped") meta += '<span class="state">stopped</span>';
      if (message.note) meta += '<span class="state">' + esc(message.note) + "</span>";
    }
    meta += "<span>" + esc(clock(message.at || chat.createdAt)) + "</span>";
    if (out) {
      var answered = (chat.messages || []).slice(index + 1).some(function (item) {
        return item.role === "assistant" && item.content;
      });
      meta += '<span class="tick">' + (answered ? "✓✓" : "✓") + "</span>";
    } else if (message.content && message.status !== "streaming") {
      meta += '<button class="msg-copy" data-copy="' + index + '" title="Copy message" aria-label="Copy message">⧉</button>';
    }
    return '<div class="' + classes + '"' + (message.status === "streaming" ? ' data-live="1"' : "") + ">" +
      '<div class="bubble"><div class="bubble-text">' + body + "</div>" +
      '<div class="msg-meta">' + meta + "</div></div></div>";
  }

  function emptyChatHtml() {
    var provider = currentProvider();
    return '<div class="chat-empty">' +
      '<img class="empty-mascot" src="assets/mascot.webp" width="368" height="500" alt="Pilli the tiger cub">' +
      "<h1>Ready when you are.</h1>" +
      "<p>Chat with a local GGUF model or a cloud provider. Keys stay on this device and every request goes through your local server.</p>" +
      '<div class="suggestions">' +
        '<button class="suggestion" data-prompt="What can PilliVesh do?">What can PilliVesh do?</button>' +
        '<button class="suggestion" data-prompt="Inspect this device with system_info and summarize it.">Inspect this device</button>' +
        '<button class="suggestion" data-prompt="Write a small Python script that watches a folder for new files.">Write some code</button>' +
      "</div>" +
      '<p class="note" style="margin-top:16px">Active: ' + esc(provider.name) + "</p>" +
    "</div>";
  }

  function renderChat(forceBottom) {
    var chat = activeChat();
    updateHeader();
    if (!chat || !(chat.messages || []).length) {
      el.messages.innerHTML = emptyChatHtml();
      return;
    }
    var html = "";
    var lastDay = "";
    chat.messages.forEach(function (message, index) {
      var key = dayKey(message.at || chat.createdAt);
      if (key !== lastDay) {
        html += '<div class="date-chip">' + esc(dayLabel(message.at || chat.createdAt)) + "</div>";
        lastDay = key;
      }
      html += messageHtml(message, index, chat);
    });
    el.messages.innerHTML = html;
    scrollBottom(forceBottom !== false);
  }

  function updateLiveBubble() {
    if (!state.live) return;
    var node = el.messages.querySelector('[data-live="1"] .bubble-text');
    if (!node) return;
    node.innerHTML = state.live.content
      ? markdown(state.live.content) + '<span class="caret"></span>'
      : typingHtml();
    scrollBottom(false);
  }

  function autosize() {
    el.input.style.height = "auto";
    el.input.style.height = Math.min(el.input.scrollHeight, 140) + "px";
  }

  function updateCharCount() {
    var length = el.input.value.length;
    el.charCount.textContent = length ? length + " / 32000" : "";
    el.charCount.className = length > 30000 ? "char-warn" : "";
  }

  function setBusyUI(busy) {
    state.busy = busy;
    el.send.classList.toggle("stop", busy);
    el.send.innerHTML = busy ? STOP_ICON : SEND_ICON;
    el.send.setAttribute("aria-label", busy ? "Stop generating" : "Send");
    el.send.title = busy ? "Stop generating" : "Send";
    updateComposerMeta();
  }

  function stopStreaming() {
    if (state.controller) state.controller.abort();
  }

  /* ---------------- sending ---------------- */

  function ensureChat() {
    var chat = activeChat();
    if (chat) return chat;
    chat = {
      id: uid("chat"),
      title: "New chat",
      providerId: currentProviderId(),
      createdAt: Date.now(),
      updatedAt: Date.now(),
      messages: []
    };
    state.activeId = chat.id;
    Store.putChat(chat);
    renderSidebar();
    return chat;
  }

  function buildMessages(chat, live) {
    var harness = Store.harness();
    var messages = [];
    if (harness.systemPrompt && harness.systemPrompt.trim()) {
      messages.push({ role: "system", content: harness.systemPrompt.trim() });
    }
    (chat.messages || []).forEach(function (message) {
      if (message === live) return;
      if (message.error) return;
      if (message.role !== "user" && message.role !== "assistant") return;
      if (!message.content) return;
      messages.push({ role: message.role, content: message.content });
    });
    return messages.slice(-25);
  }

  async function send() {
    if (state.busy) return;
    var text = el.input.value.trim();
    if (!text) return;
    if (text.length > 32000) {
      el.composerMeta.textContent = "Message too long (max 32,000 characters).";
      return;
    }
    var provider = currentProvider();
    var local = localStatus();
    if (provider.type === "local" && !local.running) {
      el.notice.hidden = false;
      el.notice.setAttribute("data-action", "models");
      el.notice.innerHTML = "No local model is loaded. <b>Open Models</b>";
      Settings.open("models");
      return;
    }
    if (provider.type !== "local" && !provider.has_key) {
      el.notice.hidden = false;
      el.notice.setAttribute("data-action", "providers");
      el.notice.innerHTML = esc(provider.name) + " has no API key. <b>Open Providers</b>";
      Settings.open("providers");
      return;
    }

    var chat = ensureChat();
    if (!(chat.messages || []).length) chat.title = titleFrom(text);
    chat.providerId = provider.id;
    chat.updatedAt = Date.now();
    chat.messages.push({ role: "user", content: text, at: Date.now() });
    Store.putChat(chat);

    el.input.value = "";
    autosize();
    updateCharCount();
    setBusyUI(true);
    renderSidebar();

    var live = {
      role: "assistant",
      content: "",
      at: Date.now(),
      status: "streaming",
      providerId: provider.id,
      model: provider.model
    };
    chat.messages.push(live);
    state.live = live;
    renderChat(true);

    var messages = buildMessages(chat, live);
    var harness = Store.harness();
    var controller = new AbortController();
    state.controller = controller;

    try {
      if (harness.useTools) {
        var response = await API.chat(messages, {
          provider: provider.id,
          max_tokens: harness.maxTokens,
          temperature: harness.temperature,
          use_tools: true,
          signal: controller.signal
        });
        if (!response.success) throw new Error(response.error || "Request failed");
        var data = response.data || {};
        var choices = data.choices || [];
        var content = choices[0] && choices[0].message ? choices[0].message.content : "";
        live.content = content || "[empty response]";
        if (data.tool_used && data.tool_used.tool) live.tool = data.tool_used.tool;
        if (data.max_iterations_reached) {
          live.error = true;
          live.note = "tool limit reached";
        }
        live.status = "done";
      } else {
        await streamReply(messages, provider.id, harness, controller, live);
        live.status = "done";
      }
    } catch (error) {
      if ((error && error.name === "AbortError") || controller.signal.aborted) {
        live.status = "stopped";
        if (!live.content) live.content = "[stopped]";
      } else {
        live.status = "error";
        live.error = true;
        live.content = String(error && error.message ? error.message : error);
      }
    } finally {
      state.controller = null;
      state.live = null;
      chat.updatedAt = Date.now();
      Store.putChat(chat);
      setBusyUI(false);
      renderSidebar();
      renderChat(true);
    }
  }

  async function streamReply(messages, providerId, harness, controller, live) {
    var response = await API.chatStream(messages, {
      provider: providerId,
      max_tokens: harness.maxTokens,
      temperature: harness.temperature,
      signal: controller.signal
    });
    var type = (response.headers && response.headers.get("content-type")) || "";
    if (!response.ok) {
      var detail = "HTTP " + response.status;
      try {
        var errorBody = await response.json();
        detail = errorBody.error || detail;
      } catch (e) {}
      throw new Error(detail);
    }
    if (type.indexOf("ndjson") >= 0 && response.body && response.body.getReader) {
      var reader = response.body.getReader();
      var decoder = new TextDecoder();
      var buffer = "";
      var done = false;
      while (!done) {
        var chunk = await reader.read();
        if (chunk.done) break;
        buffer += decoder.decode(chunk.value, { stream: true });
        var lines = buffer.split("\n");
        buffer = lines.pop();
        for (var i = 0; i < lines.length; i++) {
          var line = lines[i].trim();
          if (!line) continue;
          var event;
          try { event = JSON.parse(line); } catch (e) { continue; }
          if (event.t === "d" && event.c) {
            live.content += event.c;
            updateLiveBubble();
          } else if (event.t === "error") {
            throw new Error(event.e || "Stream error");
          } else if (event.t === "done") {
            done = true;
          }
        }
      }
    } else {
      var json = await response.json();
      if (!json.success) throw new Error(json.error || "Request failed");
      var choices = (json.data && json.data.choices) || [];
      live.content = (choices[0] && choices[0].message && choices[0].message.content) || "";
      updateLiveBubble();
    }
    if (!live.content) live.content = "[empty response]";
  }

  /* ---------------- menu / theme ---------------- */

  function toggleMenu() {
    var open = el.menu.hidden;
    el.menu.hidden = !open;
    el.menuBtn.setAttribute("aria-expanded", open ? "true" : "false");
  }

  function closeMenu() {
    el.menu.hidden = true;
    el.menuBtn.setAttribute("aria-expanded", "false");
  }

  function handleMenu(action) {
    var chat = activeChat();
    if (!chat) {
      if (action !== "delete" && action !== "rename" && action !== "clear") {
        Settings.open("assistant");
      }
      return;
    }
    if (action === "rename") {
      var name = prompt("Rename chat", chat.title || "New chat");
      if (name && name.trim()) {
        chat.title = name.trim().slice(0, 80);
        chat.updatedAt = Date.now();
        Store.putChat(chat);
        renderSidebar();
        renderChat(false);
      }
    } else if (action === "clear") {
      if (!confirm("Clear all messages in this chat?")) return;
      chat.messages = [];
      chat.updatedAt = Date.now();
      Store.putChat(chat);
      renderChat(true);
      renderSidebar();
    } else if (action === "export") {
      exportChat(chat);
    } else if (action === "delete") {
      if (!confirm("Delete this chat?")) return;
      Store.deleteChat(chat.id);
      state.activeId = null;
      el.app.classList.remove("chat-open");
      renderSidebar();
      renderChat();
    }
  }

  function exportChat(chat) {
    var lines = ["# " + (chat.title || "Chat"), ""];
    (chat.messages || []).forEach(function (message) {
      if (!message.content) return;
      lines.push("**" + (message.role === "user" ? "You" : "Assistant") + "** · " +
        new Date(message.at || chat.createdAt).toLocaleString());
      lines.push("");
      lines.push(message.content);
      lines.push("");
    });
    var blob = new Blob([lines.join("\n")], { type: "text/markdown" });
    var link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = (chat.title || "chat").replace(/[^\w\-]+/g, "-").slice(0, 40) + ".md";
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(function () { URL.revokeObjectURL(link.href); }, 1000);
  }

  function applyTheme(name) {
    var theme = name === "dark" ? "dark" : "light";
    document.documentElement.setAttribute("data-theme", theme);
    Store.saveTheme(theme);
    var meta = document.getElementById("themeColor");
    if (meta) meta.setAttribute("content", theme === "dark" ? "#171310" : "#FFF6E6");
    if (el.theme) {
      el.theme.innerHTML = '<svg><use href="#' + (theme === "dark" ? "i-sun" : "i-moon") + '"/></svg>';
      el.theme.title = theme === "dark" ? "Switch to light theme" : "Switch to dark theme";
      el.theme.setAttribute("aria-label", el.theme.title);
    }
  }

  function copyText(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(text).then(function () { return true; })
        .catch(function () { return legacyCopy(text); });
    }
    return Promise.resolve(legacyCopy(text));
  }

  function legacyCopy(text) {
    try {
      var area = document.createElement("textarea");
      area.value = text;
      area.style.position = "fixed";
      area.style.opacity = "0";
      document.body.appendChild(area);
      area.select();
      var ok = document.execCommand("copy");
      area.remove();
      return ok;
    } catch (e) { return false; }
  }

  return {
    init: init,
    go: showPage,
    setProviders: setProviders,
    refreshProviders: refreshProviders,
    refreshOverview: refreshOverview,
    refreshHome: refreshHome,
    setBenchmarkBusy: setBenchmarkBusy,
    applyHarness: function () {
      state.harness = Store.harness();
      updateToolsButton();
      updateComposerMeta();
      renderComposerNotice();
    },
    reloadChats: reloadChats,
    applyTheme: applyTheme
  };
})();

App.init();
