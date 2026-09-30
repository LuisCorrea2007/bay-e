import './style.css';
import { Camera, CameraResultType, CameraSource } from '@capacitor/camera';
import { Device } from '@capacitor/device';
import { Geolocation } from '@capacitor/geolocation';
import { Haptics, ImpactStyle } from '@capacitor/haptics';
import { Motion } from '@capacitor/motion';
import { Network } from '@capacitor/network';
import { SpeechRecognition } from '@capacitor-community/speech-recognition';

const $=s=>document.querySelector(s);
const state={core:localStorage.getItem('baye_core')||'',nodeId:'',thread:'default',motion:null,network:null,battery:null,listening:false};

function toast(t){const e=$('#toast');e.textContent=t;e.classList.add('show');setTimeout(()=>e.classList.remove('show'),1600)}
function base(path){return state.core.replace(/\/$/,'')+path}
async function api(method,path,body,form=false){
  if(!state.core)throw new Error('Configura la URL de BAY-E Core');
  const opts={method,headers:{}};
  if(body!==undefined){if(form)opts.body=body;else{opts.headers['Content-Type']='application/json';opts.body=JSON.stringify(body)}}
  const r=await fetch(base(path),opts);if(!r.ok)throw new Error(await r.text());return r.json()
}
function add(role,text,meta=''){const e=document.createElement('div');e.className='message '+role;e.textContent=text;if(meta){const s=document.createElement('small');s.textContent=meta;e.append(s)}$('#messages').append(e);$('#hero').hidden=true;$('#chat').scrollTop=$('#chat').scrollHeight}
function face(cls=''){const e=$('#face');e.className='face '+cls}
function blink(){const e=$('#face');e.classList.add('blink');setTimeout(()=>e.classList.remove('blink'),140);setTimeout(blink,2200+Math.random()*3500)}setTimeout(blink,2000);

async function ensureDevice(){
  const id=await Device.getId();state.nodeId=id.identifier;
  state.battery=await Device.getBatteryInfo();state.network=await Network.getStatus();
  await Network.addListener('networkStatusChange',s=>state.network=s);
  try{await Motion.addListener('accel',ev=>state.motion=ev.accelerationIncludingGravity||ev.acceleration)}catch{}
}
async function heartbeat(){
  if(!state.core||!state.nodeId)return;
  try{
    const info=await Device.getInfo();state.battery=await Device.getBatteryInfo();
    const payload={id:state.nodeId,name:info.name||info.model||'Android BAY-E',platform:info.platform||'android',
      capabilities:{camera:true,microphone:true,battery:true,network:true,motion:true,geolocation:true},
      telemetry:{battery:state.battery,network:state.network,motion:state.motion,model:info.model,osVersion:info.osVersion}};
    await api('POST','/api/mobile/heartbeat',payload);$('#status').textContent='conectado al Core';
  }catch(e){$('#status').textContent='sin conexión'}
}
async function loadChat(){if(!state.core)return;try{const r=await api('GET','/api/chat/history?thread_id='+state.thread+'&limit=100');$('#messages').innerHTML='';for(const m of r.messages||[])add(m.role==='baye'?'baye':'user',m.content);$('#hero').hidden=(r.messages||[]).length>0}catch(e){toast('No pude conectar con el Core')}}
async function send(text){text=(text||$('#prompt').value).trim();if(!text)return;$('#prompt').value='';add('user',text);face('thinking');try{const r=await api('POST','/api/chat/send',{text,thread_id:state.thread});add('baye',r.baye.content,(r.model?.provider||'')+' · '+(r.model?.model||''));speak(r.baye.content);await Haptics.impact({style:ImpactStyle.Light})}catch(e){add('baye','No pude contactar mi Core: '+e.message)}face('')}
function speak(text){if(!('speechSynthesis'in window))return;const u=new SpeechSynthesisUtterance(text);u.lang='es-ES';u.rate=.94;speechSynthesis.cancel();speechSynthesis.speak(u)}

async function listen(){
  try{
    const p=await SpeechRecognition.checkPermissions();if(p.speechRecognition!=='granted')await SpeechRecognition.requestPermissions();
    face('listening');state.listening=true;
    const r=await SpeechRecognition.start({language:'es-ES',maxResults:1,prompt:'Habla con BAY-E',partialResults:false,popup:false});
    state.listening=false;face('');if(r.matches?.[0])send(r.matches[0]);
  }catch(e){state.listening=false;face('');toast('No pude usar el micrófono')}
}
function b64blob(b64,type='image/jpeg'){const bytes=atob(b64),arr=new Uint8Array(bytes.length);for(let i=0;i<bytes.length;i++)arr[i]=bytes.charCodeAt(i);return new Blob([arr],{type})}
async function camera(){
  try{
    const photo=await Camera.getPhoto({quality:72,resultType:CameraResultType.Base64,source:CameraSource.Camera,correctOrientation:true,width:1280});
    const fd=new FormData();fd.append('node_id',state.nodeId);fd.append('frame',b64blob(photo.base64String,'image/'+(photo.format||'jpeg')),'mobile.'+(photo.format||'jpeg'));
    const r=await api('POST','/api/mobile/vision',fd,true);const labels=(r.detections||[]).map(x=>x.label).filter(Boolean);toast(labels.length?'Vi: '+labels.slice(0,4).join(', '):'Imagen observada; sin detecciones claras');
  }catch(e){toast('Cámara: '+e.message)}
}
async function locationOnce(){
  try{
    const p=await Geolocation.requestPermissions();if(p.location!=='granted'&&p.coarseLocation!=='granted')return toast('Permiso de ubicación denegado');
    const pos=await Geolocation.getCurrentPosition({enableHighAccuracy:false,timeout:8000});
    const text='Ubicación compartida una vez desde mi teléfono: lat '+pos.coords.latitude.toFixed(5)+', lon '+pos.coords.longitude.toFixed(5)+'.';
    await api('POST','/api/chat/send',{text:'Recuerda temporalmente este contexto de ubicación: '+text,thread_id:state.thread});toast('Ubicación compartida con BAY-E');
  }catch(e){toast('No pude obtener la ubicación')}
}

$('#send').onclick=()=>send();$('#prompt').onkeydown=e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send()}};$('#mic-btn').onclick=listen;$('#camera-btn').onclick=camera;$('#location-btn').onclick=locationOnce;$('#sensor-btn').onclick=async()=>{await heartbeat();toast('Sensores sincronizados')};
$('#settings-btn').onclick=()=>{$('#core-url').value=state.core;$('#settings').showModal()};$('#save-settings').onclick=()=>{state.core=$('#core-url').value.trim();localStorage.setItem('baye_core',state.core);setTimeout(()=>{heartbeat();loadChat()},100)};
await ensureDevice();if(!state.core)$('#settings').showModal();else{await heartbeat();await loadChat()}setInterval(heartbeat,15000);
