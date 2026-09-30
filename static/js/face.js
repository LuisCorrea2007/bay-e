/* BAY-E Face 2.0
 * A deliberately minimal companion face: two eyes and one bridge.
 * Expression comes from gaze, eyelids, spacing, tilt and micro-motion.
 * No mouth, no fake lip-sync, no decorative sci-fi chrome.
 */
const Face=(()=>{
  const instances=[];
  const clamp=(v,a=-1,b=1)=>Math.max(a,Math.min(b,Number(v)||0));
  const rand=(a,b)=>a+Math.random()*(b-a);

  const PRESETS={
    idle:{open:.92,spread:1,tilt:0,y:0},
    neutral_face:{open:.92,spread:1,tilt:0,y:0},
    happy:{open:.76,spread:1.02,tilt:0,y:-1},
    curious:{open:1.08,spread:1.05,tilt:-1.5,y:-2},
    attentive:{open:1.12,spread:1.03,tilt:0,y:-1},
    thinking:{open:.84,spread:1,tilt:-2,y:-2},
    worried:{open:.88,spread:.97,tilt:2.4,y:1},
    bored:{open:.58,spread:1,tilt:0,y:2},
    sleepy:{open:.20,spread:1,tilt:0,y:4},
    sleeping:{open:.08,spread:1,tilt:0,y:5},
    excited:{open:1.14,spread:1.06,tilt:0,y:-2},
    listening:{open:1.12,spread:1.03,tilt:0,y:-1},
    speaking:{open:.82,spread:1.01,tilt:0,y:0}
  };

  function create(el,{small=false}={}){
    if(!el)return null;
    el.innerHTML=`<div class="baymax-face ${small?"small":""}" data-state="idle" role="img" aria-label="BAY-E atento">
      <svg viewBox="0 0 360 160" aria-hidden="true">
        <g class="face-breathe">
          <g class="face-track">
            <line class="bridge" x1="116" y1="80" x2="244" y2="80"></line>
            <ellipse class="eye eye-left" cx="98" cy="80" rx="15" ry="15"></ellipse>
            <ellipse class="eye eye-right" cx="262" cy="80" rx="15" ry="15"></ellipse>
          </g>
        </g>
      </svg>
      <span class="face-status" aria-hidden="true"></span>
    </div>`;

    const root=el.querySelector(".baymax-face");
    const i={
      host:el,root,track:root.querySelector(".face-track"),
      breathe:root.querySelector(".face-breathe"),
      eyes:[root.querySelector(".eye-left"),root.querySelector(".eye-right")],
      bridge:root.querySelector(".bridge"),
      state:"idle",emotion:"idle",open:.92,spread:1,tilt:0,y:0,
      serverGaze:{x:0,y:0},pointerGaze:{x:0,y:0},wander:{x:0,y:0},
      pointerUntil:0,wanderAt:Date.now()+rand(900,2200),
      blinkAt:Date.now()+rand(1800,4300),blinking:false,blinkTimer:null
    };

    const point=(clientX,clientY)=>{
      const r=el.getBoundingClientRect();
      if(!r.width||!r.height)return;
      i.pointerGaze.x=clamp(((clientX-r.left)/r.width-.5)*2);
      i.pointerGaze.y=clamp(((clientY-r.top)/r.height-.5)*2);
      i.pointerUntil=Date.now()+1400;
    };
    el.addEventListener("pointermove",e=>point(e.clientX,e.clientY),{passive:true});
    el.addEventListener("pointerleave",()=>{i.pointerUntil=0});
    instances.push(i);
    return i;
  }

  function update(i,expr={}){
    if(!i)return;
    let state=expr.emotion||"idle";
    if(expr.listening)state="listening";
    else if(expr.thinking)state="thinking";
    else if(expr.speaking)state="speaking";
    if(state==="sleepy"&&expr.breathing===false)state="sleeping";
    const p=PRESETS[state]||PRESETS.idle;
    i.state=state;i.emotion=expr.emotion||state;
    i.open=Math.max(.05,Math.min(1.2,Number(expr.eyeOpen)||p.open));
    i.spread=p.spread;i.tilt=p.tilt;i.y=p.y;
    i.serverGaze={
      x:clamp(expr.gaze&&expr.gaze.x),
      y:clamp(expr.gaze&&expr.gaze.y)
    };
    i.root.dataset.state=state;
    i.root.setAttribute("aria-label",`BAY-E: ${state}`);
  }

  function doBlink(i,doubleBlink=false){
    if(i.blinking||i.state==="sleeping")return;
    i.blinking=true;i.root.classList.add("blink");
    clearTimeout(i.blinkTimer);
    i.blinkTimer=setTimeout(()=>{
      i.root.classList.remove("blink");i.blinking=false;
      if(doubleBlink){
        setTimeout(()=>doBlink(i,false),115);
      }
    },105);
    i.blinkAt=Date.now()+rand(2400,5600);
  }

  function targetGaze(i,now){
    if(now>i.wanderAt){
      i.wander={x:rand(-.38,.38),y:rand(-.22,.20)};
      i.wanderAt=now+rand(1800,4200);
    }
    let g=now<i.pointerUntil?i.pointerGaze:i.serverGaze;
    let x=g.x*.62+i.wander.x*.38;
    let y=g.y*.55+i.wander.y*.35;
    if(i.state==="thinking"){x+=.28;y-=.22}
    if(i.state==="listening"){x*=.45;y*=.45}
    if(i.state==="sleeping"){x=0;y=.12}
    return{x:clamp(x),y:clamp(y)};
  }

  function frame(){
    const now=Date.now();
    for(const i of instances){
      if(now>i.blinkAt)doBlink(i,Math.random()<.16);
      const g=targetGaze(i,now);
      const speaking=i.state==="speaking";
      const listening=i.state==="listening";
      const pulse=speaking?Math.sin(now/145)*.025:0;
      const listenPulse=listening?Math.sin(now/310)*.018:0;
      const open=i.blinking?.045:Math.max(.05,i.open+pulse+listenPulse);
      const dx=g.x*9,dy=g.y*5+i.y;
      const spread=(i.spread-1)*16;

      i.eyes[0].setAttribute("cx",(98-spread+dx).toFixed(2));
      i.eyes[1].setAttribute("cx",(262+spread+dx).toFixed(2));
      for(const eye of i.eyes){
        eye.setAttribute("cy",(80+dy).toFixed(2));
        eye.setAttribute("ry",(15*open).toFixed(2));
      }
      i.eyes[0].setAttribute("transform",`rotate(${i.tilt} ${98-spread+dx} ${80+dy})`);
      i.eyes[1].setAttribute("transform",`rotate(${-i.tilt} ${262+spread+dx} ${80+dy})`);
      i.bridge.setAttribute("x1",(116-spread+dx).toFixed(2));
      i.bridge.setAttribute("x2",(244+spread+dx).toFixed(2));
      i.bridge.setAttribute("y1",(80+dy).toFixed(2));
      i.bridge.setAttribute("y2",(80+dy).toFixed(2));

      const breathe=i.state==="sleeping"?.004:.009;
      const s=1+Math.sin(now/1350)*breathe;
      i.breathe.setAttribute("transform",`translate(180 80) scale(${s.toFixed(4)}) translate(-180 -80)`);
    }
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
  return{create,update,blink:doBlink};
})();
