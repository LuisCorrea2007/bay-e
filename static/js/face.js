const Face=(()=>{
  const instances=[];
  const pointer={x:0,y:0,active:false};

  function rand(a,b){return a+Math.random()*(b-a)}
  function clamp(v,a=-1,b=1){return Math.max(a,Math.min(b,v))}

  function create(el,{small=false}={}){
    if(!el)return null;
    el.innerHTML='<div class="baymax-face '+(small?'small':'')+'" aria-label="Cara de BAY-E">'+
      '<svg viewBox="0 0 320 150" role="img" aria-hidden="true">'+
        '<g class="face-track">'+
          '<circle class="eye left" cx="92" cy="75" r="13.5"></circle>'+
          '<line class="bridge" x1="106" y1="75" x2="214" y2="75"></line>'+
          '<circle class="eye right" cx="228" cy="75" r="13.5"></circle>'+
        '</g>'+
      '</svg>'+
    '</div>';
    const i={
      root:el.querySelector(".baymax-face"),
      track:el.querySelector(".face-track"),
      eyes:[...el.querySelectorAll(".eye")],
      state:"idle",
      blinkAt:Date.now()+rand(1900,5200),
      gaze:{x:0,y:0},
      target:{x:0,y:0},
      eyeOpen:1,
      lastStateAt:Date.now(),
      nextIdleLook:Date.now()+rand(2500,6500)
    };
    instances.push(i);
    return i;
  }

  function stateFrom(expr){
    if(expr.listening)return "listening";
    if(expr.thinking)return "thinking";
    if(expr.speaking)return "speaking";
    if(expr.emotion==="sleepy")return "sleeping";
    if(expr.emotion==="curious")return "curious";
    if(expr.emotion==="worried")return "worried";
    if(expr.emotion==="bored")return "bored";
    if(expr.emotion==="happy"||expr.emotion==="excited")return "happy";
    return "idle";
  }

  function update(i,expr={}){
    if(!i)return;
    const next=stateFrom(expr);
    if(next!==i.state){i.state=next;i.lastStateAt=Date.now()}
    i.root.dataset.state=i.state;
    i.eyeOpen=clamp(Number(expr.eyeOpen??.92),.12,1.15);
    i.target.x=clamp(Number(expr.gaze?.x||0));
    i.target.y=clamp(Number(expr.gaze?.y||0));
  }

  function blink(i){
    if(i.state==="sleeping")return;
    i.root.classList.add("blink");
    setTimeout(()=>i.root.classList.remove("blink"),115+rand(0,45));
    i.blinkAt=Date.now()+rand(2400,6200);
  }

  function idleLook(i,now){
    if(now<i.nextIdleLook||pointer.active)return;
    const amount=i.state==="curious"?.72:i.state==="bored"?.28:.42;
    i.target.x=rand(-amount,amount);
    i.target.y=rand(-amount*.35,amount*.35);
    i.nextIdleLook=now+rand(2600,6500);
  }

  function animate(i,now){
    if(now>i.blinkAt)blink(i);
    idleLook(i,now);

    let tx=i.target.x,ty=i.target.y;
    if(pointer.active && ["idle","happy","curious","listening"].includes(i.state)){
      tx=pointer.x*(i.state==="listening"?.35:.62);
      ty=pointer.y*.28;
    }
    if(i.state==="thinking"){
      tx=Math.sin(now/850)*.58;
      ty=-.18+Math.sin(now/1300)*.08;
    }
    if(i.state==="sleeping"){tx=0;ty=.08}
    if(i.state==="worried"){tx*=.35;ty=.1}
    if(i.state==="bored"){ty=.13}

    i.gaze.x+=(tx-i.gaze.x)*.045;
    i.gaze.y+=(ty-i.gaze.y)*.045;

    const x=i.gaze.x*9.5;
    const y=i.gaze.y*4.2;
    let rot=0;
    if(i.state==="curious")rot=Math.sin(now/1700)*.75;
    if(i.state==="thinking")rot=Math.sin(now/2100)*.45;

    i.track.setAttribute("transform","translate("+x.toFixed(2)+" "+y.toFixed(2)+") rotate("+rot.toFixed(2)+" 160 75)");

    let open=i.eyeOpen;
    if(i.state==="sleeping")open=.12;
    else if(i.state==="bored")open=Math.min(open,.58);
    else if(i.state==="happy")open=Math.min(open,.88);
    else if(i.state==="listening")open=Math.max(open,1.02);

    for(const eye of i.eyes){
      if(!i.root.classList.contains("blink"))eye.style.transform="scaleY("+open.toFixed(3)+")";
    }
  }

  function loop(){
    const now=Date.now();
    for(const i of instances)animate(i,now);
    requestAnimationFrame(loop);
  }

  window.addEventListener("pointermove",e=>{
    pointer.x=clamp((e.clientX/window.innerWidth-.5)*2);
    pointer.y=clamp((e.clientY/window.innerHeight-.5)*2);
    pointer.active=true;
  },{passive:true});
  window.addEventListener("pointerleave",()=>{pointer.active=false});

  requestAnimationFrame(loop);
  return{create,update};
})();