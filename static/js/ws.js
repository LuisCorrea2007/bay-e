/* ============================================================
   BAY-E · Cliente WebSocket con reconexión viva + helper REST.
   El estado global llega por WS; las acciones usan REST/WS indistinto.
   ============================================================ */

const Net = (() => {
  let sock = null, retry = 0, heartbeatTimer = null;
  const listeners = {}; // tipo -> [fn]

  function on(type, fn) { (listeners[type] ||= []).push(fn); return fn; }
  function fire(type, data) { (listeners[type] || []).forEach((f) => { try { f(data); } catch (e) { console.warn("ws listener", e); } }); }

  function connect() {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    sock = new WebSocket(`${proto}://${location.host}/ws`);

    sock.onopen = () => {
      retry = 0;
      setConn(true);
      fire("open", {});
      heartbeatTimer = setInterval(() => sock.readyState === 1 && sock.send(JSON.stringify({ type: "ping" })), 25000);
    };

    sock.onmessage = (ev) => {
      let msg; try { msg = JSON.parse(ev.data); } catch { return; }
      fire(msg.type || "_", msg);
      fire("*", msg);
    };

    sock.onclose = () => {
      clearInterval(heartbeatTimer);
      setConn(false);
      fire("close", {});
      // backoff exponial suave (máx 10 s) — la interfaz siempre reintenta
      const wait = Math.min(10000, 500 * 2 ** retry++);
      setTimeout(connect, wait);
    };

    sock.onerror = () => sock.close();
  }

  function send(obj) {
    if (sock && sock.readyState === 1) { sock.send(JSON.stringify(obj)); return true; }
    return false;
  }

  function command(cmd, payload) { return send({ type: "command", cmd, payload }); }
  function chat(text) { return send({ type: "chat", text }); }

  async function api(method, url, body) {
    const opt = { method, headers: { "Content-Type": "application/json" } };
    if (body !== undefined) opt.body = JSON.stringify(body);
    const r = await fetch(url, opt);
    if (!r.ok) throw new Error(`${method} ${url} → ${r.status}`);
    return r.json();
  }

  function setConn(on) {
    const dot = document.getElementById("rail-dot");
    const txt = document.getElementById("rail-conn");
    if (dot) dot.className = "dot " + (on ? "on" : "off");
    if (txt) txt.textContent = on ? "enlace vivo" : "reconectando…";
  }

  return { connect, on, send, command, chat, api };
})();
