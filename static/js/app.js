const $=(s,r=document)=>r.querySelector(s), $$=(s,r=document)=>[...r.querySelectorAll(s)];
const App={thread:"default",threads:[],state:null,faces:{},editing:null,panel:"mind",busy:false,ws:null,retry:0,audio:null,voice:{recognition:null,wake:false,manual:false,active:false,suspended:false,restart:null,armedUntil:0,local:false,blocked:false}};

function esc(s=""){return String(s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]))}
async function api(method,path,body){const o={method,headers:{}};if(body!==undefined){o.headers["Content-Type"]="application/json";o.body=JSON.stringify(body)}const r=await fetch(path,o);if(!r.ok)throw new Error(await r.text());return r.status===204?{}:r.json()}
function toast(t){const e=$("#toast");e.textContent=t;e.classList.add("show");clearTimeout(toast.t);toast.t=setTimeout(()=>e.classList.remove("show"),2200)}
function setEmpty(){const e=$("#empty-state");e.hidden=$("#messages").children.length>0}
function scrollBottom(){$("#conversation").scrollTop=$("#conversation").scrollHeight}
function grow(){const e=$("#prompt");e.style.height="auto";e.style.height=Math.min(e.scrollHeight,180)+"px"}
async function copyText(text){try{await navigator.clipboard.writeText(text);toast("Copiado")}catch{toast("No pude copiar")}}

function voiceWord(){return String(App.state?.settings?.audio?.wake_word||"bay-e")}
function updateVoiceUi(){
  const b=$("#wake-btn"),s=$("#wake-status");if(!b||!s)return;
  b.classList.toggle("active",App.voice.wake);b.classList.toggle("listening",App.voice.wake&&App.voice.active);
  b.setAttribute("aria-pressed",String(App.voice.wake));
  s.classList.toggle("on",App.voice.wake);
  s.textContent=App.voice.wake?`Manos libres · di "${voiceWord()}"`:"Manos libres · apagado";
}
function scheduleVoiceRestart(delay=350){
  clearTimeout(App.voice.restart);
  if(!App.voice.wake||App.voice.suspended||App.voice.blocked||App.state?.private_mode)return;
  App.voice.restart=setTimeout(()=>{if(App.busy||App.voice.active)return scheduleVoiceRestart(450);startVoiceRecognition(false)},delay);
}
function pauseVoiceForOutput(){
  App.voice.suspended=true;clearTimeout(App.voice.restart);
  if(App.voice.active&&App.voice.recognition){try{App.voice.recognition.abort()}catch{}}
}
function resumeVoiceAfterOutput(){
  App.voice.suspended=false;for(const f of Object.values(App.faces))Face.update(f,App.state?.expression||{});
  scheduleVoiceRestart(450);
}
function finishAudio(url=""){if(url)URL.revokeObjectURL(url);resumeVoiceAfterOutput()}
async function speak(text){
  if(!text)return;
  pauseVoiceForOutput();for(const f of Object.values(App.faces))Face.update(f,{speaking:true,emotion:"warm"});
  try{
    const r=await fetch("/api/audio/tts",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({text})});
    if(r.ok){
      const blob=await r.blob(),url=URL.createObjectURL(blob);
      if(App.audio)App.audio.pause();
      App.audio=new Audio(url);App.audio.onended=()=>finishAudio(url);App.audio.onerror=()=>finishAudio(url);
      try{await App.audio.play();return}catch{finishAudio(url)}
    }
  }catch{}
  if(!("speechSynthesis" in window)){resumeVoiceAfterOutput();return}
  speechSynthesis.cancel();const u=new SpeechSynthesisUtterance(text);u.lang="es-ES";u.rate=.94;u.pitch=1;
  u.onend=resumeVoiceAfterOutput;u.onerror=resumeVoiceAfterOutput;speechSynthesis.speak(u);
}

