const $=(s,r=document)=>r.querySelector(s), $$=(s,r=document)=>[...r.querySelectorAll(s)];
const App={thread:"default",threads:[],state:null,faces:{},editing:null,panel:"mind",busy:false,ws:null,retry:0,audio:null};

function esc(s=""){return String(s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]))}
async function api(method,path,body){const o={method,headers:{}};if(body!==undefined){o.headers["Content-Type"]="application/json";o.body=JSON.stringify(body)}const r=await fetch(path,o);if(!r.ok)throw new Error(await r.text());return r.status===204?{}:r.json()}
function toast(t){const e=$("#toast");e.textContent=t;e.classList.add("show");clearTimeout(toast.t);toast.t=setTimeout(()=>e.classList.remove("show"),2200)}
function setEmpty(){const e=$("#empty-state");e.hidden=$("#messages").children.length>0}
function scrollBottom(){$("#conversation").scrollTop=$("#conversation").scrollHeight}
function grow(){const e=$("#prompt");e.style.height="auto";e.style.height=Math.min(e.scrollHeight,180)+"px"}
async function copyText(text){try{await navigator.clipboard.writeText(text);toast("Copiado")}catch{toast("No pude copiar")}}

async function speak(text){
  if(!text)return;
  try{
    const r=await fetch("/api/audio/tts",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({text})});
    if(r.ok){
      const blob=await r.blob(),url=URL.createObjectURL(blob);
      if(App.audio)App.audio.pause();
      App.audio=new Audio(url);App.audio.onended=()=>URL.revokeObjectURL(url);await App.audio.play();return;
    }
  }catch{}
  if(!("speechSynthesis" in window))return;
  speechSynthesis.cancel();const u=new SpeechSynthesisUtterance(text);u.lang="es-ES";u.rate=.94;u.pitch=1;speechSynthesis.speak(u);
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
async function selectThread(id){App.thread=id;await loadThreads();await loadMessages();const t=App.threads.find(x=>x.id===id);$("#thread-title").textContent=t?.title||"BAY-E";$("#sidebar").classList.remove("open")}
async function newThread(){const r=await api("POST","/api/chat/threads",{title:"Nuevo chat"});App.thread=r.thread.id;await loadThreads();await loadMessages();$("#prompt").focus()}
async function loadMessages(){const r=await api("GET","/api/chat/history?thread_id="+encodeURIComponent(App.thread)+"&limit=500");$("#messages").innerHTML="";for(const m of r.messages||[])renderMessage(m);setEmpty();scrollBottom()}

