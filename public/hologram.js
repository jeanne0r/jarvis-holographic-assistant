import * as THREE from './vendor/three.module.min.js';

// Cinematic projection: transparent light, suspended instrumentation and volumetric depth.
// Audio comes only from live-state.js / rendered PCM. No synthetic voice levels.
const canvas=document.querySelector('#hologramCanvas'),stage=document.querySelector('.command-stage');
const reduced=matchMedia('(prefers-reduced-motion: reduce)'),small=matchMedia('(max-width:760px)');
const stats={ready:false,state:'idle',frames:0,frameMs:0,quality:small.matches?'mobile':'desktop',paused:true,drawCalls:0,inputRms:0,outputRms:0,mechanism:'PANORAMIC LAB',bloom:false};
Object.defineProperty(window,'jarvisHologram',{get:()=>Object.freeze({...stats})});
const geometries=new Set(),materials=new Set(),textures=new Set();
const G=g=>(geometries.add(g),g),M=m=>(materials.add(m),m);
const cyan=0x53ddff,blue=0x167eff,ice=0xc4f7ff,orange=0xff9e3d;
let renderer,scene,camera,root,frame=0,disposed=false,lost=false,visible=true,lastFrame=0,previous=0,time=0,staticSignature='',slow=0;
let reducedBucket=0,lastReducedLevel=0;
let voice={inputRms:0,outputRms:0,transport:'closed'},voiceAt=0,interruptAt=-Infinity,impulse=0,mic=0,sound=0,deploy=0,speed=.08;
let pointer={x:0,y:0},look={x:0,y:0},gaze={enabled:false,tracking:false,x:0,y:0,depth:0},gazeDepth=0,coreBaseScale=1;
let environment;let mechanisms=[],petals=[],modulators,crystal,innerCage,sparks,ground,scan,focusLight;
const uniforms={time:{value:0},mic:{value:0},sound:{value:0},energy:{value:.18},pixelRatio:{value:1}};
function luminous(color=cyan,opacity=1){return M(new THREE.MeshBasicMaterial({color,transparent:true,opacity,depthWrite:false,blending:THREE.AdditiveBlending,side:THREE.DoubleSide,forceSinglePass:true}));}
function projection(color=cyan){return M(new THREE.ShaderMaterial({uniforms:{...uniforms,tint:{value:new THREE.Color(color)}},transparent:true,depthWrite:false,blending:THREE.AdditiveBlending,side:THREE.DoubleSide,forceSinglePass:true,vertexShader:'varying vec3 p;void main(){p=position;vec4 v=vec4(position,1.);\n#ifdef USE_INSTANCING\n v=instanceMatrix*v;\n#endif\n gl_Position=projectionMatrix*modelViewMatrix*v;}',fragmentShader:'uniform vec3 tint;uniform float time;uniform float energy;varying vec3 p;void main(){float lines=pow(.5+.5*cos(p.y*170.+time*1.4),18.);float circuit=pow(.5+.5*cos(p.x*95.+p.y*20.),30.);float sweep=pow(.5+.5*cos(p.y*2.-time*.6),22.);gl_FragColor=vec4(tint,.035+lines*.14+circuit*.11+sweep*.08+energy*.05);}' }));}
const matrix=new THREE.Object3D();
function instances(geo,material,count,place){const mesh=new THREE.InstancedMesh(geo,material,count);for(let i=0;i<count;i++){matrix.position.set(0,0,0);matrix.rotation.set(0,0,0);matrix.scale.set(1,1,1);place(matrix,i);matrix.updateMatrix();mesh.setMatrixAt(i,matrix.matrix);}mesh.instanceMatrix.needsUpdate=true;return mesh;}
function radial(count,radius,width,length,depth,color,z=0,offset=0){const mesh=instances(G(new THREE.BoxGeometry(width,length,depth)),luminous(color),count,(o,i)=>{const a=offset+i/count*Math.PI*2;o.position.set(Math.sin(a)*radius,Math.cos(a)*radius,z);o.rotation.z=-a;});return mesh;}
function stroke(points,color=cyan,opacity=.5,segments=false){return new (segments?THREE.LineSegments:THREE.Line)(G(new THREE.BufferGeometry().setFromPoints(points)),M(new THREE.LineBasicMaterial({color,transparent:true,opacity,depthWrite:false})));}
function circle(radius,z=0,color=cyan,opacity=.5,length=Math.PI*2,start=0){const p=[];for(let i=0;i<=128;i++){const a=start+i/128*length;p.push(new THREE.Vector3(Math.cos(a)*radius,Math.sin(a)*radius,z));}return stroke(p,color,opacity);}
function sector(inner,outer,angle,depth){const shape=new THREE.Shape();shape.absarc(0,0,outer,0,angle,false);shape.lineTo(Math.cos(angle)*inner,Math.sin(angle)*inner);shape.absarc(0,0,inner,angle,0,true);shape.closePath();return G(new THREE.ExtrudeGeometry(shape,{depth,bevelEnabled:false,curveSegments:Math.max(1,Math.ceil(angle/.1)),steps:1}));}
function annulus(inner,outer,z,count,fill,material,offset=0){return instances(sector(inner,outer,Math.PI*2/count*fill,.012),material,count,(o,i)=>{o.position.z=z;o.rotation.z=offset+i/count*Math.PI*2;});}
function layer(z,velocity){const group=new THREE.Group();group.position.z=z;root.add(group);mechanisms.push({group,z,velocity});return group;}
function dial(radius,z){const c=document.createElement('canvas');c.width=c.height=1024;const ctx=c.getContext('2d');ctx.translate(512,512);ctx.textAlign='center';ctx.textBaseline='middle';ctx.fillStyle='#6dbbe8';ctx.font='20px monospace';for(let i=0;i<24;i++){ctx.save();ctx.rotate(i/24*Math.PI*2);ctx.translate(0,-460);ctx.fillText(String(i*15).padStart(3,'0'),0,0);ctx.restore();}const texture=new THREE.CanvasTexture(c);texture.anisotropy=renderer.capabilities.getMaxAnisotropy();textures.add(texture);const mesh=new THREE.Mesh(G(new THREE.PlaneGeometry(radius*2,radius*2)),M(new THREE.MeshBasicMaterial({map:texture,transparent:true,opacity:.85,depthWrite:false,side:THREE.DoubleSide,forceSinglePass:true})));mesh.position.z=z;return mesh;}
// Spatial architecture only: no fabricated machine readings, people or camera imagery.
function buildEnvironment(){
 const group=new THREE.Group();scene.add(group);
 const grid=[];for(let i=-12;i<=12;i++){grid.push(new THREE.Vector3(i,-2.56,-8),new THREE.Vector3(i,-2.56,5));grid.push(new THREE.Vector3(-12,-2.56,i),new THREE.Vector3(12,-2.56,i));}group.add(stroke(grid,blue,.10,true));
 const desk=new THREE.Group();desk.position.set(0,-2.30,1.0);desk.rotation.x=-Math.PI/2;group.add(desk);
 for(const [radius,alpha,color]of [[5.1,.5,cyan],[5.18,.16,blue],[4.54,.35,cyan],[4.48,.12,orange]])desk.add(circle(radius,0,color,alpha,Math.PI*.82,Math.PI*.09));
 const ribs=[];for(let i=0;i<50;i++){const a=Math.PI*.09+i/49*Math.PI*.82;ribs.push(new THREE.Vector3(Math.cos(a)*4.56,Math.sin(a)*4.56,0),new THREE.Vector3(Math.cos(a)*5.08,Math.sin(a)*5.08,0));}desk.add(stroke(ribs,cyan,.13,true));
 const deskFace=instances(G(new THREE.PlaneGeometry(.024,.35)),luminous(cyan,.45),50,(o,i)=>{const a=Math.PI*.09+i/49*Math.PI*.82;o.position.set(Math.cos(a)*5.1,Math.sin(a)*5.1,-.18);o.rotation.z=a-Math.PI/2;});desk.add(deskFace);
 // Real content screens are accessible HTML surfaces in the same workspace.
 return group;
}
function build(){
 renderer=new THREE.WebGLRenderer({canvas,alpha:true,antialias:true,powerPreference:'default',stencil:false,preserveDrawingBuffer:false});renderer.setClearColor(0,0);renderer.outputColorSpace=THREE.SRGBColorSpace;renderer.toneMapping=THREE.NoToneMapping;
 const gl=renderer.getContext(),debug=gl.getExtension('WEBGL_debug_renderer_info');if(debug&&/swiftshader|llvmpipe|software/i.test(gl.getParameter(debug.UNMASKED_RENDERER_WEBGL)))stats.quality='low';
 renderer.debug.onShaderError=(gl,p,v,f)=>{lost=true;stats.ready=false;stats.fallbackReason=gl.getProgramInfoLog(p)+' '+gl.getShaderInfoLog(v)+' '+gl.getShaderInfoLog(f);document.body.classList.remove('hologram-ready');console.warn(stats.fallbackReason);};
 scene=new THREE.Scene();camera=new THREE.PerspectiveCamera(43,1,.1,60);scene.add(new THREE.AmbientLight(0x528bc2,1.6));const key=new THREE.DirectionalLight(0xa9eaff,3.2);key.position.set(-2,4,6);scene.add(key);const rim=new THREE.DirectionalLight(0x1266ff,2.5);rim.position.set(4,-1,-3);scene.add(rim);
 root=new THREE.Group();scene.add(root);focusLight=new THREE.PointLight(0x29bfff,1.5,6);focusLight.position.set(0,0,1.5);root.add(focusLight);
 const light=luminous(cyan,.9),pale=luminous(ice,.9),electric=luminous(blue,.8),amber=luminous(orange,.85),glass=projection(cyan);
 // Suspended concentric instruments: interrupted arcs and fine indexed ticks.
 const back=layer(-.50,-.035);back.add(circle(2.26,0,cyan,.44));back.add(circle(2.30,0,blue,.3));back.add(radial(144,2.25,.009,.035,.008,cyan));back.add(annulus(2.08,2.15,.02,48,.52,electric));back.add(dial(2.08,.04));
 const halo=layer(-.28,.045);halo.add(annulus(1.83,2.02,0,24,.83,glass));halo.add(annulus(1.97,2.01,.02,12,.62,light));halo.add(radial(96,1.91,.008,.055,.006,cyan,.03));halo.add(circle(1.81,.02,cyan,.28));
 const orbit=layer(-.07,-.11);orbit.add(annulus(1.61,1.69,0,36,.75,light));orbit.add(annulus(1.56,1.59,.03,8,.50,electric));orbit.add(radial(72,1.74,.008,.034,.006,ice));orbit.add(annulus(1.71,1.73,.02,6,.12,amber));
 // A shallow, tilted data plane provides parallax rather than atom-like orbits.
 const lattice=layer(.09,.025);lattice.rotation.x=.13;
 const paths=[];for(let i=0;i<32;i++){const a=i/32*Math.PI*2,r=1.82;const pt=(v,t,z)=>new THREE.Vector3(Math.sin(t)*v,Math.cos(t)*v,z);paths.push(pt(r,a,0),pt(r-.13,a,0),pt(r-.13,a,0),pt(r-.13,a+.035,0),pt(r-.13,a+.035,0),pt(r-.24,a+.035,.05));}lattice.add(stroke(paths,cyan,.5,true));
 lattice.add(annulus(1.25,1.51,0,16,.76,glass));lattice.add(circle(1.31,.04,blue,.32));
 // Articulated holographic shutters remain legible through every other layer.
 const iris=layer(.24,.065),panel=G(new THREE.PlaneGeometry(.30,.11));
 for(let i=0;i<12;i++){const pivot=new THREE.Group(),a=i/12*Math.PI*2;pivot.rotation.z=a;const vane=new THREE.Group();const pane=new THREE.Mesh(panel,glass);pane.position.x=1.11;vane.add(pane);vane.add(stroke([new THREE.Vector3(.94,-.055,.01),new THREE.Vector3(1.22,-.055,.01),new THREE.Vector3(1.29,.04,.01)],i%4?cyan:orange,.75));pivot.add(vane);iris.add(pivot);petals.push({vane,angle:a});}
 const aperture=layer(.41,-.07);aperture.add(circle(.83,.02,cyan,.9));aperture.add(circle(.88,.01,blue,.55));aperture.add(annulus(.92,.95,0,32,.66,pale));aperture.add(annulus(.98,1.0,.01,8,.42,light));
 modulators=instances(G(new THREE.BoxGeometry(.018,.05,.009)),light,64,(o,i)=>{const a=i/64*Math.PI*2;o.position.set(Math.sin(a)*1.29,Math.cos(a)*1.29,.42);o.rotation.z=-a;});root.add(modulators);
 // Transparent energy field: analytic scanlines, rim light and no opaque crystal.
 const sphere=G(new THREE.SphereGeometry(.67,32,24));
 const field=M(new THREE.ShaderMaterial({uniforms,transparent:true,depthWrite:false,side:THREE.DoubleSide,forceSinglePass:true,blending:THREE.AdditiveBlending,vertexShader:'varying vec3 p;varying vec3 n;varying vec3 eye;void main(){p=position;n=normalize(normalMatrix*normal);vec4 v=modelViewMatrix*vec4(position,1.);eye=normalize(-v.xyz);gl_Position=projectionMatrix*v;}',fragmentShader:'uniform float time;uniform float energy;uniform float sound;varying vec3 p;varying vec3 n;varying vec3 eye;void main(){float rim=pow(1.-abs(dot(normalize(n),normalize(eye))),3.);float bands=pow(.5+.5*cos(p.y*145.-time*2.),22.);float scan=pow(.5+.5*cos(p.y*5.-time*.7),42.);vec3 c=mix(vec3(.02,.22,.65),vec3(.32,.85,1.),rim);gl_FragColor=vec4(c,.035+rim*.30+bands*.13+scan*.18+sound*.09);}' }));
 crystal=new THREE.Mesh(sphere,field);crystal.position.z=.5;root.add(crystal);
 innerCage=new THREE.Group();innerCage.position.z=.5;const grid=[];
 const link=(p,q)=>grid.push(p,q);const globe=(lat,lon)=>new THREE.Vector3(.695*Math.cos(lat)*Math.cos(lon),.695*Math.sin(lat),.695*Math.cos(lat)*Math.sin(lon));
 for(let j=-3;j<=3;j++)for(let i=0;i<64;i++)link(globe(j*Math.PI/12,i*Math.PI/32),globe(j*Math.PI/12,(i+1)*Math.PI/32));
 for(let j=0;j<12;j++)for(let i=0;i<32;i++)link(globe(-Math.PI/2+i*Math.PI/32,j*Math.PI/6),globe(-Math.PI/2+(i+1)*Math.PI/32,j*Math.PI/6));
 innerCage.add(stroke(grid,cyan,.20,true));root.add(innerCage);
 // Projected identifier, not an image of a film prop. Always luminous and crisp.
 const label=document.createElement('canvas');label.width=1024;label.height=384;const ctx=label.getContext('2d');ctx.textAlign='center';ctx.textBaseline='middle';ctx.fillStyle='#bbf5ff';ctx.font='500 128px monospace';ctx.fillText('J.A.R.V.I.S.',512,170);ctx.fillStyle='#5cc6eb';ctx.font='20px monospace';ctx.fillText('N E U R A L   I N T E R F A C E',512,260);
 const texture=new THREE.CanvasTexture(label);texture.colorSpace=THREE.SRGBColorSpace;textures.add(texture);const sign=new THREE.Mesh(G(new THREE.PlaneGeometry(1.65,.62)),M(new THREE.MeshBasicMaterial({map:texture,transparent:true,depthWrite:false,depthTest:false,blending:THREE.AdditiveBlending,side:THREE.DoubleSide,forceSinglePass:true})));sign.position.z=1.22;sign.renderOrder=10;root.add(sign);
 scan=layer(.60,.20);scan.add(annulus(1.14,1.15,0,4,.18,luminous(cyan,.8)));scan.add(circle(1.19,.01,cyan,.25));
 const mounts=layer(.15,-.022);mounts.add(radial(12,2.16,.011,.13,.01,cyan,0,.08));mounts.add(radial(6,2.18,.028,.019,.008,orange,.01,.08));
 const supports=[];for(let i=0;i<8;i++){const a=i*Math.PI/4;supports.push(new THREE.Vector3(Math.cos(a)*1.85,Math.sin(a)*1.85,-.52),new THREE.Vector3(Math.cos(a)*1.85,Math.sin(a)*1.85,.32));}root.add(stroke(supports,blue,.22,true));
 // Suspended light motes. Bounded instancing and point sprites keep mobile cost low.
 const count=small.matches?240:480,positions=new Float32Array(count*3),seed=new Float32Array(count);let rs=29;const random=()=>{rs=(Math.imul(rs,1664525)+1013904223)|0;return(rs>>>0)/4294967296;};
 for(let i=0;i<count;i++){const a=random()*Math.PI*2,r=.9+random()*1.6;positions.set([Math.sin(a)*r,Math.cos(a)*r,random()*2.5-1.25],i*3);seed[i]=random();}
 const particles=G(new THREE.BufferGeometry());particles.setAttribute('position',new THREE.BufferAttribute(positions,3));particles.setAttribute('seed',new THREE.BufferAttribute(seed,1));
 sparks=new THREE.Points(particles,M(new THREE.ShaderMaterial({uniforms,transparent:true,depthWrite:false,blending:THREE.AdditiveBlending,vertexShader:'uniform float time;uniform float energy;uniform float pixelRatio;attribute float seed;varying float a;varying float k;void main(){vec3 p=position;float phase=fract(seed+time*(.035+energy*.08));p.z=(phase-.5)*2.5;vec4 mv=modelViewMatrix*vec4(p,1.);gl_Position=projectionMatrix*mv;gl_PointSize=clamp((1.+seed)*pixelRatio*7./-mv.z,1.,3.);a=sin(phase*3.14159);k=seed;}',fragmentShader:'varying float a;varying float k;void main(){vec2 p=abs(gl_PointCoord-.5);if(p.x+p.y>.5)discard;gl_FragColor=vec4(k>.97?vec3(1.,.5,.12):vec3(.2,.7,1.),a*.6);}' })));root.add(sparks);
 ground=new THREE.Group();ground.position.y=-2.48;scene.add(ground);const platform=new THREE.Group();platform.rotation.x=-Math.PI/2;ground.add(platform);platform.add(circle(2.05,0,blue,.18));platform.add(circle(2.13,0,cyan,.35,Math.PI*1.85));platform.add(radial(90,2.1,.006,.035,.006,cyan,.01));platform.add(circle(1.74,0,blue,.18));
 const beams=[];for(let i=0;i<12;i++){const a=i*Math.PI/6;beams.push(new THREE.Vector3(Math.sin(a)*1.65,0,Math.cos(a)*1.65),new THREE.Vector3(Math.sin(a)*1.35,1.6,Math.cos(a)*.6));}ground.add(stroke(beams,cyan,.075,true));
 environment=buildEnvironment();
 renderer.compile(scene,camera);
}
function resize(){if(!renderer||!root||lost||disposed)return;const r=(small.matches?document.querySelector('.holo-scene'):stage).getBoundingClientRect();if(r.width<1||r.height<1)return;const mobile=r.width<761;
 let dpr=Math.min(devicePixelRatio||1,mobile?2:1.75,(stats.quality==='low'?1700:3200)/Math.max(r.width,r.height));if(stats.quality==='low')dpr=Math.min(dpr,1.15);
 renderer.setPixelRatio(dpr);renderer.setSize(r.width,r.height,false);uniforms.pixelRatio.value=dpr;camera.aspect=r.width/r.height;camera.updateProjectionMatrix();camera.position.set(0,mobile?.8:.7,mobile?6.8:9.05);camera.lookAt(0,-.42,0);
 environment.visible=!mobile&&r.width>=1100;stats.panorama=environment.visible;
 coreBaseScale=mobile?.90:r.width>=1100?.78:1;root.scale.setScalar(coreBaseScale);root.position.set(mobile?0:.0,mobile?.13:.22,0);ground.scale.setScalar(mobile?.84:1);ground.position.y=mobile?-1.98:-2.48;stats.quality=stats.quality==='low'?'low':mobile?'mobile':'desktop';staticSignature='';
}
function runnable(){return !!renderer&&!!root&&!lost&&!disposed&&!document.hidden&&visible&&document.body.dataset.screen==='chat'&&!document.body.classList.contains('hud-sheet-open');}
function render(timestamp){frame=0;if(!runnable()){stats.paused=true;return;}const interval=small.matches||stats.quality==='low'?32:16;if(timestamp-lastFrame<interval&&!reduced.matches){frame=requestAnimationFrame(render);return;}
 const dt=Math.min(.06,Math.max(0,(timestamp-(previous||timestamp))/1000));previous=lastFrame=timestamp;if(!reduced.matches)time+=dt;
 const state=document.body.dataset.voice||'idle';stats.state=state;stats.reducedMotion=reduced.matches;const signature=[state,canvas.width,canvas.height,document.body.classList.contains('immersive')].join('/');if(reduced.matches&&stats.ready&&signature===staticSignature){stats.paused=true;return;}staticSignature=reduced.matches?signature:'';
 const fresh=performance.now()-voiceAt<250&&voice.transport==='ready';const input=fresh?voice.inputRms:0,output=fresh?voice.outputRms:0;stats.inputRms=input;stats.outputRms=output;
 const level=x=>Math.min(1,Math.sqrt(Math.max(0,x-.001))*3.1);const attack=1-Math.exp(-dt/.045),release=1-Math.exp(-dt/.09);if(reduced.matches){mic=level(input);sound=level(output);}else{mic+=(level(input)-mic)*(level(input)>mic?attack:release);sound+=(level(output)-sound)*(level(output)>sound?attack:release);}
 impulse=Math.max(0,1-(performance.now()-interruptAt)/220);stats.interruption=impulse>0;
 const thinking=state==='thinking',speaking=state==='speaking',listening=state==='listening';const target=thinking?1:listening?.3:speaking?.5:0;deploy+=(target-deploy)*(reduced.matches?1:1-Math.exp(-dt/.24));speed+=((thinking?1.2:speaking?.35:listening?.17:.07)-speed)*(1-Math.exp(-dt/.22));
 const energy=.12+(listening?mic*.8:speaking?sound*.95:thinking?.38:0);uniforms.time.value=time;uniforms.mic.value=mic;uniforms.sound.value=sound;uniforms.energy.value=energy;
 const targetLook=gaze.enabled&&gaze.tracking?gaze:pointer;const ease=1-Math.exp(-dt/.16);
 look.x+=((reduced.matches?0:targetLook.x)-look.x)*ease;look.y+=((reduced.matches?0:targetLook.y)-look.y)*ease;gazeDepth+=((gaze.tracking&&!reduced.matches?gaze.depth:0)-gazeDepth)*ease;
 stats.cameraTracking=gaze.tracking;stats.gazeX=look.x;stats.gazeY=look.y;
 camera.position.x=look.x*.65;camera.position.y=(small.matches?.8:.7)-look.y*.45;camera.lookAt(0,-.42,0);root.position.z=gazeDepth*.3;
 // Face width relative to camera activation is a proximity cue, not a metric
 // distance. Smooth with the same head-tracking filter; bound phone enlargement
 // so the mechanical core cannot spill over the controls.
 const proximity=1+gazeDepth/.6;
 const stableProximity=1+Math.sign(proximity-1)*Math.max(0,Math.abs(proximity-1)-.035);
 const coreScale=reduced.matches?1:Math.max(.65,Math.min(small.matches?1.16:1.3,stableProximity));
 root.scale.setScalar(coreBaseScale*coreScale);stats.coreScale=coreScale;
 root.rotation.set(.08+look.y*.25+Math.sin(time*.12)*.025,-.25+look.x*.42+Math.sin(time*.10)*.075,.015);
 for(let i=0;i<mechanisms.length;i++){const o=mechanisms[i];if(!reduced.matches)o.group.rotation.z+=dt*o.velocity*(1+speed*5)*(1-impulse*.85);o.group.position.z=o.z+deploy*(i%2?.20:-.12)+(speaking&&!reduced.matches?sound*.05:0);}
 petals.forEach(({vane},i)=>{vane.rotation.x=deploy*.38+(reduced.matches?0:mic*.1);vane.rotation.z=-deploy*.18;vane.position.z=reduced.matches?0:mic*.045-impulse*.06;});
 for(let i=0;i<64;i++){const a=i/64*Math.PI*2,response=reduced.matches?0:(listening?mic:speaking?sound:0),pattern=.3+.7*Math.abs(Math.sin(a*3+.4));matrix.position.set(Math.sin(a)*1.29,Math.cos(a)*1.29,.43+deploy*.12);matrix.rotation.set(0,0,-a);matrix.scale.set(1,1+response*pattern*3.8+(thinking?.35:0),1);matrix.updateMatrix();modulators.setMatrixAt(i,matrix.matrix);}modulators.instanceMatrix.needsUpdate=true;
 if(!reduced.matches){crystal.rotation.y+=dt*(.07+sound*.25);crystal.rotation.x+=dt*.08;innerCage.rotation.z-=dt*.14;innerCage.rotation.y=Math.sin(time*.17)*.35;}
 crystal.scale.setScalar(reduced.matches?1:1+mic*.07+sound*.10-impulse*.08);crystal.position.z=.5+deploy*.1;focusLight.intensity=1.5+energy*1.5;
 const start=performance.now();try{renderer.render(scene,camera);}catch(error){lost=true;stats.ready=false;stats.fallbackReason=error.message;document.body.classList.remove('hologram-ready');return;}
 if(lost)return;stats.frames++;stats.frameMs=stats.frameMs*.9+(performance.now()-start)*.1;stats.drawCalls=renderer.info.render.calls;stats.ready=true;stats.paused=reduced.matches;if(!document.body.classList.contains('hologram-ready'))document.body.classList.add('hologram-ready');
 if(stats.frameMs>22||dt>(small.matches?.054:.047)){slow++;if(slow>20&&stats.quality!=='low'){stats.quality='low';sparks.geometry.setDrawRange(0,Math.floor(sparks.geometry.attributes.position.count*.6));resize();}}else slow=Math.max(0,slow-1);
 if(!reduced.matches)frame=requestAnimationFrame(render);
}
function resume(){cancelAnimationFrame(frame);frame=0;if(runnable()){previous=performance.now();frame=requestAnimationFrame(render);}else stats.paused=true;}
try{build();resize();resume();}catch(error){lost=true;stats.fallbackReason=error.message;console.warn('Mechanical hologram fallback:',error.message);}
const ro=new ResizeObserver(()=>{resize();resume();});ro.observe(stage);ro.observe(document.querySelector('.holo-scene'));const io=new IntersectionObserver(entries=>{visible=entries[0].isIntersecting;resume();});io.observe(stage);const observer=new MutationObserver(resume);observer.observe(document.body,{attributes:true,attributeFilter:['data-voice','data-screen','class']});
reduced.addEventListener('change',resume);small.addEventListener('change',()=>{resize();resume();});document.addEventListener('visibilitychange',resume);
document.addEventListener('jarvis:live-diagnostics',event=>{voice=event.detail;voiceAt=performance.now();if(reduced.matches){const bucket=Math.round(Math.min(1,Math.max(voice.inputRms,voice.outputRms)*4)*8);if(bucket!==reducedBucket&&voiceAt-lastReducedLevel>=100){reducedBucket=bucket;lastReducedLevel=voiceAt;staticSignature='';resume();}}});
document.addEventListener('jarvis:voice-interrupt',()=>{interruptAt=performance.now();mic=sound=0;if(reduced.matches){staticSignature='';resume();}});
stage.addEventListener('pointermove',event=>{if(event.pointerType==='touch'||reduced.matches)return;const r=stage.getBoundingClientRect();pointer.x=(event.clientX-r.left)/r.width-.5;pointer.y=(event.clientY-r.top)/r.height-.5;},{passive:true});stage.addEventListener('pointerleave',()=>{pointer.x=pointer.y=0;});
document.addEventListener('jarvis:camera-tracking',event=>{gaze=event.detail;if(!gaze.enabled)pointer={x:0,y:0};});
canvas.addEventListener('webglcontextlost',event=>{event.preventDefault();lost=true;stats.ready=false;cancelAnimationFrame(frame);document.body.classList.remove('hologram-ready');});canvas.addEventListener('webglcontextrestored',()=>{lost=false;resize();resume();});
window.addEventListener('pagehide',event=>{cancelAnimationFrame(frame);stats.paused=true;if(event.persisted)return;disposed=true;ro.disconnect();io.disconnect();observer.disconnect();geometries.forEach(g=>g.dispose());materials.forEach(m=>m.dispose());textures.forEach(t=>t.dispose());renderer?.dispose();});window.addEventListener('pageshow',event=>{if(event.persisted)resume();});
