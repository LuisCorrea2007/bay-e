/* BAY-E Chat First v2 — chat is the primary control surface. */
(() => {
  const $ = (s, r=document) => r.querySelector(s);

  function inject() {
    const head = $(".chat-head");
    if (head && !$("#chat-v2-toolbar")) {
      const bar = document.createElement("div");
      bar.id = "chat-v2-toolbar";
      bar.className = "chat-v2-toolbar";
      bar.innerHTML = `
        <div class="chat-v2-status live" id="chat-v2-status"><i></i><span>BAY-E conectado</span></div>
        <div class="chat-v2-provider">cerebro: <strong id="chat-v2-provider">conectando…</strong></div>
        <div class="chat-v2-hint">/ para escribir</div>`;
      head.parentNode.insertBefore(bar, head.nextSibling);
    }

    const composer = $(".chat-composer");
    if (composer && !$("#chat-v2-shortcuts")) {
      const dock = document.createElement("div");
      dock.id = "chat-v2-shortcuts";
      dock.className = "chat-v2-shortcuts";
      const commands = [
        ["¿Qué ves?", "¿Qué ves ahora?"],
        ["Memoria", "abre memoria"],
        ["Cómo te sientes", "¿Cómo te sientes?"],
        ["Tareas", "abre mis tareas"],
        ["Explorar", "explora la casa"],
        ["Detente", "detente"],
        ["Sistema", "estado del sistema"],
      ];
      dock.innerHTML = commands.map(([label,cmd]) =>
        `<button class="chat-chip" data-chat-command="${cmd.replace(/"/g,'&quot;')}">${label}</button>`
      ).join("");
      document.body.appendChild(dock);
      dock.addEventListener("click", e => {
        const b = e.target.closest("[data-chat-command]");
        if (!b) return;
        App.go("chat");
        const input = $("#chat-input");
        input.value = b.dataset.chatCommand;
        Views.chat.submit();
      });
    }

    // Clicking the large face returns to chat.
    $("#face-mount-main")?.addEventListener("click", () => App.go("chat"));
  }

  function bind() {
    Net.on("model", m => {
      const p = $("#chat-v2-provider");
      if (p) p.textContent = m.model ? `${m.provider} · ${m.model}` : (m.provider || "fallback");
      if (m.ui_action) setTimeout(() => App.go(m.ui_action), 650);
    });
    Net.on("state", s => {
      const p = $("#chat-v2-provider");
      if (p && s.model_provider) p.textContent = s.model_provider;
      const st = $("#chat-v2-status");
      if (st) {
        st.classList.toggle("live", !!s.alive);
        const span = st.querySelector("span");
        if (span) span.textContent = s.hardware_connected ? "BAY-E + cuerpo conectados" : "BAY-E conectado";
      }
    });

    addEventListener("keydown", e => {
      if (e.key === "/" && !/INPUT|TEXTAREA|SELECT/.test(document.activeElement?.tagName || "")) {
        e.preventDefault();
        App.go("chat");
        $("#chat-input")?.focus();
      }
      if (e.key === "Escape" && document.body.dataset.view !== "chat") App.go("chat");
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    inject();
    bind();
  });
})();