function messageTools(){return `<div class="message-tools">
<button data-act="copy">Copiar</button><button data-act="speak">Leer</button><button data-act="edit">Editar</button>
<button data-act="remember">Recordar</button><button data-act="forget">Olvidar</button><button data-act="pin">Fijar</button>
<button data-act="task">Tarea</button><button data-act="delete">Borrar</button></div>`}
function renderMessage(m){
  const el=document.createElement("article");el.className="message "+(m.role==="baye"?"baye":"user");el.dataset.id=m.id;el.dataset.content=m.content;
  el.innerHTML=`<div class="message-head"><div class="avatar">${m.role==="baye"?"BE":"TÚ"}</div><strong>${m.role==="baye"?"BAY-E":"Tú"}</strong></div><div class="bubble">${esc(m.content)}</div>${messageTools()}`;
  el.querySelector(".message-tools").onclick=async ev=>{
    const b=ev.target.closest("button");if(!b)return;const act=b.dataset.act;
    try{
      if(act==="copy")return copyText(m.content);if(act==="speak")return speak(m.content);
      if(act==="edit"){App.editing=m;$("#edit-text").value=m.content;$("#edit-modal").hidden=false;return}
      if(act==="delete"){if(!confirm("¿Borrar este mensaje?"))return;await api("DELETE","/api/chat/messages/"+m.id);return loadMessages()}
      if(["remember","forget","pin","task"].includes(act)){const r=await api("POST","/api/chat/flag",{id:m.id,action:act});toast(act==="remember"?"Guardado en memoria":act==="forget"?"Recuerdo asociado eliminado":act==="pin"?(r.fixed?"Mensaje fijado":"Mensaje desfijado"):"Convertido en tarea");if(act==="task"&&App.panel==="tasks")loadTasks();return}
    }catch(e){toast("No pude completar esa acción")}
  };
  $("#messages").append(el);setEmpty();return el;
}
function thinking(on){let e=$("#thinking");if(on&&!e){e=document.createElement("article");e.id="thinking";e.className="message baye";e.innerHTML='<div class="message-head"><div class="avatar">BE</div><strong>BAY-E</strong></div><div class="thinking"><i></i><i></i><i></i></div>';$("#messages").append(e);scrollBottom()}if(!on&&e)e.remove()}

async function loadThreads(){const r=await api("GET","/api/chat/threads");App.threads=r.threads||[];$("#threads").innerHTML="";for(const t of App.threads){const row=document.createElement("div");row.className="thread "+(t.id===App.thread?"active":"");row.innerHTML=`<button class="thread-main">${esc(t.title)}</button><button class="thread-menu">⋯</button>`;row.querySelector(".thread-main").onclick=()=>selectThread(t.id);row.querySelector(".thread-menu").onclick=async()=>{const a=prompt("Renombrar chat. Déjalo vacío para borrar:",t.title);if(a===null)return;if(a.trim())await api("PUT","/api/chat/threads/"+t.id,{title:a.trim()});else if(t.id!=="default"&&confirm("¿Borrar este chat?")){await api("DELETE","/api/chat/threads/"+t.id);if(App.thread===t.id)App.thread="default"}await loadThreads();await loadMessages()};$("#threads").append(row)}}
async function searchChats(q){
  q=(q||"").trim();
  if(q.length<2){$("#threads-label").textContent="CONVERSACIONES";return loadThreads()}
  try{
    const r=await api("GET","/api/chat/search?q="+encodeURIComponent(q)+"&limit=60"),root=$("#threads");
    $("#threads-label").textContent="RESULTADOS";
    root.innerHTML="";
    const seen=new Set();
    for(const x of r.results||[]){
      const key=x.thread_id+"|"+x.id;if(seen.has(key))continue;seen.add(key);
      const row=document.createElement("button");row.className="search-hit";
      row.innerHTML=`<strong>${esc(x.thread_title||"BAY-E")}</strong><span>${esc(x.content)}</span><small>${new Date(x.created_at*1000).toLocaleString()}</small>`;
      row.onclick=async()=>{await selectThread(x.thread_id);$("#chat-search").value="";$("#threads-label").textContent="CONVERSACIONES"};
      root.append(row);
    }
    if(!root.children.length)root.innerHTML='<div class="search-empty">No encontré mensajes con ese texto.</div>';
  }catch{toast("No pude buscar en las conversaciones")}
}

