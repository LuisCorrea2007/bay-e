const Face=(()=>{
  const instances=[];
  function create(el,{small=false}={}){
    if(!el)return null;
    el.innerHTML=`<div class="baymax-face ${small?"small":""}" aria-label="Cara de BAY-E">
      <svg viewBox="0 0 320 150" role="img">
        <g class="face-track">
          <circle class="eye left" cx="92" cy="75" r="15"></circle>
          <line class="bridge" x1="108" y1="75" x2="212" y2="75"></line>
          <circle class="eye right" cx="228" cy="75" r="15"></circle>
        </g>
      </svg>
    </div>`;
    const i={root:el.querySelector(".baymax-face"),track:el.querySelector(".face-track"),eyes:[...el.querySelectorAll(".eye")],state:"idle",blinkAt:Date.now()+rand(1800,4800),gaze:0};
    instances.push(i);return i;
  }
  function rand(a,b){return a+Math.random()*(b-a)}
  function update(i,expr={}){
    if(!i)return;
    i.state=expr.listening?"listening":expr.thinking?"thinking":expr.speaking?"speaking":expr.emotion==="sleepy"?"sleeping":expr.emotion||"idle";
    i.root.dataset.state=i.state;
    const gx=Math.max(-1,Math.min(1,Number(expr.gaze?.x||0)));
    i.gaze=gx*8;
  }
  function blink(i){
    if(i.state==="sleeping")return;
    i.root.classList.add("blink");
    setTimeout(()=>i.root.classList.remove("blink"),145);
    i.blinkAt=Date.now()+rand(2200,5600);
  }
  function loop(){
    const now=Date.now();
    for(const i of instances){
      if(now>i.blinkAt)blink(i);
      let x=i.gaze;
      if(i.state==="thinking")x+=Math.sin(now/650)*5;
      if(i.state==="listening")x*=.35;
      i.track.setAttribute("transform",`translate(${x.toFixed(1)} 0)`);
    }
    requestAnimationFrame(loop);
  }
  requestAnimationFrame(loop);
  return{create,update};
})();