async function send(text){text=(text||$("#prompt").value).trim();if(!text||App.busy)return;App.busy=true;$("#send-btn").disabled=true;$("#prompt").value="";grow();renderMessage({id:"temp_"+Date.now(),role:"user",content:text});thinking(true);$("#activity").textContent="BAY-E está pensando…";for(const f of Object.values(App.faces))Face.update(f,{thinking:true,emotion:"thinking"});
  try{const r=await api("POST","/api/chat/send",{text,thread_id:App.thread});thinking(false);await loadMessages();await loadThreads();$("#provider").textContent="IA · "+(r.model?.provider||"—");if(App.state?.settings?.audio?.tts_enabled!==false)speak(r.baye.content);await refreshState()}
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

async function loadMemory(){const q=$("#memory-search").value,type=$("#memory-type").value;const r=await api("GET",`/api/memories?q=${encodeURIComponent(q)}&type=${encodeURIComponent(type)}`);$("#memory-list").innerHTML="";for(const m of (r.memories||[]).slice(0,120)){const e=document.createElement("article");e.className="info-card";e.innerHTML=`<header><small>${esc(m.type)} · ${Math.round((m.confidence||0)*100)}%</small><span>${m.pinned?"★":""}</span></header><p>${esc(m.content)}</p><footer><span>${esc(m.source||"")}</span><div><button data-a="pin">${m.pinned?"Desfijar":"Fijar"}</button><button data-a="edit">Editar</button><button data-a="delete" class="danger-text">Borrar</button></div></footer>`;e.onclick=async ev=>{const b=ev.target.closest("button");if(!b)return;try{if(b.dataset.a==="pin")await api("POST",`/api/memories/${m.id}/pin`,{on:!m.pinned});if(b.dataset.a==="edit"){const v=prompt("Corregir recuerdo:",m.content);if(v&&v.trim())await api("POST",`/api/memories/${m.id}/correct`,{content:v.trim()})}if(b.dataset.a==="delete"&&confirm("¿Borrar este recuerdo?"))await api("DELETE",`/api/memories/${m.id}`);await loadMemory()}catch{toast("No pude modificar el recuerdo")}};$("#memory-list").append(e)}if(!$("#memory-list").children.length)$("#memory-list").innerHTML='<div class="info-card"><p>Sin resultados.</p></div>'}

async function loadTasks(){const r=await api("GET","/api/tasks");$("#task-list").innerHTML="";for(const t of r.tasks||[]){const e=document.createElement("article");e.className="info-card";e.innerHTML=`<header><small>${esc(t.status)}${t.repeat?" · "+esc(t.repeat):""}</small><span></span></header><p><strong>${esc(t.title)}</strong></p>${t.description?`<p>${esc(t.description)}</p>`:""}<footer><span>${t.scheduled_at?new Date(t.scheduled_at*1000).toLocaleString():"Sin fecha"}</span><div><button data-a="toggle">${t.status==="paused"?"Reanudar":"Pausar"}</button><button data-a="done">Hecha</button><button data-a="delete" class="danger-text">Borrar</button></div></footer>`;e.onclick=async ev=>{const b=ev.target.closest("button");if(!b)return;if(b.dataset.a==="toggle")await api("PUT",`/api/tasks/${t.id}`,{status:t.status==="paused"?"pending":"paused"});if(b.dataset.a==="done")await api("PUT",`/api/tasks/${t.id}`,{status:"done"});if(b.dataset.a==="delete"&&confirm("¿Borrar esta tarea?"))await api("DELETE",`/api/tasks/${t.id}`);await loadTasks()};$("#task-list").append(e)}if(!$("#task-list").children.length)$("#task-list").innerHTML='<div class="info-card"><p>No hay tareas todavía.</p></div>'}

async function loadWorld(){try{const r=await api("GET","/api/world"),entities=r.entities||[],relations=r.relations||[];$("#world-count").textContent=entities.length+" entidades";$("#world-list").innerHTML=entities.slice(0,60).map(x=>`<div class="info-card"><small>${esc(x.kind)} · ${Math.round((x.confidence||0)*100)}%</small><p><strong>${esc(x.label)}</strong></p><p>${relations.filter(y=>y.subject_id===x.id).slice(0,3).map(y=>esc(y.predicate)+" → "+esc((entities.find(z=>z.id===y.object_id)||{}).label||y.object_id)).join("<br>")||"Sin relaciones confirmadas"}</p></div>`).join("")||'<div class="info-card"><p>El modelo del hogar todavía está vacío.</p></div>'}catch{}}

async function loadVision(){try{const st=await api("GET","/api/vision/status");$("#vision-status").textContent=st.private_mode?"Modo privado activo":st.available?"Adaptador de visión disponible":"Sin cámara/adaptador activo";const r=await api("GET","/api/vision/detections");$("#vision-list").innerHTML=(r.detections||[]).slice(-30).reverse().map(d=>`<div class="info-card"><small>${esc(d.kind||"detección")}</small><p>${esc(d.label||"objeto")} · ${Math.round((d.confidence||0)*100)}%</p></div>`).join("")||'<div class="info-card"><p>Sin detecciones reales recientes.</p></div>'}catch{}}
async function loadDevices(){try{const r=await api("GET","/api/mobile/nodes");const root=$("#device-list");root.innerHTML=(r.nodes||[]).map(n=>`<div class="info-card" data-node="${esc(n.id)}"><header><small>${esc(n.platform)} · ${new Date(n.last_seen*1000).toLocaleString()}</small><small class="${n.paired&&!n.revoked?"device-auth":""}">${n.revoked?"revocado":n.paired?"autorizado":"sin emparejar"}</small></header><p><strong>${esc(n.name)}</strong></p><p>${esc(Object.keys(n.capabilities||{}).filter(k=>n.capabilities[k]).join(", ")||"sin capacidades")}</p>${n.paired&&!n.revoked?`<div class="device-actions"><button data-revoke="${esc(n.id)}">Revocar acceso</button></div>`:""}</div>`).join("")||'<div class="info-card"><p>No hay dispositivos enlazados todavía.</p></div>';$("[data-revoke]",root).forEach(b=>b.onclick=async()=>{if(!confirm("¿Revocar el acceso de este teléfono a BAY-E?"))return;try{await api("DELETE","/api/mobile/nodes/"+encodeURIComponent(b.dataset.revoke));toast("Acceso móvil revocado");await loadDevices()}catch(e){toast("Abre BAY-E desde 127.0.0.1 para revocar dispositivos")}})}catch{}}

async function loadLogs(){try{const r=await api("GET","/api/logs?limit=40");$("#log-list").innerHTML=(r.logs||[]).map(x=>`<div class="info-card"><small>${new Date(x.ts*1000).toLocaleTimeString()} · ${esc(x.level)} · ${esc(x.module)}</small><p>${esc(x.human||x.technical||"evento")}</p></div>`).join("")}catch{}}
async function loadSystem(){try{const [d,m]=await Promise.all([api("GET","/api/diagnostics"),api("GET","/api/modules")]);const rows=[["Guardian",d.guardian?.overall],["Modelo",d.models?.last_provider],["OpenCV",d.vision?.opencv?"ok":"offline"],["STT",d.audio?.stt?"ok":"offline"],["TTS",d.audio?.tts?"ok":"offline"],["Robot",d.robot?.connected?"ok":"offline"]];$("#diagnostics").innerHTML=rows.map(([k,v])=>`<div class="info-card"><small>${esc(k)}</small><p class="${v==="ok"?"status-ok":v==="offline"?"status-off":"status-warn"}">${esc(v||"unknown")}</p></div>`).join("");$("#module-list").innerHTML=(m.modules||[]).map(x=>`<div class="info-card"><header><small>${esc(x.name)} · ${esc(x.version)}</small><input type="checkbox" data-module="${esc(x.id)}" ${x.enabled?"checked":""}></header><p>${esc(x.desc||"")}</p></div>`).join("");$$("[data-module]",$("#module-list")).forEach(x=>x.onchange=async()=>{await api("POST",`/api/modules/${x.dataset.module}/toggle`,{on:x.checked});await refreshState()});await loadLogs()}catch{}}

function openDrawer(name){App.panel=name;$("#drawer").classList.add("open");$$(".drawer-view").forEach(v=>v.classList.toggle("active",v.dataset.view===name));$("#drawer-title").textContent={mind:"Corazón y mente",memory:"Memoria",tasks:"Tareas y rutinas",world:"Casa y mundo",vision:"Visión",control:"Cuerpo y control",devices:"Dispositivos",system:"Sistema y privacidad"}[name]||"BAY-E";if(name==="mind")loadRules();if(name==="memory")loadMemory();if(name==="tasks")loadTasks();if(name==="world")loadWorld();if(name==="vision")loadVision();if(name==="devices")loadDevices();if(name==="system")loadSystem()}

async function command(cmd,payload={}){try{const r=await api("POST","/api/command",{cmd,payload});if(r.blocked)toast("Bloqueado por seguridad: "+(r.reason||"acción no disponible"));else toast("Comando aceptado");await refreshState();return r}catch{toast("No pude ejecutar el comando")}}
function setupSpeech(){const SR=window.SpeechRecognition||window.webkitSpeechRecognition;if(!SR){$("#voice-btn").onclick=()=>toast("Dictado no disponible en este navegador");return}const r=new SR();r.lang="es-ES";r.interimResults=false;r.onstart=()=>{$("#activity").textContent="Escuchando…";$("#voice-btn").classList.add("listening");for(const f of Object.values(App.faces))Face.update(f,{listening:true,emotion:"attentive"})};r.onend=()=>{$("#activity").textContent="Listo";$("#voice-btn").classList.remove("listening");refreshState()};r.onresult=e=>send(e.results[0][0].transcript);r.onerror=()=>toast("No pude escuchar el micrófono");$("#voice-btn").onclick=()=>{try{r.start()}catch{}}}

document.addEventListener("DOMContentLoaded",async()=>{
  App.faces.main=Face.create($("#face-main"));App.faces.mind=Face.create($("#face-mind"),{small:true});
  $("#new-chat").onclick=newThread;$("#home-btn").onclick=()=>selectThread("default");$("#menu-btn").onclick=()=>$("#sidebar").classList.add("open");$("#side-close").onclick=()=>$("#sidebar").classList.remove("open");
  $("#mind-btn").onclick=()=>openDrawer("mind");$("[data-panel]").forEach(b=>b.onclick=()=>openDrawer(b.dataset.panel));$("#drawer-close").onclick=()=>$("#drawer").classList.remove("open");$("[data-prompt]").forEach(b=>b.onclick=()=>{if(b.closest(".drawer"))$("#drawer").classList.remove("open");send(b.dataset.prompt)});
  $("#pair-mobile-btn").onclick=async()=>{try{const r=await api("POST","/api/mobile/pair/start",{ttl_seconds:300});$("#pair-code-value").textContent=r.code;$("#pair-code-display").hidden=false;const end=Number(r.expires_at||0)*1000;$("#pair-code-expiry").textContent="Caduca a las "+new Date(end).toLocaleTimeString([], {hour:"2-digit",minute:"2-digit"});toast("Código listo · úsalo una sola vez")}catch(e){toast("Genera el código abriendo BAY-E en 127.0.0.1")}};
  $("#send-btn").onclick=()=>send();$("#prompt").oninput=grow;$("#prompt").onkeydown=e=>{if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();send()}};
  $("#memory-search").oninput=loadMemory;$("#memory-type").onchange=loadMemory;
  $("#rule-form").onsubmit=async e=>{e.preventDefault();await api("POST","/api/mind/rules",{kind:$("#rule-kind").value,content:$("#rule-content").value,priority:Number($("#rule-priority").value),enabled:true});$("#rule-content").value="";await loadRules();toast("Añadido a la mente de BAY-E")};
  $("#task-form").onsubmit=async e=>{e.preventDefault();await api("POST","/api/tasks",{title:$("#task-title").value,description:$("#task-description").value,repeat:$("#task-repeat").value});$("#task-title").value="";$("#task-description").value="";await loadTasks();toast("Tarea creada")};
  $("#edit-cancel").onclick=()=>$("#edit-modal").hidden=true;$("#edit-save").onclick=async()=>{if(!App.editing)return;await api("PUT","/api/chat/messages/"+App.editing.id,{content:$("#edit-text").value});$("#edit-modal").hidden=true;App.editing=null;await loadMessages();toast("Mensaje actualizado")};
  $$(".mode-grid [data-mode]").forEach(b=>b.onclick=()=>command("set_mode",{mode:b.dataset.mode}));$$("[data-move]").forEach(b=>b.onclick=()=>command("move",{dir:b.dataset.move}));$("#return-base").onclick=()=>command("return_base");$("#toggle-autonomy").onclick=()=>command("toggle_autonomy",{on:!App.state?.autonomy});$("#estop").onclick=()=>command("emergency_stop");
  $("#private-mode").onchange=async e=>{await api("PUT","/api/settings/privacy",{private_mode:e.target.checked});await refreshState()};$("#autonomy-setting").onchange=async e=>{await api("PUT","/api/settings/autonomy",{enabled:e.target.checked});await refreshState()};
  $("#backup-btn").onclick=async()=>{const r=await api("POST","/api/backups",{});toast("Backup creado: "+String(r.file||"").split(/[\\/]/).pop())};$("#retention-btn").onclick=async()=>{const r=await api("POST","/api/privacy/enforce-retention",{});toast("Retención aplicada · "+(r.deleted||0)+" eliminadas")};$("#purge-btn").onclick=async()=>{if(!confirm("Esto borrará todas las memorias y perfiles biométricos locales. ¿Continuar?"))return;await api("POST","/api/privacy/purge",{mode:"all"});toast("Memoria eliminada");loadMemory()};
  setupSpeech();connectWS();await loadThreads();if(!App.threads.some(t=>t.id===App.thread))App.thread=App.threads[0]?.id||"default";await loadMessages();await refreshState();setInterval(refreshState,15000);
});