async function selectThread(id){App.thread=id;await loadThreads();await loadMessages();const t=App.threads.find(x=>x.id===id);$("#thread-title").textContent=t?.title||"BAY-E";$("#sidebar").classList.remove("open")}
async function newThread(){const r=await api("POST","/api/chat/threads",{title:"Nuevo chat"});App.thread=r.thread.id;await loadThreads();await loadMessages();$("#prompt").focus()}
async function loadMessages(){const r=await api("GET","/api/chat/history?thread_id="+encodeURIComponent(App.thread)+"&limit=500");$("#messages").innerHTML="";for(const m of r.messages||[])renderMessage(m);setEmpty();scrollBottom()}

async function send(text){text=(text||$("#prompt").value).trim();if(!text||App.busy)return;App.busy=true;$("#send-btn").disabled=true;$("#prompt").value="";grow();renderMessage({id:"temp_"+Date.now(),role:"user",content:text});thinking(true);$("#activity").textContent="BAY-E está pensando…";for(const f of Object.values(App.faces))Face.update(f,{thinking:true,emotion:"thinking"});
  try{const r=await api("POST","/api/chat/send",{text,thread_id:App.thread});thinking(false);await loadMessages();await loadThreads();$("#provider").textContent="IA · "+(r.model?.provider||"—");if(r.learning_candidate?.status==="pending"){toast("BAY-E detectó algo que podría aprender · revísalo en Aprendizaje");await refreshLearningBadge()}if(App.state?.settings?.audio?.tts_enabled!==false)speak(r.baye.content);await refreshState()}
  catch(e){thinking(false);toast("Error al responder");console.error(e)}
  finally{App.busy=false;$("#send-btn").disabled=false;$("#activity").textContent="Listo"}
}

function applyState(s){
  if(!s||s.type!=="state")return;App.state=s;
  $("#status-line").textContent=(s.mode_label||s.mode)+" · "+s.activity;
  $("#provider").textContent="IA · "+(s.model_provider||"—");
  for(const f of Object.values(App.faces))Face.update(f,s.expression||{});
  $("#mind-state").textContent=s.expression?.emotion||"neutral";$("#mind-mode").textContent=s.mode_label||s.mode;
  $("#mind-thought").textContent=s.last_thought||"—";$("#mind-reason").textContent=s.reason||"—";$("#mind-next").textContent=s.next_decision||"—";
  $("#pill-body").textContent=s.hardware_connected?"Cuerpo · conectado":"Cuerpo · desconectado";$("#pill-privacy").textContent=s.private_mode?"Privacidad · privada":"Privacidad · normal";
  $("#control-hardware").textContent=s.hardware_connected?`Cuerpo · ${s.robot_adapter||"online"}`:"Cuerpo desconectado";
  $("#control-safety").textContent="Safety · "+(s.security?.status||"—");
  $("#toggle-autonomy").textContent=s.autonomy?"Autonomía · ON":"Autonomía · OFF";
  $("#private-mode").checked=!!s.private_mode;$("#autonomy-setting").checked=!!s.autonomy;
  if(s.private_mode&&App.voice.wake)setWakeEnabled(false,"Modo privado: escucha manos libres desactivada.");
  $$(".mode-grid [data-mode]").forEach(b=>b.classList.toggle("active",b.dataset.mode===s.mode));
  const p=s.position||{};$("#world-position").textContent=p.room&&p.room!=="unknown"?p.room:"Sin posición física confirmada";
  const dot=$("#robot-dot");if(dot&&Number.isFinite(p.x)&&Number.isFinite(p.y)){dot.style.left=(Math.max(.05,Math.min(.95,p.x))*100)+"%";dot.style.top=(Math.max(.05,Math.min(.95,p.y))*100)+"%"}
  const labels=s.emotion_labels||{},emo=s.emotions||{};$("#drive-grid").innerHTML=["energy","curiosity","boredom","sociability","attention","trust","worry","fatigue"].map(k=>`<div class="drive"><header><span>${esc(labels[k]||k)}</span><b>${Math.round((emo[k]||0)*100)}%</b></header><div class="bar"><i style="width:${Math.round((emo[k]||0)*100)}%"></i></div></div>`).join("");
}
async function refreshState(){try{applyState(await api("GET","/api/state"))}catch{}}

