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

  document.addEventListener("DOMContentLoaded", function () {
    // Cada init aislado: que un fallo no impida el resto.
    [initGroups, initSections, initSidebarToggle, initTheme, initKeys, observeAutomark, initTouch,
     initResizers, initTypeControls, initPush, initPWA, initAiProvider, initRangeOutputs,
     initSubtabs].forEach(function (fn) {
      try { fn(); } catch (err) { console.error("init error:", err); }
    });
    var h = document.querySelector("[data-help-close]");
    if (h) h.addEventListener("click", function (e) { if (e.target === h) hideHelp(); });
  });
})();
