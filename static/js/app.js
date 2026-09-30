const $=(s,r=document)=>r.querySelector(s), $$=(s,r=document)=>[...r.querySelectorAll(s)];
const UI={state:null,faces:{},busy:false,panel:"mind"};

function esc(s=""){return String(s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[c]))}
async function api(method,path,body){
  const opts={method,headers:{}};
  if(body!==undefined){opts.headers["Content-Type"]="application/json";opts.body=JSON.stringify(body)}
  const r=await fetch(path,opts); if(!r.ok) throw new Error(await r.text()); return r.json();
}
function toast(t){const el=$("#toast");el.textContent=t;el.classList.add("show");setTimeout(()=>el.classList.remove("show"),1800)}
function scrollBottom(){$("#conversation").scrollTop=$("#conversation").scrollHeight}
function setWelcome(){ $("#welcome").hidden=$("#messages").children.length>0 }
function addMessage(role,content,meta=""){
  const el=document.createElement("article");el.className="message "+role;
  el.innerHTML='<div class="avatar">'+(role==="baye"?"BE":"TÚ")+'</div><div><div class="bubble">'+esc(content)+'</div>'+(meta?'<div class="msg-meta">'+esc(meta)+'</div>':"")+'</div>';
  $("#messages").append(el);setWelcome();scrollBottom();return el;
}
function thinking(on){
  let el=$("#thinking");
  if(on&&!el){el=document.createElement("article");el.id="thinking";el.className="message baye";el.innerHTML='<div class="avatar">BE</div><div class="thinking-row"><i></i><i></i><i></i></div>';$("#messages").append(el);scrollBottom()}
  if(!on&&el)el.remove()
}
function speak(text){
  if(!("speechSynthesis" in window))return;
  speechSynthesis.cancel();const u=new SpeechSynthesisUtterance(text);u.lang="es-ES";u.rate=.97;u.pitch=1.02;
  u.onstart=()=>$("#activity-label").textContent="BAY-E está hablando";
  u.onend=()=>$("#activity-label").textContent="Listo";
  speechSynthesis.speak(u);
}
async function send(text){
  text=(text||$("#chat-input").value).trim();if(!text||UI.busy)return;
  UI.busy=true;$("#send-btn").disabled=true;$("#chat-input").value="";autoGrow();addMessage("user",text);thinking(true);$("#activity-label").textContent="BAY-E está pensando";
  try{
    const r=await api("POST","/api/chat/send",{text});thinking(false);addMessage("baye",r.baye.content,(r.model?.provider||"")+" · "+(r.model?.model||""));speak(r.baye.content);
    await refreshState(); if(UI.panel==="memory")loadMemory(); if(UI.panel==="system")loadDiagnostics();
  }catch(e){thinking(false);addMessage("baye","Tuve un problema al procesar eso: "+e.message);toast("Error de conversación")}
  UI.busy=false;$("#send-btn").disabled=false;$("#activity-label").textContent="Listo";
}
function autoGrow(){const el=$("#chat-input");el.style.height="auto";el.style.height=Math.min(el.scrollHeight,180)+"px"}
async function loadHistory(){
  try{const r=await api("GET","/api/chat/history?limit=120");$("#messages").innerHTML="";for(const m of r.messages||[])addMessage(m.role==="baye"?"baye":"user",m.content,m.emotion||"");setWelcome()}catch{}
}
function pct(v){return Math.round((Number(v)||0)*100)+"%"}
function renderState(s){
  UI.state=s;$("#status-line").textContent=(s.mode_label||s.mode||"activo")+" · "+(s.activity||"idle");
  $("#provider-pill").textContent="IA · "+(s.model_provider||"fallback");
  $("#mind-emotion").textContent=s.expression?.emotion||"neutral";$("#mind-activity").textContent=s.activity||"idle";$("#mind-thought").textContent=s.last_thought||"—";$("#mind-next").textContent=s.next_decision||"—";
  const keys=[["energy","energía"],["curiosity","curiosidad"],["boredom","aburrimiento"],["trust","confianza"],["attention","atención"],["mood","ánimo"]];
  $("#emotion-grid").innerHTML=keys.map(([k,l])=>'<div class="metric"><label>'+l+'</label><strong>'+pct(s.emotions?.[k])+'</strong></div>').join("");
  for(const f of Object.values(UI.faces)) Face.update(f,s.expression||{});
}
async function refreshState(){try{renderState(await api("GET","/api/state"))}catch{}}
function openPanel(name){
  UI.panel=name;$("#inspector").classList.add("open");$$(".panel-view").forEach(x=>x.classList.toggle("active",x.dataset.view===name));$$(".rail-action[data-panel]").forEach(x=>x.classList.toggle("active",x.dataset.panel===name));$("#panel-title").textContent={mind:"Mente",memory:"Memoria",vision:"Visión",system:"Sistema"}[name]||name;
  if(name==="memory")loadMemory();if(name==="vision")loadVision();if(name==="system")loadDiagnostics();
}
async function loadMemory(){
  const q=$("#memory-search").value.trim();try{const r=await api("GET","/api/memories?q="+encodeURIComponent(q));$("#memory-list").innerHTML=(r.memories||[]).slice(0,80).map(m=>'<div class="memory-item"><strong>'+esc(m.type)+' · '+Math.round((m.confidence||0)*100)+'%</strong><p>'+esc(m.content)+'</p><small>'+esc(m.source||"")+'</small></div>').join("")||'<div class="memory-item"><p>Sin recuerdos coincidentes.</p></div>'}catch{}
}
async function loadVision(){
  try{
    const st=await api("GET","/api/vision/status");$("#vision-status").textContent=st.available?"OpenCV listo":"sin adaptador/cámara activa";
    const d=await api("GET","/api/vision/detections");const arr=d.detections||[];$("#vision-detections").innerHTML=arr.slice(0,20).map(x=>'<div class="memory-item"><strong>'+esc(x.label||x.kind)+'</strong><p>confianza '+Math.round((x.confidence||0)*100)+'%</p></div>').join("")||'<div class="memory-item"><p>Sin detecciones reales recientes.</p></div>';
  }catch{$("#vision-status").textContent="visión no disponible"}
}
async function loadDiagnostics(){
  try{const d=await api("GET","/api/diagnostics");const rows=[];rows.push(["Guardian",d.guardian?.overall||"unknown"]);rows.push(["Modelo",d.models?.last_provider||"fallback"]);rows.push(["OpenCV",d.vision?.opencv?"ok":"offline"]);rows.push(["Detector de objetos",d.vision?.object_detector?"ok":"offline"]);rows.push(["STT",d.audio?.stt?"ok":"offline"]);rows.push(["TTS local",d.audio?.tts?"ok":"offline"]);rows.push(["Robot",d.robot?.connected?"ok":"offline"]);$("#diagnostics").innerHTML=rows.map(([k,v])=>'<div class="diag-row"><span>'+esc(k)+'</span><strong class="'+(v==="ok"?"status-ok":v==="offline"?"status-off":"status-warn")+'">'+esc(v)+'</strong></div>').join("")}catch{}
}
function newChat(){ $("#messages").innerHTML="";setWelcome();$("#chat-input").focus() }
function setupSpeech(){
  const SR=window.SpeechRecognition||window.webkitSpeechRecognition;if(!SR){$("#voice-btn").onclick=()=>toast("Dictado no disponible en este navegador");return}
  const r=new SR();r.lang="es-ES";r.interimResults=false;r.onstart=()=>$("#activity-label").textContent="Escuchando…";r.onend=()=>$("#activity-label").textContent="Listo";r.onresult=e=>{const t=e.results[0][0].transcript;$("#chat-input").value=t;send(t)};$("#voice-btn").onclick=()=>r.start()
}
document.addEventListener("DOMContentLoaded",async()=>{
  UI.faces.hero=Face.create($("#face-hero"),{size:150});UI.faces.mini=Face.create($("#face-mini"),{size:180,compact:true});UI.faces.panel=Face.create($("#face-panel"),{size:180,compact:true});
  $("#send-btn").onclick=()=>send();$("#chat-input").oninput=autoGrow;$("#chat-input").onkeydown=e=>{if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();send()}};
  $$("[data-prompt]").forEach(b=>b.onclick=()=>send(b.dataset.prompt));$$("[data-panel]").forEach(b=>b.onclick=()=>openPanel(b.dataset.panel));
  $("#inspector-toggle").onclick=()=>openPanel("mind");$("#panel-close").onclick=()=>$("#inspector").classList.remove("open");$("[data-action='new-chat']").onclick=newChat;
  $("#memory-search").oninput=()=>loadMemory();setupSpeech();await loadHistory();await refreshState();setInterval(refreshState,2500);
});