function connectWS(){
  if(App.ws&&[0,1].includes(App.ws.readyState))return;
  const proto=location.protocol==="https:"?"wss":"ws",ws=new WebSocket(`${proto}://${location.host}/ws`);App.ws=ws;
  ws.onopen=()=>{App.retry=0;$("#live-dot").className="live-dot online";$("#live-dot").title="Enlace en vivo conectado"};
  ws.onmessage=e=>{try{const m=JSON.parse(e.data);if(m.type==="state")applyState(m);if(m.type==="core_event"&&App.panel==="system")loadLogs()}catch{}};
  ws.onclose=()=>{$("#live-dot").className="live-dot warn";App.ws=null;const wait=Math.min(10000,800*Math.pow(1.7,App.retry++));setTimeout(connectWS,wait)};
  ws.onerror=()=>ws.close();
}

async function loadRules(){const r=await api("GET","/api/mind/rules");$("#rule-list").innerHTML="";for(const x of r.rules||[]){const e=document.createElement("article");e.className="rule-card";e.innerHTML=`<header><span class="kind">${esc(x.kind)} · p${x.priority}</span><label><input type="checkbox" ${x.enabled?"checked":""}> activa</label></header><p>${esc(x.content)}</p><footer><span>${x.enabled?"Aplicándose":"Desactivada"}</span><button class="danger">Borrar</button></footer>`;e.querySelector("input").onchange=ev=>api("PUT","/api/mind/rules/"+x.id,{enabled:ev.target.checked}).then(loadRules);e.querySelector(".danger").onclick=()=>api("DELETE","/api/mind/rules/"+x.id).then(loadRules);$("#rule-list").append(e)}}

async function refreshLearningBadge(){
  try{
    const r=await api("GET","/api/learning/candidates?status=pending&limit=100");
    const n=(r.candidates||[]).length,b=$("#learning-badge");
    b.textContent=String(n);b.hidden=n===0;
    $("#learning-pending").textContent=String(n);
    return n;
  }catch{return 0}
}

async function loadLearning(){
  try{
    const [pending,approved]=await Promise.all([
      api("GET","/api/learning/candidates?status=pending&limit=100"),
      api("GET","/api/learning/candidates?status=approved&limit=100")
    ]);
    const items=pending.candidates||[],root=$("#learning-list");
    $("#learning-pending").textContent=String(items.length);
    $("#learning-approved").textContent=String((approved.candidates||[]).length);
    const badge=$("#learning-badge");badge.textContent=String(items.length);badge.hidden=items.length===0;
    root.innerHTML="";
    for(const x of items){
      const e=document.createElement("article");e.className="learning-card";
      e.innerHTML=`<header><span class="learn-kind">${esc(x.kind)}</span><span class="learn-confidence">${Math.round((x.confidence||0)*100)}% confianza</span></header><p>${esc(x.content)}</p><small>${esc(x.reason||"Requiere revisión")}</small><footer><button data-a="reject">No aprender</button><button data-a="approve" class="approve">Recordar</button></footer>`;
      e.onclick=async ev=>{const b=ev.target.closest("button");if(!b)return;try{await api("POST","/api/learning/candidates/"+encodeURIComponent(x.id)+"/resolve",{action:b.dataset.a});toast(b.dataset.a==="approve"?"Aprendido con tu aprobación":"Propuesta descartada");await loadLearning();if(b.dataset.a==="approve"&&App.panel==="memory")await loadMemory()}catch{toast("No pude resolver este aprendizaje")}};
      root.append(e);
    }
    if(!items.length)root.innerHTML='<div class="learning-empty"><span>●────●</span><strong>Todo revisado.</strong><p>No tengo recuerdos pendientes de tu aprobación.</p></div>';
  }catch{toast("No pude cargar la bandeja de aprendizaje")}
}

