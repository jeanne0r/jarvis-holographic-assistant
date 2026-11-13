import * as THREE from './vendor/three.module.min.js';

// Mechanical hologram: real depth, opaque housings, emissive circuitry.
// Audio comes only from live-state.js / rendered PCM. No synthetic voice levels.
const canvas=document.querySelector('#hologramCanvas'),stage=document.querySelector('.command-stage');
const reduced=matchMedia('(prefers-reduced-motion: reduce)'),small=matchMedia('(max-width:760px)');
const stats={ready:false,state:'idle',frames:0,frameMs:0,quality:small.matches?'mobile':'desktop',paused:true,drawCalls:0,inputRms:0,outputRms:0,mechanism:'MK.II',bloom:false};
Object.defineProperty(window,'jarvisHologram',{get:()=>Object.freeze({...stats})});
const geometries=new Set(),materials=new Set(),textures=new Set();
const G=g=>(geometries.add(g),g),M=m=>(materials.add(m),m);
const cyan=0x53ddff,blue=0x167eff,ice=0xc4f7ff,orange=0xff9e3d;
let renderer,scene,camera,root,frame=0,disposed=false,lost=false,visible=true,lastFrame=0,previous=0,time=0,staticSignature='',slow=0;
let reducedBucket=0,lastReducedLevel=0;
let voice={inputRms:0,outputRms:0,transport:'closed'},voiceAt=0,interruptAt=-Infinity,impulse=0,mic=0,sound=0,deploy=0,speed=.08;
let pointer={x:0,y:0},look={x:0,y:0},gaze={enabled:false,tracking:false,x:0,y:0,depth:0},gazeDepth=0,coreBaseScale=1;
let mechanisms=[],petals=[],modulators,crystal,innerCage,sparks,ground,scan,focusLight;
const uniforms={time:{value:0},mic:{value:0},sound:{value:0},energy:{value:.18},pixelRatio:{value:1}};
function luminous(color=cyan,opacity=1){return M(new THREE.MeshBasicMaterial({color,transparent:opacity<1,opacity,depthWrite:opacity>=1,side:THREE.DoubleSide}));}
function metal(color=0x061c30,emissive=0x001426){return M(stats.quality==='low'?new THREE.MeshLambertMaterial({color,emissive,flatShading:true}):new THREE.MeshPhongMaterial({color,emissive,shininess:80,specular:0x397baa,flatShading:true}));}
const matrix=new THREE.Object3D();
function instances(geo,material,count,place){const mesh=new THREE.InstancedMesh(geo,material,count);for(let i=0;i<count;i++){matrix.position.set(0,0,0);matrix.rotation.set(0,0,0);matrix.scale.set(1,1,1);place(matrix,i);matrix.updateMatrix();mesh.setMatrixAt(i,matrix.matrix);}mesh.instanceMatrix.needsUpdate=true;return mesh;}
function radial(count,radius,width,length,depth,color,z=0,offset=0){const mesh=instances(G(new THREE.BoxGeometry(width,length,depth)),luminous(color),count,(o,i)=>{const a=offset+i/count*Math.PI*2;o.position.set(Math.sin(a)*radius,Math.cos(a)*radius,z);o.rotation.z=-a;});return mesh;}
function stroke(points,color=cyan,opacity=.5,segments=false){return new (segments?THREE.LineSegments:THREE.Line)(G(new THREE.BufferGeometry().setFromPoints(points)),M(new THREE.LineBasicMaterial({color,transparent:true,opacity,depthWrite:false})));}
function circle(radius,z=0,color=cyan,opacity=.5,length=Math.PI*2,start=0){const p=[];for(let i=0;i<=128;i++){const a=start+i/128*length;p.push(new THREE.Vector3(Math.cos(a)*radius,Math.sin(a)*radius,z));}return stroke(p,color,opacity);}
function sector(inner,outer,angle,depth){const shape=new THREE.Shape();shape.absarc(0,0,outer,0,angle,false);shape.lineTo(Math.cos(angle)*inner,Math.sin(angle)*inner);shape.absarc(0,0,inner,angle,0,true);shape.closePath();return G(new THREE.ExtrudeGeometry(shape,{depth,bevelEnabled:true,bevelThickness:.012,bevelSize:.01,bevelSegments:1,curveSegments:Math.max(1,Math.ceil(angle/.1)),steps:1}));}
function annulus(inner,outer,z,count,fill,material,offset=0){return instances(sector(inner,outer,Math.PI*2/count*fill,.065),material,count,(o,i)=>{o.position.z=z;o.rotation.z=offset+i/count*Math.PI*2;});}
function layer(z,velocity){const group=new THREE.Group();group.position.z=z;root.add(group);mechanisms.push({group,z,velocity});return group;}
function dial(radius,z){const c=document.createElement('canvas');c.width=c.height=1024;const ctx=c.getContext('2d');ctx.translate(512,512);ctx.textAlign='center';ctx.textBaseline='middle';ctx.fillStyle='#6dbbe8';ctx.font='20px monospace';for(let i=0;i<24;i++){ctx.save();ctx.rotate(i/24*Math.PI*2);ctx.translate(0,-460);ctx.fillText(String(i*15).padStart(3,'0'),0,0);ctx.restore();}const texture=new THREE.CanvasTexture(c);texture.anisotropy=renderer.capabilities.getMaxAnisotropy();textures.add(texture);const mesh=new THREE.Mesh(G(new THREE.PlaneGeometry(radius*2,radius*2)),M(new THREE.MeshBasicMaterial({map:texture,transparent:true,opacity:.85,depthWrite:false,side:THREE.DoubleSide})));mesh.position.z=z;return mesh;}
function build(){
 renderer=new THREE.WebGLRenderer({canvas,alpha:true,antialias:true,powerPreference:'default',stencil:false,preserveDrawingBuffer:false});renderer.setClearColor(0,0);renderer.outputColorSpace=THREE.SRGBColorSpace;renderer.toneMapping=THREE.NoToneMapping;
 const gl=renderer.getContext(),debug=gl.getExtension('WEBGL_debug_renderer_info');if(debug&&/swiftshader|llvmpipe|software/i.test(gl.getParameter(debug.UNMASKED_RENDERER_WEBGL)))stats.quality='low';
 renderer.debug.onShaderError=(gl,p,v,f)=>{lost=true;stats.ready=false;stats.fallbackReason=gl.getProgramInfoLog(p)+' '+gl.getShaderInfoLog(v)+' '+gl.getShaderInfoLog(f);document.body.classList.remove('hologram-ready');console.warn(stats.fallbackReason);};
 scene=new THREE.Scene();camera=new THREE.PerspectiveCamera(43,1,.1,60);scene.add(new THREE.AmbientLight(0x528bc2,1.6));const key=new THREE.DirectionalLight(0xa9eaff,3.2);key.position.set(-2,4,6);scene.add(key);const rim=new THREE.DirectionalLight(0x1266ff,2.5);rim.position.set(4,-1,-3);scene.add(rim);
 root=new THREE.Group();scene.add(root);focusLight=new THREE.PointLight(0x29bfff,1.5,6);focusLight.position.set(0,0,1.5);root.add(focusLight);
 const dark=metal(),shellMaterial=metal(0x0b2941,0x00132b),slots=luminous(0x0c405d),light=luminous(cyan),pale=luminous(ice),electric=luminous(blue),amber=luminous(orange);
 // Coaxial, physically separated mechanisms. No intersecting atomic orbits.
 const back=layer(-.52,-.07);back.add(annulus(1.89,2.18,0,18,.87,shellMaterial));back.add(annulus(2.12,2.15,.09,54,.60,electric));back.add(radial(108,2.23,.014,.065,.018,cyan,.08));back.add(circle(2.28,.03,blue,.65));back.add(circle(2.32,.01,cyan,.22));back.add(dial(2.12,.10));
 const frameRing=layer(-.25,.045);frameRing.add(annulus(1.69,1.87,0,12,.77,dark,.08));frameRing.add(annulus(1.73,1.77,.09,48,.73,light));frameRing.add(annulus(1.81,1.83,.10,96,.5,electric));
 // Radial structural bridges and tiny circuit tracks; instancing keeps calls bounded.
 frameRing.add(radial(12,1.96,.055,.21,.05,0x174e6f,.03,.12));frameRing.add(radial(12,1.96,.012,.16,.01,cyan,.065,.12));
 const outerCircuit=[];for(let i=0;i<36;i++){const a=i/36*Math.PI*2,r=1.87,da=.018;const point=(radius,angle,z)=>new THREE.Vector3(Math.sin(angle)*radius,Math.cos(angle)*radius,z);outerCircuit.push(point(r,a,.09),point(r+.075,a,.09),point(r+.075,a,.09),point(r+.075,a+da,.09),point(r+.075,a+da,.09),point(r+.14,a+da,.09));}frameRing.add(stroke(outerCircuit,cyan,.65,true));
 const rotor=layer(.02,-.18);rotor.add(annulus(1.36,1.65,0,24,.80,shellMaterial));rotor.add(annulus(1.38,1.43,.09,72,.63,light));rotor.add(annulus(1.56,1.61,.10,24,.48,electric));rotor.add(radial(72,1.49,.011,.045,.01,ice,.105));rotor.add(annulus(1.63,1.65,.12,6,.15,amber));
 // Twelve articulated vanes: mechanical iris, not a fuzzy luminous sphere.
 const bladeShape=new THREE.Shape();bladeShape.moveTo(.72,-.10);bladeShape.lineTo(1.17,-.16);bladeShape.lineTo(1.28,.09);bladeShape.lineTo(.87,.24);bladeShape.lineTo(.72,.07);bladeShape.closePath();
 const bladeGeo=G(new THREE.ExtrudeGeometry(bladeShape,{depth:.09,bevelEnabled:true,bevelThickness:.015,bevelSize:.012,bevelSegments:1,steps:1}));
 const iris=layer(.20,.12);
 for(let i=0;i<12;i++){const pivot=new THREE.Group();const angle=i/12*Math.PI*2;pivot.rotation.z=angle;const vane=new THREE.Group();vane.add(new THREE.Mesh(bladeGeo,shellMaterial));const edge=stroke([new THREE.Vector3(.75,.065,.12),new THREE.Vector3(.89,.21,.12),new THREE.Vector3(1.22,.075,.12)],i%4?cyan:orange,.95);vane.add(edge);pivot.add(vane);iris.add(pivot);petals.push({vane,angle});}
 const aperture=layer(.48,-.095);aperture.add(annulus(.63,.73,0,12,.82,dark));aperture.add(annulus(.65,.68,.10,48,.68,pale));aperture.add(circle(.79,.02,blue,.72));aperture.add(radial(24,.86,.012,.04,.018,cyan,.06));
 // Dynamic voice actuators, driven by measured PCM level rather than a sine wave.
 modulators=instances(G(new THREE.BoxGeometry(.035,.10,.04)),light,64,(o,i)=>{const a=i/64*Math.PI*2;o.position.set(Math.sin(a)*1.29,Math.cos(a)*1.29,.42);o.rotation.z=-a;});root.add(modulators);
 // A sharp faceted energy kernel, with emissive triangle edges and moving traces.
 const crystalGeo=G(new THREE.IcosahedronGeometry(.53,0));crystalGeo.computeVertexNormals();const bary=new Float32Array(crystalGeo.attributes.position.count*3);for(let i=0;i<bary.length/3;i++)bary[i*3+i%3]=1;crystalGeo.setAttribute('bary',new THREE.BufferAttribute(bary,3));
 const kernelMaterial=M(new THREE.ShaderMaterial({uniforms,vertexShader:'attribute vec3 bary;varying vec3 b;varying vec3 n;varying vec3 p;void main(){b=bary;n=normalize(normalMatrix*normal);p=position;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}',fragmentShader:`uniform float time;uniform float energy;uniform float mic;uniform float sound;varying vec3 b;varying vec3 n;varying vec3 p;void main(){float edge=1.-smoothstep(.012,.032,min(b.x,min(b.y,b.z)));float face=.25+.75*max(0.,dot(normalize(n),normalize(vec3(-.4,.7,1.))));float traces=pow(max(0.,cos(p.y*45.+p.x*12.-time*2.)),22.);vec3 c=vec3(.012,.10,.21)*face+vec3(.1,.65,1.)*edge*(.7+energy*.3);c+=vec3(.01,.18,.35)*traces;c+=vec3(.07,.23,.35)*sound;gl_FragColor=vec4(c,1.);\n#include <colorspace_fragment>\n}` }));
 crystal=new THREE.Mesh(crystalGeo,kernelMaterial);crystal.position.z=.50;root.add(crystal);
 innerCage=new THREE.Group();innerCage.position.z=.46;const cageGeo=G(new THREE.EdgesGeometry(G(new THREE.OctahedronGeometry(.69,0))));innerCage.add(new THREE.LineSegments(cageGeo,M(new THREE.LineBasicMaterial({color:cyan,transparent:true,opacity:.7}))));root.add(innerCage);
 // Six separated front-mounted brackets add thickness and hard-edged highlights.
 const mounts=layer(.32,.035);mounts.add(radial(6,1.91,.095,.24,.13,0x103953,.0,.2));mounts.add(radial(6,1.91,.019,.16,.014,cyan,.081,.2));mounts.add(radial(6,2.06,.065,.024,.018,orange,.08,.2));
 scan=layer(.62,.28);scan.add(annulus(1.07,1.10,0,4,.19,luminous(cyan,.7)));scan.add(annulus(1.12,1.14,0,16,.12,luminous(blue,.7)));
 // Axial supports connect the back and front assembly: unambiguous 3D parallax.
 const supports=[];for(let i=0;i<12;i++){const a=i*Math.PI/6;supports.push(new THREE.Vector3(Math.cos(a)*1.88,Math.sin(a)*1.88,-.56),new THREE.Vector3(Math.cos(a)*1.88,Math.sin(a)*1.88,.42));}root.add(stroke(supports,blue,.6,true));
 // Fine energy particles travel through the assembly, not on orbital ellipses.
 const count=small.matches?300:650,positions=new Float32Array(count*3),seed=new Float32Array(count);let rs=29;const random=()=>{rs=(Math.imul(rs,1664525)+1013904223)|0;return(rs>>>0)/4294967296;};
 for(let i=0;i<count;i++){const a=random()*Math.PI*2,r=.8+random()*1.7;positions.set([Math.sin(a)*r,Math.cos(a)*r,random()*2.5-1.25],i*3);seed[i]=random();}
 const particles=G(new THREE.BufferGeometry());particles.setAttribute('position',new THREE.BufferAttribute(positions,3));particles.setAttribute('seed',new THREE.BufferAttribute(seed,1));
 sparks=new THREE.Points(particles,M(new THREE.ShaderMaterial({uniforms,transparent:true,depthWrite:false,vertexShader:'uniform float time;uniform float energy;uniform float pixelRatio;attribute float seed;varying float a;varying float k;void main(){vec3 p=position;float phase=fract(seed+time*(.05+energy*.08));p.z=(phase-.5)*2.5;vec4 mv=modelViewMatrix*vec4(p,1.);gl_Position=projectionMatrix*mv;gl_PointSize=clamp((1.+seed)*pixelRatio*7./-mv.z,1.,4.);a=sin(phase*3.14159);k=seed;}',fragmentShader:'varying float a;varying float k;void main(){vec2 p=abs(gl_PointCoord-.5);if(p.x+p.y>.5)discard;gl_FragColor=vec4(k>.95?vec3(1.,.5,.12):vec3(.2,.7,1.),a*.8);}' })));root.add(sparks);
 // A restrained projection platform leaves the machinery sharply legible.
 ground=new THREE.Group();ground.position.y=-2.48;scene.add(ground);const platform=new THREE.Group();platform.rotation.x=-Math.PI/2;ground.add(platform);platform.add(circle(2.08,0,blue,.3));platform.add(circle(2.16,0,cyan,.4,Math.PI*1.85));platform.add(radial(90,2.1,.007,.055,.01,cyan,.01));platform.add(circle(1.75,0,blue,.2));
 const beams=[];for(let i=0;i<8;i++){const a=i*Math.PI/4;beams.push(new THREE.Vector3(Math.sin(a)*1.7,0,Math.cos(a)*1.7),new THREE.Vector3(Math.sin(a)*1.35,1.6,Math.cos(a)*.6));}ground.add(stroke(beams,blue,.12,true));
 renderer.compile(scene,camera);
}
function resize(){if(!renderer||!root||lost||disposed)return;const r=(small.matches?document.querySelector('.holo-scene'):stage).getBoundingClientRect();if(r.width<1||r.height<1)return;const mobile=r.width<761;
 let dpr=Math.min(devicePixelRatio||1,mobile?2:1.75,(stats.quality==='low'?1700:3200)/Math.max(r.width,r.height));if(stats.quality==='low')dpr=Math.min(dpr,1.15);
 renderer.setPixelRatio(dpr);renderer.setSize(r.width,r.height,false);uniforms.pixelRatio.value=dpr;camera.aspect=r.width/r.height;camera.updateProjectionMatrix();camera.position.set(0,mobile?.8:.7,mobile?6.8:9.05);camera.lookAt(0,-.42,0);
 coreBaseScale=mobile?.90:1;root.scale.setScalar(coreBaseScale);root.position.set(mobile?0:.22,mobile?.13:.12,0);ground.scale.setScalar(mobile?.84:1);ground.position.y=mobile?-1.98:-2.48;stats.quality=stats.quality==='low'?'low':mobile?'mobile':'desktop';staticSignature='';
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
 root.rotation.set(.10+look.y*.25+Math.sin(time*.12)*.035,-.43+look.x*.42+Math.sin(time*.10)*.10,.015);
 for(let i=0;i<mechanisms.length;i++){const o=mechanisms[i];if(!reduced.matches)o.group.rotation.z+=dt*o.velocity*(1+speed*5)*(1-impulse*.85);o.group.position.z=o.z+deploy*(i%2?.20:-.12)+(speaking&&!reduced.matches?sound*.05:0);}
 petals.forEach(({vane},i)=>{vane.rotation.x=deploy*.38+(reduced.matches?0:mic*.1);vane.rotation.z=-deploy*.18;vane.position.z=reduced.matches?0:mic*.045-impulse*.06;});
 for(let i=0;i<64;i++){const a=i/64*Math.PI*2,response=reduced.matches?0:(listening?mic:speaking?sound:0),pattern=.3+.7*Math.abs(Math.sin(a*3+.4));matrix.position.set(Math.sin(a)*1.29,Math.cos(a)*1.29,.43+deploy*.12);matrix.rotation.set(0,0,-a);matrix.scale.set(1,1+response*pattern*3.8+(thinking?.35:0),1);matrix.updateMatrix();modulators.setMatrixAt(i,matrix.matrix);}modulators.instanceMatrix.needsUpdate=true;
 if(!reduced.matches){crystal.rotation.y+=dt*(.18+sound*.4);crystal.rotation.x+=dt*.08;innerCage.rotation.z-=dt*.14;innerCage.rotation.y=Math.sin(time*.17)*.35;}
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
