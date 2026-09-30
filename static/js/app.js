const $=(s,r=document)=>r.querySelector(s), $$=(s,r=document)=>[...r.querySelectorAll(s)];
const App={thread:"default",threads:[],state:null,faces:{},editing:null,panel:"mind",busy:false};

function esc(s=""){return String(s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]))}
async function api(method,path,body){const o={method,headers:{}};if(body!==undefined){o.headers["Content-Type"]="application/json";o.body=JSON.stringify(body)}const r=await fetch(path,o);if(!r.ok)throw new Error(await r.text());return r.json()}
function toast(t){const e=$("#toast");e.textContent=t;e.classList.add("show");setTimeout(()=>e.classList.remove("show"),1600)}
function setEmpty(){const empty=$("#empty-state");empty.hidden=$("#messages").children.length>0}
function scrollBottom(){$("#conversation").scrollTop=$("#conversation").scrollHeight}
function speak(text){if(!("speechSynthesis" in window))return toast("Lectura en voz alta no disponible");speechSynthesis.cancel();const u=new SpeechSynthesisUtterance(text);u.lang="es-ES";u.rate=.94;u.pitch=1.0;speechSynthesis.speak(u)}
async function copyText(text){try{await navigator.clipboard.writeText(text);toast("Copiado")}catch{toast("No pude copiar")}}

function tools(m){return `<div class="message-tools">
<button data-act="copy" title="Copiar">Copiar</button>
<button data-act="speak" title="Leer en voz alta">Leer</button>
<button data-act="edit" title="Editar">Editar</button>
<button data-act="remember" title="Recordar">Recordar</button>
<button data-act="task" title="Crear tarea">Tarea</button>
<button data-act="delete" title="Borrar">Borrar</button>
</div>`}
function renderMessage(m){
  const el=document.createElement("article");el.className="message "+(m.role==="baye"?"baye":"user");el.dataset.id=m.id;el.dataset.content=m.content;
  el.innerHTML=`<div class="message-head"><div class="avatar">${m.role==="baye"?"BE":"TÚ"}</div><strong>${m.role==="baye"?"BAY-E":"Tú"}</strong></div><div class="bubble">${esc(m.content)}</div>${tools(m)}`;
  el.querySelector(".message-tools").onclick=async ev=>{
    const b=ev.target.closest("button");if(!b)return;const act=b.dataset.act;
    if(act==="copy")return copyText(m.content);if(act==="speak")return speak(m.content);
    if(act==="edit"){App.editing=m;$("#edit-text").value=m.content;$("#edit-modal").hidden=false;return}
    if(act==="delete"){if(!confirm("¿Borrar este mensaje?"))return;await api("DELETE","/api/chat/messages/"+m.id);await loadMessages();return}
    if(act==="remember"){await api("POST","/api/chat/flag",{id:m.id,action:"remember"});toast("Guardado en memoria");return}
    if(act==="task"){await api("POST","/api/chat/flag",{id:m.id,action:"task"});toast("Convertido en tarea");return}
  };
  $("#messages").append(el);setEmpty();return el
}
function thinking(on){let e=$("#thinking");if(on&&!e){e=document.createElement("article");e.id="thinking";e.className="message baye";e.innerHTML='<div class="message-head"><div class="avatar">BE</div><strong>BAY-E</strong></div><div class="thinking"><i></i><i></i><i></i></div>';$("#messages").append(e);scrollBottom()}if(!on&&e)e.remove()}

async function loadThreads(){const r=await api("GET","/api/chat/threads");App.threads=r.threads||[];$("#threads").innerHTML="";for(const t of App.threads){const row=document.createElement("div");row.className="thread "+(t.id===App.thread?"active":"");row.innerHTML=`<button class="thread-main">${esc(t.title)}</button><button class="thread-menu">⋯</button>`;row.querySelector(".thread-main").onclick=()=>selectThread(t.id);row.querySelector(".thread-menu").onclick=async()=>{const a=prompt("Renombrar chat. Déjalo vacío para borrar:",t.title);if(a===null)return;if(a.trim()){await api("PUT","/api/chat/threads/"+t.id,{title:a.trim()})}else if(t.id!=="default"&&confirm("¿Borrar este chat?")){await api("DELETE","/api/chat/threads/"+t.id);if(App.thread===t.id)App.thread="default"}await loadThreads();await loadMessages()};$("#threads").append(row)}}
async function selectThread(id){App.thread=id;await loadThreads();await loadMessages();const t=App.threads.find(x=>x.id===id);$("#thread-title").textContent=t?.title||"BAY-E";$("#sidebar").classList.remove("open")}
async function newThread(){const r=await api("POST","/api/chat/threads",{title:"Nuevo chat"});App.thread=r.thread.id;await loadThreads();await loadMessages();$("#prompt").focus()}
async function loadMessages(){const r=await api("GET","/api/chat/history?thread_id="+encodeURIComponent(App.thread)+"&limit=500");$("#messages").innerHTML="";for(const m of r.messages||[])renderMessage(m);setEmpty();scrollBottom()}