async function loadMemory(){const q=$("#memory-search").value,type=$("#memory-type").value;const r=await api("GET",`/api/memories?q=${encodeURIComponent(q)}&type=${encodeURIComponent(type)}`);$("#memory-list").innerHTML="";for(const m of (r.memories||[]).slice(0,120)){const e=document.createElement("article");e.className="info-card";e.innerHTML=`<header><small>${esc(m.type)} · ${Math.round((m.confidence||0)*100)}%</small><span>${m.pinned?"★":""}</span></header><p>${esc(m.content)}</p><footer><span>${esc(m.source||"")}</span><div><button data-a="pin">${m.pinned?"Desfijar":"Fijar"}</button><button data-a="edit">Editar</button><button data-a="delete" class="danger-text">Borrar</button></div></footer>`;e.onclick=async ev=>{const b=ev.target.closest("button");if(!b)return;try{if(b.dataset.a==="pin")await api("POST",`/api/memories/${m.id}/pin`,{on:!m.pinned});if(b.dataset.a==="edit"){const v=prompt("Corregir recuerdo:",m.content);if(v&&v.trim())await api("POST",`/api/memories/${m.id}/correct`,{content:v.trim()})}if(b.dataset.a==="delete"&&confirm("¿Borrar este recuerdo?"))await api("DELETE",`/api/memories/${m.id}`);await loadMemory()}catch{toast("No pude modificar el recuerdo")}};$("#memory-list").append(e)}if(!$("#memory-list").children.length)$("#memory-list").innerHTML='<div class="info-card"><p>Sin resultados.</p></div>'}

async function loadTasks(){const r=await api("GET","/api/tasks");$("#task-list").innerHTML="";for(const t of r.tasks||[]){const e=document.createElement("article");e.className="info-card";e.innerHTML=`<header><small>${esc(t.status)}${t.repeat?" · "+esc(t.repeat):""}</small><span></span></header><p><strong>${esc(t.title)}</strong></p>${t.description?`<p>${esc(t.description)}</p>`:""}<footer><span>${t.scheduled_at?new Date(t.scheduled_at*1000).toLocaleString():"Sin fecha"}</span><div><button data-a="toggle">${t.status==="paused"?"Reanudar":"Pausar"}</button><button data-a="done">Hecha</button><button data-a="delete" class="danger-text">Borrar</button></div></footer>`;e.onclick=async ev=>{const b=ev.target.closest("button");if(!b)return;if(b.dataset.a==="toggle")await api("PUT",`/api/tasks/${t.id}`,{status:t.status==="paused"?"pending":"paused"});if(b.dataset.a==="done")await api("PUT",`/api/tasks/${t.id}`,{status:"done"});if(b.dataset.a==="delete"&&confirm("¿Borrar esta tarea?"))await api("DELETE",`/api/tasks/${t.id}`);await loadTasks()};$("#task-list").append(e)}if(!$("#task-list").children.length)$("#task-list").innerHTML='<div class="info-card"><p>No hay tareas todavía.</p></div>'}

async function loadWorld(){try{const r=await api("GET","/api/world"),entities=r.entities||[],relations=r.relations||[];$("#world-count").textContent=entities.length+" entidades";$("#world-list").innerHTML=entities.slice(0,60).map(x=>`<div class="info-card"><small>${esc(x.kind)} · ${Math.round((x.confidence||0)*100)}%</small><p><strong>${esc(x.label)}</strong></p><p>${relations.filter(y=>y.subject_id===x.id).slice(0,3).map(y=>esc(y.predicate)+" → "+esc((entities.find(z=>z.id===y.object_id)||{}).label||y.object_id)).join("<br>")||"Sin relaciones confirmadas"}</p></div>`).join("")||'<div class="info-card"><p>El modelo del hogar todavía está vacío.</p></div>'}catch{}}

