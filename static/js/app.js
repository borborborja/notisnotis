(function () {
  // Colapso de categorías en el sidebar (persistente en localStorage).
  var KEY = "nn_collapsed";
  function getCollapsed() {
    try { return JSON.parse(localStorage.getItem(KEY) || "[]"); } catch (e) { return []; }
  }
  function setCollapsed(list) { localStorage.setItem(KEY, JSON.stringify(list)); }

  function initGroups() {
    var collapsed = getCollapsed();
    document.querySelectorAll(".sb-group").forEach(function (group) {
      var name = group.querySelector(".sb-group-name");
      var id = name ? name.textContent.trim() : "";
      if (collapsed.indexOf(id) !== -1) group.classList.add("collapsed");
      var btn = group.querySelector("[data-collapse-toggle]");
      if (btn) {
        btn.addEventListener("click", function () {
          group.classList.toggle("collapsed");
          var list = getCollapsed();
          var i = list.indexOf(id);
          if (group.classList.contains("collapsed")) { if (i === -1) list.push(id); }
          else if (i !== -1) list.splice(i, 1);
          setCollapsed(list);
        });
      }
    });
  }

  // Colapso de secciones del sidebar (persistente en localStorage).
  var SKEY = "nn_section_collapsed";
  function getSectionCollapsed() {
    try { return JSON.parse(localStorage.getItem(SKEY) || "[]"); } catch (e) { return []; }
  }
  function setSectionCollapsed(list) { localStorage.setItem(SKEY, JSON.stringify(list)); }
  function initSections() {
    var col = getSectionCollapsed();
    document.querySelectorAll(".sb-section").forEach(function (sec) {
      var key = sec.dataset.section || "";
      if (col.indexOf(key) !== -1) sec.classList.add("collapsed");
      var btn = sec.querySelector("[data-section-toggle]");
      if (btn) {
        btn.addEventListener("click", function () {
          sec.classList.toggle("collapsed");
          var list = getSectionCollapsed();
          var i = list.indexOf(key);
          if (sec.classList.contains("collapsed")) { if (i === -1) list.push(key); }
          else if (i !== -1) list.splice(i, 1);
          setSectionCollapsed(list);
        });
      }
    });
  }

  // Sidebar off-canvas en móvil.
  function initSidebarToggle() {
    var btn = document.querySelector("[data-sidebar-toggle]");
    function close() { document.body.classList.remove("sidebar-open"); }
    if (btn) btn.addEventListener("click", function () { document.body.classList.toggle("sidebar-open"); });
    // Cerrar al tocar el fondo oscuro.
    var backdrop = document.querySelector("[data-sidebar-close]");
    if (backdrop) backdrop.addEventListener("click", close);
    // Cerrar al navegar desde el sidebar (en móvil el menú es overlay).
    var sb = document.querySelector("[data-sidebar]");
    if (sb) sb.addEventListener("click", function (e) { if (e.target.closest("a")) close(); });
  }

  // Resalta el ítem abierto en la lista.
  document.body.addEventListener("click", function (e) {
    var item = e.target.closest && e.target.closest(".item");
    if (!item) return;
    document.querySelectorAll(".item.active").forEach(function (x) { x.classList.remove("active"); });
    item.classList.add("active");
  });

  // ---- Tema (claro / oscuro / auto) ----
  function applyTheme(name) {
    var dark = name === "dark" || (name === "auto" && matchMedia("(prefers-color-scheme: dark)").matches);
    document.documentElement.setAttribute("data-theme", dark ? "dark" : "light");
  }
  function currentTheme() { return localStorage.getItem("nn_theme") || "auto"; }
  function setTheme(name) {
    localStorage.setItem("nn_theme", name);
    applyTheme(name);
    var label = document.getElementById("theme-current");
    if (label) label.textContent = "Tema actual: " + name;
    document.querySelectorAll("[data-theme-set]").forEach(function (b) {
      b.classList.toggle("active", b.getAttribute("data-theme-set") === name);
    });
  }
  function initTheme() {
    setTheme(currentTheme());
    document.querySelectorAll("[data-theme-set]").forEach(function (b) {
      b.addEventListener("click", function () { setTheme(b.getAttribute("data-theme-set")); });
    });
    var toggle = document.querySelector("[data-theme-toggle]");
    if (toggle) {
      toggle.addEventListener("click", function () {
        var order = ["light", "dark", "auto"];
        setTheme(order[(order.indexOf(currentTheme()) + 1) % order.length]);
      });
    }
    // Reacciona a cambios del sistema cuando está en "auto".
    var mq = matchMedia("(prefers-color-scheme: dark)");
    var onChange = function () { if (currentTheme() === "auto") applyTheme("auto"); };
    if (mq.addEventListener) mq.addEventListener("change", onChange);
    else if (mq.addListener) mq.addListener(onChange);
  }

  // Auto-scroll del hilo de chat al fondo tras cada intercambio.
  document.body.addEventListener("htmx:afterSwap", function (e) {
    if (e.target && e.target.id === "chat-thread") e.target.scrollTop = e.target.scrollHeight;
    if (e.target && (e.target.id === "article-items" || e.target.classList.contains("load-more"))) {
      observeAutomark();
    }
  });

  function getCookie(name) {
    var m = document.cookie.match("(^|;)\\s*" + name + "\\s*=\\s*([^;]+)");
    return m ? m.pop() : "";
  }
  function post(url) {
    return fetch(url, { method: "POST", headers: { "X-CSRFToken": getCookie("csrftoken") } });
  }
  function postForm(url, data) {
    var body = new FormData();
    Object.keys(data || {}).forEach(function (k) { body.append(k, data[k]); });
    return fetch(url, { method: "POST", headers: { "X-CSRFToken": getCookie("csrftoken") }, body: body });
  }

  // ---- Fallback de imágenes rotas (hotlink/404/mixed-content) → placeholder ----
  var IMG_PH = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 48 48'%3E%3Crect width='48' height='48' rx='6' fill='%23e6e3f0'/%3E%3Cpath d='M24 13a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0v-6a3 3 0 0 0-3-3z' fill='%239b93b8'/%3E%3Cpath d='M30 21v1a6 6 0 0 1-12 0v-1' stroke='%239b93b8' stroke-width='2' fill='none' stroke-linecap='round'/%3E%3C/svg%3E";
  function initImageFallback() {
    document.addEventListener("error", function (e) {
      var img = e.target;
      if (img && img.tagName === "IMG" && img.hasAttribute("data-ph")) {
        img.removeAttribute("data-ph");   // evita bucle
        img.src = IMG_PH;
      }
    }, true);  // captura: los eventos 'error' de img no burbujean
  }

  // ---- Reproductor de podcasts persistente (Pocket Casts-style) ----
  var SPEEDS = [1, 1.2, 1.5, 1.75, 2, 0.8];
  function fmtTime(s) {
    s = Math.max(0, Math.floor(s || 0));
    var h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
    var mm = (h ? (m < 10 ? "0" : "") : "") + m, ss = (sec < 10 ? "0" : "") + sec;
    return (h ? h + ":" : "") + mm + ":" + ss;
  }
  function initPlayer() {
    var bar = document.getElementById("nn-player");
    if (!bar) return;
    var audio = document.getElementById("np-audio");
    var els = {
      art: document.getElementById("np-art"), title: document.getElementById("np-title"),
      artLink: document.getElementById("np-art-link"),
      feed: document.getElementById("np-feed"), toggle: document.getElementById("np-toggle"),
      seek: document.getElementById("np-seek"), cur: document.getElementById("np-cur"),
      dur: document.getElementById("np-dur"), speed: document.getElementById("np-speed"),
    };
    var cur = null;            // {id, src, title, feed, art, speed}
    var lastSave = 0, seeking = false;

    function saveProgress(beacon) {
      if (!cur || !audio.duration) return;
      var data = { position: Math.floor(audio.currentTime), duration: Math.floor(audio.duration) };
      var url = "/podcasts/ep/" + cur.id + "/progress/";
      if (beacon && navigator.sendBeacon) {
        var fd = new FormData();
        fd.append("position", data.position); fd.append("duration", data.duration);
        fd.append("csrfmiddlewaretoken", getCookie("csrftoken"));
        navigator.sendBeacon(url, fd);
      } else { postForm(url, data); }
    }
    function setPlayIcon(playing) {
      els.toggle.querySelector("use").setAttribute("href", playing ? "#i-pause" : "#i-play");
    }

    function syncRowIcon() {
      document.querySelectorAll(".ep-row.ep-playing [data-ep-play] use").forEach(function (u) {
        u.setAttribute("href", audio.paused ? "#i-play" : "#i-pause");
      });
    }
    function markNowPlaying(id) {
      document.querySelectorAll(".ep-row [data-ep-play] use").forEach(function (u) {
        u.setAttribute("href", "#i-play");  // restablecer iconos de filas previas
      });
      document.querySelectorAll(".ep-playing").forEach(function (el) { el.classList.remove("ep-playing"); });
      if (!id) return;
      document.querySelectorAll('.ep-row [data-ep-id="' + id + '"]').forEach(function (b) {
        var row = b.closest(".ep-row"); if (row) row.classList.add("ep-playing");
      });
      syncRowIcon();
    }

    function load(ep, autoplay) {
      cur = ep;
      bar.hidden = false;
      document.body.classList.add("player-on");
      els.title.textContent = ep.title || "";
      els.feed.textContent = ep.feed || "";
      var epHref = ep.id ? "/articles/" + ep.id + "/" : "#";
      els.title.setAttribute("href", epHref);
      if (els.artLink) els.artLink.setAttribute("href", epHref);
      if (ep.art) { els.art.src = ep.art; els.art.style.visibility = "visible"; }
      else { els.art.removeAttribute("src"); els.art.style.visibility = "hidden"; }
      audio.src = ep.src;
      var speed = parseFloat(ep.speed) || 1;
      audio.playbackRate = speed;
      els.speed.textContent = (speed % 1 ? speed : speed + "") + "×";
      var resume = parseFloat(ep.pos) || 0;
      audio.addEventListener("loadedmetadata", function once() {
        audio.removeEventListener("loadedmetadata", once);
        if (resume > 0 && resume < (audio.duration - 5)) audio.currentTime = resume;
      });
      try { localStorage.setItem("nn_player", JSON.stringify(ep)); } catch (e) {}
      markNowPlaying(ep.id);
      var qb = document.getElementById("np-queue");  // reset estado de "en cola" por episodio
      if (qb) { qb.classList.remove("active"); qb.title = "Añadir a la cola"; }
      if (autoplay) audio.play().catch(function () {});
    }

    function play(ep) {
      // Si ya es el episodio cargado, alternar en vez de reiniciar.
      if (cur && ep && String(cur.id) === String(ep.id) && audio.src) {
        audio.paused ? audio.play() : audio.pause();
        return;
      }
      load(ep, true);
    }
    window.nnPlay = play;   // otras partes (listas, cola) pueden invocarlo
    window.nnMarkPlaying = function () { if (cur) markNowPlaying(cur.id); };

    document.addEventListener("click", function (e) {
      var btn = e.target.closest("[data-ep-play]");
      if (!btn) return;
      e.preventDefault();
      play({
        id: btn.getAttribute("data-ep-id"), src: btn.getAttribute("data-ep-src"),
        title: btn.getAttribute("data-ep-title"), feed: btn.getAttribute("data-ep-feed"),
        art: btn.getAttribute("data-ep-art"), pos: btn.getAttribute("data-ep-pos"),
        speed: btn.getAttribute("data-ep-speed"),
      });
    });

    els.toggle.addEventListener("click", function () { audio.paused ? audio.play() : audio.pause(); });
    document.getElementById("np-back").addEventListener("click", function () { audio.currentTime -= 15; });
    document.getElementById("np-fwd").addEventListener("click", function () { audio.currentTime += 30; });
    document.getElementById("np-close").addEventListener("click", function () {
      saveProgress(false); audio.pause(); bar.hidden = true; cur = null;
      document.body.classList.remove("player-on");
    });
    document.getElementById("np-played").addEventListener("click", function () {
      if (cur) post("/podcasts/ep/" + cur.id + "/played/");
    });
    var qBtn = document.getElementById("np-queue");
    if (qBtn) qBtn.addEventListener("click", function () {
      if (!cur) return;
      post("/podcasts/ep/" + cur.id + "/queue/");
      qBtn.classList.add("active");
      qBtn.title = "En la cola";
    });
    els.speed.addEventListener("click", function () {
      var i = SPEEDS.indexOf(audio.playbackRate);
      var next = SPEEDS[(i + 1) % SPEEDS.length];
      audio.playbackRate = next;
      els.speed.textContent = (next % 1 ? next : next + "") + "×";
    });
    // Sleep timer: off → 5 → 10 → 15 → 30 → 45 → 60 min.
    var SLEEPS = [0, 5, 10, 15, 30, 45, 60], sleepIdx = 0, sleepTO = null;
    var sleepBtn = document.getElementById("np-sleep"), sleepLbl = document.getElementById("np-sleep-lbl");
    if (sleepBtn) sleepBtn.addEventListener("click", function () {
      sleepIdx = (sleepIdx + 1) % SLEEPS.length;
      var mins = SLEEPS[sleepIdx];
      if (sleepTO) { clearTimeout(sleepTO); sleepTO = null; }
      sleepLbl.textContent = mins ? mins + "m" : "";
      sleepBtn.classList.toggle("active", !!mins);
      if (mins) sleepTO = setTimeout(function () {
        audio.pause(); sleepIdx = 0; sleepLbl.textContent = ""; sleepBtn.classList.remove("active");
      }, mins * 60000);
    });

    els.seek.addEventListener("input", function () { seeking = true; });
    els.seek.addEventListener("change", function () {
      if (audio.duration) audio.currentTime = (els.seek.value / 1000) * audio.duration;
      seeking = false;
    });

    audio.addEventListener("play", function () {
      setPlayIcon(true); syncRowIcon();
      document.body.classList.add("player-playing"); document.body.classList.remove("player-paused");
    });
    audio.addEventListener("pause", function () {
      setPlayIcon(false); saveProgress(false); syncRowIcon();
      document.body.classList.add("player-paused"); document.body.classList.remove("player-playing");
    });
    audio.addEventListener("timeupdate", function () {
      if (!audio.duration) return;
      if (!seeking) els.seek.value = (audio.currentTime / audio.duration) * 1000;
      els.cur.textContent = fmtTime(audio.currentTime);
      els.dur.textContent = fmtTime(audio.duration);
      var now = Date.now();
      if (now - lastSave > 15000) { lastSave = now; saveProgress(false); }
    });
    audio.addEventListener("ended", function () {
      if (cur) post("/podcasts/ep/" + cur.id + "/played/");
      if (window.nnQueueNext) window.nnQueueNext();
    });
    audio.addEventListener("error", function () {
      if (cur && audio.src) els.feed.textContent = "No se pudo reproducir el audio.";
    });
    // Buffering: pulso en el botón de play mientras carga.
    ["waiting", "stalled", "seeking"].forEach(function (ev) {
      audio.addEventListener(ev, function () { els.toggle.classList.add("loading"); });
    });
    ["playing", "canplay", "seeked", "pause"].forEach(function (ev) {
      audio.addEventListener(ev, function () { els.toggle.classList.remove("loading"); });
    });
    window.addEventListener("pagehide", function () { saveProgress(true); });
    document.addEventListener("visibilitychange", function () {
      if (document.visibilityState === "hidden") saveProgress(true);
    });

    // Barra espaciadora: play/pausa (si hay episodio cargado y no estás escribiendo).
    document.addEventListener("keydown", function (e) {
      if (e.code !== "Space" || !cur) return;
      var t = e.target.tagName;
      if (t === "INPUT" || t === "TEXTAREA" || t === "SELECT" || e.target.isContentEditable) return;
      e.preventDefault();
      audio.paused ? audio.play() : audio.pause();
    });

    // Restaurar el último episodio al recargar (en pausa, en su posición guardada).
    try {
      var saved = JSON.parse(localStorage.getItem("nn_player") || "null");
      if (saved && saved.src) load(saved, false);
    } catch (e) {}
  }

  // ---- Listas de podcasts: cola, escuchado, reproducir-cola, reordenar ----
  function epData(el) {
    return {
      id: el.getAttribute("data-ep-id"), src: el.getAttribute("data-ep-src"),
      title: el.getAttribute("data-ep-title"), feed: el.getAttribute("data-ep-feed"),
      art: el.getAttribute("data-ep-art"), pos: el.getAttribute("data-ep-pos"),
      speed: el.getAttribute("data-ep-speed"),
    };
  }
  function initPodcasts() {
    document.addEventListener("click", function (e) {
      var q = e.target.closest("[data-queue-toggle]");
      if (q) {
        e.preventDefault();
        var on = q.getAttribute("data-queued") === "1";
        var pk = q.getAttribute("data-ep");
        post("/podcasts/ep/" + pk + "/" + (on ? "unqueue" : "queue") + "/");
        q.setAttribute("data-queued", on ? "0" : "1");
        q.classList.toggle("active", !on);
        return;
      }
      var p = e.target.closest("[data-played-toggle]");
      if (p) {
        e.preventDefault();
        post("/podcasts/ep/" + p.getAttribute("data-ep") + "/played/");
        var row = p.closest(".ep-row");
        if (row) row.classList.toggle("ep-played");
        return;
      }
    });

    // Reproducir cola con auto-avance.
    var playQueue = document.getElementById("play-queue");
    var list = document.querySelector("[data-queue-reorder]");
    if (playQueue && list) {
      playQueue.addEventListener("click", function () {
        window.nnQueue = Array.prototype.map.call(list.querySelectorAll(".ep-row[data-ep-id]"), epData);
        if (window.nnQueue.length && window.nnPlay) window.nnPlay(window.nnQueue.shift());
      });
    }
    window.nnQueueNext = function () {
      if (window.nnQueue && window.nnQueue.length && window.nnPlay) window.nnPlay(window.nnQueue.shift());
    };

    // Reordenar la cola por drag & drop.
    if (list) {
      var dragged = null;
      list.addEventListener("dragstart", function (e) { dragged = e.target.closest(".ep-row"); });
      list.addEventListener("dragover", function (e) {
        e.preventDefault();
        var over = e.target.closest(".ep-row");
        if (over && dragged && over !== dragged) {
          var rect = over.getBoundingClientRect();
          var after = (e.clientY - rect.top) > rect.height / 2;
          list.insertBefore(dragged, after ? over.nextSibling : over);
        }
      });
      list.addEventListener("drop", function () {
        var body = new FormData();
        list.querySelectorAll(".ep-row[data-ep]").forEach(function (r) {
          body.append("order[]", r.getAttribute("data-ep"));
        });
        fetch("/podcasts/queue/reorder/", { method: "POST", headers: { "X-CSRFToken": getCookie("csrftoken") }, body: body });
      });
    }
  }

  // ---- Descargas offline (PWA) ----
  function dlStore() { try { return JSON.parse(localStorage.getItem("nn_downloads") || "{}"); } catch (e) { return {}; } }
  function dlSave(s) { try { localStorage.setItem("nn_downloads", JSON.stringify(s)); } catch (e) {} }
  function swSend(msg) {
    if (navigator.serviceWorker && navigator.serviceWorker.controller)
      navigator.serviceWorker.controller.postMessage(msg);
  }
  function initDownloads() {
    if (!("serviceWorker" in navigator)) return;
    var store = dlStore();

    // Marcar botones ya descargados.
    document.querySelectorAll("[data-download]").forEach(function (b) {
      if (store[b.getAttribute("data-ep-id")]) b.classList.add("active");
    });

    document.addEventListener("click", function (e) {
      var b = e.target.closest("[data-download]");
      if (!b) return;
      e.preventDefault();
      var id = b.getAttribute("data-ep-id"), url = b.getAttribute("data-ep-src");
      store = dlStore();
      if (store[id]) {
        swSend({ type: "uncache-audio", url: url });
        delete store[id]; dlSave(store); b.classList.remove("active");
      } else {
        b.classList.add("loading");
        swSend({ type: "cache-audio", url: url });
        store[id] = { id: id, src: url, title: b.getAttribute("data-ep-title"),
          feed: b.getAttribute("data-ep-feed"), art: b.getAttribute("data-ep-art"),
          pos: b.getAttribute("data-ep-pos"), speed: b.getAttribute("data-ep-speed") };
        dlSave(store); b.classList.add("active");
      }
    });

    navigator.serviceWorker.addEventListener("message", function (e) {
      var btn = document.querySelector('[data-download][data-ep-src="' + (e.data && e.data.url) + '"]');
      if (btn) btn.classList.remove("loading");
      if (e.data && !e.data.ok && !e.data.removed) {
        // falló la descarga → revertir
        document.querySelectorAll('[data-download][data-ep-src="' + e.data.url + '"]').forEach(function (b) {
          b.classList.remove("active"); var s = dlStore(); delete s[b.getAttribute("data-ep-id")]; dlSave(s);
        });
      }
    });

    // Página de descargas (cliente).
    var list = document.getElementById("downloads-list");
    if (list) {
      var items = Object.keys(store).map(function (k) { return store[k]; });
      if (!items.length) { list.innerHTML = '<p class="muted">No tienes episodios descargados.</p>'; }
      else items.forEach(function (ep) {
        var row = document.createElement("div"); row.className = "ep-row";
        row.innerHTML =
          '<img class="ep-art" src="' + (ep.art || "") + '" alt="">' +
          '<div class="ep-body"><div class="ep-title">' + (ep.title || "") + '</div>' +
          '<div class="ep-meta muted">' + (ep.feed || "") + '</div></div>' +
          '<div class="ep-actions">' +
          '<button class="np-btn" data-ep-play data-ep-id="' + ep.id + '" data-ep-src="' + ep.src +
          '" data-ep-title="' + (ep.title || "") + '" data-ep-feed="' + (ep.feed || "") +
          '" data-ep-art="' + (ep.art || "") + '" data-ep-pos="' + (ep.pos || 0) +
          '" data-ep-speed="' + (ep.speed || 1) + '"><svg class="ic"><use href="#i-play"/></svg></button>' +
          '<button class="np-btn active" data-download data-ep-id="' + ep.id + '" data-ep-src="' + ep.src +
          '" title="Borrar descarga"><svg class="ic"><use href="#i-x"/></svg></button></div>';
        list.appendChild(row);
      });
      var usage = document.getElementById("storage-usage");
      if (usage && navigator.storage && navigator.storage.estimate)
        navigator.storage.estimate().then(function (q) {
          var mb = Math.round((q.usage || 0) / 1048576);
          usage.textContent = "Almacenamiento usado: ~" + mb + " MB";
        });
    }
  }

  // ---- Atajos de teclado (estilo miniflux / ReactFlux) ----
  var sel = -1;
  function items() { return Array.prototype.slice.call(document.querySelectorAll("#article-items .item")); }
  function setSel(i) {
    var list = items();
    if (!list.length) return;
    sel = Math.max(0, Math.min(i, list.length - 1));
    list.forEach(function (el, idx) { el.classList.toggle("kb-active", idx === sel); });
    list[sel].scrollIntoView({ block: "nearest" });
  }
  function current() { var l = items(); return sel >= 0 ? l[sel] : null; }

  function initKeys() {
    document.addEventListener("keydown", function (e) {
      var t = e.target;
      if (t && (/^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName) || t.isContentEditable)) return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      var el = current();
      switch (e.key) {
        case "j": setSel(sel + 1); break;
        case "k": setSel(sel <= 0 ? 0 : sel - 1); break;
        case "o": case "Enter": if (el) el.click(); break;
        case "m": if (el) { post("/articles/" + el.dataset.pk + "/seen/"); el.classList.add("is-read"); } break;
        case "s": if (el) post("/articles/" + el.dataset.pk + "/save/"); break;
        case "r": { var rb = document.querySelector('.toolbar form[action$="/refresh/"] button'); if (rb) rb.click(); } break;
        case "/": { var s = document.querySelector(".sb-search input"); if (s) { e.preventDefault(); s.focus(); } } break;
        case "?": toggleHelp(); break;
        case "Escape": hideHelp(); break;
        default: return;
      }
    });
  }

  function toggleHelp() { var h = document.getElementById("kb-help"); if (h) h.classList.toggle("show"); }
  function hideHelp() { var h = document.getElementById("kb-help"); if (h) h.classList.remove("show"); }

  // ---- Auto-marcar como leído al pasar el scroll ----
  var io = null;
  function observeAutomark() {
    var box = document.getElementById("article-items");
    if (!box || !box.dataset.automark) return;
    if (!io) {
      io = new IntersectionObserver(function (entries) {
        entries.forEach(function (en) {
          if (!en.isIntersecting && en.boundingClientRect.top < en.rootBounds.top && !en.target.dataset.seen) {
            en.target.dataset.seen = "1";
            en.target.classList.add("is-read");
            post("/articles/" + en.target.dataset.pk + "/seen/");
            io.unobserve(en.target);
          }
        });
      }, { root: box, threshold: 0 });
    }
    items().forEach(function (el) { if (!el.dataset.seen) io.observe(el); });
  }

  // ---- Columnas redimensionables ----
  function clamp(v, a, b) { return Math.max(a, Math.min(b, v)); }
  function initResizers() {
    var root = document.documentElement;
    document.querySelectorAll("[data-resize]").forEach(function (h) {
      h.addEventListener("pointerdown", function (e) {
        e.preventDefault();
        var kind = h.dataset.resize, startX = e.clientX;
        var cs = getComputedStyle(root);
        var startSidebar = parseInt(cs.getPropertyValue("--sidebar-w")) || 256;
        var startList = parseInt(cs.getPropertyValue("--list-w")) || 420;
        function move(ev) {
          var dx = ev.clientX - startX;
          if (kind === "sidebar") {
            var w = clamp(startSidebar + dx, 180, 460);
            root.style.setProperty("--sidebar-w", w + "px"); localStorage.setItem("nn_sidebar_w", w);
          } else {
            var w2 = clamp(startList + dx, 280, 680);
            root.style.setProperty("--list-w", w2 + "px"); localStorage.setItem("nn_list_w", w2);
          }
        }
        function up() {
          document.removeEventListener("pointermove", move);
          document.removeEventListener("pointerup", up);
          document.body.classList.remove("resizing");
        }
        document.body.classList.add("resizing");
        document.addEventListener("pointermove", move);
        document.addEventListener("pointerup", up);
      });
    });
  }

  // ---- Controles de tipografía inline (A− / A+ / serif) ----
  function savePref(key, value) {
    var fd = new FormData(); fd.append("key", key); fd.append("value", value);
    fetch("/articles/pref/", { method: "POST", headers: { "X-CSRFToken": getCookie("csrftoken") }, body: fd });
  }
  function initTypeControls() {
    var sizes = ["s", "m", "l"];
    document.body.addEventListener("click", function (e) {
      var b = e.target.closest("[data-type]"); if (!b) return;
      var body = document.body, act = b.dataset.type;
      if (act === "serif") {
        var f = body.dataset.font === "serif" ? "sans" : "serif";
        body.dataset.font = f; savePref("read_font", f);
      } else {
        var cur = sizes.indexOf(body.dataset.size || "m");
        cur = act === "size+" ? Math.min(2, cur + 1) : Math.max(0, cur - 1);
        body.dataset.size = sizes[cur]; savePref("read_size", sizes[cur]);
      }
    });
  }

  // ---- Gestos táctiles: deslizar un ítem → derecha = leído, izquierda = guardar ----
  function initTouch() {
    var box = document.getElementById("article-items");
    if (!box) return;
    var startX = 0, startY = 0, target = null;
    box.addEventListener("touchstart", function (e) {
      target = e.target.closest(".item");
      if (!target) return;
      startX = e.touches[0].clientX; startY = e.touches[0].clientY;
    }, { passive: true });
    box.addEventListener("touchend", function (e) {
      if (!target) return;
      var dx = e.changedTouches[0].clientX - startX;
      var dy = e.changedTouches[0].clientY - startY;
      if (Math.abs(dx) > 70 && Math.abs(dx) > Math.abs(dy) * 1.5) {
        if (dx > 0) { post("/articles/" + target.dataset.pk + "/seen/"); target.classList.add("is-read"); }
        else { post("/articles/" + target.dataset.pk + "/save/"); target.classList.add("swiped"); }
      }
      target = null;
    }, { passive: true });
  }

  // ---- Web Push (suscripción) ----
  function urlB64ToUint8(base64) {
    var pad = "=".repeat((4 - (base64.length % 4)) % 4);
    var b64 = (base64 + pad).replace(/-/g, "+").replace(/_/g, "/");
    var raw = atob(b64), out = new Uint8Array(raw.length);
    for (var i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
    return out;
  }
  async function subscribePush(statusEl) {
    function say(m) { if (statusEl) statusEl.textContent = m; }
    if (!("serviceWorker" in navigator) || !("PushManager" in window)) return say("Tu navegador no soporta push.");
    var info = await (await fetch("/notifications/push/key/", { credentials: "same-origin" })).json();
    if (!info.enabled) return say("Push no disponible (falta configuración VAPID).");
    if ((await Notification.requestPermission()) !== "granted") return say("Permiso denegado.");
    var reg = await navigator.serviceWorker.register("/sw.js");
    var sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: urlB64ToUint8(info.key) });
    await fetch("/notifications/push/subscribe/", {
      method: "POST", credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-CSRFToken": getCookie("csrftoken") },
      body: JSON.stringify(sub),
    });
    say("Notificaciones activadas en este dispositivo.");
  }
  function initPush() {
    var btn = document.querySelector("[data-push-subscribe]");
    if (btn) btn.addEventListener("click", function () { subscribePush(document.getElementById("push-status")); });
  }

  // ---- PWA: registra el service worker (offline + base para push) ----
  function initPWA() {
    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.register("/sw.js").catch(function () {});
    }
  }

  // Sliders con valor visible (p.ej. umbral de agrupación).
  function initRangeOutputs() {
    document.querySelectorAll("input[type=range][data-output]").forEach(function (r) {
      var out = document.getElementById(r.getAttribute("data-output"));
      if (!out) return;
      function upd() { out.textContent = r.value; }
      r.addEventListener("input", upd);
      upd();
    });
  }

  // Subpestañas (p.ej. Ajustes → Actualización: RSS / IA / Audio).
  function initSubtabs() {
    var tabs = document.querySelectorAll("[data-subtab]");
    if (!tabs.length) return;
    tabs.forEach(function (t) {
      t.addEventListener("click", function () {
        var key = t.getAttribute("data-subtab");
        tabs.forEach(function (x) { x.classList.toggle("active", x === t); });
        document.querySelectorAll("[data-subpane]").forEach(function (p) {
          p.hidden = p.getAttribute("data-subpane") !== key;
        });
      });
    });
  }

  // Filtro rápido de tablas de feeds por nombre (gestor de feeds).
  function initFeedFilter() {
    document.querySelectorAll("[data-filter]").forEach(function (input) {
      if (input.dataset.fbound) return; input.dataset.fbound = "1";
      var key = input.getAttribute("data-filter");
      var scope = document.querySelector("[data-filter-table='" + key + "'], [data-filter-scope='" + key + "']");
      if (!scope) return;
      // Tablas: filtra filas; cualquier otro contenedor: filtra hijos con data-name.
      var sel = scope.tagName === "TABLE" ? "tbody tr[data-name]" : "[data-name]";
      input.addEventListener("input", function () {
        var q = input.value.trim().toLowerCase();
        scope.querySelectorAll(sel).forEach(function (el) {
          el.hidden = q && el.getAttribute("data-name").indexOf(q) === -1;
        });
      });
    });
  }

  // Ajustes de transcripción: descargar el modelo de Whisper local.
  function initTranscribeDownload() {
    var btn = document.getElementById("dl-transcribe-model");
    if (!btn) return;
    var status = document.getElementById("dl-transcribe-status");
    btn.addEventListener("click", function () {
      var sec = document.querySelector("[data-ai-section='transcribe']");
      var sel = sec && sec.querySelector("select[name='transcribe_model']");
      var model = sel ? sel.value : "";
      if (!model) { if (status) status.textContent = "Elige un modelo primero."; return; }
      if (status) status.textContent = "Iniciando descarga…";
      var data = { transcribe_model: model };
      var url = sec.querySelector("[name='whisper_url']"); if (url) data.whisper_url = url.value;
      var prov = sec.querySelector("[name='transcribe_provider']"); if (prov) data.transcribe_provider = prov.value;
      postForm("/accounts/settings/transcribe/download/", data)
        .then(function (r) { return r.json(); })
        .then(function (d) {
          if (status) status.textContent = d.ok
            ? ("Descargando " + d.model + "… pulsa “Recuperar modelos” en unos minutos.")
            : (d.error || "Error");
        })
        .catch(function () { if (status) status.textContent = "Error de red."; });
    });
  }

  // Ajustes de IA: mostrar solo la conexión del proveedor seleccionado.
  function initAiProvider() {
    document.querySelectorAll("[data-ai-provider]").forEach(function (sel) {
      var kind = sel.getAttribute("data-ai-provider");
      function sync() {
        document.querySelectorAll("[data-conn='" + kind + "']").forEach(function (box) {
          box.hidden = box.getAttribute("data-provider") !== sel.value;
        });
      }
      sel.addEventListener("change", sync);
      sync();
    });
  }

  // Inits que tocan el contenido (#content / #reading-pane): se re-ejecutan tras un swap htmx.
  var PERSWAP = [initSubtabs, initFeedFilter, initTypeControls, initRangeOutputs, initAiProvider,
                 initTranscribeDownload];
  function runPerswap() {
    PERSWAP.forEach(function (fn) { try { fn(); } catch (err) { console.error("perswap:", err); } });
  }
  // Tras la navegación boosteada (#content) o cargar un artículo (#reading-pane), re-vincular.
  document.body.addEventListener("htmx:afterSwap", function (e) {
    if (e.target && e.target.id === "content") {
      runPerswap();
      try { observeAutomark(); } catch (err) {}
      try { if (window.nnMarkPlaying) window.nnMarkPlaying(); } catch (err) {}
      try { updateSidebarActive(); } catch (err) {}
      sel = -1;  // reinicia la navegación por teclado al cambiar de lista
    } else if (e.target && e.target.id === "reading-pane") {
      try { runPerswap(); } catch (err) {}
      try { if (window.nnMarkPlaying) window.nnMarkPlaying(); } catch (err) {}
    }
  });

  // Barra de progreso superior durante la navegación htmx.
  document.body.addEventListener("htmx:beforeRequest", function () {
    var p = document.getElementById("nn-progress"); if (p) p.classList.add("on");
  });
  document.body.addEventListener("htmx:afterRequest", function () {
    var p = document.getElementById("nn-progress"); if (p) p.classList.remove("on");
  });

  // Marca el enlace del sidebar que coincide con la URL actual.
  function updateSidebarActive() {
    var here = location.pathname + location.search;
    document.querySelectorAll(".sidebar a.sb-item").forEach(function (a) {
      a.classList.toggle("sb-active", (a.getAttribute("href") || "") === here);
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    // Una-vez (sidebar/reproductor/document, persistentes) + por-swap. Cada init aislado.
    [initGroups, initSections, initSidebarToggle, initTheme, initKeys, observeAutomark, initTouch,
     initResizers, initPush, initPWA, initPlayer, initPodcasts, initDownloads, initImageFallback,
     updateSidebarActive].concat(PERSWAP).forEach(function (fn) {
      try { fn(); } catch (err) { console.error("init error:", err); }
    });
    var h = document.querySelector("[data-help-close]");
    if (h) h.addEventListener("click", function (e) { if (e.target === h) hideHelp(); });
  });
})();