async function send(text){text=(text||$("#prompt").value).trim();if(!text||App.busy)return;App.busy=true;$("#send-btn").disabled=true;$("#prompt").value="";grow();const local={id:"temp_"+Date.now(),role:"user",content:text};renderMessage(local);thinking(true);$("#activity").textContent="BAY-E está pensando…";try{const r=await api("POST","/api/chat/send",{text,thread_id:App.thread});thinking(false);await loadMessages();await loadThreads();$("#provider").textContent="IA · "+(r.model?.provider||"—");speak(r.baye.content);await refreshState()}catch(e){thinking(false);toast("Error al responder");console.error(e)}App.busy=false;$("#send-btn").disabled=false;$("#activity").textContent="Listo"}
function grow(){const e=$("#prompt");e.style.height="auto";e.style.height=Math.min(e.scrollHeight,180)+"px"}

async function refreshState(){try{const s=await api("GET","/api/state");App.state=s;$("#status-line").textContent=(s.mode_label||s.mode)+" · "+s.activity;$("#provider").textContent="IA · "+(s.model_provider||"—");for(const f of Object.values(App.faces))Face.update(f,s.expression||{});$("#mind-state").textContent=s.expression?.emotion||"neutral";$("#mind-mode").textContent=s.mode_label||s.mode;$("#mind-thought").textContent=s.last_thought||"—";$("#mind-reason").textContent=s.reason||"—";$("#mind-next").textContent=s.next_decision||"—"}catch{}}

async function loadRules(){const r=await api("GET","/api/mind/rules");$("#rule-list").innerHTML="";for(const x of r.rules||[]){const e=document.createElement("article");e.className="rule-card";e.innerHTML=`<header><span class="kind">${esc(x.kind)} · p${x.priority}</span><label><input type="checkbox" ${x.enabled?"checked":""}> activa</label></header><p>${esc(x.content)}</p><footer><span>${x.enabled?"Aplicándose":"Desactivada"}</span><button class="danger">Borrar</button></footer>`;e.querySelector("input").onchange=ev=>api("PUT","/api/mind/rules/"+x.id,{enabled:ev.target.checked}).then(loadRules);e.querySelector(".danger").onclick=()=>api("DELETE","/api/mind/rules/"+x.id).then(loadRules);$("#rule-list").append(e)}}
async function loadMemory(){const q=$("#memory-search").value;const r=await api("GET","/api/memories?q="+encodeURIComponent(q));$("#memory-list").innerHTML=(r.memories||[]).slice(0,100).map(m=>`<div class="info-card"><small>${esc(m.type)} · ${Math.round((m.confidence||0)*100)}%</small><p>${esc(m.content)}</p></div>`).join("")||'<div class="info-card"><p>Sin resultados.</p></div>'}
async function loadVision(){try{const st=await api("GET","/api/vision/status");$("#vision-status").textContent=st.available?"OpenCV disponible":"Sin cámara/adaptador activo";const r=await api("GET","/api/vision/detections");$("#vision-list").innerHTML=(r.detections||[]).slice(0,30).map(d=>`<div class="info-card"><small>${esc(d.kind||"detección")}</small><p>${esc(d.label||"objeto")} · ${Math.round((d.confidence||0)*100)}%</p></div>`).join("")||'<div class="info-card"><p>Sin detecciones reales recientes.</p></div>'}catch{}}
async function loadDevices(){try{const r=await api("GET","/api/mobile/nodes");$("#device-list").innerHTML=(r.nodes||[]).map(n=>`<div class="info-card"><small>${esc(n.platform)} · ${new Date(n.last_seen*1000).toLocaleString()}</small><p><strong>${esc(n.name)}</strong></p><p>${esc(Object.keys(n.capabilities||{}).filter(k=>n.capabilities[k]).join(", ")||"sin capacidades")}</p></div>`).join("")||'<div class="info-card"><p>No hay teléfonos enlazados todavía.</p></div>'}catch{}}
async function loadSystem(){const d=await api("GET","/api/diagnostics");const rows=[["Guardian",d.guardian?.overall],["Modelo",d.models?.last_provider],["OpenCV",d.vision?.opencv?"ok":"offline"],["STT",d.audio?.stt?"ok":"offline"],["TTS",d.audio?.tts?"ok":"offline"],["Robot",d.robot?.connected?"ok":"offline"]];$("#diagnostics").innerHTML=rows.map(([k,v])=>`<div class="info-card"><small>${esc(k)}</small><p class="${v==="ok"?"status-ok":v==="offline"?"status-off":"status-warn"}">${esc(v||"unknown")}</p></div>`).join("")}
function openDrawer(name){App.panel=name;$("#drawer").classList.add("open");$$(".drawer-view").forEach(v=>v.classList.toggle("active",v.dataset.view===name));$("#drawer-title").textContent={mind:"Corazón y mente",memory:"Memoria",vision:"Visión",devices:"Dispositivos",system:"Sistema"}[name];if(name==="mind")loadRules();if(name==="memory")loadMemory();if(name==="vision")loadVision();if(name==="devices")loadDevices();if(name==="system")loadSystem()}