async function loadVision(){try{const st=await api("GET","/api/vision/status");$("#vision-status").textContent=st.private_mode?"Modo privado activo":st.available?"Adaptador de visión disponible":"Sin cámara/adaptador activo";const r=await api("GET","/api/vision/detections");$("#vision-list").innerHTML=(r.detections||[]).slice(-30).reverse().map(d=>`<div class="info-card"><small>${esc(d.kind||"detección")}</small><p>${esc(d.label||"objeto")} · ${Math.round((d.confidence||0)*100)}%</p></div>`).join("")||'<div class="info-card"><p>Sin detecciones reales recientes.</p></div>'}catch{}}
async function loadDevices(){try{const r=await api("GET","/api/mobile/nodes");const root=$("#device-list");root.innerHTML=(r.nodes||[]).map(n=>`<div class="info-card" data-node="${esc(n.id)}"><header><small>${esc(n.platform)} · ${new Date(n.last_seen*1000).toLocaleString()}</small><small class="${n.paired&&!n.revoked?"device-auth":""}">${n.revoked?"revocado":n.paired?"autorizado":"sin emparejar"}</small></header><p><strong>${esc(n.name)}</strong></p><p>${esc(Object.keys(n.capabilities||{}).filter(k=>n.capabilities[k]).join(", ")||"sin capacidades")}</p>${n.paired&&!n.revoked?`<div class="device-actions"><button data-revoke="${esc(n.id)}">Revocar acceso</button></div>`:""}</div>`).join("")||'<div class="info-card"><p>No hay dispositivos enlazados todavía.</p></div>';$$("[data-revoke]",root).forEach(b=>b.onclick=async()=>{if(!confirm("¿Revocar el acceso de este teléfono a BAY-E?"))return;try{await api("DELETE","/api/mobile/nodes/"+encodeURIComponent(b.dataset.revoke));toast("Acceso móvil revocado");await loadDevices()}catch(e){toast("Abre BAY-E desde 127.0.0.1 para revocar dispositivos")}})}catch{}}

async function loadLogs(){try{const r=await api("GET","/api/logs?limit=40");$("#log-list").innerHTML=(r.logs||[]).map(x=>`<div class="info-card"><small>${new Date(x.ts*1000).toLocaleTimeString()} · ${esc(x.level)} · ${esc(x.module)}</small><p>${esc(x.human||x.technical||"evento")}</p></div>`).join("")}catch{}}
async function loadSystem(){try{const [d,m]=await Promise.all([api("GET","/api/diagnostics"),api("GET","/api/modules")]);const rows=[["Guardian",d.guardian?.overall],["Modelo",d.models?.last_provider],["OpenCV",d.vision?.opencv?"ok":"offline"],["STT",d.audio?.stt?"ok":"offline"],["TTS",d.audio?.tts?"ok":"offline"],["Robot",d.robot?.connected?"ok":"offline"]];$("#diagnostics").innerHTML=rows.map(([k,v])=>`<div class="info-card"><small>${esc(k)}</small><p class="${v==="ok"?"status-ok":v==="offline"?"status-off":"status-warn"}">${esc(v||"unknown")}</p></div>`).join("");$("#module-list").innerHTML=(m.modules||[]).map(x=>`<div class="info-card"><header><small>${esc(x.name)} · ${esc(x.version)}</small><input type="checkbox" data-module="${esc(x.id)}" ${x.enabled?"checked":""}></header><p>${esc(x.desc||"")}</p></div>`).join("");$$("[data-module]",$("#module-list")).forEach(x=>x.onchange=async()=>{await api("POST",`/api/modules/${x.dataset.module}/toggle`,{on:x.checked});await refreshState()});await loadLogs()}catch{}}

function openDrawer(name){App.panel=name;$("#drawer").classList.add("open");$$(".drawer-view").forEach(v=>v.classList.toggle("active",v.dataset.view===name));$("#drawer-title").textContent={mind:"Corazón y mente",learning:"Aprendizaje",memory:"Memoria",tasks:"Tareas y rutinas",world:"Casa y mundo",vision:"Visión",control:"Cuerpo y control",devices:"Dispositivos",system:"Sistema y privacidad"}[name]||"BAY-E";if(name==="mind")loadRules();if(name==="learning")loadLearning();if(name==="memory")loadMemory();if(name==="tasks")loadTasks();if(name==="world")loadWorld();if(name==="vision")loadVision();if(name==="devices")loadDevices();if(name==="system")loadSystem()}

