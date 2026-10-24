var Store = (function () {
  var CHATS_KEY = "pv.chats.v1";
  var HARNESS_KEY = "pv.harness.v1";
  var THEME_KEY = "pv.theme.v1";
  var DEFAULT_HARNESS = {
    providerId: "local",
    systemPrompt: "",
    temperature: 0.7,
    maxTokens: 512,
    useTools: true
  };

  function read(key, fallback) {
    try {
      var raw = localStorage.getItem(key);
      return raw ? JSON.parse(raw) : fallback;
    } catch (e) {
      return fallback;
    }
  }

  function write(key, value) {
    try { localStorage.setItem(key, JSON.stringify(value)); } catch (e) {}
  }

  function chats() {
    var list = read(CHATS_KEY, []);
    return Array.isArray(list) ? list : [];
  }

  function saveChats(list) {
    write(CHATS_KEY, (list || []).slice(0, 200));
  }

  function getChat(id) {
    if (!id) return null;
    var list = chats();
    for (var i = 0; i < list.length; i++) {
      if (list[i] && list[i].id === id) return list[i];
    }
    return null;
  }

  function putChat(chat) {
    var list = chats();
    var index = -1;
    for (var i = 0; i < list.length; i++) {
      if (list[i] && list[i].id === chat.id) { index = i; break; }
    }
    if (index >= 0) list[index] = chat;
    else list.unshift(chat);
    list.sort(function (a, b) { return (b.updatedAt || 0) - (a.updatedAt || 0); });
    saveChats(list);
  }

  function deleteChat(id) {
    saveChats(chats().filter(function (chat) { return chat.id !== id; }));
  }

  function harness() {
    var saved = read(HARNESS_KEY, {});
    return Object.assign({}, DEFAULT_HARNESS, saved && typeof saved === "object" ? saved : {});
  }

  function saveHarness(settings) {
    write(HARNESS_KEY, settings);
  }

  function theme() {
    try { return localStorage.getItem(THEME_KEY) || "light"; } catch (e) { return "light"; }
  }

  function saveTheme(name) {
    try { localStorage.setItem(THEME_KEY, name); } catch (e) {}
  }

  return {
    chats: chats,
    getChat: getChat,
    putChat: putChat,
    deleteChat: deleteChat,
    saveChats: saveChats,
    harness: harness,
    saveHarness: saveHarness,
    theme: theme,
    saveTheme: saveTheme,
    defaults: DEFAULT_HARNESS
  };
})();

function uid(prefix) {
  return (prefix || "id") + "-" + Date.now().toString(36) + "-" +
    Math.random().toString(36).slice(2, 7);
}

function esc(value) {
  return String(value == null ? "" : value).replace(/[&<>"']/g, function (ch) {
    return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch];
  });
}

function clock(ts) {
  try {
    return new Date(ts || Date.now()).toLocaleTimeString([], {
      hour: "2-digit", minute: "2-digit", hour12: false
    });
  } catch (e) { return ""; }
}

function dayKey(ts) {
  var d = new Date(ts || Date.now());
  return d.getFullYear() + "-" + d.getMonth() + "-" + d.getDate();
}

function dayLabel(ts) {
  var date = new Date(ts || Date.now());
  var today = new Date();
  var yesterday = new Date();
  yesterday.setDate(today.getDate() - 1);
  if (dayKey(date) === dayKey(today)) return "TODAY";
  if (dayKey(date) === dayKey(yesterday)) return "YESTERDAY";
  try {
    return date.toLocaleDateString([], {
      day: "2-digit", month: "short", year: "numeric"
    }).toUpperCase();
  } catch (e) { return ""; }
}

function titleFrom(text) {
  var clean = String(text || "").replace(/\s+/g, " ").trim();
  if (!clean) return "New chat";
  return clean.length > 42 ? clean.slice(0, 42) + "…" : clean;
}

function initialOf(text) {
  var clean = String(text || "").trim();
  return clean ? clean.charAt(0).toUpperCase() : "?";
}

function colorFor(id) {
  var palette = ["#00a884", "#7c5cbf", "#e07a5f", "#3d8bfd", "#c26b9a", "#5a9e6f", "#b98a2f"];
  var hash = 0;
  String(id || "").split("").forEach(function (ch) {
    hash = (hash * 31 + ch.charCodeAt(0)) >>> 0;
  });
  return palette[hash % palette.length];
}

function inlineMd(text) {
  return esc(text)
    .replace(/`([^`\n]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>")
    .replace(/\n/g, "<br>");
}

function markdown(text) {
  var source = String(text || "");
  var out = "";
  var last = 0;
  var re = /```([\w+-]*)\r?\n([\s\S]*?)```/g;
  var match;
  while ((match = re.exec(source))) {
    out += inlineMd(source.slice(last, match.index));
    out += "<pre><code>" + esc(match[2].replace(/\n$/, "")) + "</code></pre>";
    last = re.lastIndex;
  }
  out += inlineMd(source.slice(last));
  return out;
}