function setupSpeech(){const SR=window.SpeechRecognition||window.webkitSpeechRecognition;if(!SR){$("#voice-btn").onclick=()=>toast("Micrófono por dictado no disponible en este navegador");return}const r=new SR();r.lang="es-ES";r.onstart=()=>$("#activity").textContent="Escuchando…";r.onend=()=>$("#activity").textContent="Listo";r.onresult=e=>send(e.results[0][0].transcript);$("#voice-btn").onclick=()=>r.start()}

document.addEventListener("DOMContentLoaded",async()=>{
 App.faces.main=Face.create($("#face-main"));App.faces.mind=Face.create($("#face-mind"),{small:true});
 $("#new-chat").onclick=newThread;$("#home-btn").onclick=()=>selectThread("default");$("#menu-btn").onclick=()=>$("#sidebar").classList.add("open");$("#side-close").onclick=()=>$("#sidebar").classList.remove("open");
 $("#mind-btn").onclick=()=>openDrawer("mind");$$("[data-panel]").forEach(b=>b.onclick=()=>openDrawer(b.dataset.panel));$("#drawer-close").onclick=()=>$("#drawer").classList.remove("open");$$("[data-prompt]").forEach(b=>b.onclick=()=>{if(b.closest(".drawer"))$("#drawer").classList.remove("open");send(b.dataset.prompt)});
 $("#send-btn").onclick=()=>send();$("#prompt").oninput=grow;$("#prompt").onkeydown=e=>{if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();send()}};
 $("#memory-search").oninput=loadMemory;$("#rule-form").onsubmit=async e=>{e.preventDefault();await api("POST","/api/mind/rules",{kind:$("#rule-kind").value,content:$("#rule-content").value,priority:Number($("#rule-priority").value),enabled:true});$("#rule-content").value="";await loadRules();toast("Añadido a la mente de BAY-E")};
 $("#edit-cancel").onclick=()=>$("#edit-modal").hidden=true;$("#edit-save").onclick=async()=>{if(!App.editing)return;await api("PUT","/api/chat/messages/"+App.editing.id,{content:$("#edit-text").value});$("#edit-modal").hidden=true;App.editing=null;await loadMessages();toast("Mensaje actualizado")};
 setupSpeech();await loadThreads();if(!App.threads.some(t=>t.id===App.thread))App.thread=App.threads[0]?.id||"default";await loadMessages();await refreshState();setInterval(refreshState,2500);
});

/* Companion UI shell interactions */
document.addEventListener("DOMContentLoaded",()=>{
  const scrim=document.querySelector("#sidebar-scrim");
  const sidebar=document.querySelector("#sidebar");
  if(scrim) scrim.addEventListener("click",()=>sidebar?.classList.remove("open"));
  document.addEventListener("keydown",e=>{
    if((e.metaKey||e.ctrlKey)&&e.key.toLowerCase()==="k"){
      e.preventDefault();
      if(typeof newThread==="function") newThread();
    }
    if(e.key==="Escape"){
      sidebar?.classList.remove("open");
      document.querySelector("#drawer")?.classList.remove("open");
      const modal=document.querySelector("#edit-modal");
      if(modal && !modal.hidden) modal.hidden=true;
    }
  });
});