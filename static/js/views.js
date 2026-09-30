/* ============================================================
   BAY-E · Vistas de la interfaz.
   Cada vista exporta: mount() (una vez) y refresh(state?) (al recibir WS).
   ============================================================ */

const Views = (() => {
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const fmtT = (ts) => new Date(ts * 1000).toLocaleTimeString("es", { hour: "2-digit", minute: "2-digit" });
  const fmtD = (ts) => new Date(ts * 1000).toLocaleDateString("es", { day: "2-digit", month: "short", year: "numeric" });
  const fmtDT = (ts) => `${fmtD(ts)} ${fmtT(ts)}`;
  let STATE = null; // último snapshot global

  const MEM_TYPES = [
    { id: "", name: "Todas", icon: "brain" },
    { id: "episodic", name: "Episódica", icon: "clock" },
    { id: "semantic", name: "Semántica", icon: "bulb" },
    { id: "person", name: "Personas", icon: "users" },
    { id: "object", name: "Objetos", icon: "box" },
    { id: "spatial", name: "Espacial", icon: "map" },
    { id: "routine", name: "Rutinas", icon: "refresh" },
  ];

  const MOOD_WORD = { happy: "Estoy contento de verte.", excited: "¡Me emociona tenerte aquí!", curious: "Tengo curiosidad por ti.", neutral_face: "Tranquilo y presente.", worried: "Algo me preocupa…", bored: "Un poco aburrido, ¿jugamos?", attentive: "Te escucho con atención.", thinking: "Pensando en algo bonito…", sleepy: "Zzz… durmiendo a medias." };
  const EMO_EMOJI = { happy: "😊", excited: "🤩", curious: "👀", neutral_face: "🙂", worried: "😟", bored: "😮‍💨", attentive: "👂", thinking: "💭", sleepy: "😴" };

  /* ═══════════════════════ MODAL genérico ═══════════════════════ */
  function modal(title, bodyHTML, footHTML = "") {
    $("#modal-title").textContent = title;
    $("#modal-body").innerHTML = bodyHTML;
    $("#modal-foot").innerHTML = footHTML;
    $("#modal-back").hidden = false;
    Icons.hydrate($("#modal"));
    return { close: () => ($("#modal-back").hidden = true), body: $("#modal-body"), foot: $("#modal-foot") };
  }
  $("#modal-x").addEventListener("click", () => ($("#modal-back").hidden = true));
  $("#modal-back").addEventListener("click", (e) => { if (e.target.id === "modal-back") e.target.hidden = true; });

  /* ═══════════════════════ TOASTS ═══════════════════════ */
  function toast(msg, err = false) {
    const t = document.createElement("div");
    t.className = "toast" + (err ? " err" : "");
    t.innerHTML = `${Icons.svg(err ? "alert" : "check")}<span>${esc(msg)}</span>`;
    $("#toasts").appendChild(t);
    setTimeout(() => { t.classList.add("out"); setTimeout(() => t.remove(), 350); }, 3200);
  }

  /* ═══════════════════════ DASHBOARD ═══════════════════════ */
  const dashboard = {
    mounted: false,
    mount() { this.mounted = true; },
    refresh(s) {
      if (!s) return;
      $("#d-activity").textContent = s.activity;
      $("#d-mode").textContent = s.mode_label;
      $("#d-emotion").textContent = s.expression.emotion.replace("_", " ");
      const room = (s.rooms.find((r) => r.id === s.position.room) || {}).name || "—";
      $("#d-room").textContent = room;
      $("#d-thought").textContent = s.last_thought;
      $("#d-decision").textContent = s.next_decision;
      $("#d-reason").textContent = s.reason;
      $("#d-memory").textContent = s.last_memory || "aún no hay recuerdos nuevos";
      $("#d-event").textContent = s.last_event;
      $("#d-learning").textContent = s.learning;
      $("#d-doubt-row").hidden = !s.doubt;
      if (s.doubt) $("#d-doubt").textContent = s.doubt;
      $("#hero-context").textContent = s.context;
      $("#hero-mood-word").textContent = MOOD_WORD[s.expression.emotion] || MOOD_WORD.neutral_face;
      // mini-barras emocionales
      const keys = ["energy", "curiosity", "mood", "attention"];
      $("#d-emobars").innerHTML = keys.map((k) => `
        <div class="mbar"><span>${s.emotion_labels[k]}</span>
          <div class="track"><div class="fill" style="width:${(s.emotions[k] * 100) | 0}%"></div></div>
          <b>${(s.emotions[k] * 100) | 0}%</b></div>`).join("");
    },
  };

  /* ═══════════════════════ CHAT ═══════════════════════ */
  const chat = {
    pending: {}, // id -> nodo parcial
    mounted: false,
    mount() {
      if (this.mounted) return; this.mounted = true;
      $("#chat-send").addEventListener("click", () => this.submit());
      $("#chat-input").addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); this.submit(); } });
      $("#qc-send").addEventListener("click", () => this.quick());
      $("#qc-text").addEventListener("keydown", (e) => { if (e.key === "Enter") this.quick(); });
      $("#chat-mic").addEventListener("click", () => this.mic());
      Net.on("chat", (m) => this.renderMsg(m.message, m.final));
      Net.on("chat_partial", (m) => this.partial(m));
      Net.on("indicator", (m) => this.indicator(m.value));
    },
    async loadHistory() {
      const { messages } = await Net.api("GET", "/api/chat/history?limit=120");
      $("#chat-scroll").innerHTML = "";
      messages.forEach((m) => this.renderMsg(m, true));
      this.scroll();
    },
    submit() {
      const v = $("#chat-input").value.trim();
      if (!v) return;
      $("#chat-input").value = "";
      if (!Net.chat(v)) this.restFallback(v);
      this.indicator("listening");
    },
    quick() {
      const v = $("#qc-text").value.trim();
      if (!v) return;
      $("#qc-text").value = "";
      App.go("chat");
      setTimeout(() => { $("#chat-input").value = v; chat.submit(); }, 350);
    },
    async restFallback(text) {
      try {
        const r = await Net.api("POST", "/api/chat/send", { text });
        this.renderMsg(r.user, true); this.renderMsg(r.baye, true); this.scroll();
      } catch (e) { toast("sin conexión con BAY-E", true); }
    },
    partial(m) {
      let node = this.pending[m.id];
      if (!node) {
        node = this.buildNode({ id: m.id, role: "baye", content: "" }, false);
        this.pending[m.id] = node;
      }
      $(".bubble", node).textContent = m.content;
      this.scroll();
    },
    renderMsg(msg, final) {
      if (final && this.pending[msg.id]) {
        $(".bubble", this.pending[msg.id]).textContent = msg.content;
        delete this.pending[msg.id];
        return;
      }
      if (this.pending[msg.id]) return;
      this.buildNode(msg, true);
      this.scroll();
    },
    buildNode(msg, withTools) {
      const el = document.createElement("div");
      el.className = `msg ${msg.role === "user" ? "user" : "baye"} ${msg.fixed ? "fixed" : ""}`;
      el.dataset.id = msg.id;
      const tools = msg.role === "baye" && withTools ? `
        <div class="msg-tools">
          <button class="mt" data-a="remember">${Icons.svg("pin")}recordar</button>
          <button class="mt" data-a="forget">${Icons.svg("x")}olvidar</button>
          <button class="mt" data-a="pin">${Icons.svg("pin")}fijar</button>
          <button class="mt" data-a="repeat">${Icons.svg("refresh")}repetir</button>
          <button class="mt" data-a="task">${Icons.svg("list")}→ tarea</button>
          <button class="mt" data-a="memory">${Icons.svg("brain")}→ memoria</button>
        </div>` : "";
      el.innerHTML = `<div class="bubble">${esc(msg.content)}</div>${tools}`;
      $("#chat-scroll").appendChild(el);
      if (withTools) {
        $$(".mt", el).forEach((b) => b.addEventListener("click", () => this.toolAction(b.dataset.a, msg)));
      }
      return el;
    },
    async toolAction(a, msg) {
      if (a === "repeat") { this.speakOut(msg.content); toast("Repitiendo en voz alta…"); return; }
      try {
        const r = await Net.api("POST", "/api/chat/flag", { id: msg.id, action: a });
        if (a === "pin") { toast(r.fixed ? "Mensaje fijado 📌" : "Desfijado"); $(`[data-id="${msg.id}"]`)?.classList.toggle("fixed", r.fixed); }
        if (a === "remember" || a === "memory") toast("Guardado en la memoria de BAY-E 🧠");
        if (a === "forget") { toast("Olvidado"); }
        if (a === "task") { toast("Convertido en tarea ✅"); tasks.load(); }
      } catch (e) { toast("no se pudo aplicar", true); }
    },
    speakOut(text) {
      if (!("speechSynthesis" in window)) return;
      const u = new SpeechSynthesisUtterance(text);
      u.lang = "es-ES"; u.rate = .98; u.pitch = 1.15;
      speechSynthesis.cancel(); speechSynthesis.speak(u);
    },
    indicator(v) {
      $$(".ci").forEach((el) => el.classList.toggle("on", el.dataset.ci === v));
      const map = { listening: "Escuchando…", thinking: "Pensando…", speaking: "Hablando…" };
      const banner = $("#act-banner");
      if (v && map[v]) { $("#act-banner-txt").textContent = map[v]; banner.classList.add("show"); }
      else banner.classList.remove("show");
    },
    mic() {
      const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!SR) { toast("Tu navegador no soporta dictado por voz", true); return; }
      const rec = new SR(); rec.lang = "es-ES"; rec.interimResults = false;
      $("#chat-mic").classList.add("rec"); $("#hearing").hidden = false;
      rec.onresult = (e) => { $("#chat-input").value = e.results[0][0].transcript; this.submit(); };
      rec.onerror = () => { toast("no te escuché bien, intenta otra vez", true); };
      rec.onend = () => { $("#chat-mic").classList.remove("rec"); $("#hearing").hidden = true; };
      rec.start();
    },
    scroll() { const sc = $("#chat-scroll"); sc.scrollTop = sc.scrollHeight; },
  };

  /* ═══════════════════════ MEMORIA ═══════════════════════ */
  const memory = {
    filter: { q: "", type: "", tag: "", archived: false },
    cache: [],
    merging: null, // id origen cuando fusionamos
    mounted: false,
    mount() {
      if (this.mounted) return; this.mounted = true;
      $("#mem-types").innerHTML = MEM_TYPES.map((t, i) =>
        `<div class="mtype ${i === 0 ? "on" : ""}" data-t="${t.id}">${Icons.svg(t.icon)}<span>${t.name}</span><span class="cnt" data-cnt="${t.id}">0</span></div>`).join("");
      $$(".mtype").forEach((el) => el.addEventListener("click", () => {
        $$(".mtype").forEach((x) => x.classList.remove("on")); el.classList.add("on");
        this.filter.type = el.dataset.t; this.load();
      }));
      $("#mem-q").addEventListener("input", (e) => { this.filter.q = e.target.value; clearTimeout(this._t); this._t = setTimeout(() => this.load(), 250); });
      $("#mem-tag").addEventListener("change", (e) => { this.filter.tag = e.target.value; this.load(); });
      $("#mem-show-archived").addEventListener("change", (e) => { this.filter.archived = e.target.checked; this.load(); });
      $("#mem-new").addEventListener("click", () => this.form(null));
      $("#mem-import").addEventListener("change", (e) => this.importFile(e.target.files[0]));
      $("#merge-cancel").addEventListener("click", () => { this.merging = null; $("#merge-bar").hidden = true; this.load(); });
    },
    async load() {
      const f = this.filter;
      const { memories } = await Net.api("GET", `/api/memories?q=${encodeURIComponent(f.q)}&type=${f.type}&tag=${f.tag}&archived=${f.archived}`);
      this.cache = memories;
      // contadores por tipo
      for (const t of MEM_TYPES) {
        const cnt = memories.filter((m) => !t.id || m.type === t.id).length;
        const el = $(`[data-cnt="${t.id}"]`); if (el) el.textContent = cnt;
      }
      // etiquetas dinámicas
      const tags = [...new Set(memories.flatMap((m) => m.tags))].slice(0, 24);
      $("#mem-tag").innerHTML = `<option value="">Etiqueta: todas</option>` + tags.map((t) => `<option ${t === this.filter.tag ? "selected" : ""}>${esc(t)}</option>`).join("");
      this.render();
    },
    render() {
      const list = $("#mem-list");
      if (!this.cache.length) { list.innerHTML = `<p class="empty">BAY-E no encuentra memorias con ese criterio.</p>`; return; }
      list.innerHTML = this.cache.map((m) => `
        <div class="mem-card ${m.pinned ? "pinned" : ""} ${m.archived ? "archived" : ""} ${this.merging ? "merge-target" : ""}" data-id="${m.id}">
          <div class="mem-top">
            <span class="badge ${m.type}">${m.type}</span>
            <span class="mem-id">${m.id}</span>
            <span class="mem-conf"><div class="conf-track"><div class="conf-fill" style="width:${(m.confidence * 100) | 0}%"></div></div>${(m.confidence * 100) | 0}%</span>
          </div>
          <div class="mem-content">${m.pinned ? "📌 " : ""}${esc(m.content)}</div>
          ${m.detail ? `<div class="mem-detail">${esc(m.detail)}</div>` : ""}
          <div class="mem-meta">
            <span>creada ${fmtD(m.created_at)}</span><span>· actualizada ${fmtDT(m.updated_at)}</span>
            <span>· fuente: ${esc(m.source)}</span><span>· usada ${fmtDT(m.last_used)}</span>
          </div>
          ${m.tags.length ? `<div class="mem-tags">${m.tags.map((t) => `<span class="tag">#${esc(t)}</span>`).join("")}</div>` : ""}
          <div class="mem-btns">
            <button class="btn sm btn-ghost" data-a="detail">${Icons.svg("eye")}detalle</button>
            <button class="btn sm btn-ghost" data-a="edit">${Icons.svg("edit")}editar</button>
            <button class="btn sm btn-ghost" data-a="correct">${Icons.svg("check")}corregir</button>
            <button class="btn sm btn-ghost" data-a="pin">${Icons.svg("pin")}${m.pinned ? "desfijar" : "fijar"}</button>
            <button class="btn sm btn-ghost" data-a="archive">${Icons.svg("archive")}${m.archived ? "reactivar" : "archivar"}</button>
            <button class="btn sm btn-ghost" data-a="merge">${Icons.svg("merge")}fusionar</button>
            <button class="btn sm danger" data-a="del">${Icons.svg("trash")}borrar</button>
          </div>
        </div>`).join("");
      $$(".mem-card").forEach((card) => {
        const m = this.cache.find((x) => x.id === card.dataset.id);
        $$(".tag", card).forEach((tg) => tg.addEventListener("click", () => { this.filter.tag = tg.textContent.slice(1); $("#mem-tag").value = this.filter.tag; this.load(); }));
        $$("[data-a]", card).forEach((b) => b.addEventListener("click", () => this.action(b.dataset.a, m, card)));
      });
    },
    async action(a, m, card) {
      if (this.merging && a !== "merge") { /* durante fusión solo se elige destino */ }
      switch (a) {
        case "detail": {
          const rel = m.relations.map((r) => (this.cache.find((x) => x.id === r) || {}).content || r);
          modal(`Memoria ${m.id}`, `
            <div class="kv"><label>ID</label><b class="mono">${m.id}</b></div>
            <div class="kv"><label>Tipo</label><b>${m.type}</b></div>
            <div class="kv"><label>Contenido</label><b>${esc(m.content)}</b></div>
            <div class="kv"><label>Detalle</label><b>${esc(m.detail || "—")}</b></div>
            <div class="kv"><label>Creada</label><b>${fmtDT(m.created_at)}</b></div>
            <div class="kv"><label>Actualizada</label><b>${fmtDT(m.updated_at)}</b></div>
            <div class="kv"><label>Último uso</label><b>${fmtDT(m.last_used)} (${m.use_count}×)</b></div>
            <div class="kv"><label>Fuente</label><b>${esc(m.source)}</b></div>
            <div class="kv"><label>Confianza</label><b>${(m.confidence * 100) | 0}%</b></div>
            <div class="kv"><label>Etiquetas</label><b>${m.tags.map((t) => "#" + esc(t)).join(" ") || "—"}</b></div>
            <div class="kv"><label>Relaciones</label><b>${rel.map(esc).join(" · ") || "—"}</b></div>`);
          break;
        }
        case "edit": this.form(m); break;
        case "correct": {
          const val = prompt("Corrige esta memoria:", m.content);
          if (val && val !== m.content) { await Net.api("POST", `/api/memories/${m.id}/correct`, { content: val }); toast("Corregida ✓ confianza reforzada"); this.load(); }
          break;
        }
        case "pin": await Net.api("POST", `/api/memories/${m.id}/pin`, { on: !m.pinned }); this.load(); break;
        case "archive": await Net.api("POST", `/api/memories/${m.id}/archive`, { on: !m.archived }); this.load(); break;
        case "merge":
          if (!this.merging) {
            this.merging = m.id; $("#merge-src-t").textContent = m.content.slice(0, 40);
            $("#merge-bar").hidden = false; toast("Ahora haz clic en «fusionar» de la memoria destino");
          } else {
            await Net.api("POST", "/api/memories/merge", { primary: this.merging, secondary: m.id });
            this.merging = null; $("#merge-bar").hidden = true; toast("Memorias fusionadas 🧬"); this.load();
          }
          break;
        case "del":
          if (confirm("¿Borrar esta memoria para siempre?")) { await Net.api("DELETE", `/api/memories/${m.id}`); toast("Memoria borrada"); this.load(); }
          break;
      }
    },
    form(m) {
      const isNew = !m;
      const md = modal(isNew ? "Nueva memoria" : `Editar ${m.id}`, `
        <label class="fld"><span>Tipo</span><select id="mf-type">${MEM_TYPES.slice(1).map((t) => `<option value="${t.id}" ${m?.type === t.id ? "selected" : ""}>${t.name}</option>`).join("")}</select></label>
        <label class="fld"><span>Contenido</span><textarea id="mf-content" rows="2">${esc(m?.content || "")}</textarea></label>
        <label class="fld"><span>Detalle</span><textarea id="mf-detail" rows="2">${esc(m?.detail || "")}</textarea></label>
        <div class="row2">
          <label class="fld"><span>Fuente</span><select id="mf-source">${["user", "vision", "audio", "chat", "system", "sensor", "learning"].map((s) => `<option ${m?.source === s ? "selected" : ""}>${s}</option>`).join("")}</select></label>
          <label class="fld"><span>Confianza (${((m?.confidence ?? .8) * 100) | 0}%)</span><input type="range" id="mf-conf" min="0" max="100" value="${((m?.confidence ?? .8) * 100) | 0}"></label>
        </div>
        <label class="fld"><span>Etiquetas (coma)</span><input id="mf-tags" value="${esc((m?.tags || []).join(", "))}"></label>
        <label class="switch"><input type="checkbox" id="mf-pin" ${m?.pinned ? "checked" : ""}><span></span>Fijar como prioritaria</label>`,
        `<button class="btn btn-ghost" id="mf-cancel">Cancelar</button><button class="btn btn-primary" id="mf-save">${isNew ? "Crear" : "Guardar"}</button>`);
      $("#mf-cancel").onclick = md.close;
      $("#mf-save").onclick = async () => {
        const body = {
          type: $("#mf-type").value, content: $("#mf-content").value.trim(), detail: $("#mf-detail").value.trim(),
          source: $("#mf-source").value, confidence: +$("#mf-conf").value / 100,
          tags: $("#mf-tags").value.split(",").map((t) => t.trim()).filter(Boolean), pinned: $("#mf-pin").checked,
        };
        if (!body.content) { toast("el contenido no puede estar vacío", true); return; }
        if (isNew) await Net.api("POST", "/api/memories", body);
        else await Net.api("PUT", `/api/memories/${m.id}`, body);
        md.close(); toast(isNew ? "Recuerdo creado 🧠" : "Memoria actualizada"); this.load();
      };
    },
    async importFile(file) {
      if (!file) return;
      const fd = new FormData(); fd.append("file", file);
      const r = await fetch("/api/memories/import", { method: "POST", body: fd });
      const j = await r.json();
      toast(`${j.imported} memorias importadas`); this.load();
    },
  };

  /* ═══════════════════════ CORAZÓN ═══════════════════════ */
  const heart = {
    chartOn: ["mood", "energy", "curiosity"],
    series: [],
    mounted: false,
    mount() {
      if (this.mounted) return; this.mounted = true;
      const keys = Object.keys(App.stateLabels || {});
      $("#gauges").innerHTML = (keys.length ? keys : ["energy", "curiosity", "boredom", "sociability", "attention", "trust", "worry", "fatigue", "mood", "activity"]).map((k) => `
        <div class="gauge" data-k="${k}"><label><span></span><b></b></label>
        <input type="range" min="0" max="100" value="50" data-key="${k}"></div>`).join("");
      $$("#gauges input").forEach((inp) => inp.addEventListener("input", () => {
        Net.command("adjust_emotion", { key: inp.dataset.key, value: +inp.value / 100 });
      }));
      $$("#emo-mode button").forEach((b) => b.addEventListener("click", () => {
        $$("#emo-mode button").forEach((x) => x.classList.remove("on")); b.classList.add("on");
        Net.command("set_emotion_mode", { mode: b.dataset.m });
      }));
      const colors = { mood: "#5eeaff", energy: "#45e0a0", curiosity: "#9b7bff", worry: "#ff6b81", boredom: "#61779a", fatigue: "#ff9d6b", sociability: "#ff7ac8", attention: "#ffc46b", trust: "#4d8dff", activity: "#7df0ff" };
      $("#chart-legend").innerHTML = Object.entries(colors).map(([k, c]) => `<span class="cl" data-k="${k}"><i style="background:${c}"></i>${App.stateLabels?.[k] || k}</span>`).join("");
      $$(".cl").forEach((el) => el.addEventListener("click", () => {
        const k = el.dataset.k;
        this.chartOn.includes(k) ? this.chartOn = this.chartOn.filter((x) => x !== k) : this.chartOn.push(k);
        el.classList.toggle("off"); this.drawChart();
      }));
      this.colors = colors;
    },
    refresh(s) {
      if (!s) return;
      $$(".gauge").forEach((g) => {
        const k = g.dataset.k, v = s.emotions[k] ?? 0;
        $("label span", g).textContent = s.emotion_labels[k] || k;
        $("label b", g).textContent = `${(v * 100) | 0}%`;
        const inp = $("input", g);
        if (document.activeElement !== inp) inp.value = v * 100;
        g.classList.toggle("manual-off", s.emotion_mode === "auto");
      });
      $("#hb-mood").textContent = (s.expression.emotion || "").replace("_", " ");
      $("#hb-emoji").textContent = EMO_EMOJI[s.expression.emotion] || "🙂";
      $("#hb-mood-sub").textContent = `ánimo ${(s.emotions.mood * 100) | 0}% · energía ${(s.emotions.energy * 100) | 0}% · modo ${s.emotion_mode}`;
      $("#emo-hint").style.opacity = s.emotion_mode === "manual" ? "1" : ".6";
      // serie histórica local (suavizada) para gráfica inmediata
      this.series.push({ ...s.emotions, ts: s.ts });
      if (this.series.length > 90) this.series.shift();
      this.drawChart();
    },
    setHistory(hist) {
      this.hist = hist;
      this.drawChart();
    },
    drawChart() {
      const cv = $("#emo-chart"); if (!cv) return;
      const dpr = devicePixelRatio || 1;
      const W = cv.clientWidth, H = 260;
      cv.width = W * dpr; cv.height = H * dpr;
      const ctx = cv.getContext("2d"); ctx.scale(dpr, dpr);
      ctx.clearRect(0, 0, W, H);
      // rejilla
      ctx.strokeStyle = "rgba(120,180,255,.1)"; ctx.lineWidth = 1;
      for (let i = 0; i <= 4; i++) { const y = (H - 24) * i / 4 + 8; ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke(); }
      const src = this.hist?.length > 12 ? this.hist : null;
      const data = src ? src.map((h) => h.data) : this.series;
      if (data.length < 2) return;
      for (const key of this.chartOn) {
        ctx.beginPath();
        ctx.strokeStyle = this.colors[key] || "#5eeaff"; ctx.lineWidth = 2;
        ctx.shadowColor = this.colors[key]; ctx.shadowBlur = 6;
        data.forEach((d, i) => {
          const x = W * i / (data.length - 1);
          const y = 8 + (H - 24) * (1 - (d[key] ?? 0));
          i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
        });
        ctx.stroke(); ctx.shadowBlur = 0;
      }
    },
  };

  /* ═══════════════════════ VISIÓN ═══════════════════════ */
  const vision = {
    dets: [],
    current: null,
    mounted: false,
    mount() {
      if (this.mounted) return; this.mounted = true;
      Net.on("detection", (m) => this.onDet(m.detection));
      $("#cam-toggle").addEventListener("click", () => {
        const on = !(STATE?.sensors?.camera); Net.command("sensor", { sensor: "camera", on });
      });
      $("#det-save").addEventListener("click", () => {
        if (!this.current) return toast("no hay detección activa", true);
        Net.api("POST", "/api/memories", { type: this.current.kind === "person" ? "person" : "object", content: `Visto: ${this.current.label} (${(this.current.confidence * 100) | 0}%)`, source: "vision", confidence: this.current.confidence, tags: ["visual", this.current.kind] })
          .then(() => toast("Guardado como memoria visual 📸"));
      });
      $("#det-star").addEventListener("click", () => {
        if (!this.current) return;
        Net.api("POST", "/api/memories", { type: "episodic", content: `Momento importante: ${this.current.label}`, source: "vision", confidence: .95, tags: ["importante"], pinned: true }).then(() => toast("Marcado como importante ⭐"));
      });
      $("#det-ignore").addEventListener("click", () => {
        this.dets = this.dets.filter((d) => d.id !== this.current?.id); this.current = null; this.render(); toast("Detección ignorada");
      });
    },
    onDet(d) {
      this.dets.unshift(d); if (this.dets.length > 30) this.dets.pop();
      this.current = d; this.render();
    },
    refresh(s) {
      STATE = s;
      const off = !s.sensors.camera || s.private_mode;
      $("#feed-off").hidden = !off;
      $("#feed-img").style.opacity = off ? ".15" : "1";
    },
    render() {
      const col = { person: "#ff7ac8", animal: "#45e0a0", object: "#5eeaff", motion: "#ffc46b", scene: "#9b7bff", sound: "#4d8dff" };
      const kindC = (k) => col[k] || "#5eeaff";
      // cajas sobre el feed
      $("#feed-boxes").innerHTML = this.dets.slice(0, 3).map((d) => `
        <div class="fbox ${d.kind}" style="left:${d.box.x * 100}%;top:${d.box.y * 100}%;width:${d.box.w * 100}%;height:${d.box.h * 100}%;border-color:${kindC(d.kind)}">
          <span style="background:${kindC(d.kind)}">${esc(d.label)} · ${(d.confidence * 100) | 0}%</span></div>`).join("");
      $("#det-list").innerHTML = this.dets.slice(0, 12).map((d, i) => `
        <div class="det" data-i="${i}" style="${d.id === this.current?.id ? "border-color:" + kindC(d.kind) : ""}">
          <span class="kind-dot" style="background:${kindC(d.kind)}"></span>
          <span>${esc(d.label)} <small style="color:var(--txt-faint)">(${d.kind})</small></span>
          <time>${fmtT(d.ts)}</time><span class="conf">${(d.confidence * 100) | 0}%</span>
        </div>`).join("") || `<p class="empty">BAY-E aún no ha visto nada…</p>`;
      $$(".det").forEach((el) => el.addEventListener("click", () => { this.current = this.dets[+el.dataset.i]; this.render(); }));
      // nube de etiquetas personas/objetos/animales
      const groups = { person: "Personas", object: "Objetos", animal: "Animales" };
      $("#tag-cloud").innerHTML = Object.entries(groups).map(([k, label]) => {
        const items = [...new Set(this.dets.filter((d) => d.kind === k).map((d) => d.label))];
        return items.length ? `<div style="margin-bottom:8px"><small style="color:var(--txt-faint);letter-spacing:.1em;text-transform:uppercase;font-size:10px">${label}</small><div class="mem-tags">${items.map((t) => `<span class="tag" style="border-color:${kindC(k)};color:${kindC(k)}">${esc(t)}</span>`).join("")}</div></div>` : "";
      }).join("") || `<p class="empty">sin reconocimientos todavía</p>`;
    },
  };

  /* ═══════════════════════ CONTROL ═══════════════════════ */
  const control = {
    modes: [
      { id: "idle", name: "Reposo activo", icon: "moon" }, { id: "conversation", name: "Conversación", icon: "chat" },
      { id: "explore", name: "Explorar", icon: "compass" }, { id: "follow", name: "Seguir", icon: "users" },
      { id: "patrol", name: "Patrullar", icon: "shield" }, { id: "observe", name: "Observar", icon: "eye" },
      { id: "rest", name: "Descansar", icon: "moon" }, { id: "charging", name: "Cargar", icon: "battery" },
    ],
    mounted: false,
    mount() {
      if (this.mounted) return; this.mounted = true;
      $("#mode-grid").innerHTML = this.modes.map((m) => `<button class="mode-btn" data-m="${m.id}">${Icons.svg(m.icon)}${m.name}</button>`).join("");
      $$(".mode-btn").forEach((b) => b.addEventListener("click", () => Net.command("set_mode", { mode: b.dataset.m })));
      $$(".db").forEach((b) => {
        const dir = b.dataset.dir;
        const press = (e) => { e.preventDefault(); b.classList.add("pressed"); Net.command("move", { dir }); };
        const rel = () => { b.classList.remove("pressed"); if (dir !== "stop") Net.command("move", { dir: "stop" }); };
        b.addEventListener("pointerdown", press); b.addEventListener("pointerup", rel); b.addEventListener("pointerleave", rel);
      });
      const sendLook = () => Net.command("look", { yaw: +$("#yaw").value / 100, pitch: +$("#pitch").value / 100 });
      $("#yaw").addEventListener("input", sendLook); $("#pitch").addEventListener("input", sendLook);
      $("#look-grid").addEventListener("pointermove", (e) => {
        if (e.buttons !== 1) return;
        const r = e.currentTarget.getBoundingClientRect();
        $("#yaw").value = ((e.clientX - r.left) / r.width * 2 - 1) * 100;
        $("#pitch").value = ((e.clientY - r.top) / r.height * 2 - 1) * 100;
        sendLook();
      });
      $("#sw-autonomy").addEventListener("change", (e) => Net.command("toggle_autonomy", { on: e.target.checked }));
      $("#btn-base").addEventListener("click", () => Net.command("return_base"));
      $("#goal-add").addEventListener("click", () => this.addGoal());
      $("#goal-in").addEventListener("keydown", (e) => e.key === "Enter" && this.addGoal());
    },
    addGoal() {
      const v = $("#goal-in").value.trim(); if (!v) return;
      Net.command("queue_goal", { label: v, room: STATE?.position?.room || "living" });
      $("#goal-in").value = "";
    },
    refresh(s) {
      $$(".mode-btn").forEach((b) => b.classList.toggle("on", b.dataset.m === s.mode));
      $("#sw-autonomy").checked = s.autonomy;
      $("#c-task").textContent = s.current_task || "ninguna";
      $("#c-next").textContent = s.next_decision;
      $("#c-reason").textContent = s.reason;
      const sec = $("#c-security");
      sec.textContent = s.security.status === "ok" ? "OK · " + s.security.detail : "⚠ " + s.security.detail;
      sec.className = s.security.status === "ok" ? "ok" : "alert";
      $("#goal-list").innerHTML = s.goal_queue.length
        ? s.goal_queue.map((g) => `<li>${Icons.svg("target")}${esc(g.label)}<span class="x" data-g="${g.id}">✕</span></li>`).join("")
        : `<li class="empty">Sin objetivos pendientes</li>`;
      $$("#goal-list .x").forEach((x) => x.addEventListener("click", () => Net.command("dequeue_goal", { id: x.dataset.g })));
      $("#look-dot").style.left = `${(+$("#yaw").value + 100) / 2}%`;
      $("#look-dot").style.top = `${(+$("#pitch").value + 100) / 2}%`;
    },
  };

  /* ═══════════════════════ MENTE ═══════════════════════ */
  const mind = {
    mounted: false,
    mount() { this.mounted = true; },
    refresh(s) {
      if (!$("#view-mind").classList.contains("is-active")) return;
      const items = [
        { ic: "target", cls: "", label: "Objetivo actual", text: s.current_task || s.next_decision },
        { ic: "compass", cls: "decide", label: "Motivo / razón", text: s.reason },
        { ic: "eye", cls: "", label: "Contexto percibido", text: s.context },
        { ic: "brain", cls: "memory", label: "Memoria relevante usada", text: s.memory_used || "Ninguna recientemente — estoy formando recuerdos nuevos." },
        { ic: "bulb", cls: "decide", label: "Siguiente decisión", text: s.next_decision },
        { ic: "sparkle", cls: "learn", label: "Aprendizaje reciente", text: s.learning },
      ];
      if (s.doubt) items.push({ ic: "help", cls: "doubt", label: "Confusión / duda", text: s.doubt });
      const html = items.map((i) => `<div class="mind-item ${i.cls}">${Icons.svg(i.ic)}<div><label>${i.label}</label><p>${esc(i.text)}</p></div></div>`).join("");
      if ($("#mind-stream").dataset.sig !== html) { $("#mind-stream").dataset.sig = html; $("#mind-stream").innerHTML = html; }
    },
  };

  /* ═══════════════════════ TAREAS ═══════════════════════ */
  const tasks = {
    mounted: false,
    mount() {
      if (this.mounted) return; this.mounted = true;
      $("#task-new").addEventListener("click", () => this.form(null));
    },
    async load() {
      const { tasks: list } = await Net.api("GET", "/api/tasks");
      this.list = list;
      $("#task-list").innerHTML = list.length ? list.map((t) => `
        <div class="task ${t.status === "done" ? "done" : ""}" data-id="${t.id}">
          <button class="t-check" data-a="toggle">${t.status === "done" ? Icons.svg("check") : ""}</button>
          <div class="t-main">
            <div class="t-title">${esc(t.title)}</div>
            ${t.description ? `<div class="t-desc">${esc(t.description)}</div>` : ""}
            <div class="t-meta">
              <span class="t-pill st">${t.status}</span>
              ${t.repeat ? `<span class="t-pill">🔁 ${t.repeat}</span>` : ""}
              ${t.room ? `<span class="t-pill">📍 ${esc(roomName(t.room))}</span>` : ""}
              ${t.scheduled_at ? `<span class="t-pill">⏰ ${fmtDT(t.scheduled_at)}</span>` : ""}
              ${t.done_log.length ? `<span class="t-pill">✅ ${t.done_log.length} cumplimientos · último ${t.done_log[t.done_log.length - 1]}</span>` : ""}
            </div>
          </div>
          <div class="t-btns">
            <button class="btn sm btn-ghost" data-a="pause">${t.status === "paused" ? "reanudar" : "pausar"}</button>
            <button class="btn sm btn-ghost" data-a="retry">reintentar</button>
            <button class="btn sm btn-ghost" data-a="edit">${Icons.svg("edit")}</button>
            <button class="btn sm danger" data-a="del">${Icons.svg("trash")}</button>
          </div>
        </div>`).join("") : `<p class="empty">Sin tareas. Crea la primera y BAY-E velará por ella.</p>`;
      $$(".task").forEach((el) => {
        const t = list.find((x) => x.id === el.dataset.id);
        $$("[data-a]", el).forEach((b) => b.addEventListener("click", () => this.action(b.dataset.a, t)));
      });
    },
    async action(a, t) {
      if (a === "toggle") await Net.api("PUT", `/api/tasks/${t.id}`, { status: t.status === "done" ? "pending" : "done" });
      if (a === "pause") await Net.api("PUT", `/api/tasks/${t.id}`, { status: t.status === "paused" ? "pending" : "paused" });
      if (a === "retry") await Net.api("PUT", `/api/tasks/${t.id}`, { status: "running" });
      if (a === "edit") return this.form(t);
      if (a === "del" && confirm("¿Borrar tarea?")) await Net.api("DELETE", `/api/tasks/${t.id}`);
      this.load();
    },
    form(t) {
      const isNew = !t;
      const md = modal(isNew ? "Nueva tarea / rutina" : "Editar tarea", `
        <label class="fld"><span>Título</span><input id="tf-title" value="${esc(t?.title || "")}"></label>
        <label class="fld"><span>Descripción</span><textarea id="tf-desc" rows="2">${esc(t?.description || "")}</textarea></label>
        <div class="row2">
          <label class="fld"><span>Habitación</span><select id="tf-room"><option value="">—</option>${(STATE?.rooms || []).map((r) => `<option value="${r.id}" ${t?.room === r.id ? "selected" : ""}>${r.name}</option>`).join("")}</select></label>
          <label class="fld"><span>Repetir</span><select id="tf-repeat">${["", "daily", "weekly", "weekdays", "hourly"].map((r) => `<option value="${r}" ${t?.repeat === r ? "selected" : ""}>${r || "una vez"}</option>`).join("")}</select></label>
        </div>
        <div class="row2">
          <label class="fld"><span>Día</span><input type="date" id="tf-date"></label>
          <label class="fld"><span>Hora</span><input type="time" id="tf-time" value="08:00"></label>
        </div>`,
        `<button class="btn btn-ghost" id="tf-cancel">Cancelar</button><button class="btn btn-primary" id="tf-save">${isNew ? "Crear" : "Guardar"}</button>`);
      $("#tf-cancel").onclick = md.close;
      $("#tf-save").onclick = async () => {
        const title = $("#tf-title").value.trim();
        if (!title) return toast("falta el título", true);
        const sched = ($("#tf-date").value && $("#tf-time").value) ? new Date($("#tf-date").value + "T" + $("#tf-time").value).getTime() / 1000 : (t?.scheduled_at || 0);
        const body = { title, description: $("#tf-desc").value.trim(), room: $("#tf-room").value, repeat: $("#tf-repeat").value, scheduled_at: sched };
        if (isNew) await Net.api("POST", "/api/tasks", body); else await Net.api("PUT", `/api/tasks/${t.id}`, body);
        md.close(); toast(isNew ? "Tarea creada ✅" : "Tarea actualizada"); this.load();
      };
    },
  };
  const roomName = (id) => (STATE?.rooms.find((r) => r.id === id) || {}).name || id;

  /* ═══════════════════════ MAPA ═══════════════════════ */
  const homeMap = {
    mounted: false, explored: new Set(["living", "hall"]),
    mount() { this.mounted = true; },
    refresh(s) {
      const svg = $("#map-svg");
      if (!svg.dataset.built) {
        svg.dataset.built = 1;
        const restricted = (s.settings?.privacy?.restricted_zones || []);
        svg.innerHTML = s.rooms.map((r) => `
          <rect class="room-rect" data-r="${r.id}" x="${r.x * 100}" y="${r.y * 100}" width="${r.w * 100}" height="${r.h * 100}" rx="2"/>
          <text class="room-label" x="${(r.x + r.w / 2) * 100}" y="${(r.y + r.h / 2) * 100}" text-anchor="middle">${r.name.toUpperCase()}</text>`).join("") +
          `<path class="base-icon" d="M${(0.8 * 100) - 3} ${(0.86 * 100)} l3 -6 l3 6 z"/><text class="room-label" x="80" y="95" text-anchor="middle">⚡ BASE</text>`;
      }
      const robot = $("#map-robot");
      robot.style.left = s.position.x * 100 + "%";
      robot.style.top = s.position.y * 100 + "%";
      this.explored.add(s.position.room);
      $$(".room-rect", svg).forEach((rc) => {
        rc.classList.toggle("explored", this.explored.has(rc.dataset.r));
        const rn = (s.rooms.find((r) => r.id === rc.dataset.r) || {}).name;
        rc.classList.toggle("favorite", rn === "Salón");
        rc.classList.toggle("restricted", restricted_has(s, rn));
      });
      $("#mp-room").textContent = roomName(s.position.room);
      $("#mp-zones").innerHTML = s.rooms.map((r) => `<span class="tag" style="${this.explored.has(r.id) ? "" : "opacity:.4"}">${r.name}</span>`).join("");
      const objs = memory.cache.filter((m) => m.type === "object").slice(0, 4).map((m) => m.content.split("—")[0]);
      $("#mp-objects").textContent = objs.join(" · ") || "registrando…";
    },
  };
  const restricted_has = (s, name) => (s.settings?.privacy?.restricted_zones || []).some((z) => name && name.includes(z));

  /* ═══════════════════════ MÓDULOS ═══════════════════════ */
  const modules = {
    mounted: false,
    mount() {
      if (this.mounted) return; this.mounted = true;
      $("#upd-check").addEventListener("click", async () => {
        const r = await Net.api("POST", "/api/updates/check", {});
        $("#upd-list").innerHTML = r.available.map((u) => `
          <div class="upd">${Icons.svg("sparkle")}<span>${esc(u.name)}</span><span class="kind">${u.kind}</span>
          <button class="btn sm btn-primary" data-n="${esc(u.name)}">instalar</button></div>`).join("");
        $$("#upd-list [data-n]").forEach((b) => b.addEventListener("click", async () => {
          await Net.api("POST", "/api/updates/install", { name: b.dataset.n });
          b.outerHTML = `<span style="color:var(--green);font-size:11px">instalado ✓</span>`; toast("Actualización aplicada");
        }));
      });
      $("#bk-create").addEventListener("click", async () => { await Net.api("POST", "/api/backups", {}); toast("Backup creado 💾"); this.loadBackups(); });
      $("#load-voice").addEventListener("click", () => toast("Voz «guardián» descargada e instalada 🎙️"));
      $("#load-model").addEventListener("click", () => toast("Modelo de visión v0.9.5 cargado 🧠"));
      $("#changelog").innerHTML = `
        <b>v1.0.0</b> · 30/09/2026 — Nacimiento de BAY-E: cara viva, memoria SQLite, WebSocket en tiempo real.<br>
        <b>v0.9.4</b> — Módulo de visión: detección de personas, animales y movimiento.<br>
        <b>v0.8.1</b> — Escucha STT preparada para Whisper local.<br>
        <b>v0.7.3</b> — Mapa del hogar y rutas base (puerto ROS 2 listo).`;
    },
    refresh(s) {
      $("#mod-version").textContent = "v" + (s.version || "1.0.0");
      $("#mod-list").innerHTML = s.modules.map((m) => `
        <div class="mod ${m.enabled ? "" : "off"}">
          <span class="mod-ic">${Icons.svg(m.icon)}</span>
          <div><b>${esc(m.name)} <span class="ver">${m.version}</span></b><small>${esc(m.desc)}</small></div>
          <label class="switch"><input type="checkbox" data-m="${m.id}" ${m.enabled ? "checked" : ""}><span></span></label>
        </div>`).join("");
      $$("#mod-list input").forEach((inp) => inp.addEventListener("change", async () => {
        await Net.api("POST", `/api/modules/${inp.dataset.m}/toggle`, { on: inp.checked });
        toast(`Módulo ${inp.checked ? "activado" : "desactivado"}`);
      }));
      this.loadBackups();
    },
    async loadBackups() {
      try {
        const { backups } = await Net.api("GET", "/api/backups");
        $("#bk-list").innerHTML = backups.length ? backups.map((b) => `
          <li>${Icons.svg("save")}<span>${b.name}</span><span style="color:var(--txt-faint)">${(b.size / 1024).toFixed(1)} KB</span>
          <button class="btn sm btn-ghost x" data-n="${b.name}">restore</button></li>`).join("") : `<li class="empty">sin backups aún</li>`;
        $$("#bk-list [data-n]").forEach((b) => b.addEventListener("click", async () => {
          await Net.api("POST", "/api/backups/restore", { name: b.dataset.n }); toast("Backup restaurado ↺");
        }));
      } catch (e) { /* silencioso */ }
    },
  };

  /* ═══════════════════════ AJUSTES ═══════════════════════ */
  const settings = {
    sections: [
      { id: "identity", name: "Identidad", icon: "sparkle" }, { id: "audio", name: "Audio y voz", icon: "voice" },
      { id: "vision", name: "Visión", icon: "eye" }, { id: "personality", name: "Personalidad", icon: "heart" },
      { id: "autonomy", name: "Autonomía", icon: "compass" }, { id: "security", name: "Seguridad", icon: "shield" },
      { id: "hardware", name: "Hardware / ROS 2", icon: "cpu" }, { id: "privacy", name: "Privacidad", icon: "key" },
    ],
    mounted: false, cur: "identity",
    mount() {
      if (this.mounted) return; this.mounted = true;
      $("#set-tabs").innerHTML = this.sections.map((s) => `<button class="set-tab" data-s="${s.id}">${Icons.svg(s.icon)}${s.name}</button>`).join("");
      $$(".set-tab").forEach((b) => b.addEventListener("click", () => { this.cur = b.dataset.s; this.paintTabs(); this.render(); }));
    },
    paintTabs() { $$(".set-tab").forEach((b) => b.classList.toggle("on", b.dataset.s === this.cur)); },
    refresh(s) { this.st = s.settings; if ($("#view-settings").classList.contains("is-active")) this.render(); },
    fields: {
      identity: [["name", "Nombre", "text"], ["species", "Especie", "text"], ["birthday", "Nacimiento", "text"], ["voice", "Voz", "select:cálida · suave,juguetona,serena,guardián,piloto"], ["language", "Idioma", "select:es,ca,en,fr"], ["personality", "Arquetipo", "select:baymax,walle,personalizado"]],
      audio: [["tts_enabled", "Voz activada", "bool"], ["wake_word", "Palabra de activación", "text"], ["volume", "Volumen (0-1)", "num"], ["rate", "Velocidad (0.5-2)", "num"]],
      vision: [["camera_enabled", "Cámara activada", "bool"], ["fps", "FPS", "num"], ["detect_people", "Detectar personas", "bool"], ["detect_animals", "Detectar animales", "bool"], ["save_captures", "Guardar capturas", "bool"]],
      personality: [["auto_emotions", "Emociones automáticas", "bool"], ["curiosity_level", "Curiosidad base", "num"], ["affection", "Cariño", "num"], ["humor", "Sentido del humor", "num"], ["handicap_speak", "Habla enternecedora", "bool"]],
      autonomy: [["enabled", "Autonomía general", "bool"], ["explore_when_bored", "Explorar si se aburre", "bool"], ["sleep_at_night", "Dormir de noche", "bool"], ["return_base_battery", "Umbral batería (%)", "num"]],
      security: [["max_speed", "Velocidad máxima (m/s)", "num"], ["stairs_allowed", "Permitir escaleras", "bool"], ["night_patrol", "Patrulla nocturna", "bool"], ["child_lock", "Bloqueo infantil", "bool"]],
      hardware: [["ros2_bridge", "Puente ROS 2", "bool"], ["ros_domain_id", "ROS_DOMAIN_ID", "num"], ["model_paths.llm", "Ruta modelo LLM", "text"], ["model_paths.vision", "Ruta modelo visión", "text"], ["model_paths.tts", "Ruta modelo TTS", "text"], ["model_paths.stt", "Ruta modelo STT", "text"]],
      privacy: [["private_mode", "Modo privado", "bool"], ["retention_days", "Retención (días)", "num"], ["restricted_zones", "Zonas restringidas (coma)", "list"], ["forbidden_objects", "Objetos prohibidos (coma)", "list"]],
    },
    render() {
      const st = this.st?.[this.cur] || {};
      const get = (path) => path.split(".").reduce((o, k) => o?.[k], st);
      $("#set-body").innerHTML = (this.fields[this.cur] || []).map(([k, label, type]) => {
        const v = get(k);
        if (type === "bool") return `<label class="switch" style="align-self:center"><input type="checkbox" data-k="${k}" ${v ? "checked" : ""}><span></span>${label}</label>`;
        if (type.startsWith("select")) { const opts = type.slice(7).split(","); return `<label class="fld ${["model_paths.llm"].includes(k) ? "set-field-wide" : ""}"><span>${label}</span><select data-k="${k}">${opts.map((o) => `<option ${String(v) === o ? "selected" : ""}>${o}</option>`).join("")}</select></label>`; }
        if (type === "list") return `<label class="fld set-field-wide"><span>${label}</span><input data-k="${k}" value="${esc((v || []).join(", "))}"></label>`;
        return `<label class="fld ${k.startsWith("model_paths") ? "set-field-wide" : ""}"><span>${label}</span><input type="${type === "num" ? "number" : "text"} step="any" data-k="${k}" value="${esc(v ?? "")}"></label>`;
      }).join("") + `<div class="set-field-wide"><button class="btn btn-primary" id="st-save">${Icons.svg("check")}Guardar sección</button></div>`;
      $("#st-save").onclick = async () => {
        const patch = {};
        $$("[data-k]", $("#set-body")).forEach((el) => {
          let val = el.type === "checkbox" ? el.checked : el.value;
          if (el.type === "number") val = parseFloat(val) || 0;
          if (el.tagName === "SELECT" && /^\d/.test(val)) val = parseInt(val);
          const parts = el.dataset.k.split(".");
          if (parts.length === 1) patch[parts[0]] = val;
          else { (patch[parts[0]] ||= {})[parts[1]] = val; }
        });
        await Net.api("PUT", `/api/settings/${this.cur}`, patch);
        toast("Configuración guardada ⚙️");
      };
    },
  };

  /* ═══════════════════════ PRIVACIDAD ═══════════════════════ */
  const privacy = {
    mounted: false,
    mount() {
      if (this.mounted) return; this.mounted = true;
      $$("[data-purge]").forEach((b) => b.addEventListener("click", () => this.purge(b.dataset.purge)));
      $("#pv-save").addEventListener("click", async () => {
        await Net.api("PUT", "/api/settings/privacy", {
          private_mode: $("#pv-private").checked,
          retention_days: +$("#pv-ret").value || 180,
          restricted_zones: $("#pv-zones").value.split(",").map((x) => x.trim()).filter(Boolean),
          forbidden_objects: $("#pv-forb").value.split(",").map((x) => x.trim()).filter(Boolean),
        });
        toast("Política de privacidad actualizada 🔒");
      });
      $("#pv-private").addEventListener("change", (e) => Net.command("private_mode", { on: e.target.checked }));
    },
    async purge(mode) {
      const msgs = { all: "¿BORRAR TODAS las memorias? Esta acción es irreversible.", type: "¿Borrar todas las memorias de este tipo?", person: "¿Borrar memorias asociadas a esa persona?", before: "¿Borrar memorias anteriores a la fecha?" };
      if (!confirm(msgs[mode])) return;
      const body = { mode };
      if (mode === "type") body.type = $("#pv-type").value;
      if (mode === "person") body.person = $("#pv-person").value;
      if (mode === "before") body.timestamp = new Date($("#pv-date").value).getTime() / 1000;
      const r = await Net.api("POST", "/api/privacy/purge", body);
      toast(`${r.deleted} memorias borradas`);
      memory.load(); this.loadSensitive();
    },
    refresh(s) {
      const p = s.settings.privacy;
      $("#pv-private").checked = p.private_mode;
      $("#pv-zones").value = (p.restricted_zones || []).join(", ");
      $("#pv-forb").value = (p.forbidden_objects || []).join(", ");
      $("#pv-ret").value = p.retention_days;
      // permisos por persona (derivados de memorias tipo person)
      const people = memory.cache.filter((m) => m.type === "person").map((m) => m.content.split("—")[0].trim());
      $("#perm-list").innerHTML = people.map((n, i) => `
        <div class="perm">${Icons.svg("users")}<span>${esc(n)}</span>
        <label class="switch"><input type="checkbox" ${i === 0 ? "checked" : ""}><span></span>confianza total</label></div>`).join("") || `<p class="empty">sin personas registradas</p>`;
      this.loadSensitive();
    },
    async loadSensitive() {
      try {
        const { logs } = await Net.api("GET", "/api/logs?sensitive=true&limit=40");
        $("#sens-list").innerHTML = logs.map((l) => `<div class="sens">${esc(l.human)}<time>${fmtDT(l.ts)} · ${esc(l.module)}</time></div>`).join("") || `<p class="empty">sin acciones sensibles registradas</p>`;
      } catch (e) { }
    },
  };

  /* ═══════════════════════ LOGS ═══════════════════════ */
  const logs = {
    mode: "human", mounted: false,
    mount() {
      if (this.mounted) return; this.mounted = true;
      $$("#log-seg button").forEach((b) => b.addEventListener("click", () => {
        $$("#log-seg button").forEach((x) => x.classList.remove("on")); b.classList.add("on");
        this.mode = b.dataset.l;
        $("#log-human").hidden = this.mode !== "human";
        $("#log-tech").hidden = this.mode !== "tech";
        this.load();
      }));
      $("#log-level").addEventListener("change", () => this.load());
    },
    async load() {
      const lv = $("#log-level").value;
      const { logs } = await Net.api("GET", `/api/logs?limit=200&level=${lv}`);
      this.last = logs;
      if (this.mode === "human") {
        $("#log-human").innerHTML = logs.map((l) => `
          <div class="lh ${l.level}"><time>${fmtDT(l.ts)}</time><span class="lv">${l.level}</span>
          <span class="mod">${l.module}</span><span>${esc(l.human)}</span></div>`).join("") || `<p class="empty">sin eventos</p>`;
      } else {
        $("#log-tech").innerHTML = logs.map((l) =>
          `<span class="ts">[${new Date(l.ts * 1000).toISOString()}]</span> <span class="${l.level === "error" ? "er" : l.level === "warn" ? "wr" : ""}">${l.level.toUpperCase().padEnd(9)}</span> ${l.module.padEnd(9)} :: ${esc(l.human)} ${l.technical ? "// " + esc(l.technical) : ""}`).join("\n");
      }
    },
  };

  /* ═══════════════════════ ESTADO GLOBAL → UI ═══════════════════════ */
  function applyState(s) {
    STATE = s;
    // hero / chips
    $("#chip-mode b").textContent = s.mode_label;
    $("#chip-batt").textContent = Math.round(s.battery) + "%";
    $(".chip-batt").classList.toggle("low", s.battery < 20);
    $(".chip-batt").classList.toggle("charging", s.charging);
    $("#chip-autonomy b").textContent = "autonomía " + (s.autonomy ? "on" : "off");
    $("#hero-activity").textContent = s.activity === "idle" ? s.mode_label.toLowerCase() : s.activity;
    $("#mobar-mode").textContent = s.mode_label;
    $("#btn-private").classList.toggle("on", s.private_mode);
    $$("#hero-sensors .sensor").forEach((el) => el.classList.toggle("live", !!s.sensors[el.dataset.k]));
    $$("#hero-sensors .sensor").forEach((el) => el.onclick = () => Net.command("sensor", { sensor: el.dataset.k, on: !s.sensors[el.dataset.k] }));
    // caras vivas
    Face.update(App.faceMain, s.expression);
    Face.update(App.faceMini, s.expression);
    // vistas
    dashboard.refresh(s); heart.refresh(s); vision.refresh(s); control.refresh(s);
    mind.refresh(s); homeMap.refresh(s); modules.refresh(s); settings.refresh(s); privacy.refresh(s);
    if ($("#view-memory").classList.contains("is-active")) memory.load();
  }

  return { get STATE() { return STATE; }, applyState, chat, memory, heart, vision, control, mind, tasks, homeMap, modules, settings, privacy, logs, dashboard, modal, toast, esc, fmtDT, fmtT, MEM_TYPES };
})();