async function command(cmd,payload={}){try{const r=await api("POST","/api/command",{cmd,payload});if(r.blocked)toast("Bloqueado por seguridad: "+(r.reason||"acción no disponible"));else toast("Comando aceptado");await refreshState();return r}catch{toast("No pude ejecutar el comando")}}
function normalizedSpeech(text){return String(text||"").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g,"").replace(/[^a-z0-9\s-]/g," ").replace(/\s+/g," ").trim()}
function handleWakeTranscript(transcript){
  const raw=String(transcript||"").trim(),norm=normalizedSpeech(raw);if(!norm)return;
  const match=norm.match(/\b(?:bay[\s-]?e|baye|bai[\s-]?e)\b/);
  if(match){
    App.voice.armedUntil=Date.now()+8000;
    const rawMatch=raw.match(/\b(?:bay[\s-]?e|baye|bai[\s-]?e)\b/i);
    const command=(rawMatch?raw.slice((rawMatch.index||0)+rawMatch[0].length):norm.slice((match.index||0)+match[0].length)).trim();
    if(command){send(command);App.voice.armedUntil=0}else{toast("Te escucho · dime qué necesitas");$("#activity").textContent="BAY-E está atento…"}
    return;
  }
  if(Date.now()<App.voice.armedUntil){App.voice.armedUntil=0;send(raw)}
}
function startVoiceRecognition(manual=false){
  const r=App.voice.recognition;if(!r||App.voice.active||App.voice.suspended||App.voice.blocked)return;
  if(App.state?.private_mode)return toast("El modo privado bloquea la escucha del micrófono");
  App.voice.manual=manual;
  try{r.start()}catch{if(App.voice.wake)scheduleVoiceRestart(500)}
}
function setWakeEnabled(on,message=""){
  const v=App.voice,b=$("#wake-btn");v.wake=!!on;v.armedUntil=0;clearTimeout(v.restart);
  if(!v.wake&&v.active&&v.recognition){try{v.recognition.abort()}catch{}}
  updateVoiceUi();
  if(message)toast(message);
  if(v.wake){toast(v.local?"Manos libres activo · reconocimiento local disponible":"Manos libres activo · el navegador puede usar un servicio de voz");startVoiceRecognition(false)}
}
function setupSpeech(){
  const SR=window.SpeechRecognition||window.webkitSpeechRecognition,b=$("#wake-btn"),mic=$("#voice-btn");
  if(!SR){mic.onclick=()=>toast("Dictado no disponible en este navegador");b.disabled=true;b.title="Reconocimiento de voz no disponible";updateVoiceUi();return}
  const r=new SR();App.voice.recognition=r;r.lang="es-ES";r.interimResults=false;r.continuous=false;r.maxAlternatives=1;
  if(typeof SR.available==="function"&&"processLocally" in r){
    SR.available({langs:["es-ES"],processLocally:true,quality:"command"}).then(status=>{if(status==="available"){r.processLocally=true;App.voice.local=true;updateVoiceUi()}}).catch(()=>{});
  }
  r.onstart=()=>{App.voice.active=true;mic.classList.toggle("listening",App.voice.manual);b.classList.toggle("listening",App.voice.wake);$("#activity").textContent=App.voice.manual?"Escuchando…":`Esperando "${voiceWord()}"…`;for(const f of Object.values(App.faces))Face.update(f,{listening:true,emotion:"attentive"})};
  r.onend=()=>{const wasManual=App.voice.manual;App.voice.active=false;App.voice.manual=false;mic.classList.remove("listening");b.classList.remove("listening");$("#activity").textContent="Listo";if(!App.voice.suspended)for(const f of Object.values(App.faces))Face.update(f,App.state?.expression||{});if(App.voice.wake)scheduleVoiceRestart(wasManual?450:300)};
  r.onresult=e=>{const transcript=e.results?.[0]?.[0]?.transcript||"";if(App.voice.manual)send(transcript);else if(App.voice.wake)handleWakeTranscript(transcript)};
  r.onerror=e=>{App.voice.active=false;const fatal=["not-allowed","service-not-allowed","audio-capture"].includes(e.error);if(fatal){App.voice.blocked=true;setWakeEnabled(false);toast("No pude mantener el micrófono activo: revisa permisos")}else if(App.voice.manual&&e.error!=="no-speech")toast("No pude escuchar el micrófono")};
  mic.onclick=()=>{if(App.voice.active&&App.voice.manual){try{r.stop()}catch{};return}startVoiceRecognition(true)};
  b.onclick=()=>{if(App.state?.private_mode)return toast("Desactiva modo privado para usar manos libres");setWakeEnabled(!App.voice.wake)};
  updateVoiceUi();
}

