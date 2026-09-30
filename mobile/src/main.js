import './style.css';
import { Camera, CameraResultType, CameraSource } from '@capacitor/camera';
import { Device } from '@capacitor/device';
import { Geolocation } from '@capacitor/geolocation';
import { Haptics, ImpactStyle } from '@capacitor/haptics';
import { Motion } from '@capacitor/motion';
import { Network } from '@capacitor/network';
import { SpeechRecognition } from '@capacitor-community/speech-recognition';
import { SecureStorage } from '@aparajita/capacitor-secure-storage';
import { normalizeCoreUrl } from './core-url.js';

const $=s=>document.querySelector(s);
let storedCore='';
try{storedCore=normalizeCoreUrl(localStorage.getItem('baye_core')||'')}catch{localStorage.removeItem('baye_core')}
const state={core:storedCore,token:'',nodeId:'',thread:'default',motion:null,network:null,battery:null,listening:false};

function toast(t){const e=$('#toast');e.textContent=t;e.classList.add('show');setTimeout(()=>e.classList.remove('show'),1900)}
function base(path){return state.core.replace(/\/$/,'')+path}
async function initSecureStorage(){
  await SecureStorage.setKeyPrefix('baye_');
  state.token=(await SecureStorage.getItem('mobile_token'))||'';
}
async function saveToken(token){
  state.token=token||'';
  if(state.token)await SecureStorage.setItem('mobile_token',state.token);
  else await SecureStorage.removeItem('mobile_token');
  renderPairState();
}
async function api(method,path,body,form=false,auth=true){
  if(!state.core)throw new Error('Configura la URL de BAY-E Core');
  const opts={method,headers:{}};
  if(auth&&state.token)opts.headers.Authorization='Bearer '+state.token;
  if(body!==undefined){if(form)opts.body=body;else{opts.headers['Content-Type']='application/json';opts.body=JSON.stringify(body)}}
  const r=await fetch(base(path),opts);
  if(!r.ok){
    const raw=await r.text();
    let detail=raw;try{detail=JSON.parse(raw).detail||raw}catch{}
    const err=new Error(detail);err.status=r.status;throw err;
  }
  return r.json()
}
function add(role,text,meta=''){const e=document.createElement('div');e.className='message '+role;e.textContent=text;if(meta){const s=document.createElement('small');s.textContent=meta;e.append(s)}$('#messages').append(e);$('#hero').hidden=true;$('#chat').scrollTop=$('#chat').scrollHeight}
function face(cls=''){const e=$('#face');e.className='face '+cls}
function blink(){const e=$('#face');e.classList.add('blink');setTimeout(()=>e.classList.remove('blink'),140);setTimeout(blink,2200+Math.random()*3500)}setTimeout(blink,2000);
function renderPairState(){
  const paired=Boolean(state.token);
  $('#pair-state').textContent=paired?'Emparejado de forma segura':'Pendiente de emparejar';
  $('#pair-code').disabled=paired;
  $('#pair-code').placeholder=paired?'Token protegido en Android Keystore':'Código de 6 dígitos';
  $('#save-settings').textContent=paired?'Guardar URL':'Emparejar y guardar';
  $('#disconnect-btn').hidden=!paired;
}

async function ensureDevice(){
  const id=await Device.getId();state.nodeId=id.identifier;
  state.battery=await Device.getBatteryInfo();state.network=await Network.getStatus();
  await Network.addListener('networkStatusChange',s=>state.network=s);
  try{await Motion.addListener('accel',ev=>state.motion=ev.accelerationIncludingGravity||ev.acceleration)}catch{}
}
async function pairIfNeeded(){
  if(state.token)return;
  const code=$('#pair-code').value.trim();
  if(!/^\d{6}$/.test(code))throw new Error('Escribe el código de 6 dígitos generado por BAY-E Core');
  const info=await Device.getInfo();
  const r=await api('POST','/api/v1/mobile/pair/claim',{
    id:state.nodeId,code,name:info.name||info.model||'Android BAY-E',platform:info.platform||'android'
  },false,false);
  await saveToken(r.token);
  $('#pair-code').value='';
}
async function heartbeat(){
  if(!state.core||!state.nodeId||!state.token)return;
  try{
    const info=await Device.getInfo();state.battery=await Device.getBatteryInfo();
    const payload={id:state.nodeId,name:info.name||info.model||'Android BAY-E',platform:info.platform||'android',
      capabilities:{camera:true,microphone:true,battery:true,network:true,motion:true,geolocation:true},
      telemetry:{battery:state.battery,network:state.network,motion:state.motion,model:info.model,osVersion:info.osVersion}};
    await api('POST','/api/v1/mobile/heartbeat',payload);$('#status').textContent='conectado · seguro';
  }catch(e){
    $('#status').textContent=e.status===401?'emparejamiento requerido':'sin conexión';
    if(e.status===401){await saveToken('');$('#settings').showModal()}
  }
}
async function loadChat(){
  if(!state.core||!state.token)return;
  try{
    const q='?node_id='+encodeURIComponent(state.nodeId)+'&thread_id='+encodeURIComponent(state.thread)+'&limit=100';
    const r=await api('GET','/api/v1/mobile/chat/history'+q);
    $('#messages').innerHTML='';for(const m of r.messages||[])add(m.role==='baye'?'baye':'user',m.content);
    $('#hero').hidden=(r.messages||[]).length>0;
  }catch(e){toast(e.status===401?'Vuelve a emparejar este teléfono':'No pude conectar con el Core')}
}
async function send(text){
  text=(text||$('#prompt').value).trim();if(!text)return;
  if(!state.token){$('#settings').showModal();return toast('Empareja este teléfono primero')}
  $('#prompt').value='';add('user',text);face('thinking');
  try{
    const r=await api('POST','/api/v1/mobile/chat/send',{text,thread_id:state.thread,node_id:state.nodeId});
    add('baye',r.baye.content,(r.model?.provider||'')+' · '+(r.model?.model||''));
    await Haptics.impact({style:ImpactStyle.Light});await speak(r.baye.content);
  }catch(e){add('baye','No pude contactar mi Core: '+e.message)}
  face('');
}
async function speak(text){
  if(!text)return;
  face('speaking');
  try{
    const r=await fetch(base('/api/v1/audio/tts'),{method:'POST',headers:{'Content-Type':'application/json',...(state.token?{Authorization:'Bearer '+state.token}:{})},body:JSON.stringify({text})});
    if(r.ok){
      const blob=await r.blob(),url=URL.createObjectURL(blob),audio=new Audio(url);
      try{await new Promise((resolve,reject)=>{audio.onended=resolve;audio.onerror=reject;audio.play().catch(reject)});return}
      finally{URL.revokeObjectURL(url)}
    }
  }catch{}
  if(!('speechSynthesis'in window))return;
  await new Promise(resolve=>{const u=new SpeechSynthesisUtterance(text);u.lang='es-ES';u.rate=.94;u.onend=resolve;u.onerror=resolve;speechSynthesis.cancel();speechSynthesis.speak(u)});
}

