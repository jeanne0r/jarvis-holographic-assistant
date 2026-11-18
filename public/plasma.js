/* Procedural light, rendered on the GPU. Audio never passes through this effect. */
(() => {
  const canvas = document.querySelector('#plasmaCore');
  const stage = document.querySelector('.command-stage');
  const sheet = document.querySelector('#cockpitSheet');
  let gl;
  try {gl=canvas.getContext('webgl',{alpha:true,antialias:false,depth:false,stencil:false,premultipliedAlpha:false,powerPreference:'low-power'});} catch {return;}
  if(!gl)return;
  const vertex='attribute vec2 p;void main(){gl_Position=vec4(p,0.,1.);}';
  const fragment=`precision mediump float;
  uniform vec2 size;uniform float time;uniform float strength;
  float band(float x,float width){return exp(-abs(x)*width);}
  void main(){
    vec2 uv=(gl_FragCoord.xy-.5*size)/min(size.x,size.y)*2.;
    float radius=length(uv);float sphere=.63;float inside=step(radius,sphere);
    float z=sqrt(max(0.,sphere*sphere-radius*radius));
    vec3 p=vec3(uv,z)/sphere;
    float a=time*.16;float c=cos(a),s=sin(a);
    p.xz=mat2(c,-s,s,c)*p.xz;
    float ang=atan(p.y,p.x);float waves=sin(p.x*8.+p.z*5.+time*.6)*.11+sin(p.y*13.-p.z*7.-time*.33)*.05;
    float currents=band(sin(p.y*10.+p.x*3.+p.z*5.+waves*7.+time*.5),22.);
    float cross=band(sin(p.x*9.-p.y*4.+p.z*8.+waves*9.-time*.27),32.);
    float ribbons=band(sin(p.y*5.+p.z*4.+sin(p.x*5.+time*.3)*.7),48.);
    float edge=band(radius-sphere,115.);
    float aura=exp(-max(0.,radius-sphere)*10.)*.14;
    float core=exp(-radius*radius*28.);
    float flare=exp(-abs(uv.y+.07*sin(time*.3))*100.)*exp(-abs(uv.x)*3.3)*.17;
    float halo=band(radius-(.77+.006*sin(ang*22.+time*.5)),130.)*.1;
    float light=(currents*.55+cross*.28+ribbons*.75)*inside;
    vec3 color=vec3(.01,.14,.21)*(inside*.8+aura)+vec3(.07,.7,1.)*(light+edge*.8+aura+halo);
    color+=vec3(.55,1.,1.)*pow(max(0.,light),2.)*.8;
    color+=vec3(.38,.91,1.)*core*(.8+strength*.75)+vec3(.7,1.,1.)*exp(-radius*radius*180.)*1.7;
    color+=vec3(.23,.69,1.)*flare;
    float amber=band(sin(p.z*7.-p.y*3.+p.x*4.+time*.22),60.)*inside*.12;
    color+=vec3(1.,.46,.12)*amber;
    color*=1.+strength*.38;
    float alpha=clamp(max(max(color.r,color.g),color.b),0.,1.);
    gl_FragColor=vec4(color,alpha);
  }`;
  let program;
  function compile(type,source){const shader=gl.createShader(type);gl.shaderSource(shader,source);gl.compileShader(shader);if(!gl.getShaderParameter(shader,gl.COMPILE_STATUS))throw Error('shader');return shader;}
  try {program=gl.createProgram();gl.attachShader(program,compile(gl.VERTEX_SHADER,vertex));gl.attachShader(program,compile(gl.FRAGMENT_SHADER,fragment));gl.linkProgram(program);if(!gl.getProgramParameter(program,gl.LINK_STATUS))return;}catch{return;}
  gl.useProgram(program);
  const buffer=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,buffer);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array([-1,-1,1,-1,-1,1,-1,1,1,-1,1,1]),gl.STATIC_DRAW);
  const p=gl.getAttribLocation(program,'p');gl.enableVertexAttribArray(p);gl.vertexAttribPointer(p,2,gl.FLOAT,false,0,0);
  const size=gl.getUniformLocation(program,'size'),time=gl.getUniformLocation(program,'time'),strength=gl.getUniformLocation(program,'strength');
  const reduced=matchMedia('(prefers-reduced-motion: reduce)');
  let visible=true,frame=0,last=0,elapsed=0,disposed=false;
  function resize(){const r=canvas.getBoundingClientRect(),scale=Math.min(devicePixelRatio||1,1.25,640/Math.max(1,r.width,r.height));canvas.width=Math.max(1,Math.round(r.width*scale));canvas.height=Math.max(1,Math.round(r.height*scale));gl.viewport(0,0,canvas.width,canvas.height);}
  function draw(now){frame=0;if(disposed||document.hidden||!visible||sheet.open)return;
    if(now-last>=40||reduced.matches){elapsed+=Math.min(80,Math.max(0,now-last))/1000;last=now;
      const state=document.body.dataset.voice;gl.uniform2f(size,canvas.width,canvas.height);gl.uniform1f(time,elapsed);gl.uniform1f(strength,state==='speaking'?.65+.35*Math.sin(elapsed*8.):state==='listening'?.3:0.);gl.drawArrays(gl.TRIANGLES,0,6);
    }
    if(!reduced.matches)frame=requestAnimationFrame(draw);
  }
  function resume(){cancelAnimationFrame(frame);frame=0;if(!disposed&&!document.hidden&&visible){last=performance.now()-40;frame=requestAnimationFrame(draw);}}
  const ro=new ResizeObserver(()=>{resize();resume();});ro.observe(canvas);
  const io=new IntersectionObserver(entries=>{visible=entries[0].isIntersecting;resume();});io.observe(stage);
  sheet.addEventListener('close',resume);document.addEventListener('visibilitychange',resume);document.addEventListener('jarvis:voice-state',()=>{if(reduced.matches)resume();});reduced.addEventListener('change',resume);
  canvas.addEventListener('webglcontextlost',event=>{event.preventDefault();disposed=true;cancelAnimationFrame(frame);document.body.classList.remove('plasma-ready');});
  canvas.addEventListener('webglcontextrestored',()=>{ /* Keep the SVG fallback until the next visit. */ });
  document.body.classList.add('plasma-ready');resize();resume();
  window.addEventListener('pagehide',()=>{disposed=true;cancelAnimationFrame(frame);ro.disconnect();io.disconnect();},{once:true});
})();