document.addEventListener("DOMContentLoaded",async()=>{
  App.faces.main=Face.create($("#face-main"));App.faces.mind=Face.create($("#face-mind"),{small:true});
  $("#new-chat").onclick=newThread;$("#home-btn").onclick=()=>selectThread("default");$("#menu-btn").onclick=()=>$("#sidebar").classList.add("open");$("#side-close").onclick=()=>$("#sidebar").classList.remove("open");
  let searchTimer=0;$("#chat-search").oninput=e=>{clearTimeout(searchTimer);searchTimer=setTimeout(()=>searchChats(e.target.value),180)};
  $("#mind-btn").onclick=()=>openDrawer("mind");$$("[data-panel]").forEach(b=>b.onclick=()=>openDrawer(b.dataset.panel));$("#drawer-close").onclick=()=>$("#drawer").classList.remove("open");$$("[data-prompt]").forEach(b=>b.onclick=()=>{if(b.closest(".drawer"))$("#drawer").classList.remove("open");send(b.dataset.prompt)});
  $("#pair-mobile-btn").onclick=async()=>{try{const r=await api("POST","/api/mobile/pair/start",{ttl_seconds:300});$("#pair-code-value").textContent=r.code;$("#pair-code-display").hidden=false;const end=Number(r.expires_at||0)*1000;$("#pair-code-expiry").textContent="Caduca a las "+new Date(end).toLocaleTimeString([], {hour:"2-digit",minute:"2-digit"});toast("Código listo · úsalo una sola vez")}catch(e){toast("Genera el código abriendo BAY-E en 127.0.0.1")}};
  $("#send-btn").onclick=()=>send();$("#prompt").oninput=grow;$("#prompt").onkeydown=e=>{if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();send()}};
  $("#memory-search").oninput=loadMemory;$("#memory-type").onchange=loadMemory;
  $("#rule-form").onsubmit=async e=>{e.preventDefault();await api("POST","/api/mind/rules",{kind:$("#rule-kind").value,content:$("#rule-content").value,priority:Number($("#rule-priority").value),enabled:true});$("#rule-content").value="";await loadRules();toast("Añadido a la mente de BAY-E")};
  $("#task-form").onsubmit=async e=>{e.preventDefault();await api("POST","/api/tasks",{title:$("#task-title").value,description:$("#task-description").value,repeat:$("#task-repeat").value});$("#task-title").value="";$("#task-description").value="";await loadTasks();toast("Tarea creada")};
  $("#edit-cancel").onclick=()=>$("#edit-modal").hidden=true;$("#edit-save").onclick=async()=>{if(!App.editing)return;await api("PUT","/api/chat/messages/"+App.editing.id,{content:$("#edit-text").value});$("#edit-modal").hidden=true;App.editing=null;await loadMessages();toast("Mensaje actualizado")};
  $$(".mode-grid [data-mode]").forEach(b=>b.onclick=()=>command("set_mode",{mode:b.dataset.mode}));$$("[data-move]").forEach(b=>b.onclick=()=>command("move",{dir:b.dataset.move}));$("#return-base").onclick=()=>command("return_base");$("#toggle-autonomy").onclick=()=>command("toggle_autonomy",{on:!App.state?.autonomy});$("#estop").onclick=()=>command("emergency_stop");
  $("#private-mode").onchange=async e=>{await api("PUT","/api/settings/privacy",{private_mode:e.target.checked});await refreshState()};$("#autonomy-setting").onchange=async e=>{await api("PUT","/api/settings/autonomy",{enabled:e.target.checked});await refreshState()};
  $("#backup-btn").onclick=async()=>{const r=await api("POST","/api/backups",{});toast("Backup creado: "+String(r.file||"").split(/[\\/]/).pop())};$("#retention-btn").onclick=async()=>{const r=await api("POST","/api/privacy/enforce-retention",{});toast("Retención aplicada · "+(r.deleted||0)+" eliminadas")};$("#purge-btn").onclick=async()=>{if(!confirm("Esto borrará todas las memorias y perfiles biométricos locales. ¿Continuar?"))return;await api("POST","/api/privacy/purge",{mode:"all"});toast("Memoria eliminada");loadMemory()};
  setupSpeech();connectWS();await loadThreads();if(!App.threads.some(t=>t.id===App.thread))App.thread=App.threads[0]?.id||"default";await loadMessages();await refreshState();await refreshLearningBadge();setInterval(refreshState,15000);setInterval(refreshLearningBadge,30000);
});
