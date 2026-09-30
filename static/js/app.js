/* ============================================================
   BAY-E · Controlador de aplicación: navegación, arranque, WS.
   ============================================================ */

const App = (() => {
  const V = Views;
  let faceMain = null, faceMini = null;
  const stateLabels = {}; // relleno desde el primer snapshot

  /* ---------- navegación entre vistas ---------- */
  function go(view) {
    document.body.dataset.view = view;
    $$(".rail-btn[data-nav]").forEach((b) => b.classList.toggle("is-active", b.dataset.nav === view));
    $$(".view").forEach((v) => v.classList.toggle("is-active", v.id === "view-" + view));
    document.body.classList.remove("rail-open");
    // cargas perezosas por vista
    if (view === "memory") V.memory.load();
    if (view === "tasks") V.tasks.load();
    if (view === "logs") V.logs.load();
    if (view === "settings") V.settings.render();
    if (view === "privacy") V.privacy.refresh(V.STATE);
    if (view === "mind" && V.STATE) V.mind.refresh(V.STATE);
    window.scrollTo({ top: 0 });
  }
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];

  /* ---------- arranque ---------- */
  async function boot() {
    Icons.hydrate(document);

    // dos caras vivas: protagonista (hero) y mini (móvil)
    faceMain = Face.create(document.getElementById("face-mount-main"), { size: 210 });
    faceMini = Face.create(document.getElementById("face-mount-mini"), { compact: true, size: 46 });

    // rail + menú móvil
    $$(".rail-btn[data-nav]").forEach((b) => b.addEventListener("click", () => go(b.dataset.nav)));
    document.getElementById("moburger").addEventListener("click", () => document.body.classList.toggle("rail-open"));
    document.getElementById("btn-private").addEventListener("click", () => Net.command("private_mode", {}));

    // montar todas las vistas una vez
    Object.values(V).forEach((v) => typeof v?.mount === "function" && v.mount());

    // estado inicial vía REST (por si el WS tarda)
    try {
      const s0 = await Net.api("GET", "/api/state");
      onState(s0);
    } catch (e) { console.warn("estado inicial REST no disponible", e); }

    // historial de chat persistente
    V.chat.loadHistory();

    // WebSocket vivo
    Net.on("state", onState);
    Net.on("open", async () => {
      try { V.heart.setHistory((await Net.api("GET", "/api/history")).history); } catch (e) { }
    });
    Net.connect();

    // atajos de teclado: números 1-9 cambian de vista con Alt
    addEventListener("keydown", (e) => {
      if (!e.altKey) return;
      const order = ["dashboard", "chat", "memory", "heart", "vision", "control", "mind", "tasks", "map"];
      const i = parseInt(e.key) - 1;
      if (i >= 0 && i < order.length) go(order[i]);
    });
  }

  /* ---------- receptor de snapshots ---------- */
  let first = true;
  function onState(s) {
    Object.assign(stateLabels, s.emotion_labels || {});
    V.applyState(s);
    if (first) { first = false; go("dashboard"); }
  }

  return { boot, go, get faceMain() { return faceMain; }, get faceMini() { return faceMini; }, stateLabels };
})();

document.addEventListener("DOMContentLoaded", App.boot);