async function listen(){
  if(!state.token){$('#settings').showModal();return}
  try{
    const p=await SpeechRecognition.checkPermissions();if(p.speechRecognition!=='granted')await SpeechRecognition.requestPermissions();
    face('listening');state.listening=true;
    const r=await SpeechRecognition.start({language:'es-ES',maxResults:1,prompt:'Habla con BAY-E',partialResults:false,popup:false});
    state.listening=false;face('');if(r.matches?.[0])send(r.matches[0]);
  }catch(e){state.listening=false;face('');toast('No pude usar el micrófono')}
}
function b64blob(b64,type='image/jpeg'){const bytes=atob(b64),arr=new Uint8Array(bytes.length);for(let i=0;i<bytes.length;i++)arr[i]=bytes.charCodeAt(i);return new Blob([arr],{type})}
async function camera(){
  if(!state.token){$('#settings').showModal();return}
  try{
    const photo=await Camera.getPhoto({quality:72,resultType:CameraResultType.Base64,source:CameraSource.Camera,correctOrientation:true,width:1280});
    const fd=new FormData();fd.append('node_id',state.nodeId);fd.append('frame',b64blob(photo.base64String,'image/'+(photo.format||'jpeg')),'mobile.'+(photo.format||'jpeg'));
    const r=await api('POST','/api/v1/mobile/vision',fd,true);const labels=(r.detections||[]).map(x=>x.label).filter(Boolean);
    toast(labels.length?'Vi: '+labels.slice(0,4).join(', '):'Imagen observada; sin detecciones claras');
  }catch(e){toast('Cámara: '+e.message)}
}
async function locationOnce(){
  if(!state.token){$('#settings').showModal();return}
  try{
    const p=await Geolocation.requestPermissions();if(p.location!=='granted'&&p.coarseLocation!=='granted')return toast('Permiso de ubicación denegado');
    const pos=await Geolocation.getCurrentPosition({enableHighAccuracy:false,timeout:8000});
    await api('POST','/api/v1/mobile/location',{node_id:state.nodeId,lat:pos.coords.latitude,lon:pos.coords.longitude,remember:false});
    toast('Ubicación compartida una vez; no se guardó en memoria');
  }catch(e){toast('No pude compartir la ubicación')}
}
async function saveSettings(){
  try{
    state.core=normalizeCoreUrl($('#core-url').value);
    localStorage.setItem('baye_core',state.core);
    await pairIfNeeded();
    $('#settings').close();
    await heartbeat();await loadChat();toast('Teléfono conectado con BAY-E');
  }catch(e){toast(e.message)}
}
async function disconnectLocal(){
  await saveToken('');$('#status').textContent='sin emparejar';$('#messages').innerHTML='';$('#hero').hidden=false;$('#settings').showModal();
}

$('#send').onclick=()=>send();$('#prompt').onkeydown=e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send()}};
$('#mic-btn').onclick=listen;$('#camera-btn').onclick=camera;$('#location-btn').onclick=locationOnce;$('#sensor-btn').onclick=async()=>{await heartbeat();toast('Sensores sincronizados')};
$('#settings-btn').onclick=()=>{$('#core-url').value=state.core;renderPairState();$('#settings').showModal()};
$('#save-settings').onclick=e=>{e.preventDefault();saveSettings()};$('#disconnect-btn').onclick=e=>{e.preventDefault();disconnectLocal()};

await initSecureStorage();await ensureDevice();renderPairState();
if(!state.core||!state.token){$('#settings').showModal()}else{await heartbeat();await loadChat()}
setInterval(heartbeat,15000);
