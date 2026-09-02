/* ================================================================
   KhidmatAI — AI Assistant page (chat.js)
   Auth-guarded ChatGPT-style chat on POST /api/chat:
   - Recent conversations (localStorage) + New Chat
   - Welfare resources sidebar
   - Retry button + error state
   - Database / Web source badges on every answer
   - Voice input (STT) + voice replies (TTS)
   ================================================================ */
(function () {
  "use strict";

  /* ---------- Auth guard ---------- */
  var user = null;
  try {
    user = JSON.parse(localStorage.getItem("kai_user") || "null");
  } catch (e) { user = null; }
  if (!user || !user.email) {
    location.replace("/login");
    return;
  }

  /* ---------- Theme ---------- */
  var root = document.documentElement;
  var themeBtn = document.getElementById("themeToggle");
  var themeIcon = document.getElementById("themeIcon");

  function applyTheme(mode) {
    var dark = mode === "dark";
    root.classList.toggle("dark-mode", dark);
    document.body.classList.toggle("dark-mode", dark);
    if (themeIcon) themeIcon.textContent = dark ? "☀" : "☾";
  }
  applyTheme(localStorage.getItem("khidmat-theme") || "light");
  if (themeBtn) {
    themeBtn.addEventListener("click", function () {
      var next = root.classList.contains("dark-mode") ? "light" : "dark";
      localStorage.setItem("khidmat-theme", next);
      applyTheme(next);
    });
  }

  /* ---------- User chip ---------- */
  var nameEl = document.getElementById("chatUserName");
  var avatarEl = document.getElementById("chatAvatar");
  var displayName = user.name || user.email;
  if (nameEl) nameEl.textContent = displayName.split(" ")[0];
  if (avatarEl) avatarEl.textContent = (displayName.trim()[0] || "K").toUpperCase();

  function byId(id) { return document.getElementById(id); }

  /* ---------- DOM refs ---------- */
  var chatScroll = byId("chatScroll");
  var chatWelcome = byId("chatWelcome");
  var chatInput = byId("chatInput");
  var chatComposer = byId("chatComposer");
  var sendBtn = byId("sendBtn");
  var micBtn = byId("micBtn");
  var ttsToggle = byId("ttsToggle");
  var sidebar = byId("chatSidebar");
  var sidebarToggle = byId("chatSidebarToggle");
  var newChatBtn = byId("newChatBtn");
  var recentBox = byId("recentChats");

  var chatBusy = false;

  function escHtml(s) {
    var d = document.createElement("div");
    d.textContent = s == null ? "" : String(s);
    return d.innerHTML;
  }

  function scrollBottom() {
    chatScroll.scrollTop = chatScroll.scrollHeight;
  }

  /* ================================================================
     CONVERSATIONS (localStorage: kai_chats + kai_active_chat)
     Each chat: { id, title, updated_at,
                  messages: [{role:'user', text} | {role:'bot', data}] }
     ================================================================ */
  var CHATS_KEY = "kai_chats";
  var ACTIVE_KEY = "kai_active_chat";
  var MAX_CHATS = 15;
  var MAX_MESSAGES = 60;

  var chats = [];
  var activeChatId = null;

  function loadChats() {
    try { chats = JSON.parse(localStorage.getItem(CHATS_KEY) || "[]"); }
    catch (e) { chats = []; }
    if (!Array.isArray(chats)) chats = [];
  }

  function saveChats() {
    try {
      chats.sort(function (a, b) { return (b.updated_at || 0) - (a.updated_at || 0); });
      chats = chats.slice(0, MAX_CHATS);
      localStorage.setItem(CHATS_KEY, JSON.stringify(chats));
      if (activeChatId) localStorage.setItem(ACTIVE_KEY, activeChatId);
      else localStorage.removeItem(ACTIVE_KEY);
    } catch (e) { /* storage full or disabled — chat still works in memory */ }
  }

  function activeChat() {
    for (var i = 0; i < chats.length; i++) {
      if (chats[i].id === activeChatId) return chats[i];
    }
    return null;
  }

  function ensureChat() {
    var c = activeChat();
    if (c) return c;
    c = {
      id: "c" + Date.now() + "-" + Math.random().toString(36).slice(2, 7),
      title: "New conversation",
      updated_at: Date.now(),
      messages: []
    };
    chats.unshift(c);
    activeChatId = c.id;
    saveChats();
    return c;
  }

  function relTime(ts) {
    if (!ts) return "";
    var diff = Date.now() - ts;
    if (diff < 60000) return "now";
    if (diff < 3600000) return Math.floor(diff / 60000) + "m";
    if (diff < 86400000) return Math.floor(diff / 3600000) + "h";
    if (diff < 604800000) return Math.floor(diff / 86400000) + "d";
    try { return new Date(ts).toLocaleDateString(); } catch (e) { return ""; }
  }

  function renderRecent() {
    if (!recentBox) return;
    recentBox.innerHTML = "";
    if (!chats.length) {
      var empty = document.createElement("p");
      empty.className = "chat-recent-empty";
      empty.textContent = "No conversations yet.";
      recentBox.appendChild(empty);
      return;
    }
    var sorted = chats.slice().sort(function (a, b) { return (b.updated_at || 0) - (a.updated_at || 0); });
    sorted.forEach(function (c) {
      var item = document.createElement("div");
      item.className = "chat-recent-item" + (c.id === activeChatId ? " active" : "");

      var open = document.createElement("button");
      open.type = "button";
      open.className = "chat-recent-open";
      open.title = c.title || "Conversation";
      var title = document.createElement("span");
      title.className = "chat-recent-title";
      title.textContent = c.title || "Conversation";
      var time = document.createElement("span");
      time.className = "chat-recent-time";
      time.textContent = relTime(c.updated_at);
      open.appendChild(title);
      open.appendChild(time);
      open.addEventListener("click", function () { openChat(c.id); });

      var del = document.createElement("button");
      del.type = "button";
      del.className = "chat-recent-del";
      del.title = "Delete conversation";
      del.setAttribute("aria-label", "Delete conversation");
      var delIcon = document.createElement("i");
      delIcon.className = "fa-solid fa-xmark";
      del.appendChild(delIcon);
      del.addEventListener("click", function (ev) {
        ev.stopPropagation();
        deleteChat(c.id);
      });

      item.appendChild(open);
      item.appendChild(del);
      recentBox.appendChild(item);
    });
  }

  function clearMessageDom() {
    Array.prototype.slice.call(chatScroll.children).forEach(function (child) {
      if (child !== chatWelcome) child.remove();
    });
  }

  function showWelcome(show) {
    if (chatWelcome) chatWelcome.style.display = show ? "" : "none";
  }

  function renderConversation(c) {
    clearMessageDom();
    var hasMessages = c && c.messages && c.messages.length;
    showWelcome(!hasMessages);
    if (hasMessages) {
      c.messages.forEach(function (m) {
        if (m.role === "user") {
          appendUserMsg(m.text);
        } else if (m.role === "bot" && m.data) {
          appendBotMsg(m.data, false);
        }
      });
    }
    refreshRetryButtons();
    scrollBottom();
  }

  function openChat(id) {
    var c = null;
    for (var i = 0; i < chats.length; i++) { if (chats[i].id === id) { c = chats[i]; break; } }
    if (!c) return;
    activeChatId = id;
    saveChats();
    renderConversation(c);
    renderRecent();
    closeSidebar();
    chatInput.focus();
  }

  function deleteChat(id) {
    chats = chats.filter(function (c) { return c.id !== id; });
    if (activeChatId === id) {
      activeChatId = null;
      clearMessageDom();
      showWelcome(true);
      refreshRetryButtons();
    }
    saveChats();
    renderRecent();
  }

  function newChat() {
    activeChatId = null;
    clearMessageDom();
    showWelcome(true);
    refreshRetryButtons();
    saveChats();
    renderRecent();
    closeSidebar();
    chatInput.focus();
  }

  if (newChatBtn) newChatBtn.addEventListener("click", newChat);

  /* ---------- Sidebar (mobile drawer) ---------- */
  function closeSidebar() {
    if (sidebar) sidebar.classList.remove("open");
  }

  if (sidebarToggle && sidebar) {
    sidebarToggle.addEventListener("click", function () {
      sidebar.classList.toggle("open");
    });
    Array.prototype.slice.call(sidebar.querySelectorAll("a, button")).forEach(function (el) {
      el.addEventListener("click", function () {
        if (el !== sidebarToggle && !el.classList.contains("chat-recent-del")) closeSidebar();
      });
    });
  }

  /* ---------- Suggestion chips ---------- */
  document.querySelectorAll("#suggestionRow .suggestion").forEach(function (chip) {
    chip.addEventListener("click", function () {
      chatInput.value = chip.textContent.trim();
      sendChat();
    });
  });

  /* ---------- Deep link (?q=...) from dashboard suggestions ---------- */
  try {
    var deepLink = new URLSearchParams(window.location.search).get("q");
    if (deepLink && deepLink.trim()) {
      chatInput.value = deepLink.trim().slice(0, 5000);
      setTimeout(sendChat, 150);
    }
  } catch (e) { /* ignore bad params */ }

  /* ---------- Composer ---------- */
  chatInput.addEventListener("input", function () {
    chatInput.style.height = "auto";
    chatInput.style.height = Math.min(chatInput.scrollHeight, 130) + "px";
  });

  chatComposer.addEventListener("submit", function (event) {
    event.preventDefault();
    sendChat();
  });

  /* ---------- Language preference (shared with dashboard via kai_lang) ---------- */
  function chatLanguage() {
    var v = "english";
    try { v = (localStorage.getItem("kai_lang") || "english").toLowerCase(); } catch (e) { /* keep default */ }
    return v === "urdu" || v === "roman" ? v : "english";
  }

  function ttsLang() {
    return chatLanguage() === "urdu" ? "ur-PK" : "en-US";
  }

  /* ---------- Send flow ---------- */
  function appendUserMsg(text) {
    var div = document.createElement("div");
    div.className = "chat-bubble user";
    div.textContent = text;
    chatScroll.appendChild(div);
    scrollBottom();
    return div;
  }

  function sendChat() {
    var msg = chatInput.value.trim();
    if (!msg || chatBusy) return;
    chatInput.value = "";
    chatInput.style.height = "auto";
    sendMessage(msg);
  }

  async function sendMessage(msg) {
    if (chatBusy) return;
    showWelcome(false);
    appendUserMsg(msg);

    var c = ensureChat();
    c.messages.push({ role: "user", text: msg });
    var userCount = 0;
    c.messages.forEach(function (m) { if (m.role === "user") userCount++; });
    if (userCount === 1) {
      c.title = msg.length > 42 ? msg.slice(0, 42) + "\u2026" : msg;
    }
    c.updated_at = Date.now();
    if (c.messages.length > MAX_MESSAGES) c.messages = c.messages.slice(-MAX_MESSAGES);
    saveChats();
    renderRecent();

    await requestAnswer();
  }

  /* Ask the assistant for the last user message of the active conversation.
     Used by normal sends, error retries and regenerate. */
  async function requestAnswer() {
    if (chatBusy) return;
    var c = activeChat();
    var lastUser = null;
    if (c) {
      for (var i = c.messages.length - 1; i >= 0; i--) {
        if (c.messages[i].role === "user") { lastUser = c.messages[i]; break; }
      }
    }
    if (!lastUser) return;

    chatBusy = true;
    sendBtn.disabled = true;

    var loader = document.createElement("div");
    loader.className = "chat-loading";
    var loaderIcon = document.createElement("i");
    loaderIcon.className = "fa-solid fa-circle-notch spin";
    loader.appendChild(loaderIcon);
    loader.appendChild(document.createTextNode(" KhidmatAI is thinking..."));
    chatScroll.appendChild(loader);
    scrollBottom();

    try {
      var r = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: lastUser.text, language: chatLanguage() })
      });
      if (r.status === 429) throw new Error("You are sending messages too quickly. Please wait a moment.");
      var d = {};
      try { d = await r.json(); } catch (e) { /* non-JSON error */ }
      if (!r.ok) throw new Error((d && d.detail) || "Something went wrong. Please try again.");
      loader.remove();
      var botData = {
        answer: d.answer || {},
        db_count: Array.isArray(d.matches) ? d.matches.length : 0,
        web_count: Array.isArray(d.sources) ? d.sources.length : 0
      };
      appendBotMsg(botData, true);
      c.messages.push({ role: "bot", data: botData });
      c.updated_at = Date.now();
      saveChats();
      renderRecent();
    } catch (err) {
      loader.remove();
      appendErrorBubble((err && err.message) || "Sorry, something went wrong. Please try again.");
    }

    chatBusy = false;
    sendBtn.disabled = false;
    chatInput.focus();
  }

  /* ---------- Error state (with retry button) ---------- */
  function appendErrorBubble(text) {
    var div = document.createElement("div");
    div.className = "chat-bubble bot chat-error";

    var head = document.createElement("div");
    head.className = "chat-error-head";
    var icon = document.createElement("i");
    icon.className = "fa-solid fa-triangle-exclamation";
    head.appendChild(icon);
    var msg = document.createElement("span");
    msg.textContent = text;
    head.appendChild(msg);
    div.appendChild(head);

    var retry = document.createElement("button");
    retry.type = "button";
    retry.className = "chat-retry-btn";
    var retryIcon = document.createElement("i");
    retryIcon.className = "fa-solid fa-rotate-right";
    retry.appendChild(retryIcon);
    retry.appendChild(document.createTextNode(" Retry"));
    retry.addEventListener("click", function () {
      div.remove();
      requestAnswer();
    });
    div.appendChild(retry);

    chatScroll.appendChild(div);
    refreshRetryButtons();
    scrollBottom();
  }

  /* ---------- Retry button under the latest answer ---------- */
  function refreshRetryButtons() {
    Array.prototype.slice.call(document.querySelectorAll(".msg-retry-btn")).forEach(function (b) { b.remove(); });
    var bubbles = chatScroll.querySelectorAll(".chat-bubble.bot:not(.chat-error)");
    if (!bubbles.length) return;
    var last = bubbles[bubbles.length - 1];
    var tools = last.querySelector(".msg-tools");
    if (!tools) return;
    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "tts-btn msg-retry-btn";
    btn.title = "Regenerate this response";
    btn.setAttribute("aria-label", "Regenerate this response");
    var icon = document.createElement("i");
    icon.className = "fa-solid fa-rotate-right";
    btn.appendChild(icon);
    btn.addEventListener("click", regenerateLast);
    tools.appendChild(btn);
  }

  function regenerateLast() {
    if (chatBusy) return;
    var c = activeChat();
    if (!c || !c.messages.length) return;
    var lastUserIdx = -1;
    for (var i = c.messages.length - 1; i >= 0; i--) {
      if (c.messages[i].role === "user") { lastUserIdx = i; break; }
    }
    if (lastUserIdx === -1) return;
    c.messages = c.messages.slice(0, lastUserIdx + 1);
    renderConversation(c);
    requestAnswer();
  }

  /* ---------- Source badges (Database / Web) ---------- */
  function buildSourceBadges(data) {
    var dbN = data && data.db_count ? Number(data.db_count) : 0;
    var webN = data && data.web_count ? Number(data.web_count) : 0;
    if (!dbN && !webN) return null;
    var row = document.createElement("div");
    row.className = "chat-sources";
    if (dbN) {
      var db = document.createElement("span");
      db.className = "src-badge db";
      var dbIcon = document.createElement("i");
      dbIcon.className = "fa-solid fa-database";
      db.appendChild(dbIcon);
      db.appendChild(document.createTextNode(" Database" + (dbN > 1 ? " \u00b7 " + dbN + " programs" : "")));
      row.appendChild(db);
    }
    if (webN) {
      var web = document.createElement("span");
      web.className = "src-badge web";
      var webIcon = document.createElement("i");
      webIcon.className = "fa-solid fa-globe";
      web.appendChild(webIcon);
      web.appendChild(document.createTextNode(" Web" + (webN > 1 ? " \u00b7 " + webN + " sources" : "")));
      row.appendChild(web);
    }
    return row;
  }

  /* ---------- Render assistant answer ----------
     Structure: source badges → summary (bullets) → official source →
     program cards → next steps → tools (listen / regenerate).
     Technical details such as model names are never shown. */
  function appendBotMsg(data, live) {
    var ans = (data && data.answer) || {};
    var div = document.createElement("div");
    div.className = "chat-bubble bot";

    // Database / Web source badges
    var badges = buildSourceBadges(data);
    if (badges) div.appendChild(badges);

    // Summary (always rendered prominently; bullets parsed)
    var summaryText = String(ans.summary || "").trim();
    if (!summaryText) {
      var n = (ans.programs || []).length;
      summaryText = n > 0
        ? "Found " + n + " verified option" + (n > 1 ? "s" : "") + " for you."
        : "Please check official sources for the latest information.";
    }

    var summary = document.createElement("div");
    summary.className = "chat-summary";
    summaryText.split("\n").forEach(function (line) {
      var t = line.trim();
      if (!t) return;
      if (t.charAt(0) === "\u2022" || t.charAt(0) === "-") {
        var b = document.createElement("div");
        b.className = "summary-bullet";
        b.textContent = t.substring(1).trim();
        summary.appendChild(b);
      } else {
        var p = document.createElement("p");
        p.textContent = t;
        summary.appendChild(p);
      }
    });
    div.appendChild(summary);

    // Top-level official source
    var officialSource = String(ans.official_source || "");
    if (/^https?:\/\//i.test(officialSource)) {
      var src = document.createElement("div");
      src.className = "chat-official-source";
      var a = document.createElement("a");
      a.href = officialSource;
      a.target = "_blank";
      a.rel = "noopener";
      a.textContent = "Official Source";
      src.appendChild(document.createTextNode("\u2197 "));
      src.appendChild(a);
      div.appendChild(src);
    }

    // Program cards
    var programs = ans.programs || [];
    if (programs.length) {
      var wrap = document.createElement("div");
      wrap.className = "chat-programs";
      programs.forEach(function (p) {
        var card = document.createElement("div");
        card.className = "chat-program-card";

        var title = document.createElement("strong");
        title.textContent = p.title || "Program";
        card.appendChild(title);

        if (p.match_level) {
          var badge = document.createElement("span");
          badge.className = "match-badge";
          badge.textContent = p.match_level;
          card.appendChild(document.createTextNode(" "));
          card.appendChild(badge);
        }

        if (p.why_match) {
          var why = document.createElement("p");
          why.className = "why-match";
          why.textContent = p.why_match;
          card.appendChild(why);
        }

        var progSource = String(p.official_source || p.source_url || "");
        if (/^https?:\/\//i.test(progSource)) {
          var link = document.createElement("a");
          link.className = "prog-source-link";
          link.href = progSource;
          link.target = "_blank";
          link.rel = "noopener";
          link.textContent = "\u2197 Official Source";
          card.appendChild(link);
        }
        wrap.appendChild(card);
      });
      div.appendChild(wrap);
    }

    // Next steps
    var steps = ans.next_steps || [];
    if (steps.length) {
      var ns = document.createElement("div");
      ns.className = "chat-next-steps";
      var label = document.createElement("strong");
      label.textContent = "Next steps:";
      ns.appendChild(label);
      var ul = document.createElement("ul");
      steps.forEach(function (s) {
        var li = document.createElement("li");
        li.textContent = s;
        ul.appendChild(li);
      });
      ns.appendChild(ul);
      div.appendChild(ns);
    }

    // Listen button (TTS) — regenerate button is added by refreshRetryButtons()
    var tools = document.createElement("div");
    tools.className = "msg-tools";
    var ttsBtn = document.createElement("button");
    ttsBtn.className = "tts-btn";
    ttsBtn.type = "button";
    ttsBtn.title = "Listen to this response";
    ttsBtn.setAttribute("aria-label", "Listen to this response");
    var ttsIcon = document.createElement("i");
    ttsIcon.className = "fa-solid fa-volume-high";
    ttsBtn.appendChild(ttsIcon);
    ttsBtn.addEventListener("click", function () { speakText(summaryText, ttsLang()); });
    tools.appendChild(ttsBtn);
    div.appendChild(tools);

    chatScroll.appendChild(div);
    refreshRetryButtons();
    scrollBottom();

    // Auto voice reply when enabled (only for fresh answers, not restored chats)
    if (live && _ttsEnabled && summaryText) {
      speakText(summaryText.replace(/\u2022/g, "").trim(), ttsLang());
    }
  }

  /* ---------- Voice input (Speech-to-Text) ---------- */
  var _recognition = null;
  var _isListening = false;

  function appendNotice(text) {
    var div = document.createElement("div");
    div.className = "chat-bubble bot";
    div.textContent = text;
    chatScroll.appendChild(div);
    scrollBottom();
  }

  function toggleVoiceInput() {
    if (!("webkitSpeechRecognition" in window) && !("SpeechRecognition" in window)) {
      appendNotice("Voice input is not supported in this browser. Please use Chrome or Edge.");
      return;
    }
    if (_isListening) { stopVoiceInput(); return; }
    startVoiceInput();
  }

  function startVoiceInput() {
    var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    _recognition = new SR();
    _recognition.lang = "en-US";
    _recognition.continuous = false;
    _recognition.interimResults = true;
    _recognition.maxAlternatives = 1;

    _recognition.onstart = function () {
      _isListening = true;
      micBtn.classList.add("listening");
      micBtn.title = "Listening... Click to stop";
    };
    _recognition.onresult = function (event) {
      var transcript = "";
      for (var i = event.resultIndex; i < event.results.length; i++) {
        transcript += event.results[i][0].transcript;
      }
      chatInput.value = transcript;
    };
    _recognition.onend = function () {
      _isListening = false;
      micBtn.classList.remove("listening");
      micBtn.title = "Voice input";
      if (chatInput.value.trim()) sendChat();
    };
    _recognition.onerror = function (event) {
      _isListening = false;
      micBtn.classList.remove("listening");
      if (event.error === "not-allowed") {
        appendNotice("Microphone access denied. Please allow microphone permissions in your browser.");
      }
    };
    _recognition.start();
  }

  function stopVoiceInput() {
    if (_recognition) { _recognition.stop(); _recognition = null; }
    _isListening = false;
    micBtn.classList.remove("listening");
  }

  if (micBtn) micBtn.addEventListener("click", toggleVoiceInput);

  /* ---------- Text-to-Speech ---------- */
  var _ttsEnabled = localStorage.getItem("kai_tts") === "true";

  function renderTtsToggle() {
    if (!ttsToggle) return;
    ttsToggle.style.background = _ttsEnabled ? "#e8f5ef" : "#f1f6f4";
    ttsToggle.style.color = _ttsEnabled ? "#087b5c" : "#5c716b";
  }
  renderTtsToggle();

  if (ttsToggle) {
    ttsToggle.addEventListener("click", function () {
      _ttsEnabled = !_ttsEnabled;
      localStorage.setItem("kai_tts", String(_ttsEnabled));
      renderTtsToggle();
      if (!_ttsEnabled) stopSpeech();
    });
  }

  function speakText(text, lang) {
    if (!("speechSynthesis" in window) || !text) return;
    stopSpeech();
    var utter = new SpeechSynthesisUtterance(text);
    utter.lang = lang || "en-US";
    utter.rate = 1.0;
    utter.pitch = 1.0;
    utter.volume = 1.0;
    var voices = speechSynthesis.getVoices();
    var match = voices.find(function (v) { return v.lang.indexOf((lang || "en").slice(0, 2)) === 0; });
    if (match) utter.voice = match;
    speechSynthesis.speak(utter);
  }

  function stopSpeech() {
    if ("speechSynthesis" in window) speechSynthesis.cancel();
  }

  if ("speechSynthesis" in window) {
    speechSynthesis.getVoices();
    speechSynthesis.onvoiceschanged = function () { speechSynthesis.getVoices(); };
  }

  /* ---------- Boot: restore last conversation ---------- */
  loadChats();
  try { activeChatId = localStorage.getItem(ACTIVE_KEY) || null; } catch (e) { activeChatId = null; }
  var bootChat = activeChat();
  if (bootChat && bootChat.messages && bootChat.messages.length) {
    renderConversation(bootChat);
  } else {
    activeChatId = null;
    showWelcome(true);
  }
  renderRecent();
  chatInput.focus();
})();
