/* ============================================================
   BAY-E · CARA VIVA — motor de animación facial en tiempo real.
   SVG tipo "dos puntos + línea" (guiño a Baymax) con:
     · parpadeo natural aleatorio (y doble parpadeo ocasional)
     · respiración / micro-movimiento de presencia
     · deriva sutil de mirada + reacción al cursor
     · ondas al escuchar, partículas al pensar, boca al hablar
     · Zzz dormido, cejas/párpados/mouth por emoción
   API:  Face.create(mountEl, {compact}) ;  Face.update(exprObj)
   ============================================================ */

const Face = (() => {
  const EMO_COLORS = {
    happy: "#f5f5f5", excited: "#dfe7ff", curious: "#d5ccff", thinking: "#bfcaff",
    attentive: "#f5f5f5", worried: "#ffc1b0", bored: "#8d8d93", sleepy: "#777b88",
    neutral_face: "#eeeeef",
  };

  // ---------- plantilla SVG ----------
  function markup(id) {
    return `
    <svg viewBox="0 0 240 240" width="100%" height="100%" role="img" aria-label="Cara viva de BAY-E">
      <defs>
        <radialGradient id="halo-${id}" cx="50%" cy="46%" r="55%">
          <stop offset="0%" stop-color="#202024"/>
          <stop offset="55%" stop-color="#111113"/>
          <stop offset="100%" stop-color="#080809"/>
        </radialGradient>
        <linearGradient id="eyeGrad-${id}" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#ffffff"/>
          <stop offset="100%" stop-color="#c9c9ce"/>
        </linearGradient>
        <filter id="softGlow-${id}" x="-60%" y="-60%" width="220%" height="220%">
          <feGaussianBlur stdDeviation="4" result="b"/>
          <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
        </filter>
      </defs>

      <!-- halo exterior vivo -->
      <circle class="face-glow" cx="120" cy="120" r="112" fill="none" stroke="rgba(255,255,255,.10)" stroke-width="1.5"/>
      <circle cx="120" cy="120" r="104" fill="url(#halo-${id})" stroke="rgba(255,255,255,.14)" stroke-width="1.4"/>

      <!-- ondas de escucha -->
      <g class="waves" filter="url(#softGlow-${id})">
        <circle class="wave-ring" cx="120" cy="120" r="88" fill="none" stroke="#e8e8eb" stroke-width="1.6"/>
        <circle class="wave-ring" cx="120" cy="120" r="88" fill="none" stroke="#e8e8eb" stroke-width="1.2" style="animation-delay:.55s"/>
        <circle class="wave-ring" cx="120" cy="120" r="88" fill="none" stroke="#e8e8eb" stroke-width=".9" style="animation-delay:1.1s"/>
      </g>

      <!-- cuerpo facial (respira) -->
      <g class="face-body">
        <!-- antena de estado -->
        <line class="ant-stalk" x1="120" y1="16" x2="120" y2="30" stroke="#e8e8eb" stroke-width="2" opacity=".7"/>
        <circle class="ant-tip" cx="120" cy="14" r="4.5" fill="#f2f2f3" filter="url(#softGlow-${id})"/>

        <!-- partículas de pensamiento -->
        <g class="think">
          <circle class="think-particle" cx="168" cy="64" r="3" fill="#b8a6ff"/>
          <circle class="think-particle" cx="180" cy="52" r="2.2" fill="#f2f2f3" style="animation-delay:.7s"/>
          <circle class="think-particle" cx="172" cy="42" r="1.6" fill="#aebcff" style="animation-delay:1.4s"/>
        </g>

        <!-- Zzz dormir -->
        <g class="zzz" opacity="0">
          <text x="172" y="70" font-size="16" fill="#8fb8e8" font-family="Sora">z</text>
          <text x="184" y="54" font-size="13" fill="#6f9ccf" font-family="Sora">z</text>
          <text x="194" y="40" font-size="10" fill="#5a83b4" font-family="Sora">z</text>
        </g>

        <!-- párpados superiores (forma de ceja) -->
        <path class="lid lid-l" d="" stroke-width="4.5" stroke-linecap="round" fill="none"/>
        <path class="lid lid-r" d="" stroke-width="4.5" stroke-linecap="round" fill="none"/>

        <!-- ojos guiño Baymax: círculo recortado abajo por el párpado -->
        <g class="eyes">
          <clipPath id="lids-${id}">
            <rect class="clip-l" x="40" y="80" width="70" height="80"/>
            <rect class="clip-r" x="130" y="80" width="70" height="80"/>
          </clipPath>
          <g clip-path="url(#lids-${id})">
            <circle class="eye eye-l" cx="75" cy="118" r="24" fill="url(#eyeGrad-${id})" filter="url(#softGlow-${id})"/>
            <circle class="eye eye-r" cx="165" cy="118" r="24" fill="url(#eyeGrad-${id})" filter="url(#softGlow-${id})"/>
            <circle class="pupil pup-l" cx="75" cy="118" r="9" fill="#04101f"/>
            <circle class="pupil pup-r" cx="165" cy="118" r="9" fill="#04101f"/>
            <circle class="glint gl-l" cx="81" cy="111" r="3.4" fill="#eafcff" opacity=".95"/>
            <circle class="glint gl-r" cx="171" cy="111" r="3.4" fill="#eafcff" opacity=".95"/>
          </g>
        </g>

        <!-- mejillas de cariño -->
        <circle class="cheek ck-l" cx="58" cy="150" r="9" fill="#ff7ac8" opacity="0"/>
        <circle class="cheek ck-r" cx="182" cy="150" r="9" fill="#ff7ac8" opacity="0"/>

        <!-- boca -->
        <path class="mouth" d="" stroke-width="5" stroke-linecap="round" fill="none"/>
      </g>
    </svg>`;
  }

  // ---------- creación de instancia ----------
  function create(mount, opts = {}) {
    if (!mount) return null;
    const id = Math.random().toString(36).slice(2, 7);
    mount.innerHTML = `<div class="face-shell ${opts.compact ? "compact" : ""}" style="width:${opts.size || 190}px;height:${opts.size || 190}px">${markup(id)}</div>`;
    const shell = mount.querySelector(".face-shell");
    const q = (s) => shell.querySelector(s);

    const els = {
      lidL: q(".lid-l"), lidR: q(".lid-r"), clipL: q(".clip-l"), clipR: q(".clip-r"),
      pupL: q(".pup-l"), pupR: q(".pup-r"), glL: q(".gl-l"), glR: q(".gl-r"),
      mouth: q(".mouth"), zzz: q(".zzz"), antTip: q(".ant-tip"), antStalk: q(".ant-stalk"),
      ckL: q(".cheek.ck-l"), ckR: q(".cheek.ck-r"), eyes: q(".eyes"),
    };

    const inst = {
      shell, els, id, compact: !!opts.compact,
      target: { eyeOpen: .9, brow: 0, mouth: .15, pupil: 1, gazeX: 0, gazeY: 0 },
      cur: { eyeOpen: .9, brow: 0, mouth: .15, pupil: 1, gazeX: 0, gazeY: 0 },
      emotion: "neutral_face", speaking: false, listening: false, thinking: false, sleeping: false,
      blink: { phase: "open", t: nextBlink(), e: 1 },
      wander: { x: 0, y: 0, tx: 0, ty: 0, t: 2 },
      mouse: null, t: 0,
    };

    // la cara sigue suavemente al puntero dentro de su zona
    if (!opts.compact) {
      const hero = document.getElementById("hero") || document.body;
      hero.addEventListener("pointermove", (ev) => {
        const r = shell.getBoundingClientRect();
        const dx = (ev.clientX - (r.left + r.width / 2)) / (r.width * 1.4);
        const dy = (ev.clientY - (r.top + r.height / 2)) / (r.height * 1.4);
        inst.mouse = { x: Math.max(-1, Math.min(1, dx)), y: Math.max(-1, Math.min(1, dy)) };
      });
      hero.addEventListener("pointerleave", () => (inst.mouse = null));
    }

    tickers.push(inst);
    if (!running) startLoop();
    return inst;
  }

  function nextBlink() { return 1.6 + Math.random() * 4.2; }

  // ---------- actualización desde el cerebro ----------
  function update(inst, expr) {
    if (!inst || !expr) return;
    inst.target.eyeOpen = expr.eyeOpen ?? .9;
    inst.target.brow = expr.brow ?? 0;
    inst.target.mouth = expr.mouth ?? .15;
    inst.target.pupil = expr.pupil ?? 1;
    inst.emotion = expr.emotion || "neutral_face";
    inst.speaking = !!expr.speaking;
    inst.listening = !!expr.listening;
    inst.thinking = !!expr.thinking;
    inst.sleeping = expr.emotion === "sleepy";
    // la mirada objetivo combina cabeza + deriva interna
    inst.baseGaze = expr.gaze || { x: 0, y: 0 };
    applyClasses(inst);
  }

  function applyClasses(inst) {
    const c = inst.shell.classList;
    c.toggle("breathing", !inst.sleeping);
    c.toggle("sleeping", inst.sleeping);
    c.toggle("listening", inst.listening);
    c.toggle("thinking", inst.thinking);
    inst.els.zzz.setAttribute("opacity", inst.sleeping ? "1" : "0");
    const col = EMO_COLORS[inst.emotion] || "#5eeaff";
    inst.els.antTip.setAttribute("fill", col);
    inst.els.mouth.setAttribute("stroke", col);
    inst.els.lidL.setAttribute("stroke", col);
    inst.els.lidR.setAttribute("stroke", col);
    inst.els.eyes.style.transition = "transform .8s ease";
  }

  // ---------- bucle maestro (60fps) ----------
  const tickers = [];
  let running = false, last = 0;

  function lerp(a, b, k) { return a + (b - a) * k; }

  function frame(ts) {
    const dt = Math.min(.05, (ts - last) / 1000 || .016);
    last = ts;
    for (const inst of tickers) step(inst, dt, ts / 1000);
    requestAnimationFrame(frame);
  }

  function step(inst, dt, time) {
    const { els, cur, target, blink, wander } = inst;
    inst.t += dt;

    // --- parpadeo natural (con doble parpadeo ocasional) ---
    blink.t -= dt;
    let lidPos; // 0 = abierto del todo, 1 = cerrado
    if (inst.sleeping) {
      lidPos = .92;                                   // párpados casi caídos
    } else if (blink.phase === "close") {
      lidPos = Math.min(1, (blink.e += dt * 14));
      if (blink.e >= 1) { blink.phase = "open"; blink.e = 1; }
    } else if (blink.phase === "open") {
      lidPos = Math.max(0, (blink.e -= dt * 10));
      if (blink.e <= 0) {
        blink.phase = "wait";
        // 12% de posibilidad de doble parpadeo inmediato
        blink.t = Math.random() < .12 ? .12 : nextBlink();
      }
    } else { // wait
      lidPos = 0;
      if (blink.t <= 0) { blink.phase = "close"; blink.e = 0; }
    }

    // apertura efectiva = objetivo emocional × factor del párpado
    const openness = Math.max(.06, target.eyeOpen * (1 - lidPos));
    cur.eyeOpen = lerp(cur.eyeOpen, openness, .35);

    // --- deriva de mirada (wander) + ratón + cabeza ---
    wander.t -= dt;
    if (wander.t <= 0) {
      wander.tx = (Math.random() - .5) * .8;