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
    happy: "#5eeaff", excited: "#7df0ff", curious: "#9b7bff", thinking: "#4d8dff",
    attentive: "#5eeaff", worried: "#ff9d6b", bored: "#61779a", sleepy: "#3f5f8f",
    neutral_face: "#5eeaff",
  };

  // ---------- plantilla SVG ----------
  function markup(id) {
    return `
    <svg viewBox="0 0 240 240" width="100%" height="100%" role="img" aria-label="Cara viva de BAY-E">
      <defs>
        <radialGradient id="halo-${id}" cx="50%" cy="46%" r="55%">
          <stop offset="0%" stop-color="#1a3550"/>
          <stop offset="55%" stop-color="#0c1c30"/>
          <stop offset="100%" stop-color="#071120"/>
        </radialGradient>
        <linearGradient id="eyeGrad-${id}" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#9ff6ff"/>
          <stop offset="100%" stop-color="#3ec8f0"/>
        </linearGradient>
        <filter id="softGlow-${id}" x="-60%" y="-60%" width="220%" height="220%">
          <feGaussianBlur stdDeviation="4" result="b"/>
          <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
        </filter>
      </defs>

      <!-- halo exterior vivo -->
      <circle class="face-glow" cx="120" cy="120" r="112" fill="none" stroke="rgba(94,234,255,.16)" stroke-width="1.5"/>
      <circle cx="120" cy="120" r="104" fill="url(#halo-${id})" stroke="rgba(120,200,255,.28)" stroke-width="1.4"/>

      <!-- ondas de escucha -->
      <g class="waves" filter="url(#softGlow-${id})">
        <circle class="wave-ring" cx="120" cy="120" r="88" fill="none" stroke="#5eeaff" stroke-width="1.6"/>
        <circle class="wave-ring" cx="120" cy="120" r="88" fill="none" stroke="#5eeaff" stroke-width="1.2" style="animation-delay:.55s"/>
        <circle class="wave-ring" cx="120" cy="120" r="88" fill="none" stroke="#5eeaff" stroke-width=".9" style="animation-delay:1.1s"/>
      </g>

      <!-- cuerpo facial (respira) -->
      <g class="face-body">
        <!-- antena de estado -->
        <line class="ant-stalk" x1="120" y1="16" x2="120" y2="30" stroke="#5eeaff" stroke-width="2" opacity=".7"/>
        <circle class="ant-tip" cx="120" cy="14" r="4.5" fill="#5eeaff" filter="url(#softGlow-${id})"/>

        <!-- partículas de pensamiento -->
        <g class="think">
          <circle class="think-particle" cx="168" cy="64" r="3" fill="#9b7bff"/>
          <circle class="think-particle" cx="180" cy="52" r="2.2" fill="#5eeaff" style="animation-delay:.7s"/>
          <circle class="think-particle" cx="172" cy="42" r="1.6" fill="#4d8dff" style="animation-delay:1.4s"/>
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
      wander.ty = (Math.random() - .5) * .5;
      wander.t = 1.2 + Math.random() * 3;
    }
    wander.x = lerp(wander.x, wander.tx, .04);
    wander.y = lerp(wander.y, wander.ty, .04);

    const base = inst.baseGaze || { x: 0, y: 0 };
    let gx = base.x + wander.x * .35 + (inst.mouse ? inst.mouse.x * .55 : 0);
    let gy = base.y + wander.y * .3 + (inst.mouse ? inst.mouse.y * .45 : 0);
    if (inst.thinking) { // mirar hacia arriba-derecha al pensar
      gx += .3 + Math.sin(time * 1.3) * .25;
      gy += -.45 + Math.cos(time * .9) * .15;
    }
    cur.gazeX = lerp(cur.gazeX, Math.max(-1, Math.min(1, gx)), .08);
    cur.gazeY = lerp(cur.gazeY, Math.max(-1, Math.min(1, gy)), .08);

    cur.brow = lerp(cur.brow, target.brow, .08);
    cur.pupil = lerp(cur.pupil, target.pupil, .1);

    // --- boca: forma base + movimiento al hablar ---
    let m = target.mouth;
    if (inst.speaking) {
      m += Math.sin(time * 16) * .28 + Math.sin(time * 23.7) * .18; // articulación orgánica
    } else if (inst.emotion === "happy" || inst.emotion === "excited") {
      m += Math.sin(time * 1.8) * .04;                              // sonrisa que respira
    }
    cur.mouth = lerp(cur.mouth, m, .22);

    // ================= RENDER =================
    const EX = 75, EY = 118, R = 24;           // geometría de los ojos
    const halfH = R * cur.eyeOpen;             // mitad visible del ojo
    const topY = EY - R;                        // parte superior del círculo
    const lidTop = EY - halfH;                  // línea del párpado

    // párpados como cejas expresivas (curvatura según brow)
    const browLift = cur.brow * 10;
    const tilt = (inst.emotion === "worried" ? 6 : 0) * (cur.brow < 0 ? 1 : 0);
    for (const [lid, cx] of [[els.lidL, EX], [els.lidR, 240 - EX]]) {
      const y = lidTop - 6 - Math.max(0, browLift);
      const bend = -8 - cur.brow * 7;
      const skew = cx < 120 ? -tilt : tilt;
      lid.setAttribute("d", `M ${cx - 27} ${y + 2 + skew} Q ${cx} ${y + bend} ${cx + 27} ${y + 2 - skew}`);
    }

    // recorte inferior de los ojos (el párpado baja desde arriba)
    for (const [clip, cx] of [[els.clipL, EX - 35], [els.clipR, 240 - EX - 35]]) {
      clip.setAttribute("y", String(lidTop));
      clip.setAttribute("height", String(halfH + R + 8));
    }

    // escala vertical del globo ocular para un cierre suave
    const scaleY = cur.eyeOpen;
    for (const eye of [els.eyeL || (els.eyeL = shellQ(inst, ".eye-l")), els.eyeR || (els.eyeR = shellQ(inst, ".eye-r"))]) {
      if (!eye) continue;
      eye.setAttribute("transform", `translate(${EX * (eye === els.eyeL ? 1 : 3)} ${EY}) scale(1 ${scaleY.toFixed(3)}) translate(${-EX * (eye === els.eyeL ? 1 : 3)} ${-EY})`);
    }

    // pupilas + brillos siguen la mirada
    const px = cur.gazeX * 8, py = cur.gazeY * 6;
    els.pupL.setAttribute("cx", EX + px); els.pupL.setAttribute("cy", EY + py);
    els.pupR.setAttribute("cx", 240 - EX + px); els.pupR.setAttribute("cy", EY + py);
    els.glL.setAttribute("cx", EX + px + 5); els.glL.setAttribute("cy", EY + py - 6);
    els.glR.setAttribute("cx", 240 - EX + px + 5); els.glR.setAttribute("cy", EY + py - 6);
    const pr = 9 * cur.pupil * (inst.emotion === "excited" ? 1.15 : 1);
    els.pupL.setAttribute("r", pr); els.pupR.setAttribute("r", pr);

    // boca: curva cuadrática centrada, abre al hablar
    const MX = 120, MY = 172;
    const smile = cur.mouth * 16;                    // curvatura
    const openAmt = inst.speaking ? Math.abs(Math.sin(time * 16)) * 7 + 2 : Math.max(0, cur.mouth) * 2;
    const w = 34 + Math.abs(cur.mouth) * 8;
    if (openAmt > 3.5) {
      // boca abierta (hablando) → óvalo
      els.mouth.setAttribute("d", `M ${MX - w / 2} ${MY} Q ${MX} ${MY + smile} ${MX + w / 2} ${MY} Q ${MX} ${MY + smile + openAmt * 2.4} ${MX - w / 2} ${MY} Z`);
      els.mouth.setAttribute("fill", "rgba(94,234,255,.14)");
    } else {
      els.mouth.setAttribute("d", `M ${MX - w / 2} ${MY} Q ${MX} ${MY + smile} ${MX + w / 2} ${MY}`);
      els.mouth.setAttribute("fill", "none");
    }

    // mejillas rosadas cuando hay cariño/felicidad alta
    const blush = (inst.emotion === "happy" || inst.emotion === "excited") ? .35 : 0;
    els.ckL.setAttribute("opacity", blush); els.ckR.setAttribute("opacity", blush);

    // leve cabeceo orgánico de presencia (no en compacta)
    if (!inst.compact) {
      const nodX = Math.sin(time * .7) * 1.6 + cur.gazeX * 2.5;
      const nodY = Math.sin(time * .5 + 1) * 1.2 + cur.gazeY * 1.5;
      inst.els.eyes.parentNode && null;
      shellQ(inst, ".face-body")?.setAttribute("transform", `translate(${nodX.toFixed(2)} ${nodY.toFixed(2)})`);
    }
  }

  function shellQ(inst, sel) { return inst.shell.querySelector(sel); }

  function startLoop() { running = true; requestAnimationFrame(frame); }

  return { create, update, EMO_COLORS };
})();
